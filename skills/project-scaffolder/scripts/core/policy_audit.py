"""Read-only environment and dependency policy inspection."""

import re
from datetime import datetime, timezone
from pathlib import Path

from core.capability_registry import CapabilityRegistry
from core.capability_resolver import CapabilityResolver
from core.dependency_audit_parsers import parse_dependency_audit
from core.dependency_inventory import inspect_lockfile_inventory
from core.safe_executor import execute_safe_command, execute_safe_tokens, find_safe_executable
from core.verification import _redact_tokens


def _probe_version(command, root):
    if not command:
        return {"status": "not-applicable", "version": None}
    result = execute_safe_command(
        " ".join(command), cwd=root, timeout_seconds=5, authorized_root=root
    )
    output = (result.stdout or result.stderr).strip().splitlines()
    return {
        "status": result.status.lower().replace(" ", "-"),
        "version": output[0][:160] if output else None,
        "message": result.message,
    }


def audit_package_manager(root: Path, registry: CapabilityRegistry):
    report = CapabilityResolver(registry).resolve(root, ["package_manager"])
    if report.status != "resolved":
        return {
            "status": report.status,
            "candidates": [
                {
                    "id": item.provider_id,
                    "confidence": item.confidence,
                    "evidence": [entry.source for entry in item.evidence],
                }
                for item in report.candidates
            ],
            "errors": report.errors,
            "unresolved": report.unresolved_kinds,
        }

    provider = report.selected[0]
    policy = provider.payload
    manifests = [
        {"path": rel, "present": (root / rel).is_file()} for rel in policy.get("manifests", [])
    ]
    locks = [
        {"path": rel, "present": (root / rel).is_file()} for rel in policy.get("lockfiles", [])
    ]
    present_locks = [item for item in locks if item["present"]]
    absent_manifests = [item["path"] for item in manifests if not item["present"]]
    lock_policy = policy.get("lockfile_policy", "not-applicable")
    status = (
        "not-verified"
        if present_locks
        else (
            "missing-lockfile"
            if lock_policy == "required"
            else (
                "missing-recommended-lockfile" if lock_policy == "recommended" else "not-applicable"
            )
        )
    )
    if absent_manifests:
        status = "inconsistent"
    manager = policy.get("manager", "")
    executable_name = policy.get("executable", manager)
    executable = find_safe_executable(executable_name) if executable_name else None
    probe = policy.get("version_probe", [executable_name, "--version"] if executable_name else [])
    version_probe = (
        _probe_version(probe, root)
        if executable
        else {
            "status": "not-verified",
            "version": None,
            "message": "Manager executable is unavailable",
        }
    )
    freshness = _lockfile_freshness(root, manifests, locks)
    inventory = inspect_lockfile_inventory(root, provider)
    registry_configs = [
        {"path": rel, "present": (root / rel).is_file()}
        for rel in policy.get("registry_config_paths", [])
    ]
    return {
        "status": status,
        "provider": provider.id,
        "manager": manager,
        "manager_available": bool(executable),
        "version_probe": version_probe,
        "manifests": manifests,
        "lockfiles": locks,
        "lockfile_policy": lock_policy,
        "lockfile_consistency": freshness["consistency"],
        "lockfile_freshness": freshness,
        "dependency_inventory": inventory,
        "dependency_groups_supported": policy.get("dependency_groups", []),
        "version_strategy": policy.get("version_strategy", "manager-defined"),
        "registry_config_indicators": registry_configs,
        "dependency_evidence": {
            "direct": [
                {
                    "path": item["path"],
                    "status": "manifest-present" if item["present"] else "missing",
                }
                for item in manifests
            ],
            "transitive": [
                {
                    "path": item["path"],
                    "status": "lockfile-present" if item["present"] else "missing",
                }
                for item in locks
            ],
            "limitation": "File presence is dependency evidence only; package names and semantic graph consistency require a manager-specific audit.",
        },
        "dependency_audit": {
            "status": "not-run",
            "tool_command": policy.get("audit", []),
            "database": None,
            "checked_at": None,
            "limitation": "No vulnerability or license command was executed during read-only policy audit.",
        },
        "lockfile_check": {
            "status": "not-run",
            "command": policy.get("lock_check", {}).get("command", []),
            "network_policy": policy.get("lock_check", {}).get("network_policy", "unsupported"),
            "description": policy.get("lock_check", {}).get("description"),
            "consistency": "not-verified",
        },
        "locked_install": policy.get("locked_install", []),
        "commands": {key: policy.get(key, []) for key in ("add", "remove", "update", "audit")},
        "evidence": [
            source
            for candidate in report.candidates
            if candidate.provider_id == provider.id
            for source in (item.source for item in candidate.evidence)
        ],
    }


