#!/usr/bin/env python3
"""
safe_executor.py - Allowlist-guarded, bounded-output command execution for verification.
Part of the 'project-scaffolder' engineering skill.

Architecture Note (Process Isolation Tiers):
1. Restricted Executor (this module): A command-policy boundary that validates executable allowlists,
   rejects dangerous arguments/interpreter eval modes, verifies working directories, and bounds output memory/disk usage.
   IMPORTANT: A Restricted Executor is NOT an OS or container sandbox; child processes inherit ambient permissions.
2. Sandboxed Executor: When executing untrusted code or untrusted profiles, processes must be executed
   inside an external OS or container boundary (e.g. Linux namespaces, Docker, gVisor) with least privilege.
"""

import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Set

from core.contract import VerificationResult

SAFE_BINARY_WHITELIST: Set[str] = {
    "cargo", "rustc", "go", "gcc", "g++", "clang", "clang++", "zig",
    "make", "cmake", "ninja", "python", "python3", "uv", "pip", "pytest",
    "node", "npm", "pnpm", "yarn", "deno", "bun", "govulncheck", "ruff",
    "clippy", "gofmt", "rustfmt", "eslint", "prettier", "pre-commit",
    "unity", "unity.exe", "godot", "godot.exe", "dotnet", "platformio",
    "pio", "idf.py", "git", "gitleaks",
}

# Interpreter entry points are intentionally narrower than the executable allowlist.
# Arbitrary scripts/eval flags turn an allowlisted interpreter into arbitrary code execution.
SAFE_INTERPRETER_MODULES = {
    "python": {"pytest", "unittest", "compileall", "ruff"},
    "python3": {"pytest", "unittest", "compileall", "ruff"},
}
UNSAFE_INTERPRETER_FLAGS = {
    "-c", "-m", "--eval", "-e", "-p", "--print", "--require", "-r",
    "--loader", "--import", "--experimental-loader",
}

SAFE_GIT_SUBCOMMANDS: Set[str] = {
    "status", "diff", "rev-parse", "log", "branch", "describe",
    "tag", "config", "ls-files", "check-ignore", "version",
}
BLOCKED_PKG_MGR_SUBCOMMANDS: Set[str] = {
    "exec", "publish", "login", "config", "init",
}
BLOCKED_CARGO_SUBCOMMANDS: Set[str] = {
    "install", "publish", "login", "yank", "owner",
}

DEFAULT_MAX_SPOOL_BYTES = 5 * 1024 * 1024  # 5 MB monitored spool ceiling


