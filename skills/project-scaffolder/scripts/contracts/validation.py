"""Schema validation for declarative capability provider records."""

import re
from pathlib import Path, PureWindowsPath
from typing import Any, Dict, List

from contracts.models import CONTRACT_VERSION, PROVIDER_KINDS, ProviderDescriptor

PROVIDER_ID = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
EVIDENCE_QUALITIES = {"observed", "declared", "inferred", "weak"}
PROVIDER_FIELDS = {
    "id",
    "kind",
    "schema_version",
    "capabilities",
    "matches",
    "requires",
    "conflicts",
    "payload",
}


def validate_provider_record(data: Any, source: str = "") -> List[str]:
    errors = []
    if not isinstance(data, dict):
        return ["Provider record must be a JSON object"]

    unknown = sorted(set(data) - PROVIDER_FIELDS)
    missing = sorted({"id", "kind", "schema_version", "capabilities", "payload"} - set(data))
    if unknown:
        errors.append("Unknown provider fields: " + ", ".join(unknown))
    if missing:
        errors.append("Missing provider fields: " + ", ".join(missing))
    if errors:
        return errors

    if not isinstance(data["id"], str) or not PROVIDER_ID.fullmatch(data["id"]):
        errors.append("id must be a lowercase provider slug")
    if not isinstance(data["kind"], str) or data["kind"] not in PROVIDER_KINDS:
        errors.append("kind must be one of: " + ", ".join(sorted(PROVIDER_KINDS)))
    if type(data["schema_version"]) is not int or data["schema_version"] != CONTRACT_VERSION:
        errors.append("schema_version is unsupported; expected %d" % CONTRACT_VERSION)
    if not _string_list(data["capabilities"], allow_empty=False):
        errors.append("capabilities must be a non-empty list of strings")
    if not isinstance(data["payload"], dict):
        errors.append("payload must be an object")
    else:
        errors.extend(_validate_payload(data["kind"], data["payload"]))

    for field in ("requires", "conflicts"):
        if field in data and not _string_list(data[field], allow_empty=True):
            errors.append(field + " must be a list of provider IDs")

    matches = data.get("matches", [])
    if not isinstance(matches, list):
        errors.append("matches must be a list")
    else:
        for index, rule in enumerate(matches):
            if (
                not isinstance(rule, dict)
                or not isinstance(rule.get("path"), str)
                or not rule["path"]
            ):
                errors.append("matches[%d] requires a non-empty path" % index)
                continue
            marker_path = Path(rule["path"])
            windows_path = PureWindowsPath(rule["path"])
            if (
                marker_path.is_absolute()
                or windows_path.is_absolute()
                or ".." in marker_path.parts
                or ".." in windows_path.parts
            ):
                errors.append("matches[%d].path must stay within the discovery root" % index)
            if set(rule) - {"path", "contains", "weight", "quality"}:
                errors.append("matches[%d] contains unsupported fields" % index)
            if "contains" in rule and not isinstance(rule["contains"], str):
                errors.append("matches[%d].contains must be a string" % index)
            quality = rule.get("quality", "observed")
            if not isinstance(quality, str) or quality not in EVIDENCE_QUALITIES:
                errors.append(
                    "matches[%d].quality must be one of: %s"
                    % (index, ", ".join(sorted(EVIDENCE_QUALITIES)))
                )
            weight = rule.get("weight", 1)
            if type(weight) is not int or not 1 <= weight <= 5:
                errors.append("matches[%d].weight must be an integer from 1 to 5" % index)
    return errors


def provider_descriptor(data: Dict[str, Any], source: str = "") -> ProviderDescriptor:
    errors = validate_provider_record(data, source)
    if errors:
        raise ValueError("; ".join(errors))
    return ProviderDescriptor(
        id=data["id"],
        kind=data["kind"],
        schema_version=data["schema_version"],
        capabilities=list(data["capabilities"]),
        matches=list(data.get("matches", [])),
        requires=list(data.get("requires", [])),
        conflicts=list(data.get("conflicts", [])),
        payload=dict(data["payload"]),
        source=source,
    )


def _string_list(value: Any, allow_empty: bool) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and item for item in value)
    )


