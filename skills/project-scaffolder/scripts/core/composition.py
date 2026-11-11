"""Compose selected declarative providers into a validated, write-ready plan."""

import json
import re
from dataclasses import replace
from pathlib import Path

from contracts.models import CompositionPlan, DirectorySpec, FileSpec, VerificationCheck


def apply_toolchain_versions(providers, version_specs):
    """Add user-pinned version files from declared toolchain generation rules."""
    by_id = {provider.id: provider for provider in providers}
    updates = {}
    for spec in version_specs:
        if "=" not in spec:
            raise ValueError("Version must use provider-id=version syntax")
        provider_id, version = spec.split("=", 1)
        provider = by_id.get(provider_id)
        if provider is None:
            raise ValueError("Version target provider is not selected: %s" % provider_id)
        if provider.kind != "toolchain":
            raise ValueError("Version target must be a toolchain provider: %s" % provider_id)
        generation = provider.payload.get("generation")
        if not generation:
            raise ValueError("Provider does not declare a version file generator: %s" % provider_id)
        if provider_id in updates:
            raise ValueError("Multiple version values were supplied for %s" % provider_id)
        if not re.fullmatch(generation["validation_pattern"], version):
            raise ValueError("Version value is not accepted by provider %s" % provider_id)
        payload = dict(provider.payload)
        files = list(payload.get("files", []))
        files.append(
            {
                "path": generation["path"],
                "content": generation["content_template"].replace("{version}", version),
                "description": "User-selected %s version pin" % payload.get("runtime", "toolchain"),
            }
        )
        payload["files"] = files
        updates[provider_id] = replace(provider, payload=payload)
    return [updates.get(provider.id, provider) for provider in providers]


def apply_dependency_spec(providers, dependency_spec):
    """Render a non-empty, explicitly supplied dependency spec through provider metadata.

    Lockfiles are intentionally not emitted here. The selected native manager must
    resolve and create them after the user reviews and confirms the plan.
    """
    if not isinstance(dependency_spec, dict):
        raise ValueError("Dependency specification must be a JSON object")
    updates = {}
    candidates = [
        provider
        for provider in providers
        if provider.kind == "package_manager" and provider.payload.get("manifest_generation")
    ]
    if len(candidates) != 1:
        raise ValueError(
            "Select exactly one package manager provider that declares manifest generation"
        )

    provider = candidates[0]
    generation = provider.payload["manifest_generation"]
    dependencies = dependency_spec.get("dependencies")
    if not isinstance(dependencies, dict) or not dependencies:
        raise ValueError("Dependency specification must include at least one dependency")
    dev_dependencies = dependency_spec.get("development_dependencies", {})
    if not isinstance(dev_dependencies, dict):
        raise ValueError("development_dependencies must be an object")

    output = dict(generation.get("static_fields", {}))
    for input_field, output_field in (
        ("project_name", generation.get("project_name_field")),
        ("version", generation.get("version_field")),
        ("go_version", generation.get("go_version_field")),
        ("edition", generation.get("edition_field")),
    ):
        value = dependency_spec.get(input_field)
        if output_field:
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Dependency specification requires a non-empty %s" % input_field)
            output[output_field] = value.strip()

    groups = (
        (dependencies, generation.get("runtime_dependencies_field")),
        (dev_dependencies, generation.get("development_dependencies_field")),
    )
    assigned = False
    for entries, field in groups:
        if entries and not field:
            raise ValueError("Provider %s does not support this dependency group" % provider.id)
        if not entries:
            continue
        for name, version in entries.items():
            if (
                not isinstance(name, str)
                or not re.fullmatch(r"[A-Za-z0-9@][A-Za-z0-9._/@+-]{0,199}", name)
                or not isinstance(version, str)
                or not version.strip()
                or any(ord(char) < 32 for char in version)
            ):
                raise ValueError(
                    "Dependency names and version constraints must be non-empty safe strings"
                )
        output[field] = dict(sorted((name, version.strip()) for name, version in entries.items()))
        assigned = True
    if not assigned:
        raise ValueError("Dependency specification contains no dependencies for supported groups")

    payload = dict(provider.payload)
    files = list(payload.get("files", []))
    renderer = generation.get("renderer", "json")
    content = _render_dependency_manifest(
        renderer, output, generation, dependency_spec, provider.id
    )
    files.append(
        {
            "path": generation["path"],
            "content": content,
            "description": "Manifest rendered from the explicit dependency specification",
        }
    )
    payload["files"] = files
    updates[provider.id] = replace(provider, payload=payload)
    return [updates.get(item.id, item) for item in providers]


