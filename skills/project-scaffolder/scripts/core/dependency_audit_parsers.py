"""Bounded provider-specific parsers for machine-readable dependency audits."""

import json
from urllib.parse import urlsplit, urlunsplit

MAX_OUTPUT_CHARS = 1_048_576
MAX_FINDINGS = 500
MAX_TEXT = 1000
_SEVERITIES = {"none", "info", "low", "moderate", "medium", "high", "critical"}


def parse_dependency_audit(provider, result):
    config = provider.payload.get("dependency_audit_parser", {})
    fmt = config.get("format")
    if getattr(result, "output_truncated", False):
        return _not_verified("output-truncated")
    raw = result.stdout or ""
    if len(raw) > MAX_OUTPUT_CHARS:
        return _not_verified("output-exceeds-limit")
    try:
        if fmt == "uv-audit-preview-json":
            return _parse_uv(raw, result, config)
        if fmt == "pnpm-audit-json":
            return _parse_pnpm(raw, result, config)
        if fmt == "cargo-audit-json":
            return _parse_cargo(raw, result, config)
        if fmt == "govulncheck-json-stream":
            return _parse_govulncheck(raw, result, config)
    except json.JSONDecodeError:
        return _not_verified("invalid-json")
    except (TypeError, ValueError, KeyError):
        return _not_verified("malformed-output")
    return {"status": "not-interpreted", "reason": "unsupported-parser"}


def _parse_uv(raw, result, config):
    data = _json_document(raw)
    if (
        not isinstance(data.get("schema"), dict)
        or data["schema"].get("version") != config.get("schema_version")
        or not isinstance(data.get("summary"), dict)
        or not isinstance(data.get("vulnerabilities"), list)
        or not isinstance(data.get("adverse_statuses"), list)
    ):
        return _not_verified("schema-mismatch")
    summary = data["summary"]
    vuln_count = _nonnegative_int(summary.get("vulnerabilities"))
    adverse_count = _nonnegative_int(summary.get("adverse_statuses"))
    audited = _nonnegative_int(summary.get("audited_packages"))
    if vuln_count is None or adverse_count is None or audited is None:
        return _not_verified("invalid-summary-counts")
    if vuln_count != len(data["vulnerabilities"]) or adverse_count != len(data["adverse_statuses"]):
        return _not_verified("summary-record-count-mismatch")
    if max(vuln_count, adverse_count) > _limit(config):
        return _not_verified("finding-limit-exceeded")
    return _report(
        "uv-audit-preview-json", result, audited, vuln_count, adverse_count, None, "preview"
    )


def _parse_pnpm(raw, result, config):
    data = _json_document(raw)
    advisories = data.get("advisories")
    metadata = data.get("metadata")
    if (
        set(data) - {"advisories", "metadata"}
        or not isinstance(advisories, dict)
        or not isinstance(metadata, dict)
    ):
        return _not_verified("schema-mismatch")
    expected_metadata = {
        "vulnerabilities",
        "dependencies",
        "devDependencies",
        "optionalDependencies",
        "totalDependencies",
    }
    if set(metadata) != expected_metadata:
        return _not_verified("schema-mismatch")
    counts = metadata.get("vulnerabilities")
    if not isinstance(counts, dict) or any(
        _nonnegative_int(counts.get(level)) is None
        for level in ("info", "low", "moderate", "high", "critical")
    ):
        return _not_verified("invalid-severity-counts")
    dependencies = _nonnegative_int(metadata.get("totalDependencies"))
    if dependencies is None or len(advisories) > _limit(config):
        return _not_verified("finding-limit-exceeded-or-invalid-dependency-count")
    findings = []
    observed = {level: 0 for level in counts}
    for advisory_id, item in advisories.items():
        if not isinstance(item, dict):
            return _not_verified("malformed-advisory-record")
        severity = item.get("severity")
        name = item.get("module_name")
        identifier = item.get("github_advisory_id") or str(advisory_id)
        versions = item.get("findings")
        if (
            severity not in _SEVERITIES
            or not isinstance(name, str)
            or not isinstance(versions, list)
        ):
            return _not_verified("malformed-advisory-record")
        normalized_level = "moderate" if severity == "medium" else severity
        if normalized_level not in observed:
            return _not_verified("unknown-severity")
        observed[normalized_level] += 1
        if len(findings) + len(versions) > _limit(config):
            return _not_verified("finding-limit-exceeded")
        patched_versions = item.get("patched_versions", "__missing__")
        if patched_versions is not None and not isinstance(patched_versions, str):
            return _not_verified("malformed-patched-version-field")
        for match in versions:
            if not isinstance(match, dict) or not isinstance(match.get("version"), str):
                return _not_verified("malformed-package-match")
            findings.append(
                {
                    "id": str(identifier)[:200],
                    "package": name[:MAX_TEXT],
                    "version": match["version"][:200],
                    "severity": normalized_level,
                    "title": _short(item.get("title")),
                    "patched_versions": (
                        _short(patched_versions) if patched_versions != "__missing__" else None
                    ),
                    "fix_available": (
                        patched_versions is not None if patched_versions != "__missing__" else None
                    ),
                }
            )
    if observed != {level: _nonnegative_int(counts[level]) for level in observed}:
        return _not_verified("severity-count-mismatch")
    report = _report(
        "pnpm-audit-json",
        result,
        dependencies,
        sum(observed.values()),
        0,
        findings,
        "pnpm-audit-report",
    )
    report["package_match_count"] = len(findings)
    report["severity_counts"] = {level: _nonnegative_int(count) for level, count in counts.items()}
    return report


