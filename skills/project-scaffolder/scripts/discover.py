#!/usr/bin/env python3
"""
discover.py - Generic 3-Axis Project Discovery Engine
Part of the 'project-scaffolder' skill.

Rule 1 & Rule 2 Compliance:
- Fully domain-agnostic and stack-agnostic.
- Queries registered adapters dynamically from profiles.
- Zero hardcoded tech stack branches in stack resolution.
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent directory for imports
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.contract import StackAdapter
from core.io_utils import inspect_conflicts
from core.registry import AdapterRegistry

# Declarative topology detection rules for domain-agnostic inspection
DEFAULT_TOPOLOGY_RULES: List[Dict[str, Any]] = [
    {
        "topology": "monorepo",
        "any_markers": ["pnpm-workspace.yaml", "turbo.json", "lerna.json"],
        "content_patterns": [
            {"files": ["Cargo.toml", "package.json"], "patterns": ["[workspace]", "workspaces"]}
        ],
    },
    {
        "topology": "microservices",
        "all_markers": ["docker-compose.yml"],
        "min_globs": [("*/Dockerfile", 2)],
    },
    {
        "topology": "modular_monolith",
        "any_min_globs": [("**/*.asmdef", 2), ("components/*/CMakeLists.txt", 2)],
    },
]


def detect_topology(root: Path, rules: Optional[List[Dict[str, Any]]] = None) -> str:
    """Detect topology signals dynamically using declarative rules; return unknown when evidence is weak."""
    active_rules = rules if rules is not None else DEFAULT_TOPOLOGY_RULES
    for rule in active_rules:
        topo = rule.get("topology", "unknown")
        # Check any_markers
        if any(next(root.glob(marker), None) is not None for marker in rule.get("any_markers", [])):
            return topo
        # Check all_markers and min_globs
        if "all_markers" in rule:
            if all((root / m).exists() for m in rule["all_markers"]):
                if all(
                    len(list(root.glob(pat))) >= min_c for pat, min_c in rule.get("min_globs", [])
                ):
                    return topo
        # Check any_min_globs
        if any(len(list(root.glob(pat))) >= min_c for pat, min_c in rule.get("any_min_globs", [])):
            return topo
        # Check content patterns
        for cp in rule.get("content_patterns", []):
            target_files = cp.get("files", [])
            patterns = cp.get("patterns", [])
            for p in root.glob("*"):
                if p.is_file() and p.name in target_files:
                    try:
                        txt = p.read_text(encoding="utf-8", errors="ignore")
                        if any(pattern in txt for pattern in patterns):
                            return topo
                    except (OSError, UnicodeError):
                        continue

    return "unknown"


def detect_3axis(
    root: Path, registry: AdapterRegistry = None
) -> Tuple[str, str, str, StackAdapter]:
    """
    Detects Domain, Tech Stack, and Topology.
    Queries the registry of StackAdapters dynamically.
    Returns: (domain, stack_id, topology, matched_adapter)
    """
    if registry is None:
        profiles_dir = SKILL_ROOT / "profiles"
        registry = AdapterRegistry(profiles_dir=profiles_dir)

    adapter = registry.match_workspace(root)
    topology = detect_topology(root)

    if adapter:
        evidence = (
            adapter.match_evidence(root)
            if hasattr(adapter, "match_evidence")
            else {"score": None, "matched": []}
        )
        adapter._discovery_state = "matched"
        adapter._discovery_candidates = registry.last_match_candidates
        adapter._discovery_evidence = evidence
        adapter._profile_load_errors = registry.load_errors
        return adapter.domain, adapter.stack_id, topology, adapter

    # Generic fallback adapter
    from adapters.profile_adapter import ProfileAdapter

    fallback_adapter = ProfileAdapter(
        {
            "domain": "generic",
            "stack": "generic",
            "name": "Unknown Project (requirements discovery needed)",
            "directories": [],
            "mandatory_categories": [],
            "na_categories": [],
        }
    )
    fallback_adapter._discovery_state = "ambiguous" if registry.last_match_candidates else "unknown"
    fallback_adapter._discovery_candidates = registry.last_match_candidates
    fallback_adapter._profile_load_errors = registry.load_errors
    return "generic", "generic", topology, fallback_adapter


def discover_project_units(
    root: Path, registry: AdapterRegistry = None, max_depth: int = 4, max_directories: int = 2000
) -> List[Dict[str, Any]]:
    """Find nested project roots from registered profile evidence, without guessing layouts."""
    root = root.resolve()
    registry = registry or AdapterRegistry(profiles_dir=SKILL_ROOT / "profiles")
    ignored = {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "vendor",
        "Library",
        "Temp",
        "obj",
        "bin",
        "target",
        "Build",
        "dist",
        "__pycache__",
    }
    queue = [(root, 0)]
    visited = 0
    units = []
    seen = set()
    while queue and visited < max_directories:
        current, depth = queue.pop(0)
        visited += 1
        adapter = registry.match_workspace(current)
        candidates = list(registry.last_match_candidates or [])
        state = "matched" if adapter else ("ambiguous" if candidates else "unknown")
        if adapter or candidates:
            key = str(current)
            if key not in seen:
                seen.add(key)
                evidence = adapter.match_evidence(current) if adapter else {}
                units.append(
                    {
                        "path": "." if current == root else current.relative_to(root).as_posix(),
                        "status": state,
                        "domain": adapter.domain if adapter else None,
                        "stack": adapter.stack_id if adapter else None,
                        "evidence": evidence.get("matched", []),
                        "candidates": candidates if not adapter else [],
                    }
                )
        if depth >= max_depth:
            continue
        try:
            children = sorted(
                (
                    entry
                    for entry in current.iterdir()
                    if entry.is_dir() and not entry.is_symlink() and entry.name not in ignored
                ),
                key=lambda entry: entry.name.casefold(),
            )
        except OSError:
            continue
        queue.extend((child, depth + 1) for child in children)
    return {"units": units, "directories_scanned": visited, "truncated": bool(queue)}


def inspect_existing_conflicts(target_path: Path, planned_files: list):
    """Bridge for backward compatibility."""
    return inspect_conflicts(target_path, planned_files)


def main():
    parser = argparse.ArgumentParser(description="3-axis project stack discovery engine.")
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Target project directory (default: current directory)",
    )
    args = parser.parse_args()
    root = Path(args.target).resolve()
    domain, stack, topology, adapter = detect_3axis(root)

    print("================================================================================")
    print("             3-AXIS PROJECT DISCOVERY (GENERIC ADAPTER ENGINE)                 ")
    print("================================================================================")
    print(f"Target Directory : {root}")
    print(f"Detected Domain  : {domain.upper()}")
    print(f"Detected Stack   : {stack.upper()} ({adapter.display_name})")
    print(f"Detected Topology: {topology.upper()}")
    state = getattr(adapter, "_discovery_state", "matched")
    if state != "matched":
        print(
            f"Discovery State  : {state.upper()} (no structure will be generated from a generic fallback)"
        )
        for candidate in getattr(adapter, "_discovery_candidates", [])[:5]:
            print(
                f"  Candidate: {candidate['domain']}/{candidate['stack']} score={candidate['score']} evidence={candidate['matched']}"
            )
        for error in getattr(adapter, "_profile_load_errors", []):
            print(f"  Profile Load Error: {error['path']}: {error['error']}")
    print("--------------------------------------------------------------------------------")


if __name__ == "__main__":
    main()
