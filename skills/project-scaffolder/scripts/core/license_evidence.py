"""Read-only extraction of declared license evidence from a local CycloneDX JSON SBOM."""

import hashlib
import json
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

MAX_SBOM_BYTES = 5 * 1024 * 1024
MAX_COMPONENTS = 10_000
MAX_LICENSES_PER_COMPONENT = 50
MAX_REFERENCES_PER_COMPONENT = 50
SUPPORTED_SPEC_VERSIONS = {"1.4", "1.5", "1.6", "1.7"}


def inspect_license_evidence(root: Path, relative_path: str):
    """Extract declarations and provenance without deciding legal acceptability."""
    if not isinstance(relative_path, str) or not relative_path.strip():
        return {"status": "not-verified", "reason": "a relative SBOM path is required"}
    candidate = Path(relative_path)
    if candidate.is_absolute() or candidate.anchor:
        return {
            "status": "not-verified",
            "reason": f"SBOM path '{relative_path}' is outside the target project: provide a relative path inside the target directory instead of an absolute or rooted path",
        }
    if ".." in candidate.parts:
        return {
            "status": "not-verified",
            "reason": f"SBOM path '{relative_path}' escapes outside the target project ('..' traversal is not permitted)",
        }
    root = root.resolve()
    path = (root / candidate).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return {
            "status": "not-verified",
            "reason": f"SBOM path '{relative_path}' resolves outside the target project boundary",
        }
    if not path.exists():
        return {
            "status": "not-verified",
            "reason": f"SBOM file is missing at relative path inside target project: {relative_path}",
        }
    if not path.is_file():
        return {
            "status": "not-verified",
            "reason": f"SBOM path exists inside target project but is not a regular file: {relative_path}",
        }
    try:
        if path.stat().st_size > MAX_SBOM_BYTES:
            return {"status": "not-verified", "reason": "SBOM exceeds the 5 MiB read limit"}
        raw = path.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {"status": "not-verified", "reason": "SBOM is unreadable or invalid UTF-8 JSON"}
    if (
        not isinstance(document, dict)
        or document.get("bomFormat") != "CycloneDX"
        or document.get("specVersion") not in SUPPORTED_SPEC_VERSIONS
        or not isinstance(document.get("components", []), list)
    ):
        return {
            "status": "not-verified",
            "reason": "document is not a supported CycloneDX JSON SBOM",
        }

    queue = deque(
        (component, "$.components[%d]" % index)
        for index, component in enumerate(document.get("components", []))
    )
    components = []
    while queue:
        component, pointer = queue.popleft()
        if not isinstance(component, dict):
            return {"status": "not-verified", "reason": "component record is malformed"}
        if len(components) >= MAX_COMPONENTS:
            return {"status": "not-verified", "reason": "SBOM exceeds the 10,000 component limit"}
        licenses = component.get("licenses", [])
        references = component.get("externalReferences", [])
        children = component.get("components", [])
        if (
            not isinstance(licenses, list)
            or not isinstance(references, list)
            or not isinstance(children, list)
        ):
            return {
                "status": "not-verified",
                "reason": "component license/reference structure is malformed",
            }
        if (
            len(licenses) > MAX_LICENSES_PER_COMPONENT
            or len(references) > MAX_REFERENCES_PER_COMPONENT
        ):
            return {
                "status": "not-verified",
                "reason": "component evidence exceeds per-component limits",
            }
        declarations = []
        for index, item in enumerate(licenses):
            declaration = _license_declaration(item)
            if declaration is not None:
                declaration["evidence_pointer"] = pointer + ".licenses[%d]" % index
            declarations.append(declaration)
        if any(item is None for item in declarations):
            return {
                "status": "not-verified",
                "reason": "component contains an unsupported license declaration",
            }
        source_refs = []
        for index, item in enumerate(references):
            reference = _source_reference(item)
            if reference is not None:
                reference["evidence_pointer"] = pointer + ".externalReferences[%d]" % index
                source_refs.append(reference)
        components.append(
            {
                "name": _short_text(component.get("name")),
                "version": _short_text(component.get("version")),
                "purl": _short_text(component.get("purl")),
                "bom_ref": _short_text(component.get("bom-ref")),
                "status": "declared" if declarations else "unknown",
                "license_declarations": declarations,
                "package_source_references": source_refs,
                "evidence_pointer": pointer,
            }
        )
        queue.extend(
            (child, pointer + ".components[%d]" % index) for index, child in enumerate(children)
        )
    components.sort(
        key=lambda item: (item["purl"] or "", item["name"] or "", item["version"] or "")
    )
    return {
        "status": "parsed",
        "source_document": relative_path.replace("\\", "/"),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "format": "CycloneDX JSON",
        "spec_version": document["specVersion"],
        "component_count": len(components),
        "declared_license_count": sum(len(item["license_declarations"]) for item in components),
        "unknown_license_component_count": sum(item["status"] == "unknown" for item in components),
        "components": components,
        "decision": "not-evaluated",
        "limitation": "These are declarations copied from the supplied SBOM, not independently verified package-origin claims or legal advice. No allow/deny policy was applied.",
    }


def _license_declaration(item):
    if not isinstance(item, dict):
        return None
    license_data = item.get("license")
    expression = item.get("expression")
    if (license_data is None) == (expression is None):
        return None
    if expression is not None:
        if not isinstance(expression, str) or not expression.strip():
            return None
        return {"kind": "expression", "value": expression[:1000]}
    if not isinstance(license_data, dict):
        return None
    license_id = license_data.get("id")
    name = license_data.get("name")
    if license_id is not None and not isinstance(license_id, str):
        return None
    if name is not None and not isinstance(name, str):
        return None
    if license_id and name:
        declaration = {"kind": "identifier-and-name", "value": license_id[:300], "name": name[:500]}
        reference = _safe_url(license_data.get("url"))
        if reference:
            declaration["declared_license_reference"] = reference
        return declaration
    value = license_id or name
    if value:
        declaration = {"kind": "identifier" if license_id else "name", "value": value[:1000]}
        reference = _safe_url(license_data.get("url"))
        if reference:
            declaration["declared_license_reference"] = reference
        return declaration
    if isinstance(license_data.get("text"), dict) and isinstance(
        license_data["text"].get("content"), str
    ):
        text = license_data["text"]["content"].encode("utf-8", errors="replace")
        return {
            "kind": "embedded-text",
            "sha256": hashlib.sha256(text).hexdigest(),
            "byte_length": len(text),
        }
    return None


def _source_reference(item):
    if not isinstance(item, dict) or item.get("type") not in {
        "vcs",
        "source-distribution",
        "distribution",
        "distribution-intake",
        "license",
    }:
        return None
    safe_url = _safe_url(item.get("url"))
    if safe_url is None:
        return None
    return {"type": item["type"], "url": safe_url}


def _safe_url(url):
    if not isinstance(url, str) or len(url) > 2048:
        return None
    try:
        parts = urlsplit(url)
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


def _short_text(value):
    return value[:1000] if isinstance(value, str) and value else None