def run_package_audit(root: Path, provider, confirmed=False):
    """Run only the selected provider's declared audit command after explicit confirmation."""
    if provider is None or provider.kind != "package_manager":
        return {
            "status": "not-verified",
            "message": "A resolved package-manager provider is required.",
        }
    command = provider.payload.get("audit", [])
    if not command:
        return {
            "status": "not-applicable",
            "provider": provider.id,
            "message": "The selected provider declares no audit command.",
        }
    network_policy = provider.payload.get("audit_network_policy")
    write_effects = provider.payload.get("audit_write_effects")
    if (
        provider.payload.get("audit_requires_confirmation") is not True
        or network_policy not in {"offline-required", "may-access-network"}
        or not isinstance(write_effects, list)
        or not isinstance(provider.payload.get("audit_timeout_seconds"), int)
        or not isinstance(provider.payload.get("audit_output_limit"), int)
    ):
        return {
            "status": "not-verified",
            "provider": provider.id,
            "message": "Provider audit execution policy is incomplete; no process was started.",
        }
    if not confirmed:
        return {
            "status": "not-verified",
            "provider": provider.id,
            "tool_command": _redact_tokens(command),
            "network_policy": network_policy,
            "write_effects": write_effects,
            "message": "Explicit confirmation is required; no process was started.",
        }
    missing_manifests = [
        path for path in provider.payload.get("manifests", []) if not (root / path).is_file()
    ]
    missing_lockfiles = [
        path for path in provider.payload.get("lockfiles", []) if not (root / path).is_file()
    ]
    if missing_manifests or (
        missing_lockfiles and not provider.payload.get("audit_allow_missing_lockfiles", False)
    ):
        return {
            "status": "not-run",
            "provider": provider.id,
            "missing_manifests": missing_manifests,
            "missing_lockfiles": missing_lockfiles,
            "message": "Package audit was not run because declared manifest or lockfile inputs are missing.",
        }
    parser = provider.payload.get("dependency_audit_parser", {})
    result = execute_safe_tokens(
        command,
        cwd=root,
        authorized_root=root,
        allowed_argv=command,
        provider_id=provider.id,
        operation_id="dependency-audit",
        timeout_seconds=provider.payload["audit_timeout_seconds"],
        display_command=" ".join(_redact_tokens(command)),
        output_limit=provider.payload["audit_output_limit"],
    )
    executed = result.exit_code is not None
    status = (
        "completed"
        if result.status == "PASS"
        else "completed-nonzero"
        if result.status == "FAIL" and executed
        else "not-verified"
    )
    parsed = parse_dependency_audit(provider, result) if parser else None
    execution_status = status
    if parsed is not None and parsed.get("status") == "not-verified":
        status = "not-verified"
    return {
        "status": status,
        "execution_status": execution_status,
        "provider": provider.id,
        "tool_command": _redact_tokens(command),
        "tool_version": _probe_version(
            provider.payload.get("audit_version_probe", provider.payload.get("version_probe", [])),
            root,
        ),
        "exit_code": result.exit_code,
        "database": provider.payload.get("audit_database", "not-reported-by-provider"),
        "network_policy": network_policy,
        "write_effects": write_effects,
        "checked_at": _utc_timestamp(datetime.now(timezone.utc).timestamp()) if executed else None,
        "findings": parsed if parsed is not None else "not-interpreted",
        "output_summary": (
            "Raw output withheld. Provider-declared parser reports bounded findings from tool output."
            if parsed is not None
            else "Raw output withheld. Review the manager's audit output locally; findings remain uninterpreted."
        ),
        "message": result.message,
        "limitation": (
            parser.get("limitation")
            if parser
            else "A completed command is execution evidence only. Vulnerability counts, severity, license results, and database identity require a provider-specific result parser."
        ),
    }


