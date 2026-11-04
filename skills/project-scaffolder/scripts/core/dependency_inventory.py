"""Small, bounded parsers for explicitly declared package lockfile formats."""

import json
import re
from pathlib import Path

MAX_LOCKFILE_BYTES = 10 * 1024 * 1024
MAX_PACKAGES = 5000


def inspect_lockfile_inventory(root: Path, provider):
    config = provider.payload.get("inventory_parser")
    if not config:
        return {
            "status": "not-supported",
            "packages": [],
            "limitation": "This provider has no reviewed lockfile inventory parser.",
        }
    relative_path = config["path"]
    path = root / relative_path
    if not path.is_file():
        return {"status": "not-available", "path": relative_path, "packages": []}
    try:
        resolved_root = root.resolve()
        resolved_path = path.resolve()
        resolved_path.relative_to(resolved_root)
        if path.stat().st_size > MAX_LOCKFILE_BYTES:
            return {
                "status": "size-limited",
                "path": relative_path,
                "packages": [],
                "limitation": "Lockfile exceeds the bounded inventory parser size.",
            }
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError):
        return {
            "status": "unavailable",
            "path": relative_path,
            "packages": [],
            "limitation": "Lockfile could not be safely read as an in-root UTF-8 file.",
        }

    try:
        if config["format"] == "toml-package-sections":
            packages = _parse_toml_sections(content)
        elif config["format"] == "unity-upm-lock-json":
            packages = _parse_unity_lock(content)
        elif config["format"] == "go-sum-lines":
            packages = _parse_go_sum(content)
        elif config["format"] == "pnpm-lock-v9-yaml":
            packages = _parse_pnpm_lock_v9(content)
        else:
            return {"status": "not-supported", "path": relative_path, "packages": []}
    except (ValueError, json.JSONDecodeError):
        return {
            "status": "parse-error",
            "path": relative_path,
            "packages": [],
            "limitation": "Lockfile does not match the provider-declared parser format.",
        }

    truncated = len(packages) > MAX_PACKAGES
    packages = packages[:MAX_PACKAGES]
    return {
        "status": "truncated" if truncated else "available",
        "path": relative_path,
        "package_count": len(packages),
        "packages": packages,
        "scope": config.get("scope", "resolved-lockfile-packages"),
        "limitation": config.get(
            "limitation",
            "Inventory names and versions only; this does not prove semantic consistency, vulnerability status, or license compliance.",
        ),
    }


def _parse_toml_sections(content):
    sections = re.split(r"(?m)^\[\[package\]\]\s*$", content)
    packages = []
    for section in sections[1:]:
        name = re.search(r'(?m)^name\s*=\s*"([^"\n]{1,300})"\s*$', section)
        version = re.search(r'(?m)^version\s*=\s*"([^"\n]{1,100})"\s*$', section)
        if name and version:
            packages.append(
                {"name": name.group(1), "version": version.group(1), "dependency_scope": "resolved"}
            )
    return sorted(packages, key=lambda item: (item["name"].casefold(), item["version"]))


def _parse_unity_lock(content):
    document = json.loads(content)
    dependencies = document.get("dependencies")
    if not isinstance(dependencies, dict):
        raise ValueError("Unity lock dependencies must be an object")
    packages = []
    for name, item in dependencies.items():
        if not isinstance(name, str) or not isinstance(item, dict):
            continue
        version = item.get("version")
        depth = item.get("depth")
        if not isinstance(version, str) or not isinstance(depth, int):
            continue
        packages.append(
            {
                "name": name[:300],
                "version": version[:100],
                "dependency_scope": "direct" if depth == 0 else "transitive",
            }
        )
    return sorted(packages, key=lambda item: (item["name"].casefold(), item["version"]))


def _parse_go_sum(content):
    packages = {}
    for line in content.splitlines():
        fields = line.split()
        if len(fields) != 3 or fields[1].endswith("/go.mod"):
            continue
        module, version, checksum = fields
        version = version.removesuffix("/go.mod")
        if not re.fullmatch(r"v[0-9][A-Za-z0-9.+-]*", version):
            continue
        module = re.sub(r"!([a-z])", lambda match: match.group(1).upper(), module)
        packages[(module, version)] = {
            "name": module,
            "version": version,
            "dependency_scope": "resolved-checksum",
        }
    return sorted(packages.values(), key=lambda item: (item["name"].casefold(), item["version"]))


def _parse_pnpm_lock_v9(content):
    if not re.search(r"(?m)^lockfileVersion:\s*['\"]?9(?:\.0)?['\"]?\s*$", content):
        raise ValueError("Only pnpm lockfile version 9 is supported")
    packages = {}
    section = None
    for line in content.splitlines():
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1]
            continue
        if (
            section not in {"packages", "snapshots"}
            or not line.startswith("  ")
            or line.startswith("    ")
        ):
            continue
        raw_key = line[2:].strip()
        if not raw_key.endswith(":"):
            continue
        key = raw_key[:-1].strip()
        if key.startswith("'") and key.endswith("'"):
            key = key[1:-1].replace("''", "'")
        elif key.startswith('"') and key.endswith('"'):
            try:
                key = json.loads(key)
            except json.JSONDecodeError:
                continue
        if key.startswith("/"):
            key = key[1:]
        key = key.split("(", 1)[0]
        if "@" not in key:
            continue
        name, version = key.rsplit("@", 1)
        if not name or not re.fullmatch(r"[0-9][A-Za-z0-9.+-]*", version):
            continue
        packages[(name, version)] = {
            "name": name,
            "version": version,
            "dependency_scope": "resolved",
        }
    return sorted(packages.values(), key=lambda item: (item["name"].casefold(), item["version"]))
