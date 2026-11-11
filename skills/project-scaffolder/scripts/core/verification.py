"""Execute declared verification checks and preserve evidence/status semantics."""

import re

from contracts.models import VerificationEvidence

from core.safe_executor import execute_safe_tokens

TEST_COUNT_PATTERNS = (
    re.compile(r"\b([1-9]\d*)\s+passed\b", re.IGNORECASE),
    re.compile(r"test result:\s*ok\.\s*([1-9]\d*) passed", re.IGNORECASE),
    re.compile(r"\bRan\s+([1-9]\d*)\s+tests?\b.*\bOK\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bAll\s+([1-9]\d*)\s+tests?\s+passed", re.IGNORECASE),
    re.compile(r"Test Suites:\s*[1-9]\d* passed", re.IGNORECASE),
    re.compile(r"(?m)^ok\s+[^\n]+\s+\d+(?:\.\d+)?s(?:\s+\(cached\))?\s*$"),
)


def run_verification_checks(checks, root, timeout_seconds=180, confirmed=False):
    """Run provider-scoped commands only after validating policy and explicit confirmation."""
    evidence = []
    for check in checks:
        if not check.command:
            evidence.append(
                VerificationEvidence(
                    check_id=check.id,
                    status="NOT APPLICABLE",
                    required=check.required,
                    message="No command was declared for this check.",
                )
            )
            continue
        policy = check.execution_policy or {}
        if (
            policy.get("mode") != "exact-argv"
            or policy.get("allowed_argv") != check.command
            or policy.get("cwd_scope") != "project-root"
            or policy.get("network_policy") not in {"offline-required", "may-access-network"}
            or not isinstance(policy.get("write_effects"), list)
        ):
            evidence.append(
                VerificationEvidence(
                    check_id=check.id,
                    status="NOT VERIFIED",
                    required=check.required,
                    command=_redact_tokens(check.command),
                    message="Provider command policy is missing, invalid, or does not exactly authorize this argv; no process was started.",
                )
            )
            continue
        needs_confirmation = (
            policy.get("requires_confirmation") is True
            or policy.get("network_policy") == "may-access-network"
            or bool(policy.get("write_effects"))
        )
        if needs_confirmation and not confirmed:
            evidence.append(
                VerificationEvidence(
                    check_id=check.id,
                    status="NOT VERIFIED",
                    required=check.required,
                    command=_redact_tokens(check.command),
                    message=(
                        "Execution requires explicit confirmation. Preview: %s; network=%s; writes=%s. No process was started."
                        % (
                            " ".join(_redact_tokens(check.command)),
                            policy.get("network_policy"),
                            ", ".join(policy.get("write_effects", [])) or "none",
                        )
                    ),
                )
            )
            continue
        result = execute_safe_tokens(
            check.command,
            cwd=root,
            authorized_root=root,
            allowed_argv=policy.get("allowed_argv"),
            provider_id=check.capability,
            operation_id=check.id,
            timeout_seconds=min(int(policy.get("timeout_seconds", timeout_seconds)), timeout_seconds),
            output_limit=int(policy.get("output_limit", 800)),
            display_command=" ".join(_redact_tokens(check.command)),
        )
        output = "%s\n%s" % (result.stdout or "", result.stderr or "")
        status = result.status
        if status == "FAIL" and result.message.startswith("Execution blocked by policy"):
            status = "NOT VERIFIED"
        expected = check.expected_evidence or {}
        if status == "PASS":
            if expected.get("requires_assertions") and not _test_count(output):
                status = "NOT VERIFIED"
            if status == "PASS":
                required_literals = expected.get("stdout_contains", [])
                if any(literal not in output for literal in required_literals):
                    status = "NOT VERIFIED"
            if status == "PASS" and expected.get("minimum_test_count"):
                count = _test_count(output)
                if count is None or count < expected["minimum_test_count"]:
                    status = "NOT VERIFIED"
        summary = (
            "Command completed with exit code %s." % result.exit_code
            if result.exit_code is not None
            else result.message
        )
        if status == "NOT VERIFIED" and result.status == "PASS":
            summary = "Command exited successfully but did not provide the evidence required by the check."
        evidence.append(
            VerificationEvidence(
                check_id=check.id,
                status=status,
                command=_redact_tokens(check.command),
                exit_code=result.exit_code,
                output_summary=summary[:200],
                message=result.message,
            )
        )
    return evidence


def _test_count(output):
    for pattern in TEST_COUNT_PATTERNS:
        match = pattern.search(output)
        if match:
            return int(match.group(1)) if match.lastindex else 1
    return None


def _redact_tokens(tokens):
    redacted = []
    redact_next = False
    for token in tokens:
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue
        lowered = token.lower()
        if any(
            part in lowered for part in ("token", "password", "secret", "credential", "api-key")
        ):
            redacted.append("<redacted>")
        else:
            safe = re.sub(r"(?i)(://)[^/@\s]+@", r"\1<redacted>@", token)
            safe = re.sub(
                r"(?i)([?&](?:token|access_token|api[_-]?key|password|secret)=)[^&\s]+",
                r"\1<redacted>",
                safe,
            )
            safe = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*", r"\1<redacted>", safe)
            redacted.append(safe)
        if (
            lowered.startswith("--")
            and any(
                part in lowered for part in ("token", "password", "secret", "credential", "api-key")
            )
            and "=" not in token
        ):
            redact_next = True
    return redacted
