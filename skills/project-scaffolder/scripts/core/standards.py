"""Standards metadata validation and explainable, evidence-based selection."""

from datetime import date

REQUIRED_METADATA = {
    "name",
    "classification",
    "source",
    "scope",
    "applicability",
    "requirement",
    "conflicts",
    "dependencies",
    "enforcement",
    "verification",
    "last_reviewed",
}
CLASSIFICATIONS = {"official", "community-guideline", "team-convention"}
REQUIREMENTS = {"required", "recommended", "optional"}


def validate_standard(provider):
    errors = []
    data = provider.payload
    missing = sorted(REQUIRED_METADATA - set(data))
    if missing:
        errors.append("missing metadata: " + ", ".join(missing))
    classification = data.get("classification")
    if not isinstance(classification, str) or classification not in CLASSIFICATIONS:
        errors.append("classification must be official, community-guideline, or team-convention")
    requirement = data.get("requirement")
    if not isinstance(requirement, str) or requirement not in REQUIREMENTS:
        errors.append("requirement must be required, recommended, or optional")
    if not isinstance(data.get("source"), dict) or not data.get("source"):
        errors.append("source must identify a reference")
    elif isinstance(classification, str) and classification in {"official", "community-guideline"}:
        source = data["source"]
        if not isinstance(source.get("url"), str) or not source["url"].startswith(
            ("https://", "http://")
        ):
            errors.append("official/community standards require a source URL")
        if not (data.get("version") or data.get("edition")):
            errors.append("official/community standards require a version or edition")
    if not isinstance(data.get("scope"), list) or not data.get("scope"):
        errors.append("scope must be a non-empty list")
    elif not all(isinstance(item, str) and item for item in data["scope"]):
        errors.append("scope entries must be strings")
    for field in ("conflicts", "dependencies"):
        if not isinstance(data.get(field), list) or not all(
            isinstance(item, str) and item for item in data[field]
        ):
            errors.append("%s must be a list of IDs" % field)
    for field in ("enforcement", "verification"):
        if not isinstance(data.get(field), dict):
            errors.append("%s must be an object" % field)
    try:
        date.fromisoformat(data.get("last_reviewed", ""))
    except (TypeError, ValueError):
        errors.append("last_reviewed must be an ISO date")
    return errors


def resolve_standards(root, registry, explicit_ids=None):
    """Return all applicable standards and reasons; conflicting standards are not silently picked."""
    explicit_ids = set(explicit_ids or [])
    selected = []
    candidates = []
    errors = []
    for provider in registry.list("standards"):
        metadata_errors = validate_standard(provider)
        if metadata_errors:
            errors.append("%s: %s" % (provider.id, "; ".join(metadata_errors)))
            continue
        matched = []
        for rule in provider.matches:
            marker = root / rule["path"]
            try:
                marker.resolve().relative_to(root.resolve())
            except (OSError, ValueError):
                continue
            if not marker.is_file():
                continue
            contains = rule.get("contains")
            if contains is not None:
                try:
                    with marker.open("rb") as source:
                        content = source.read(1024 * 1024).decode("utf-8", errors="replace")
                    if contains not in content:
                        continue
                except OSError:
                    continue
            matched.append(str(marker))
        candidates.append(
            {
                "id": provider.id,
                "requirement": provider.payload["requirement"],
                "classification": provider.payload["classification"],
                "evidence": matched,
                "applicability_status": "applicable"
                if matched or provider.id in explicit_ids
                else "not-applicable",
                "reason": "explicitly requested"
                if provider.id in explicit_ids
                else (
                    "existing applicability evidence" if matched else "no applicability evidence"
                ),
            }
        )
        if provider.id in explicit_ids or matched:
            selected.append(provider)
    unknown = explicit_ids - {provider.id for provider in registry.list("standards")}
    if unknown:
        errors.append("Unknown standards: " + ", ".join(sorted(unknown)))
    selected_ids = {provider.id for provider in selected}
    for provider in selected:
        collisions = sorted(set(provider.payload.get("conflicts", [])) & selected_ids)
        missing = sorted(set(provider.payload.get("dependencies", [])) - selected_ids)
        if collisions:
            errors.append("%s conflicts with %s" % (provider.id, ", ".join(collisions)))
        if missing:
            errors.append("%s depends on %s" % (provider.id, ", ".join(missing)))
    return {
        "status": "conflict" if errors else ("resolved" if selected else "no-applicable-standards"),
        "selected": [provider.id for provider in selected],
        "candidates": candidates,
        "errors": errors,
    }