def validate_legacy_profile(data: Any) -> List[str]:
    """Validate compatibility-profile structure and generated paths before loading."""
    if not isinstance(data, dict):
        return ["Profile must be a JSON object"]
    errors = []
    for field in ("domain", "stack", "name"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            errors.append("%s must be a non-empty string" % field)
    if not isinstance(data.get("directories"), list):
        errors.append(
            "directories must be declared as a list; generic directories are not inferred"
        )
    list_fields = (
        "markers",
        "directories",
        "lfs_patterns",
        "config_manifests",
        "test_commands",
        "build_commands",
    )
    for field in list_fields:
        if field in data and (
            not isinstance(data[field], list)
            or not all(isinstance(item, str) for item in data[field])
        ):
            errors.append("%s must be a list of strings" % field)
    for field in ("markers", "config_manifests"):
        values = data.get(field, [])
        if isinstance(values, list):
            for marker in values:
                path = (
                    marker.split(":", 1)[0]
                    if field == "markers" and isinstance(marker, str)
                    else marker
                )
                if isinstance(path, str) and not _safe_profile_path(path):
                    errors.append("%s contains an unsafe relative path" % field)
                    break
    values = data.get("lfs_patterns", [])
    if isinstance(values, list) and any(
        isinstance(path, str) and not _safe_profile_path(path) for path in values
    ):
        errors.append("lfs_patterns contains an unsafe relative pattern")
    for field in ("mandatory_categories", "na_categories"):
        if field in data and (
            not isinstance(data[field], list)
            or not all(type(item) is int and 1 <= item <= 20 for item in data[field])
        ):
            errors.append("%s must be a list of integers from 1 to 20" % field)
    for field in ("entry_points", "smoke_tests"):
        items = data.get(field, [])
        if not isinstance(items, list):
            errors.append("%s must be a list" % field)
            continue
        for index, item in enumerate(items):
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("path"), str)
                or not isinstance(item.get("template"), str)
            ):
                errors.append("%s[%d] requires string path and template" % (field, index))
            elif not _safe_profile_path(item["path"]):
                errors.append("%s[%d].path escapes the project root" % (field, index))
    layouts = data.get("architecture_layouts", {})
    if not isinstance(layouts, dict):
        errors.append("architecture_layouts must be an object")
    elif any(
        not isinstance(paths, list)
        or not all(isinstance(path, str) and _safe_profile_path(path) for path in paths)
        for paths in layouts.values()
    ):
        errors.append("architecture_layouts values must contain safe relative paths")
    for path in (
        data.get("directories", []) if isinstance(data.get("directories", []), list) else []
    ):
        if isinstance(path, str) and not _safe_profile_path(path):
            errors.append("directories contains a path outside the project root")
            break
    common = data.get("architecture_common_directories", [])
    if not isinstance(common, list) or not all(
        isinstance(path, str) and _safe_profile_path(path) for path in common
    ):
        errors.append("architecture_common_directories must contain safe relative paths")
    topology = data.get("topology_directories", {})
    if not isinstance(topology, dict) or any(
        not isinstance(paths, list)
        or not all(isinstance(path, str) and _safe_profile_path(path) for path in paths)
        for paths in topology.values()
    ):
        errors.append("topology_directories must contain safe relative path lists")
    for field in ("architecture_entry_points", "architecture_smoke_tests"):
        catalog = data.get(field, {})
        if not isinstance(catalog, dict):
            errors.append("%s must be an object" % field)
            continue
        for items in catalog.values():
            if not isinstance(items, list) or any(
                not isinstance(item, dict)
                or not isinstance(item.get("path"), str)
                or not _safe_profile_path(item["path"])
                or not isinstance(item.get("template"), str)
                for item in items
            ):
                errors.append("%s entries require safe paths and string templates" % field)
                break
    return errors


def _safe_profile_path(value: str) -> bool:
    candidate = Path(value)
    windows = PureWindowsPath(value)
    return not (
        "\x00" in value
        or candidate.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in candidate.parts
        or ".." in windows.parts
    )


