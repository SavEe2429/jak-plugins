#!/usr/bin/env python3
"""
registry.py - Dynamic Adapter and Profile Registry
Part of the 'project-scaffolder' skill.

Features:
- Dynamically discovers all profiles in profiles/ without hardcoded lists.
- Supports external custom Python adapters implementing StackAdapter.
- Selects a unique evidence-backed match and preserves ambiguous candidates.
- Satisfies Open-Closed Principle (OCP): new stacks require zero changes here.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from adapters.profile_adapter import ProfileAdapter
from contracts.validation import (
    provider_descriptor,
    validate_legacy_profile,
    validate_provider_record,
)

from core.contract import StackAdapter


class AdapterRegistry:
    """Central registry of all available tech stack adapters."""

    def __init__(self, profiles_dir: Optional[Path] = None):
        self._adapters: Dict[Tuple[str, str], StackAdapter] = {}
        self.last_match_candidates = []
        self.load_errors = []
        if profiles_dir and profiles_dir.exists():
            self.load_profiles_from_dir(profiles_dir)

    def register(self, adapter: StackAdapter):
        """Registers an adapter instance."""
        key = (adapter.domain.lower(), adapter.stack_id.lower())
        self._adapters[key] = adapter

    def load_profiles_from_dir(self, profiles_dir: Path):
        """Scans profiles directory recursively and registers ProfileAdapters."""
        verification_by_profile = {}
        verification_dir = profiles_dir.parent / "providers" / "verification"
        if verification_dir.exists():
            for provider_file in verification_dir.rglob("*.json"):
                try:
                    data = json.loads(provider_file.read_text(encoding="utf-8"))
                    errors = validate_provider_record(data, str(provider_file))
                    if errors:
                        raise ValueError("Invalid verification provider: " + "; ".join(errors))
                    provider = provider_descriptor(data, str(provider_file))
                    if provider.kind != "verification":
                        raise ValueError("Provider kind must be verification")
                    prefix = "verification.profile."
                    if not provider.id.startswith(prefix):
                        raise ValueError("Verification provider ID must start with %s" % prefix)
                    suffix = provider.id[len(prefix) :].replace(".", "/")
                    verification_by_profile[suffix] = provider
                except (OSError, ValueError) as exc:
                    self.load_errors.append({"path": str(provider_file), "error": str(exc)})
        for json_file in profiles_dir.rglob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                validation_errors = validate_legacy_profile(data)
                if validation_errors:
                    raise ValueError("Invalid legacy profile: " + "; ".join(validation_errors))
                relative_profile = json_file.relative_to(profiles_dir).with_suffix("").as_posix()
                verification_provider = verification_by_profile.get(relative_profile)
                adapter = ProfileAdapter(
                    data, profile_path=json_file, verification_provider=verification_provider
                )
                self.register(adapter)
            except (OSError, ValueError) as exc:
                self.load_errors.append({"path": str(json_file), "error": str(exc)})

    def get(self, domain: str, stack: str) -> Optional[StackAdapter]:
        """Retrieves adapter by domain and stack ID."""
        key = (domain.lower(), stack.lower())
        if key in self._adapters:
            return self._adapters[key]
        if domain.lower() in {"", "generic"}:
            matches = [
                adapter
                for (registered_domain, registered_stack), adapter in self._adapters.items()
                if registered_stack == stack.lower()
            ]
            return matches[0] if len(matches) == 1 else None
        return None

    def list_all(self) -> List[StackAdapter]:
        """Returns all registered adapters."""
        return list(self._adapters.values())

    def match_workspace(self, root: Path) -> Optional[StackAdapter]:
        """Select a unique best evidence match; ties require clarification."""
        scored = []
        for adapter in self._adapters.values():
            if hasattr(adapter, "match_evidence"):
                evidence = adapter.match_evidence(root)
            else:
                evidence = {"score": 2 if adapter.matches_workspace(root) else 0, "matched": []}
            threshold = int(getattr(adapter, "_data", {}).get("match_threshold", 2))
            if evidence["score"] >= threshold:
                scored.append((evidence["score"], adapter, evidence))

        scored.sort(key=lambda item: item[0], reverse=True)
        self.last_match_candidates = [
            {
                "domain": a.domain,
                "stack": a.stack_id,
                "name": a.display_name,
                "score": score,
                "matched": evidence["matched"],
            }
            for score, a, evidence in scored
        ]
        if not scored:
            return None
        if len(scored) > 1:
            return None
        return scored[0][1]
