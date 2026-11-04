#!/usr/bin/env python3
"""
verify.py - Evidence-Based Dynamic Verification Engine
Part of the 'project-scaffolder' skill.

Rule 1 & Rule 2 Compliance:
- Fully domain-agnostic and stack-agnostic.
- Executes verification commands defined by the active StackAdapter.
- Protected by a restricted command-policy executor (allowlist-checked, no shell=True; not an OS/container sandbox).
- Outputs structured evidence with commands, exit codes, and stdout/stderr snippets.
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict

# Add script folder to path
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.contract import StackAdapter, VerificationResult
from core.io_utils import check_crlf_files
from core.registry import AdapterRegistry
from core.safe_executor import execute_safe_command, execute_safe_tokens
from discover import detect_3axis


def check_line_endings(target_path: Path) -> Dict[str, Any]:
    """Scans all text files for CRLF line endings."""
    crlf_files = check_crlf_files(target_path)
    return {"passed": len(crlf_files) == 0, "count": len(crlf_files), "files": crlf_files[:10]}


def run_precommit(target_path: Path) -> VerificationResult:
    """Executes pre-commit hook suite safely."""
    if not (target_path / ".pre-commit-config.yaml").exists():
        return VerificationResult(
            status="NOT APPLICABLE", message="No .pre-commit-config.yaml found."
        )

    return execute_safe_command("pre-commit run --all-files", cwd=target_path, timeout_seconds=120)


def _execute_profile_check(
    target_path: Path, adapter: StackAdapter, check: Dict[str, Any], fallback_timeout: int
) -> VerificationResult:
    """Execute only the exact argv and root scope declared by the selected verification provider."""
    provider = getattr(adapter, "verification_provider", None)
    command = check.get("command")
    policy = check.get("execution_policy")
    if (
        provider is None
        or not isinstance(command, list)
        or not command
        or not isinstance(policy, dict)
        or policy.get("mode") != "exact-argv"
        or policy.get("allowed_argv") != command
        or policy.get("cwd_scope") != "project-root"
    ):
        return VerificationResult(
            status="NOT VERIFIED",
            command=" ".join(command) if isinstance(command, list) else "",
            message="Selected verification provider has no valid exact-argv execution policy; no process was started.",
        )
    return execute_safe_tokens(
        command,
        cwd=target_path,
        authorized_root=target_path,
        allowed_argv=policy["allowed_argv"],
        provider_id=provider.id,
        operation_id=check.get("id", "unknown"),
        timeout_seconds=min(int(policy.get("timeout_seconds", fallback_timeout)), fallback_timeout),
        output_limit=int(policy.get("output_limit", 800)),
        display_command=" ".join(command),
    )


def run_test_suite(target_path: Path, adapter: StackAdapter) -> VerificationResult:
    """Executes test runner dynamically as specified by the active adapter."""
    test_commands = adapter.get_test_commands()
    if not test_commands:
        return VerificationResult(
            status="NOT APPLICABLE",
            message=f"No automated test runner configured in adapter '{adapter.display_name}'",
        )

    last_res = None
    provider = getattr(adapter, "verification_provider", None)
    declared_checks = provider.payload.get("checks", []) if provider is not None else []
    for cmd in test_commands:
        check = next(
            (
                item for item in declared_checks
                if item.get("kind") == "test"
                and " ".join(item.get("command", [])) == cmd
            ),
            None,
        )
        if check is None:
            return VerificationResult(
                status="NOT VERIFIED",
                command=cmd,
                message="Test command has no matching provider operation policy; no process was started.",
            )
        res = _execute_profile_check(target_path, adapter, check, 180)
        if res.status in ["PASS", "FAIL"]:
            if res.status == "PASS" and not _has_test_assertion_evidence(
                target_path, cmd, res.stdout, res.stderr
            ):
                return VerificationResult(
                    status="NOT VERIFIED",
                    command=cmd,
                    exit_code=res.exit_code,
                    stdout=res.stdout,
                    stderr=res.stderr,
                    message="Command exited successfully, but output did not prove that at least one test assertion ran.",
                )
            return res
        last_res = res

    return last_res or VerificationResult(
        status="NOT VERIFIED", message="Test execution could not be initiated."
    )


def _has_test_assertion_evidence(target_path: Path, command: str, stdout: str, stderr: str) -> bool:
    """Require an explicit non-zero test count or successful test result."""
    output = f"{stdout}\n{stderr}"
    patterns = (
        r"\b[1-9]\d*\s+passed\b",
        r"test result:\s*ok\.\s*[1-9]\d* passed",
        r"\bRan\s+[1-9]\d*\s+tests?\b.*\bOK\b",
        r"\bAll\s+[1-9]\d*\s+tests?\s+passed\b",
        r"\b[1-9]\d*% tests passed\b.*\bout of [1-9]\d*\b",
        r"\bTests?:\s*[1-9]\d* passed\b",
        r"\bTest Suites:\s*[1-9]\d* passed\b",
        r"(?m)^ok\s+[^\n]+\s+\d+(?:\.\d+)?s(?:\s+\(cached\))?\s*$",
    )
    if any(re.search(pattern, output, re.IGNORECASE) for pattern in patterns):
        return True

    tokens = command.split()
    if "-testResults" in tokens:
        index = tokens.index("-testResults")
        if index + 1 < len(tokens):
            result_file = target_path / tokens[index + 1]
            try:
                suite = ET.parse(result_file).getroot()
                total = int(suite.attrib.get("total", "0"))
                failed = int(suite.attrib.get("failed", "0")) + int(suite.attrib.get("errors", "0"))
                return total > 0 and failed == 0
            except (OSError, ET.ParseError, ValueError):
                return False
    return False


def run_build_verification(target_path: Path, adapter: StackAdapter) -> VerificationResult:
    """Executes build step dynamically as specified by the active adapter."""
    build_commands = adapter.get_build_commands()
    if not build_commands:
        return VerificationResult(
            status="NOT APPLICABLE",
            message=f"No build step required for adapter '{adapter.display_name}'",
        )

    provider = getattr(adapter, "verification_provider", None)
    declared_checks = provider.payload.get("checks", []) if provider is not None else []
    for cmd in build_commands:
        check = next(
            (
                item for item in declared_checks
                if item.get("kind") == "build"
                and " ".join(item.get("command", [])) == cmd
            ),
            None,
        )
        if check is None:
            return VerificationResult(
                status="NOT VERIFIED",
                command=cmd,
                message="Build command has no matching provider operation policy; no process was started.",
            )
        res = _execute_profile_check(target_path, adapter, check, 240)
        if res.status in ["PASS", "FAIL"]:
            return res

    return VerificationResult(
        status="NOT VERIFIED", message="Build execution could not be initiated."
    )


def main():
    arguments = sys.argv[1:]
    confirmed = "--confirm-command-execution" in arguments
    arguments = [item for item in arguments if item != "--confirm-command-execution"]
    target = Path(arguments[0] if arguments else ".").resolve()
    registry = AdapterRegistry(profiles_dir=SKILL_ROOT / "profiles")
    domain, stack, topology, adapter = detect_3axis(target, registry=registry)

    if adapter.stack_id == "generic":
        print(
            f"No process was started because {getattr(adapter, '_discovery_state', 'unknown')} stack discovery did not identify a supported profile."
        )
        for error in getattr(adapter, "_profile_load_errors", []):
            print(f"Profile load error: {error['path']}: {error['error']}")
        print("Clarify the project stack or provide a matching profile before executing commands.")
        sys.exit(2)

    if not confirmed:
        preview = {
            "status": "CONFIRMATION REQUIRED",
            "target": str(target),
            "provider": "legacy-profile.%s.%s" % (domain, stack),
            "test_commands": adapter.get_test_commands(),
            "build_commands": adapter.get_build_commands(),
            "pre_commit": ["pre-commit", "run", "--all-files"]
            if (target / ".pre-commit-config.yaml").exists()
            else [],
            "network_policy": "may-access-network",
            "write_effects": [
                "test reports",
                "build artifacts",
                "tool caches",
                "pre-commit-managed files",
            ],
            "message": "No process was started. Review this preview and re-run with --confirm-command-execution.",
        }
        print(json.dumps(preview, indent=2, sort_keys=True))
        return 2

    print("================================================================================")
    print("             EVIDENCE-BASED DYNAMIC VERIFICATION RUNNER                         ")
    print("================================================================================")
    print(f"Target Directory : {target}")
    print(f"Adapter Active   : {adapter.display_name} ({adapter.stack_id})")
    print(f"Domain Archetype : {domain.upper()}")
    print("--------------------------------------------------------------------------------\n")

    # 1. Line endings
    print("[1/4] Line Ending Verification (Strict LF)...")
    lf_res = check_line_endings(target)
    if lf_res["passed"]:
        print("  [x] PASS: 100% strict LF line endings verified across all source files.")
    else:
        print(
            f"  [ ] FAIL: Found {lf_res['count']} file(s) with CRLF: {', '.join(lf_res['files'])}"
        )

    # 2. Pre-commit
    print("\n[2/4] Pre-commit Hook Execution...")
    pc_res = run_precommit(target)
    print(f"  Status    : {pc_res.status}")
    if pc_res.command:
        print(f"  Command   : {pc_res.command}")
        print(f"  Exit Code : {pc_res.exit_code}")
    if pc_res.message:
        print(f"  Notice    : {pc_res.message}")

    # 3. Test Runner
    print("\n[3/4] Test Suite Execution (Adapter Contract)...")
    test_res = run_test_suite(target, adapter)
    print(f"  Status    : {test_res.status}")
    if test_res.command:
        print(f"  Command   : {test_res.command}")
        print(f"  Exit Code : {test_res.exit_code}")
    if test_res.stdout:
        print(f"  Output    : {test_res.stdout.strip()[:300]}")
    if test_res.message:
        print(f"  Notice    : {test_res.message}")

    # 4. Build Step
    print("\n[4/4] Build Verification (Adapter Contract)...")
    build_res = run_build_verification(target, adapter)
    print(f"  Status    : {build_res.status}")
    if build_res.command:
        print(f"  Command   : {build_res.command}")
        print(f"  Exit Code : {build_res.exit_code}")
    if build_res.message:
        print(f"  Notice    : {build_res.message}")

    statuses = [
        "PASS" if lf_res["passed"] else "FAIL",
        pc_res.status,
        test_res.status,
        build_res.status,
    ]
    if "FAIL" in statuses:
        summary = "FAILED"
    elif any(status not in ("PASS", "NOT APPLICABLE") for status in statuses):
        summary = "INCOMPLETE (required execution evidence is unavailable)"
    else:
        summary = "PASSED"
    print("\n================================================================================")
    print(f"VERIFICATION SUMMARY: {summary}")
    print(
        "NOT APPLICABLE checks are excluded; PASS requires the verification criteria for that check."
    )
    print("================================================================================\n")
    if "FAIL" in statuses:
        return 1
    if any(status not in ("PASS", "NOT APPLICABLE") for status in statuses):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