def _validate_payload(kind: str, payload: Dict[str, Any]) -> List[str]:
    errors = []
    path_fields = []
    if kind == "package_manager":
        path_fields = ["manifests", "lockfiles", "registry_config_paths"]
        for field in (
            "locked_install",
            "add",
            "remove",
            "update",
            "audit",
            "version_probe",
            "audit_version_probe",
        ):
            if field in payload and not _string_list(payload[field], allow_empty=True):
                errors.append("payload.%s must be a list of strings" % field)
        for field in ("manager", "executable", "lockfile_policy"):
            if field in payload and not isinstance(payload[field], str):
                errors.append("payload.%s must be a string" % field)
        lock_policy = payload.get("lockfile_policy", "not-applicable")
        if not isinstance(lock_policy, str) or lock_policy not in {
            "required",
            "recommended",
            "not-applicable",
        }:
            errors.append("payload.lockfile_policy is unsupported")
        if "dependency_groups" in payload and not _string_list(
            payload["dependency_groups"], allow_empty=True
        ):
            errors.append("payload.dependency_groups must be a list of strings")
        if (
            "audit_allow_missing_lockfiles" in payload
            and type(payload["audit_allow_missing_lockfiles"]) is not bool
        ):
            errors.append("payload.audit_allow_missing_lockfiles must be a boolean")
        if "audit_network_policy" in payload and payload["audit_network_policy"] not in {
            "offline-required",
            "may-access-network",
        }:
            errors.append("payload.audit_network_policy is unsupported")
        if payload.get("audit"):
            if not _string_list(payload.get("audit_write_effects"), allow_empty=True):
                errors.append("payload.audit_write_effects must be a list of strings")
            if type(payload.get("audit_timeout_seconds")) is not int or not 1 <= payload["audit_timeout_seconds"] <= 600:
                errors.append("payload.audit_timeout_seconds must be from 1 to 600")
            if type(payload.get("audit_output_limit")) is not int or not 800 <= payload["audit_output_limit"] <= 1048576:
                errors.append("payload.audit_output_limit must be from 800 to 1048576")
            if payload.get("audit_requires_confirmation") is not True:
                errors.append("payload.audit_requires_confirmation must be true for declared audit commands")
            if (
                payload.get("audit_network_policy") not in {"offline-required", "may-access-network"}
                or payload.get("audit_write_effects")
            ) and payload.get("audit_requires_confirmation") is not True:
                errors.append("payload audit commands with network/write effects require confirmation")
        if "version_strategy" in payload:
            strategy = payload["version_strategy"]
            if not isinstance(strategy, str) or strategy not in {
                "exact",
                "compatible-range",
                "minimum",
                "controlled-range",
                "manager-defined",
            }:
                errors.append("payload.version_strategy is unsupported")
        if "lock_check" in payload:
            check = payload["lock_check"]
            if not isinstance(check, dict):
                errors.append("payload.lock_check must be an object")
            else:
                if not _string_list(check.get("command"), allow_empty=False):
                    errors.append("payload.lock_check.command must be a non-empty list of strings")
                if check.get("network_policy") not in {"offline-required", "may-access-network"}:
                    errors.append("payload.lock_check.network_policy is unsupported")
                if not _string_list(check.get("write_effects"), allow_empty=True):
                    errors.append("payload.lock_check.write_effects must be a list of strings")
                if type(check.get("timeout_seconds")) is not int or not 1 <= check["timeout_seconds"] <= 600:
                    errors.append("payload.lock_check.timeout_seconds must be from 1 to 600")
                if type(check.get("output_limit")) is not int or not 800 <= check["output_limit"] <= 1048576:
                    errors.append("payload.lock_check.output_limit must be from 800 to 1048576")
                if check.get("requires_confirmation") is not True:
                    errors.append("payload.lock_check.requires_confirmation must be true")
                if (
                    "allow_missing_lockfiles" in check
                    and type(check["allow_missing_lockfiles"]) is not bool
                ):
                    errors.append("payload.lock_check.allow_missing_lockfiles must be a boolean")
                if (
                    not isinstance(check.get("description"), str)
                    or not check["description"].strip()
                ):
                    errors.append("payload.lock_check.description must be a non-empty string")
        if "inventory_parser" in payload:
            parser = payload["inventory_parser"]
            if not isinstance(parser, dict):
                errors.append("payload.inventory_parser must be an object")
            else:
                if not isinstance(parser.get("path"), str) or not _safe_profile_path(
                    parser["path"]
                ):
                    errors.append("payload.inventory_parser.path must be a safe relative path")
                if parser.get("format") not in {
                    "toml-package-sections",
                    "unity-upm-lock-json",
                    "go-sum-lines",
                    "pnpm-lock-v9-yaml",
                }:
                    errors.append("payload.inventory_parser.format is unsupported")
                for field in ("scope", "limitation"):
                    if field in parser and not isinstance(parser[field], str):
                        errors.append("payload.inventory_parser.%s must be a string" % field)
        if "dependency_audit_parser" in payload:
            parser = payload["dependency_audit_parser"]
            if not isinstance(parser, dict):
                errors.append("payload.dependency_audit_parser must be an object")
            else:
                if parser.get("format") not in {
                    "uv-audit-preview-json",
                    "pnpm-audit-json",
                    "cargo-audit-json",
                    "govulncheck-json-stream",
                }:
                    errors.append("payload.dependency_audit_parser.format is unsupported")
                supported_schemas = {
                    "uv-audit-preview-json": {"preview"},
                    "pnpm-audit-json": {"pnpm-audit-report"},
                    "cargo-audit-json": {"cargo-audit-report"},
                    "govulncheck-json-stream": {"protocol-v1"},
                }
                parser_format = parser.get("format")
                if (
                    parser_format in supported_schemas
                    and parser.get("schema_version") not in supported_schemas[parser_format]
                ):
                    errors.append(
                        "payload.dependency_audit_parser.schema_version is unsupported for its format"
                    )
                if (
                    type(parser.get("max_findings")) is not int
                    or not 1 <= parser["max_findings"] <= 500
                ):
                    errors.append(
                        "payload.dependency_audit_parser.max_findings must be between 1 and 500"
                    )
                if not isinstance(parser.get("limitation"), str):
                    errors.append("payload.dependency_audit_parser.limitation must be a string")
        if "manifest_generation" in payload:
            generation = payload["manifest_generation"]
            if not isinstance(generation, dict):
                errors.append("payload.manifest_generation must be an object")
            else:
                path = generation.get("path")
                if not isinstance(path, str) or not _safe_profile_path(path):
                    errors.append("payload.manifest_generation.path must be a safe relative path")
                for field in (
                    "project_name_field",
                    "version_field",
                    "runtime_dependencies_field",
                    "development_dependencies_field",
                    "go_version_field",
                    "edition_field",
                ):
                    if field in generation and (
                        not isinstance(generation[field], str)
                        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", generation[field])
                    ):
                        errors.append("payload.manifest_generation.%s must be a field name" % field)
                static_fields = generation.get("static_fields", {})
                if not isinstance(static_fields, dict) or not all(
                    isinstance(key, str) for key in static_fields
                ):
                    errors.append(
                        "payload.manifest_generation.static_fields must be an object with string keys"
                    )
                if generation.get("renderer", "json") not in {
                    "json",
                    "go-mod",
                    "cargo-toml",
                    "uv-toml",
                }:
                    errors.append("payload.manifest_generation.renderer is unsupported")
    elif kind == "toolchain":
        path_fields = ["version_file"]
        if "probe" in payload and not _string_list(payload["probe"], allow_empty=True):
            errors.append("payload.probe must be a list of strings")
        for field in ("version_pattern", "detected_pattern", "version_policy", "runtime"):
            if field in payload and not isinstance(payload[field], str):
                errors.append("payload.%s must be a string" % field)
        version_policy = payload.get("version_policy", "")
        if not isinstance(version_policy, str) or version_policy not in {
            "exact",
            "compatible",
            "minimum",
            "channel",
            "",
        }:
            errors.append("payload.version_policy is unsupported")
        requirement_level = payload.get("requirement_level", "required")
        if not isinstance(requirement_level, str) or requirement_level not in {
            "minimum-supported",
            "required",
            "recommended",
            "exact-pin",
            "optional",
        }:
            errors.append("payload.requirement_level is unsupported")
        if "environment_preparation" in payload and not _string_list(
            payload["environment_preparation"], allow_empty=False
        ):
            errors.append("payload.environment_preparation must be a non-empty list of strings")
        if "compatibility" in payload:
            compatibility = payload["compatibility"]
            if not isinstance(compatibility, list):
                errors.append("payload.compatibility must be a list")
            else:
                for index, rule in enumerate(compatibility):
                    if (
                        not isinstance(rule, dict)
                        or not isinstance(rule.get("with"), str)
                        or not isinstance(rule.get("policy"), str)
                        or rule["policy"] not in {"exact", "compatible", "minimum"}
                        or not isinstance(rule.get("version"), str)
                    ):
                        errors.append(
                            "payload.compatibility[%d] requires with, policy, and version" % index
                        )
        if "generation" in payload:
            generation = payload["generation"]
            if (
                not isinstance(generation, dict)
                or not isinstance(generation.get("path"), str)
                or not _safe_profile_path(generation["path"])
            ):
                errors.append("payload.generation.path must be a safe relative path")
            elif not isinstance(generation.get("content_template"), str) or not isinstance(
                generation.get("validation_pattern"), str
            ):
                errors.append(
                    "payload.generation requires a content template and validation pattern"
                )
            else:
                try:
                    re.compile(generation["validation_pattern"])
                except re.error:
                    errors.append(
                        "payload.generation.validation_pattern must be a valid regular expression"
                    )
    elif kind == "architecture":
        path_fields = ["directories"]
        for field in ("description",):
            if not isinstance(payload.get(field), str) or not payload[field].strip():
                errors.append("payload.%s must be a non-empty string" % field)
        for field in ("constraints", "tradeoffs", "supported_template_capabilities"):
            if field in payload and not _string_list(payload[field], allow_empty=True):
                errors.append("payload.%s must be a list of strings" % field)
    elif kind == "verification":
        checks = payload.get("checks", [])
        if not isinstance(checks, list):
            errors.append("payload.checks must be a list")
        else:
            seen = set()
            for index, check in enumerate(checks):
                if not isinstance(check, dict):
                    errors.append("payload.checks[%d] must be an object" % index)
                    continue
                if (
                    not isinstance(check.get("id"), str)
                    or not check["id"]
                    or check.get("kind") not in {"test", "build"}
                    or not _string_list(check.get("command"), allow_empty=False)
                ):
                    errors.append(
                        "payload.checks[%d] requires id, test/build kind, and command" % index
                    )
                elif check["id"] in seen:
                    errors.append("payload.checks contains duplicate id %s" % check["id"])
                else:
                    seen.add(check["id"])
                if "required" in check and type(check["required"]) is not bool:
                    errors.append("payload.checks[%d].required must be a boolean" % index)
                execution = check.get("execution_policy")
                if not isinstance(execution, dict):
                    errors.append("payload.checks[%d].execution_policy is required" % index)
                else:
                    allowed_execution_fields = {
                        "mode", "allowed_argv", "cwd_scope", "network_policy",
                        "write_effects", "timeout_seconds", "output_limit",
                        "requires_confirmation",
                    }
                    if set(execution) - allowed_execution_fields:
                        errors.append("payload.checks[%d].execution_policy has unknown fields" % index)
                    if execution.get("mode") != "exact-argv":
                        errors.append("payload.checks[%d].execution_policy.mode must be exact-argv" % index)
                    if execution.get("allowed_argv") != check.get("command"):
                        errors.append("payload.checks[%d].execution_policy.allowed_argv must exactly match command" % index)
                    if execution.get("cwd_scope") != "project-root":
                        errors.append("payload.checks[%d].execution_policy.cwd_scope must be project-root" % index)
                    if execution.get("network_policy") not in {"offline-required", "may-access-network"}:
                        errors.append("payload.checks[%d].execution_policy.network_policy is invalid" % index)
                    if not _string_list(execution.get("write_effects"), allow_empty=True):
                        errors.append("payload.checks[%d].execution_policy.write_effects must be a list of strings" % index)
                    if type(execution.get("timeout_seconds")) is not int or not 1 <= execution["timeout_seconds"] <= 600:
                        errors.append("payload.checks[%d].execution_policy.timeout_seconds must be from 1 to 600" % index)
                    if type(execution.get("output_limit")) is not int or not 0 <= execution["output_limit"] <= 5000:
                        errors.append("payload.checks[%d].execution_policy.output_limit must be from 0 to 5000" % index)
                    if type(execution.get("requires_confirmation")) is not bool:
                        errors.append("payload.checks[%d].execution_policy.requires_confirmation must be boolean" % index)
                    elif (
                        execution.get("network_policy") == "may-access-network"
                        or bool(execution.get("write_effects"))
                    ) and not execution["requires_confirmation"]:
                        errors.append("payload.checks[%d] must require confirmation for network or write effects" % index)
                expected = check.get("expected_evidence", {})
                if not isinstance(expected, dict):
                    errors.append("payload.checks[%d].expected_evidence must be an object" % index)
                elif (
                    (
                        "requires_assertions" in expected
                        and type(expected["requires_assertions"]) is not bool
                    )
                    or (
                        "minimum_test_count" in expected
                        and (
                            type(expected["minimum_test_count"]) is not int
                            or expected["minimum_test_count"] < 1
                        )
                    )
                    or (
                        "stdout_contains" in expected
                        and not _string_list(expected["stdout_contains"], allow_empty=True)
                    )
                ):
                    errors.append("payload.checks[%d].expected_evidence is invalid" % index)
        policy = payload.get("project_policy", {})
        if not isinstance(policy, dict):
            errors.append("payload.project_policy must be an object")
        else:
            for field in ("config_manifests", "module_boundary_patterns"):
                values = policy.get(field, [])
                if not isinstance(values, list) or not all(
                    isinstance(value, str) and _safe_profile_path(value.split(":", 1)[0])
                    for value in values
                ):
                    errors.append(
                        "payload.project_policy.%s must contain safe relative paths" % field
                    )
            for field in ("mandatory_categories", "na_categories"):
                values = policy.get(field, [])
                if not isinstance(values, list) or not all(
                    type(value) is int and 1 <= value <= 20 for value in values
                ):
                    errors.append(
                        "payload.project_policy.%s must contain category numbers from 1 to 20"
                        % field
                    )
    elif kind == "template":
        path_fields = ["directories"]
    for field in path_fields:
        if field not in payload:
            continue
        values = payload[field]
        if field == "version_file":
            values = [values] if isinstance(values, str) else values
        elif (
            field == "directories"
            and isinstance(values, list)
            and all(isinstance(item, dict) for item in values)
        ):
            values = [item.get("path") for item in values]
        if not isinstance(values, list) or not all(
            isinstance(value, str) and _safe_profile_path(value) for value in values
        ):
            errors.append("payload.%s must contain safe relative paths" % field)
    if kind == "template":
        directories = payload.get("directories", [])
        if not isinstance(directories, list) or any(
            not isinstance(item, (str, dict))
            or (isinstance(item, dict) and not isinstance(item.get("path"), str))
            for item in directories
        ):
            errors.append("payload.directories must be a list of paths or path objects")
        files = payload.get("files", [])
        if not isinstance(files, list):
            errors.append("payload.files must be a list")
        else:
            for index, item in enumerate(files):
                if (
                    not isinstance(item, dict)
                    or not isinstance(item.get("path"), str)
                    or not _safe_profile_path(item["path"])
                ):
                    errors.append("payload.files[%d].path must be a safe relative path" % index)
                elif not isinstance(item.get("content"), str):
                    errors.append("payload.files[%d].content must be a string" % index)
        checks = payload.get("verification_checks", [])
        if not isinstance(checks, list):
            errors.append("payload.verification_checks must be a list")
        else:
            for index, item in enumerate(checks):
                if (
                    not isinstance(item, dict)
                    or not isinstance(item.get("id"), str)
                    or not item["id"]
                ):
                    errors.append("payload.verification_checks[%d] requires an id" % index)
                elif (
                    "command" in item and not _string_list(item["command"], allow_empty=True)
                ) or (
                    "expected_evidence" in item and not isinstance(item["expected_evidence"], dict)
                ):
                    errors.append("payload.verification_checks[%d] has invalid fields" % index)
                elif "expected_evidence" in item:
                    expected = item["expected_evidence"]
                    if (
                        (
                            "requires_assertions" in expected
                            and type(expected["requires_assertions"]) is not bool
                        )
                        or (
                            "minimum_test_count" in expected
                            and (
                                type(expected["minimum_test_count"]) is not int
                                or expected["minimum_test_count"] < 1
                            )
                        )
                        or (
                            "stdout_contains" in expected
                            and not _string_list(expected["stdout_contains"], allow_empty=True)
                        )
                    ):
                        errors.append(
                            "payload.verification_checks[%d].expected_evidence is invalid" % index
                        )
    return errors