def run_package_lock_check(root: Path, provider, confirmed=False):
    """Execute an explicit, provider-declared consistency check after confirmation."""
    if provider is None or provider.kind != "package_manager":
        return {
            "status": "not-verified",
            "consistency": "not-verified",
            "message": "A resolved package-manager provider is required.",
        }
    policy = provider.payload
    check = policy.get("lock_check")
    if not check:
        return {
            "status": "not-applicable",
            "consistency": "not-verified",
            "provider": provider.id,
            "message": "No native lockfile check is declared.",
        }
    write_effects = check.get("write_effects")
    if (
        check.get("requires_confirmation") is not True
        or check.get("network_policy") not in {"offline-required", "may-access-network"}
        or not isinstance(write_effects, list)
        or not isinstance(check.get("timeout_seconds"), int)
        or not isinstance(check.get("output_limit"), int)
    ):
        return {
            "status": "not-verified",
            "consistency": "not-verified",
            "provider": provider.id,
            "message": "Provider lock-check execution policy is incomplete; no process was started.",
        }
    missing_locks = [path for path in policy.get("lockfiles", []) if not (root / path).is_file()]
    missing_manifests = [
        path for path in policy.get("manifests", []) if not (root / path).is_file()
    ]
    if missing_manifests or (missing_locks and not check.get("allow_missing_lockfiles", False)):
        return {
            "status": "not-run",
            "consistency": "not-verified",
            "provider": provider.id,
            "missing_lockfiles": missing_locks,
            "missing_manifests": missing_manifests,
            "network_policy": check["network_policy"],
            "message": "Native check was not run because its declared manifest or lockfile is missing.",
        }

    command = check["command"]
    if not confirmed:
        return {
            "status": "not-verified",
            "consistency": "not-verified",
            "provider": provider.id,
            "command": _redact_tokens(command),
            "network_policy": check["network_policy"],
            "write_effects": write_effects,
            "message": "Explicit confirmation is required; no process was started.",
        }
    result = execute_safe_tokens(
        command,
        cwd=root,
        authorized_root=root,
        allowed_argv=command,
        provider_id=provider.id,
        operation_id="lock-consistency-check",
        timeout_seconds=check["timeout_seconds"],
        output_limit=check["output_limit"],
        display_command=" ".join(_redact_tokens(command)),
    )
    executed = result.exit_code is not None
    if result.status == "PASS":
        status, consistency = "passed", "consistent"
    elif executed:
        status, consistency = "review-required", "not-verified"
    else:
        status, consistency = "not-verified", "not-verified"
    return {
        "status": status,
        "consistency": consistency,
        "provider": provider.id,
        "command": _redact_tokens(command),
        "network_policy": check["network_policy"],
        "write_effects": write_effects,
        "missing_lockfiles": missing_locks,
        "allow_missing_lockfiles": check.get("allow_missing_lockfiles", False),
        "description": check["description"],
        "tool_version": _probe_version(policy.get("version_probe", []), root),
        "exit_code": result.exit_code,
        "checked_at": _utc_timestamp(datetime.now(timezone.utc).timestamp()) if executed else None,
        "output_summary": "Raw output withheld; a non-zero result needs local review to distinguish lock drift from tool, cache, or network errors.",
        "message": result.message,
    }


def _lockfile_freshness(root: Path, manifests, lockfiles):
    """Use timestamps only to flag a possible stale lock; never claim semantic sync."""
    present_manifests = [root / item["path"] for item in manifests if item["present"]]
    present_locks = [root / item["path"] for item in lockfiles if item["present"]]
    if not present_locks:
        return {
            "status": "missing" if lockfiles else "not-applicable",
            "consistency": "not-verified",
            "reason": "No declared lockfile is present"
            if lockfiles
            else "Provider has no lockfile",
        }
    if not present_manifests:
        return {
            "status": "not-verified",
            "consistency": "not-verified",
            "reason": "No declared manifest is present",
        }
    newest_manifest = max(path.stat().st_mtime for path in present_manifests)
    oldest_lock = min(path.stat().st_mtime for path in present_locks)
    if newest_manifest > oldest_lock:
        return {
            "status": "stale-or-unknown",
            "consistency": "not-verified",
            "reason": "A manifest is newer than a declared lockfile; timestamp evidence cannot prove semantic drift",
            "newest_manifest_utc": _utc_timestamp(newest_manifest),
            "oldest_lockfile_utc": _utc_timestamp(oldest_lock),
        }
    return {
        "status": "not-verified",
        "consistency": "not-verified",
        "reason": "Lockfile is not older than the manifest, but semantic consistency requires a manager-specific check",
    }