def _parse_cargo(raw, result, config):
    data = _json_document(raw)
    vulnerabilities = data.get("vulnerabilities")
    warnings = data.get("warnings", {})
    if (
        not isinstance(vulnerabilities, dict)
        or not isinstance(warnings, dict)
        or not isinstance(vulnerabilities.get("list"), list)
    ):
        return _not_verified("schema-mismatch")
    records = vulnerabilities["list"]
    declared_count = _nonnegative_int(vulnerabilities.get("count"))
    declared_found = vulnerabilities.get("found")
    if (
        declared_count is None
        or declared_count != len(records)
        or type(declared_found) is not bool
        or declared_found != (declared_count > 0)
    ):
        return _not_verified("vulnerability-count-mismatch")
    if len(records) > _limit(config):
        return _not_verified("finding-limit-exceeded")
    findings = []
    for record in records:
        if not isinstance(record, dict):
            return _not_verified("malformed-vulnerability-record")
        advisory, package = record.get("advisory"), record.get("package")
        if not isinstance(advisory, dict) or not isinstance(package, dict):
            return _not_verified("malformed-vulnerability-record")
        identifier = advisory.get("id")
        name, version = package.get("name"), package.get("version")
        severity = advisory.get("severity")
        if not all(isinstance(value, str) and value for value in (identifier, name, version)):
            return _not_verified("malformed-vulnerability-identity")
        if severity is not None and severity not in _SEVERITIES:
            return _not_verified("unknown-severity")
        patched = _bounded_string_list(advisory.get("patched_versions"))
        if patched is None:
            versions = record.get("versions", {})
            patched = _bounded_string_list(
                versions.get("patched") if isinstance(versions, dict) else None
            )
        findings.append(
            {
                "id": identifier[:200],
                "package": name[:MAX_TEXT],
                "version": version[:200],
                "severity": severity.lower() if isinstance(severity, str) else "not-reported",
                "title": _short(advisory.get("title")),
                "patched_versions": patched,
            }
        )
    warning_count = 0
    for bucket in warnings.values():
        if not isinstance(bucket, list):
            return _not_verified("malformed-warning-bucket")
        warning_count += len(bucket)
    if warning_count > _limit(config):
        return _not_verified("finding-limit-exceeded")
    report = _report(
        "cargo-audit-json", result, None, len(findings), warning_count, findings, "stable"
    )
    report["warning_buckets"] = sorted(warnings.keys())
    return report


