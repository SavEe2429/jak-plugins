#!/usr/bin/env python3
"""
profile_adapter.py - Generic Profile-Driven StackAdapter Implementation
Part of the 'project-scaffolder' skill.

Converts declarative JSON/YAML Profile definitions into full-featured
StackAdapter instances compliant with the Adapter Contract.
Enables new stacks to be added purely by creating a Profile JSON without any code edits.
"""

import os
import shlex
from pathlib import Path
from typing import Any, Dict, List, Tuple

from contracts.models import ProviderDescriptor
from core.contract import FileSpec, StackAdapter


class ProfileAdapter(StackAdapter):
    """Adapter driven strictly by profile configuration data."""

    def __init__(
        self,
        profile_data: Dict[str, Any],
        profile_path: Path = None,
        verification_provider: ProviderDescriptor = None,
    ):
        self._data = profile_data
        self._profile_path = profile_path
        self.verification_provider = verification_provider

    def _project_policy(self) -> Dict[str, Any]:
        if self.verification_provider is not None:
            return self.verification_provider.payload.get("project_policy", {})
        return self._data

    def _verification_checks(self) -> List[Dict[str, Any]]:
        if self.verification_provider is not None:
            return self.verification_provider.payload.get("checks", [])
        checks = []
        for index, command in enumerate(self.get_test_commands()):
            checks.append(
                {
                    "id": "legacy-test-%d" % (index + 1),
                    "kind": "test",
                    "command": shlex.split(command, posix=os.name != "nt"),
                    "required": True,
                    "expected_evidence": {"requires_assertions": True},
                }
            )
        for index, command in enumerate(self.get_build_commands()):
            checks.append(
                {
                    "id": "legacy-build-%d" % (index + 1),
                    "kind": "build",
                    "command": shlex.split(command, posix=os.name != "nt"),
                    "required": True,
                    "expected_evidence": {},
                }
            )
        return checks

    @property
    def domain(self) -> str:
        return self._data.get("domain", "generic")

    @property
    def stack_id(self) -> str:
        return self._data.get("stack", "generic")

    @property
    def display_name(self) -> str:
        return self._data.get("name", f"{self.domain.capitalize()} - {self.stack_id}")

    @property
    def markers(self) -> List[str]:
        return self._data.get("markers", [])

    def matches_workspace(self, root: Path) -> bool:
        """Returns true only when evidence reaches this profile's threshold."""
        return self.match_evidence(root)["score"] >= int(self._data.get("match_threshold", 2))

    def match_evidence(self, root: Path) -> Dict[str, Any]:
        """Score marker evidence; generic filenames are deliberately weak."""
        if not self.markers:
            return {"score": 0, "matched": []}

        weights = self._data.get("marker_weights", {})
        matched = []
        for marker in self.markers:
            weight = int(weights.get(marker, 0))
            found = False
            # Check content matching marker: "file.ext:content_substring"
            if ":" in marker:
                filename, search_term = marker.split(":", 1)
                file_path = root / filename
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore").lower()
                        if search_term.lower() in content:
                            found = True
                            weight = weight or 3
                    except (OSError, UnicodeError):
                        continue
            elif "*" in marker:
                found = any(root.glob(marker))
                if found:
                    weight = weight or (
                        2 if Path(marker).suffix not in {".py", ".js", ".ts"} else 1
                    )
            else:
                found = (root / marker).exists()
                if found:
                    generic_names = {
                        "main.py",
                        "app.py",
                        "index.js",
                        "index.ts",
                        "src",
                        "assets",
                        "notebooks",
                        "tests",
                        "test",
                        "include",
                        "lib",
                        "docs",
                        "config",
                    }
                    weight = weight or (1 if Path(marker).name.lower() in generic_names else 2)
            if found:
                matched.append({"marker": marker, "weight": weight})

        return {"score": sum(item["weight"] for item in matched), "matched": matched}

    def get_architecture_options(self) -> Dict[str, List[str]]:
        """Return profile-supported architecture directory compositions."""
        return self._data.get("architecture_layouts", {})

    def to_template_provider(
        self,
        project_name: str,
        topology: str = "unknown",
        architecture: str = None,
        include_ci: bool = True,
        include_runbook: bool = True,
    ) -> ProviderDescriptor:
        """Expose a legacy profile as a temporary template provider for the new composer."""
        files = []
        for spec in (
            self.get_entry_points(project_name, architecture)
            + self.get_smoke_tests(project_name, architecture)
            + self.get_supporting_files(topology, architecture, include_runbook)
        ):
            files.append(
                {"path": spec.rel_path, "content": spec.content, "description": spec.description}
            )
        workflow = self.get_ci_workflow(project_name) if include_ci else ""
        if workflow:
            files.append(
                {
                    "path": ".github/workflows/ci.yml",
                    "content": workflow,
                    "description": "Legacy profile CI workflow",
                }
            )
        checks = self._verification_checks()
        matches = []
        for marker in self.markers:
            if ":" in marker:
                path, contains = marker.split(":", 1)
                matches.append(
                    {"path": path, "contains": contains, "weight": 1, "quality": "declared"}
                )
            else:
                matches.append({"path": marker, "weight": 1, "quality": "declared"})
        return ProviderDescriptor(
            id="legacy-profile.%s.%s" % (self.domain.lower(), self.stack_id.lower()),
            kind="template",
            schema_version=1,
            capabilities=["legacy-profile-compatibility"],
            matches=matches,
            payload={
                "directories": [
                    {"path": path} for path in self.get_directories(topology, architecture)
                ],
                "files": files,
                "verification_checks": checks,
            },
            source=str(self._profile_path or "legacy-profile"),
        )

    def to_verification_provider(self) -> ProviderDescriptor:
        """Return profile policy/check data through the versioned verification contract."""
        if self.verification_provider is not None:
            return self.verification_provider
        return ProviderDescriptor(
            id="verification.profile.%s.%s" % (self.domain.lower(), self.stack_id.lower()),
            kind="verification",
            schema_version=1,
            capabilities=["verification-checks", "project-readiness-policy"],
            payload={
                "checks": self._verification_checks(),
                "project_policy": {
                    "config_manifests": self.get_config_manifests(),
                    "module_boundary_patterns": self._data.get("module_boundary_patterns", []),
                    "mandatory_categories": self.get_mandatory_categories(),
                    "na_categories": self.get_na_categories(),
                },
            },
            source=str(self._profile_path or "legacy-profile"),
        )

    def get_directories(self, topology: str = "unknown", architecture: str = None) -> List[str]:
        if architecture:
            layouts = self.get_architecture_options()
            if architecture not in layouts:
                raise ValueError(
                    f"Architecture '{architecture}' is not supported by profile '{self.stack_id}'."
                )
            common = self._data.get("architecture_common_directories", [])
            return list(dict.fromkeys(common + layouts[architecture]))
        # Support topology-specific overrides if defined in profile
        topo_dirs = self._data.get("topology_directories", {}).get(topology)
        if topo_dirs:
            return topo_dirs
        return self._data.get("directories", [])

    def get_gitattributes_lfs_patterns(self) -> List[str]:
        return self._data.get("lfs_patterns", [])

    def get_entry_points(self, project_name: str, architecture: str = None) -> List[FileSpec]:
        specs = []
        raw_items = self._data.get("architecture_entry_points", {}).get(
            architecture, self._data.get("entry_points", [])
        )
        for item in raw_items:
            path_str = item.get("path", "").replace("{project_name}", project_name)
            template = item.get("template", "").replace("{project_name}", project_name)
            desc = item.get("description", "Entry point source file")
            if (
                Path(path_str).as_posix() == "AGENTS.md"
                and "logbook" in self.get_directories(architecture=architecture)
                and "logbook/README.md" not in template
            ):
                template += (
                    "\n## Session logbook\n\n"
                    "After technical work, append an honest summary to `logbook/current.md`. "
                    "Read `logbook/README.md` first and follow its append-only and archive rules.\n"
                )
            if path_str and template:
                specs.append(FileSpec(rel_path=path_str, content=template, description=desc))
        return specs

    def get_smoke_tests(self, project_name: str, architecture: str = None) -> List[FileSpec]:
        specs = []
        raw_items = self._data.get("architecture_smoke_tests", {}).get(
            architecture, self._data.get("smoke_tests", [])
        )
        for item in raw_items:
            path_str = item.get("path", "").replace("{project_name}", project_name)
            template = item.get("template", "").replace("{project_name}", project_name)
            desc = item.get("description", "Passing smoke test fixture")
            if path_str and template:
                specs.append(FileSpec(rel_path=path_str, content=template, description=desc))
        return specs

    def get_supporting_files(
        self, topology: str = "unknown", architecture: str = None, include_runbook: bool = True
    ) -> List[FileSpec]:
        """Add a self-describing append-only logbook wherever a profile declares one."""
        if "logbook" not in self.get_directories(topology, architecture):
            return []
        readme = """# Logbook Guide

Use `current.md` as the active project-session log. Append each new entry at the end; never rewrite or remove earlier entries.

Each entry records:

- Timestamp and author.
- Scope and actions taken.
- Test or verification method, including when none was run.
- Outcome, including failures and items that remain unverified.

When an append would take `current.md` over 500 lines, move the existing file to `YYYY-MM-DD_logbook.md` (use a timestamp suffix if another archive already exists for that date), create a fresh `current.md` with these operating rules, then append the new entry. Treat rotated archives as immutable. Never invent test results.
"""
        current = """# Project Logbook

This is the active append-only project session log. Follow [README.md](README.md).

## Operating Rules

- Append every technical session to the bottom; do not overwrite or delete prior entries.
- Record timestamp, author, scope/actions, test or verification method, and outcome.
- State explicitly when tests or verification were not run.
- Before an append would exceed 500 lines, rotate this file to `YYYY-MM-DD_logbook.md`; add a timestamp suffix if needed to avoid a name collision.
- Keep rotated archives immutable.
- Never fabricate test execution history.
"""
        files = [
            FileSpec("logbook/README.md", readme, "Logbook usage and archive policy"),
            FileSpec("logbook/current.md", current, "Active append-only project logbook"),
        ]
        has_agent_runbook = any(
            Path(spec.rel_path).as_posix() == "AGENTS.md"
            for spec in self.get_entry_points("", architecture)
        )
        if include_runbook and not has_agent_runbook:
            files.append(
                FileSpec(
                    "AGENTS.md",
                    "# Project Agent Instructions\n\n"
                    "After technical work, append an honest summary to `logbook/current.md`. "
                    "Read `logbook/README.md` and follow its append-only and archive rules.\n",
                    "Project instructions linking agents to the session logbook",
                )
            )
        return files

    def get_ci_workflow(self, project_name: str) -> str:
        ci_raw = self._data.get("ci_workflow")
        if ci_raw:
            return ci_raw.replace("{project_name}", project_name)

        return ""

    def get_test_commands(self) -> List[str]:
        if self.verification_provider is not None:
            return [
                shlex.join(item["command"])
                for item in self._verification_checks()
                if item.get("kind") == "test"
            ]
        return self._data.get("test_commands", [])

    def get_build_commands(self) -> List[str]:
        if self.verification_provider is not None:
            return [
                shlex.join(item["command"])
                for item in self._verification_checks()
                if item.get("kind") == "build"
            ]
        cmds = self._data.get("build_commands", [])
        if not cmds and "build_command" in self._data:
            single = self._data.get("build_command")
            if single:
                cmds = [single]
        return cmds

    def get_config_manifests(self) -> List[str]:
        return self._project_policy().get("config_manifests", [])

    def get_mandatory_categories(self) -> List[int]:
        # Default all 20 unless exempted
        return self._project_policy().get("mandatory_categories", list(range(1, 21)))

    def get_na_categories(self) -> List[int]:
        return self._project_policy().get("na_categories", [])

    def check_config_manifest(self, root: Path) -> Tuple[bool, str]:
        manifests = self.get_config_manifests()
        if not manifests:
            # Fallback check on markers
            manifests = [m for m in self.markers if ":" not in m]

        found = []
        for m in manifests:
            if "*" in m:
                if any(root.glob(m)):
                    found.append(m)
            elif (root / m).exists():
                found.append(m)

        if found:
            return True, f"Configuration manifest committed: {', '.join(found)}"
        return (
            False,
            f"Missing required configuration manifest (expected one of: {', '.join(manifests)})",
        )

    def check_module_boundaries(self, root: Path, topology: str) -> Tuple[bool, str]:
        patterns = self._project_policy().get("module_boundary_patterns", [])
        for pat in patterns:
            if ":" in pat:
                fname, search_term = pat.split(":", 1)
                fpath = root / fname
                if fpath.exists():
                    try:
                        if (
                            search_term.lower()
                            in fpath.read_text(encoding="utf-8", errors="ignore").lower()
                        ):
                            return True, f"Module boundary verified in {fname} ('{search_term}')"
                    except (OSError, UnicodeError):
                        continue
            elif "*" in pat:
                matches = list(root.glob(pat))
                if matches:
                    if all(match.is_dir() for match in matches):
                        kind_label = "directories"
                    elif all(match.is_file() for match in matches):
                        kind_label = "files"
                    else:
                        kind_label = "entries"
                    return True, f"Found {len(matches)} module boundary {kind_label} matching {pat}"
            elif (root / pat).exists():
                return True, f"Module boundary manifest found: {pat}"

        return False, f"No explicit module-boundary evidence found for topology '{topology}'"