def _utc_timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def scan_secret_indicators(root: Path, max_bytes=1024 * 1024):
    """Report suspicious tracked-workspace content without returning secret values."""
    patterns = (
        (
            "credential-assignment",
            re.compile(
                rb"(?i)(?:api[_-]?key|secret|password|access[_-]?token)\s*[:=]\s*['\"]?([A-Za-z0-9_./+\-=]{12,})"
            ),
        ),
        ("private-key-header", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    )
    ignored = {".git", ".venv", "node_modules", "Library", "target", "bin", "obj", ".backup"}
    findings = []
    root_resolved = root.resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.resolve().relative_to(root_resolved)
        except (OSError, ValueError):
            continue
        if any(part in ignored for part in rel.parts[:-1]):
            continue
        try:
            if path.stat().st_size > max_bytes:
                continue
            content = path.read_bytes()
        except OSError:
            continue
        indicators = [name for name, pattern in patterns if pattern.search(content)]
        if indicators:
            findings.append(
                {
                    "path": str(rel).replace("\\", "/"),
                    "status": "review-required",
                    "indicators": indicators,
                }
            )
    return findings


def analyze_ci_parity(root: Path, provider):
    """Compare declared package manager and lockfile policy with simple CI evidence."""
    candidates = [root / ".github/workflows", root / ".gitlab-ci.yml", root / "azure-pipelines.yml"]
    workflow_files = []
    if candidates[0].is_dir():
        workflow_files.extend(candidates[0].glob("*.yml"))
        workflow_files.extend(candidates[0].glob("*.yaml"))
    workflow_files.extend(path for path in candidates[1:] if path.is_file())
    workflow_files = sorted(path for path in set(workflow_files) if _within_root(path, root))
    if not workflow_files:
        return {"status": "not-verified", "reason": "No supported CI workflow was found"}
    commands = "\n".join(_read_limited(path, 1024 * 1024) for path in workflow_files)
    commands = "\n".join(line.split("#", 1)[0] for line in commands.splitlines())
    manager = provider.payload.get("manager", "")
    install = provider.payload.get("locked_install", [])
    manager_present = bool(manager and manager in commands)
    if install and len(install) >= 2:
        manager_pattern = r"(?<![\w./-])%s\s+%s\b[^\n]*?(?<![\w-])%s(?![\w-])" % tuple(
            re.escape(token) for token in (install[0], install[1], install[-1])
        )
        lock_enforced = bool(re.search(manager_pattern, commands))
    else:
        lock_enforced = False
    return {
        "status": "evidence-found" if manager_present and lock_enforced else "drift-or-unknown",
        "workflow_files": [str(path.relative_to(root)) for path in workflow_files],
        "manager_present": manager_present,
        "locked_install_evidence": lock_enforced,
        "claim": "Textual workflow evidence only; CI execution and outcome are not verified",
        "expected_manager": manager,
        "expected_locked_install": install,
    }


def analyze_toolchain_ci_parity(root: Path, reports):
    """Compare local version declarations with textual CI references to the same pin."""
    workflows = _ci_workflow_files(root)
    if not workflows:
        return [
            {
                "provider": report["provider"],
                "runtime": report["runtime"],
                "status": "not-verified",
                "reason": "No supported CI workflow was found",
            }
            for report in reports
        ]
    ci_text = "\n".join(_read_limited(path, 1024 * 1024) for path in workflows)
    ci_text = "\n".join(line.split("#", 1)[0] for line in ci_text.splitlines())
    results = []
    for report in reports:
        provider_id = report["provider"]
        version_file = Path(report["evidence"][0]).name if report.get("evidence") else ""
        declared = report.get("declared")
        file_reference = bool(
            version_file
            and re.search(r"(?<![\w.-])%s(?![\w.-])" % re.escape(version_file), ci_text)
        )
        version_reference = bool(
            declared and re.search(r"(?<![\w.])%s(?![\w.])" % re.escape(declared), ci_text)
        )
        aligned = file_reference or version_reference
        results.append(
            {
                "provider": provider_id,
                "runtime": report["runtime"],
                "status": "evidence-found" if aligned else "drift-or-unknown",
                "local_version_file": version_file or None,
                "ci_references_version_file": file_reference,
                "ci_references_declared_version": version_reference,
                "workflow_files": [str(path.relative_to(root)) for path in workflows],
                "claim": "Textual workflow evidence only; CI execution and outcome are not verified",
            }
        )
    return results


def _ci_workflow_files(root: Path):
    candidates = [root / ".github/workflows", root / ".gitlab-ci.yml", root / "azure-pipelines.yml"]
    workflows = []
    if candidates[0].is_dir():
        workflows.extend(candidates[0].glob("*.yml"))
        workflows.extend(candidates[0].glob("*.yaml"))
    workflows.extend(path for path in candidates[1:] if path.is_file())
    return sorted(path for path in set(workflows) if _within_root(path, root))


def audit_toolchains(root: Path, registry: CapabilityRegistry):
    """Inspect declared runtime versions and optionally collect read-only version output."""
    reports = []
    for provider in registry.list("toolchain"):
        evidence = []
        for rule in provider.matches:
            path = root / rule["path"]
            try:
                path.resolve().relative_to(root.resolve())
            except (OSError, ValueError):
                continue
            if path.is_file():
                evidence.append(path)
        if not evidence:
            continue
        policy = provider.payload
        version_path = root / policy["version_file"]
        try:
            declared = _read_limited(version_path, 4096).strip()[:160]
        except OSError:
            declared = None
        probe = policy.get("probe", [])
        probe_result = (
            _probe_version(probe, root) if probe else {"status": "not-applicable", "version": None}
        )
        declared_match = re.search(
            policy.get("version_pattern", r"(?P<version>\d+(?:\.\d+)+)"), declared or ""
        )
        detected_match = re.search(
            policy.get("detected_pattern", r"(?P<version>\d+(?:\.\d+)+)"),
            probe_result.get("version") or "",
        )
        expected = declared_match.group("version") if declared_match else None
        actual = detected_match.group("version") if detected_match else None
        status = _compare_versions(expected, actual, policy.get("version_policy"))
        reports.append(
            {
                "provider": provider.id,
                "runtime": policy.get("runtime"),
                "declared": expected,
                "detected": actual,
                "probe_status": probe_result["status"],
                "status": status,
                "requirement_level": policy.get("requirement_level", "required"),
                "compatibility_rules": policy.get("compatibility", []),
                "environment_preparation": policy.get("environment_preparation", []),
                "reason": "Compared declared and detected versions using provider policy"
                if status in {"matched", "mismatch"}
                else "A version could not be parsed or the runtime probe was unavailable",
                "evidence": [str(path.relative_to(root)) for path in evidence],
            }
        )
    for report in reports:
        report["compatibility"] = _audit_declared_compatibility(
            report.pop("compatibility_rules"), reports, report["provider"]
        )
    return reports


def _audit_declared_compatibility(rules, reports, source_provider):
    """Evaluate declared runtime constraints only when one observed target is available."""
    results = []
    for rule in rules:
        targets = [
            item
            for item in reports
            if item["runtime"] == rule.get("with") and item["provider"] != source_provider
        ]
        actual = targets[0].get("detected") if len(targets) == 1 else None
        status = _compare_versions(rule.get("version"), actual, rule.get("policy"))
        reason = (
            "Compared observed target version against declared compatibility rule"
            if status in {"matched", "mismatch"}
            else (
                "Multiple providers describe target runtime"
                if len(targets) > 1
                else "No unique observed target runtime version was available"
            )
        )
        results.append(
            {
                "with": rule.get("with"),
                "required_version": rule.get("version"),
                "detected": actual,
                "policy": rule.get("policy"),
                "status": status,
                "reason": reason,
            }
        )
    return results


def _compare_versions(expected, actual, policy):
    if not expected or not actual:
        return "not-verified"
    expected_parts = tuple(int(part) for part in re.findall(r"\d+", expected))
    actual_parts = tuple(int(part) for part in re.findall(r"\d+", actual))
    if not expected_parts or not actual_parts:
        return "not-verified"
    if policy == "minimum":
        size = max(len(expected_parts), len(actual_parts))
        expected_parts += (0,) * (size - len(expected_parts))
        actual_parts += (0,) * (size - len(actual_parts))
        return "matched" if actual_parts >= expected_parts else "mismatch"
    if policy == "compatible":
        return "matched" if actual_parts[: len(expected_parts)] == expected_parts else "mismatch"
    if policy == "exact":
        return "matched" if actual_parts == expected_parts else "mismatch"
    return "not-verified"


def _within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _read_limited(path: Path, limit: int) -> str:
    with path.open("rb") as source:
        return source.read(limit).decode("utf-8", errors="replace")