def _render_dependency_manifest(renderer, output, generation, dependency_spec, provider_id):
    if renderer == "json":
        return json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if renderer == "go-mod":
        module_path = output.get(generation.get("project_name_field", "module"), "")
        go_version = output.get(generation.get("go_version_field", "go"), "")
        dependencies = output.get(generation.get("runtime_dependencies_field", "require"), {})
        development = dependency_spec.get("development_dependencies", {})
        if not isinstance(module_path, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9.-]*(?:/[A-Za-z0-9._~-]+)+", module_path
        ):
            raise ValueError("Go module path must be an explicit safe module path")
        if not isinstance(go_version, str) or not re.fullmatch(
            r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", go_version
        ):
            raise ValueError("Go manifest generation requires an explicit go_version")
        if development:
            raise ValueError("Go Modules does not declare a separate development dependency group")
        lines = ["module " + module_path, "", "go " + go_version]
        if dependencies:
            lines.extend(["", "require ("])
            for name, version in sorted(dependencies.items()):
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*(?:/[A-Za-z0-9._~+-]+)+", name):
                    raise ValueError("Go dependency must use a safe module path")
                if not re.fullmatch(r"v[0-9][A-Za-z0-9.+-]*", version):
                    raise ValueError("Go dependency version must be an explicit v-prefixed version")
                lines.append("\t%s %s" % (name, version))
            lines.append(")")
        return "\n".join(lines) + "\n"
    if renderer in {"cargo-toml", "uv-toml"}:
        return _render_toml_manifest(renderer, output, generation, dependency_spec, provider_id)
    raise ValueError(
        "Provider %s declares unsupported manifest renderer: %s" % (provider_id, renderer)
    )


def _render_toml_manifest(renderer, output, generation, dependency_spec, provider_id):
    def quote(value):
        return json.dumps(value, ensure_ascii=False)
    project_name = output.get(generation.get("project_name_field", "name"), "")
    version = output.get(generation.get("version_field", "version"), "")
    dependencies = output.get(generation.get("runtime_dependencies_field", "dependencies"), {})
    development = output.get(
        generation.get("development_dependencies_field", "dev-dependencies"), {}
    )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", project_name):
        raise ValueError("Project name must be an explicit safe package name")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+!-]{0,99}", version):
        raise ValueError("Project version must be an explicit safe version string")
    if renderer == "cargo-toml":
        edition = output.get(generation.get("edition_field", "edition"), "")
        if edition not in {"2015", "2018", "2021", "2024"}:
            raise ValueError("Cargo manifest generation requires an explicit supported edition")
        sections = [
            "[package]",
            "name = " + quote(project_name),
            "version = " + quote(version),
            "edition = " + quote(edition),
        ]
        for title, entries in (("dependencies", dependencies), ("dev-dependencies", development)):
            if entries:
                sections.extend(["", "[" + title + "]"])
                sections.extend(
                    "%s = %s" % (quote(name), quote(constraint))
                    for name, constraint in sorted(entries.items())
                )
        return "\n".join(sections) + "\n"
    if renderer == "uv-toml":
        lines = [
            "[project]",
            "name = " + quote(project_name),
            "version = " + quote(version),
            "dependencies = [",
        ]
        lines.extend(
            "  " + quote(name + constraint) + ","
            for name, constraint in sorted(dependencies.items())
        )
        lines.append("]")
        if development:
            lines.extend(["", "[dependency-groups]", "dev = ["])
            lines.extend(
                "  " + quote(name + constraint) + ","
                for name, constraint in sorted(development.items())
            )
            lines.append("]")
        return "\n".join(lines) + "\n"
    raise ValueError("Provider %s declares unsupported TOML renderer: %s" % (provider_id, renderer))