def _terminate_process_tree(process) -> None:
    """Best-effort termination of the process and descendants started in its own group."""
    pid = getattr(process, "pid", None)
    if pid is not None and os.name == "nt":
        taskkill = shutil.which("taskkill")
        if taskkill:
            try:
                result = subprocess.run(
                    [taskkill, "/PID", str(pid), "/T", "/F"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    shell=False,
                    timeout=10,
                )
                if result.returncode == 0:
                    return
            except (OSError, subprocess.TimeoutExpired):
                pass
    elif pid is not None:
        try:
            os.killpg(pid, signal.SIGKILL)
            return
        except (OSError, ProcessLookupError, PermissionError):
            pass
    process.kill()


_WINDOWS_EXECUTABLE_SUFFIXES = (".exe", ".cmd", ".bat", ".com")


def _strip_executable_suffix(name: str) -> str:
    """Strip known executable extensions (plus Windows batch shims on Windows)."""
    lowered = name.lower()
    suffixes = _WINDOWS_EXECUTABLE_SUFFIXES if os.name == "nt" else (".exe",)
    for suffix in suffixes:
        if lowered.endswith(suffix):
            return lowered[: -len(suffix)]
    return lowered


class RestrictedExecutor:
    """
    Tier-1 Restricted Executor: Enforces command allowlists, argument validation,
    working directory boundaries, and bounded output spooling.
    """

    def __init__(
        self,
        binary_allowlist: Optional[Set[str]] = None,
        interpreter_modules: Optional[dict] = None,
        max_spool_bytes: int = DEFAULT_MAX_SPOOL_BYTES,
        authorized_root: Optional[Path] = None,
    ):
        self.binary_allowlist = binary_allowlist or SAFE_BINARY_WHITELIST
        self.interpreter_modules = interpreter_modules or SAFE_INTERPRETER_MODULES
        self.max_spool_bytes = max_spool_bytes
        self.authorized_root = Path(os.path.realpath(str(authorized_root))) if authorized_root is not None else None

    def find_safe_executable(self, binary_name: str) -> Optional[str]:
        """Resolve an allowlisted executable through PATH."""
        return shutil.which(binary_name)

    def validate_arguments(self, binary: str, args: List[str]) -> Optional[str]:
        """Reject interpreter modes that execute arbitrary inline or user-supplied code."""
        name = _strip_executable_suffix(Path(binary).name)
        if name in self.interpreter_modules:
            if not args:
                return "Interpreter invocation requires an explicitly permitted module."
            if args[0] in {"-c", "-"} or (
                args[0] == "-m"
                and (len(args) < 2 or args[1] not in self.interpreter_modules[name])
            ):
                return "Arbitrary interpreter code/module execution is blocked by policy."
            if args[0] != "-m":
                return "Python execution is limited to approved -m modules."
            if any(arg in {"-c", "--eval"} for arg in args):
                return "Arbitrary interpreter code/module execution is blocked by policy."
            return None
        if name in {"node", "deno", "bun"}:
            if any(arg in UNSAFE_INTERPRETER_FLAGS for arg in args):
                return "Inline/eval or dynamic module execution is blocked by policy."
            if any(arg in {"--eval", "--print", "-e", "-p"} for arg in args):
                return "Inline/eval execution is blocked by policy."
            return None
        if name == "git":
            if any(arg in {"-c", "--config-env"} or arg.startswith("--config-env=") for arg in args):
                return "Git configuration overrides (-c / --config-env) are blocked by security policy."
            if any(arg == "-C" for arg in args):
                return "Git directory change flag (-C) is blocked by security policy; use cwd confinement instead."
            subcmd = next((arg for arg in args if not arg.startswith("-")), None)
            if subcmd is not None and subcmd.lower() not in SAFE_GIT_SUBCOMMANDS:
                return f"Git subcommand '{subcmd}' is blocked by security policy; only read-only status and inspection commands are permitted."
            return None
        if name in {"npm", "pnpm", "yarn"}:
            if any(arg in BLOCKED_PKG_MGR_SUBCOMMANDS for arg in args):
                return "Package manager subcommand/flag is blocked by security policy."
            return None
        if name == "cargo":
            subcmd = next((arg for arg in args if not arg.startswith("-")), None)
            if subcmd is not None and subcmd.lower() in BLOCKED_CARGO_SUBCOMMANDS:
                return f"Cargo subcommand '{subcmd}' is blocked by security policy."
            return None
        if name == "make":
            if any(arg in {"-e", "--environment-overrides", "--eval"} or arg.startswith("--eval=") for arg in args):
                return "Make environment overrides and eval flags are blocked by security policy."
            return None
        if name == "gitleaks":
            subcmd = next((arg for arg in args if not arg.startswith("-")), None)
            if subcmd is not None and subcmd.lower() not in {"detect", "protect", "version"}:
                return f"Gitleaks subcommand '{subcmd}' is blocked by security policy; permitted subcommands are detect, protect, version."
            return None
        return None

    def execute(
        self,
        tokens: List[str],
        cwd: Path,
        timeout_seconds: int = 120,
        display_command: str = "",
        output_limit: int = 800,
        authorized_root: Optional[Path] = None,
        allowed_argv: Optional[List[str]] = None,
        provider_id: str = "",
        operation_id: str = "",
    ) -> VerificationResult:
        """Execute a vetted argv without a shell and spool output to disk to bound memory use."""
        if not isinstance(tokens, (list, tuple)) or not tokens or not all(
            isinstance(token, str) and token for token in tokens
        ):
            return VerificationResult(status="NOT APPLICABLE", message="Empty or invalid command tokens.")

        argv = list(tokens)
        display_command = display_command or " ".join(argv)

        if allowed_argv is not None and argv != list(allowed_argv):
            return VerificationResult(
                status="NOT VERIFIED",
                command=display_command,
                message=(
                    "Execution blocked by provider policy for %s/%s: argv does not exactly match the declared operation; no process was started."
                    % (provider_id or "unknown-provider", operation_id or "unknown-operation")
                ),
            )

        # Validate arguments for illegal null bytes
        if any("\0" in arg for arg in argv):
            return VerificationResult(
                status="FAIL",
                command=display_command,
                message="Command arguments contain illegal null bytes.",
            )

        # Validate working directory
        if not isinstance(cwd, Path):
            cwd = Path(cwd)
        try:
            # Check for unconfined parent traversal before resolving
            if any(part == ".." for part in cwd.parts):
                if authorized_root is None and self.authorized_root is None:
                    return VerificationResult(
                        status="FAIL",
                        command=display_command,
                        message="Working directory contains unconfined parent path traversal ('..'); no process was started.",
                    )

            resolved_cwd = Path(os.path.realpath(str(cwd)))
            if not resolved_cwd.is_dir():
                return VerificationResult(
                    status="FAIL",
                    command=display_command,
                    message=f"Working directory does not exist or is not a directory: {cwd}",
                )
            effective_root = authorized_root if authorized_root is not None else self.authorized_root
            if effective_root is not None:
                resolved_root = Path(os.path.realpath(str(effective_root)))
                try:
                    resolved_cwd.relative_to(resolved_root)
                except ValueError:
                    return VerificationResult(
                        status="FAIL",
                        command=display_command,
                        message="Working directory escapes the authorized project root; no process was started.",
                    )
        except (OSError, RuntimeError) as exc:
            return VerificationResult(
                status="FAIL",
                command=display_command,
                message=f"Invalid working directory '{cwd}': {exc}",
            )

        executable = argv[0]
        # Reject directory traversal, absolute paths, or path separators in executable token
        if Path(executable).name != executable or "/" in executable or "\\" in executable:
            return VerificationResult(
                status="FAIL",
                command=display_command,
                message="Executable must be an allowlisted command name, not a path.",
            )

        base = executable.lower()
        base_no_ext = _strip_executable_suffix(base)
        if base not in self.binary_allowlist and base_no_ext not in self.binary_allowlist:
            return VerificationResult(
                status="NOT VERIFIED",
                command=display_command,
                message=f"Execution blocked: executable '{base}' is not allowlisted; no process was started.",
            )

        argument_error = self.validate_arguments(base, argv[1:])
        if argument_error:
            return VerificationResult(status="FAIL", command=display_command, message=argument_error)

        resolved = self.find_safe_executable(executable)
        if not resolved:
            return VerificationResult(
                status="NOT VERIFIED",
                command=display_command,
                message=f"Executable '{executable}' was not found.",
            )

        resolved_path = Path(resolved)
        resolved_name = _strip_executable_suffix(resolved_path.name)
        requested_name = _strip_executable_suffix(executable)
        if resolved_name != requested_name:
            return VerificationResult(
                status="FAIL",
                command=display_command,
                message="Resolved executable identity does not match the allowlisted command name; no process was started.",
            )
        try:
            if not resolved_path.resolve().is_file():
                return VerificationResult(
                    status="FAIL",
                    command=display_command,
                    message=f"Resolved executable '{resolved}' is not a valid file.",
                )
        except (OSError, RuntimeError) as exc:
            return VerificationResult(
                status="FAIL",
                command=display_command,
                message=f"Cannot verify executable path '{resolved}': {exc}",
            )

        argv[0] = resolved
        limit = max(0, int(output_limit))

        try:
            # Temporary files prevent unbounded stdout/stderr accumulation in Python memory.
            with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
                process_options = {}
                if os.name == "nt":
                    process_options["creationflags"] = getattr(
                        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
                    )
                else:
                    process_options["start_new_session"] = True
                process = subprocess.Popen(
                    argv,
                    cwd=str(resolved_cwd),
                    stdout=stdout_file,
                    stderr=stderr_file,
                    stdin=subprocess.DEVNULL,
                    shell=False,
                    **process_options,
                )

                # Monitor execution, enforce timeout and max spool limit
                return_code = None
                timed_out = False
                spool_exceeded = False

                if hasattr(process, "poll"):
                    start_time = time.monotonic()
                    while True:
                        poll_status = process.poll()
                        if poll_status is not None:
                            return_code = poll_status
                            break
                        stdout_file.seek(0, 2)
                        stderr_file.seek(0, 2)
                        if (stdout_file.tell() + stderr_file.tell()) > self.max_spool_bytes:
                            spool_exceeded = True
                            _terminate_process_tree(process)
                            process.wait()
                            break
                        if (time.monotonic() - start_time) > timeout_seconds:
                            timed_out = True
                            _terminate_process_tree(process)
                            process.wait()
                            break
                        time.sleep(0.02)
                else:
                    try:
                        return_code = process.wait(timeout=timeout_seconds)
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        _terminate_process_tree(process)
                        process.wait()

                stdout_file.seek(0, 2)
                stderr_file.seek(0, 2)
                out_size, err_size = stdout_file.tell(), stderr_file.tell()
                stdout_file.seek(max(0, out_size - limit))
                stderr_file.seek(max(0, err_size - min(limit, 500)))
                stdout = stdout_file.read(limit).decode("utf-8", errors="replace")
                stderr = stderr_file.read(min(limit, 500)).decode("utf-8", errors="replace")

                if spool_exceeded:
                    return VerificationResult(
                        status="FAIL",
                        command=display_command,
                        stdout=stdout,
                        stderr=stderr,
                        message=f"Process output exceeded safety spool limit ({self.max_spool_bytes // (1024*1024)}MB); process terminated.",
                        output_truncated=True,
                    )

                if timed_out:
                    return VerificationResult(
                        status="FAIL",
                        command=display_command,
                        stdout=stdout,
                        stderr=stderr,
                        message=f"Command timed out after {timeout_seconds} seconds.",
                        output_truncated=(out_size + err_size) > limit,
                    )

            return VerificationResult(
                status="PASS" if return_code == 0 else "FAIL",
                command=display_command,
                exit_code=return_code,
                stdout=stdout,
                stderr=stderr,
                message="Command executed successfully."
                if return_code == 0
                else f"Process exited with code {return_code}",
                output_truncated=(out_size + err_size) > limit,
            )
        except OSError as exc:
            return VerificationResult(
                status="FAIL",
                command=display_command,
                message=f"Unable to start command: {exc}",
            )


# Default global instance of RestrictedExecutor
_DEFAULT_RESTRICTED_EXECUTOR = RestrictedExecutor()


def find_safe_executable(binary_name: str) -> Optional[str]:
    """Resolve an allowlisted executable through PATH."""
    return _DEFAULT_RESTRICTED_EXECUTOR.find_safe_executable(binary_name)


def _validate_arguments(binary: str, args: List[str]) -> Optional[str]:
    """Module-level validator backward compatibility wrapper."""
    return _DEFAULT_RESTRICTED_EXECUTOR.validate_arguments(binary, args)


def execute_safe_command(
    cmd_str: str,
    cwd: Path,
    timeout_seconds: int = 120,
    authorized_root: Optional[Path] = None,
) -> VerificationResult:
    """Parse a configured command and pass it through the same token policy."""
    if not cmd_str or not cmd_str.strip():
        return VerificationResult(status="NOT APPLICABLE", message="Empty command string provided.")
    try:
        tokens = shlex.split(cmd_str, posix=sys.platform != "win32")
    except ValueError as exc:
        return VerificationResult(
            status="FAIL", command=cmd_str, message=f"Invalid command syntax: {exc}"
        )
    if not tokens:
        return VerificationResult(status="NOT APPLICABLE", message="No executable tokens found.")
    return execute_safe_tokens(
        tokens,
        cwd,
        timeout_seconds,
        display_command=cmd_str,
        authorized_root=authorized_root,
    )


def execute_safe_tokens(
    tokens: List[str],
    cwd: Path,
    timeout_seconds: int = 120,
    display_command: str = "",
    output_limit: int = 800,
    authorized_root: Optional[Path] = None,
    allowed_argv: Optional[List[str]] = None,
    provider_id: str = "",
    operation_id: str = "",
) -> VerificationResult:
    """Execute vetted argv via the default RestrictedExecutor."""
    return _DEFAULT_RESTRICTED_EXECUTOR.execute(
        tokens=tokens,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        display_command=display_command,
        output_limit=output_limit,
        authorized_root=authorized_root,
        allowed_argv=allowed_argv,
        provider_id=provider_id,
        operation_id=operation_id,
    )