def _parse_govulncheck(raw, result, config):
    messages = _json_stream(raw)
    if not messages or len(messages) > _limit(config) * 20:
        return _not_verified("empty-stream-or-message-limit-exceeded")
    allowed = {"config", "progress", "SBOM", "osv", "finding"}
    config_message = None
    advisories = {}
    findings = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            return _not_verified("malformed-stream-message")
        populated = [key for key in allowed if key in message]
        if len(populated) != 1 or set(message) - allowed:
            return _not_verified("unknown-or-ambiguous-stream-message")
        kind = populated[0]
        value = message[kind]
        if not isinstance(value, dict):
            return _not_verified("malformed-stream-payload")
        if kind == "config":
            if (
                index != 0
                or config_message is not None
                or not isinstance(value.get("protocol_version"), str)
                or not value["protocol_version"].startswith("v1.")
            ):
                return _not_verified("invalid-config-message")
            config_message = value
        elif kind == "osv":
            identifier = value.get("id")
            if not isinstance(identifier, str) or not identifier:
                return _not_verified("malformed-osv-record")
            aliases = value.get("aliases", [])
            if not isinstance(aliases, list) or not all(
                isinstance(alias, str) for alias in aliases
            ):
                return _not_verified("malformed-osv-aliases")
            advisories[identifier] = {
                "id": identifier[:200],
                "aliases": [alias[:200] for alias in aliases[:50]],
                "summary": _short(value.get("summary")),
            }
        elif kind == "finding":
            identifier = value.get("osv")
            trace = value.get("trace", [])
            if not isinstance(identifier, str) or not isinstance(trace, list):
                return _not_verified("malformed-finding-record")
            if len(findings) >= _limit(config):
                return _not_verified("finding-limit-exceeded")
            package_evidence = []
            for frame in trace[:50]:
                if not isinstance(frame, dict):
                    return _not_verified("malformed-trace-frame")
                module = frame.get("module")
                if isinstance(module, dict) and isinstance(module.get("path"), str):
                    package_evidence.append(
                        {
                            "module": module["path"][:MAX_TEXT],
                            "version": _short(module.get("version")),
                            "package": _short(frame.get("package")),
                            "function": _short(frame.get("function")),
                        }
                    )
            findings.append(
                {
                    "id": identifier[:200],
                    "fixed_version": _short(value.get("fixed_version")),
                    "trace": package_evidence,
                }
            )
    if config_message is None:
        return _not_verified("missing-config-message")
    known_ids = set(advisories)
    if any(finding["id"] not in known_ids for finding in findings):
        return _not_verified("finding-references-missing-osv-record")
    unique_ids = sorted({finding["id"] for finding in findings})
    if len(unique_ids) > _limit(config):
        return _not_verified("finding-limit-exceeded")
    normalized = []
    for identifier in unique_ids:
        advisory = advisories[identifier]
        matching = [finding for finding in findings if finding["id"] == identifier]
        normalized.append(
            {
                **advisory,
                "finding_count": len(matching),
                "fix_versions": sorted(
                    {item["fixed_version"] for item in matching if item["fixed_version"]}
                ),
                "traces": [trace for item in matching for trace in item["trace"]][:100],
            }
        )
    audited = (
        len((messages[-1].get("SBOM") or {}).get("roots", [])) if "SBOM" in messages[-1] else None
    )
    report = _report(
        "govulncheck-json-stream",
        result,
        audited,
        len(unique_ids),
        0,
        normalized,
        "protocol:" + config_message["protocol_version"],
    )
    report["database"] = _safe_url(config_message.get("db"))
    report["database_last_modified"] = _short(config_message.get("db_last_modified"))
    report["scan_level"] = _short(config_message.get("scan_level"))
    return report


def _json_document(raw):
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    return data


def _json_stream(raw):
    decoder = json.JSONDecoder()
    cursor = 0
    messages = []
    while cursor < len(raw):
        while cursor < len(raw) and raw[cursor].isspace():
            cursor += 1
        if cursor >= len(raw):
            break
        message, cursor = decoder.raw_decode(raw, cursor)
        messages.append(message)
        if len(messages) > MAX_FINDINGS * 20:
            raise ValueError("stream limit exceeded")
    return messages


def _report(source, result, audited, vulnerability_count, warning_count, findings, schema_version):
    if findings is not None and len(findings) > MAX_FINDINGS:
        return _not_verified("finding-limit-exceeded")
    if vulnerability_count or warning_count:
        status = "findings-present"
    elif result.exit_code == 0:
        status = "no-findings-reported"
    else:
        return _not_verified("nonzero-exit-without-findings")
    report = {
        "status": status,
        "source": source,
        "schema_version": schema_version,
        "audited_packages": audited,
        "vulnerability_count": vulnerability_count,
        (
            "adverse_status_count" if source == "uv-audit-preview-json" else "warning_count"
        ): warning_count,
        "license_status": "not-reported",
        "severity_breakdown": "not-reported",
        "finding_scope": "Results reflect the provider tool's active filters and ignore configuration; those settings are not independently evaluated.",
    }
    if findings is not None:
        report["findings"] = findings
    return report


def _not_verified(reason):
    return {"status": "not-verified", "reason": reason}


def _nonnegative_int(value):
    return value if type(value) is int and value >= 0 else None


def _limit(config):
    value = config.get("max_findings", MAX_FINDINGS)
    return value if type(value) is int and 1 <= value <= MAX_FINDINGS else MAX_FINDINGS


def _short(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value[:MAX_TEXT]
    return None


def _safe_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"https", "http"}
            or not parts.hostname
            or parts.username
            or parts.password
        ):
            return None
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except ValueError:
        return None


def _bounded_string_list(value):
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return [item[:200] for item in value[:50]]