def compose_plan(context, providers, registry=None):
    """Combine provider payload contributions and reject ambiguous ownership."""
    plan = CompositionPlan(context=context)
    architectures = [provider for provider in providers if provider.kind == "architecture"]
    templates = [provider for provider in providers if provider.kind == "template"]
    if registry is not None:
        plan.conflicts.extend(registry.validate_selection([provider.id for provider in providers]))
    for architecture in architectures:
        supported = set(architecture.payload.get("supported_template_capabilities", []))
        for template in templates:
            declared = template.payload.get("template_capabilities")
            if declared is None:
                plan.unresolved.append(
                    "Architecture/template compatibility is not declared for %s and %s"
                    % (architecture.id, template.id)
                )
            elif not supported.intersection(declared):
                plan.conflicts.append(
                    "Template %s does not support architecture %s" % (template.id, architecture.id)
                )
    by_path = {}
    by_path_owners = {}
    conflicted_paths = {}
    for provider in providers:
        plan.selected_provider_ids.append(provider.id)
        payload = provider.payload
        directory_paths = {item.rel_path for item in plan.directories}
        for item in payload.get("directories", []):
            if item["path"] not in directory_paths:
                plan.directories.append(
                    DirectorySpec(
                        rel_path=item["path"],
                        reason=item.get("reason", ""),
                        required=item.get("required", True),
                    )
                )
                directory_paths.add(item["path"])
        for item in payload.get("files", []):
            spec = FileSpec(
                rel_path=item["path"],
                content=item["content"],
                description=item.get("description", ""),
            )
            if spec.rel_path in conflicted_paths:
                conflicted_paths[spec.rel_path].add(provider.id)
                continue
            previous = by_path.get(spec.rel_path)
            if previous is not None and previous.content != spec.content:
                owners = set(by_path_owners.get(spec.rel_path, set()))
                owners.add(provider.id)
                conflicted_paths[spec.rel_path] = owners
                by_path.pop(spec.rel_path, None)
            elif previous is not None:
                # Identical shared templates (such as a common logbook guide)
                # can be contributed by multiple legacy profiles safely.
                by_path_owners[spec.rel_path].add(provider.id)
                continue
            else:
                by_path[spec.rel_path] = spec
                by_path_owners[spec.rel_path] = {provider.id}

    for rel_path, owners in sorted(conflicted_paths.items()):
        plan.conflicts.append(
            "Conflicting file contributions for %s (%s)"
            % (rel_path, ", ".join(sorted(owners)))
        )
        for item in payload.get("verification_checks", []):
            plan.verification_checks.append(
                VerificationCheck(
                    id=item["id"],
                    capability=provider.id,
                    command=item.get("command", []),
                    required=item.get("required", True),
                    expected_evidence=item.get("expected_evidence", {}),
                )
            )

    plan.files = list(by_path.values())
    file_paths = {Path(item.rel_path) for item in plan.files}
    directory_paths = {Path(item.rel_path) for item in plan.directories}
    for file_path in file_paths:
        if file_path in directory_paths:
            plan.conflicts.append("Path is both a file and directory: %s" % file_path)
        parent = file_path.parent
        while str(parent) not in (".", ""):
            if parent in file_paths:
                plan.conflicts.append(
                    "File path %s is nested beneath planned file %s" % (file_path, parent)
                )
                break
            parent = parent.parent
    plan.requires_confirmation = bool(plan.files or plan.directories)
    return plan
