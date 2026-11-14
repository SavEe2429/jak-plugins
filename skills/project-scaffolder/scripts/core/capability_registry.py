"""Versioned declarative capability provider registry."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from contracts.models import ProviderDescriptor
from contracts.validation import provider_descriptor, validate_provider_record


class CapabilityRegistry:
    """Loads only validated data providers; it never imports executable plugins."""

    def __init__(self):
        self._providers: Dict[str, ProviderDescriptor] = {}
        self.load_errors: List[Dict[str, str]] = []

    def register_record(self, data: dict, source: str = "") -> ProviderDescriptor:
        errors = validate_provider_record(data, source)
        if errors:
            raise ValueError("Invalid provider %s: %s" % (source or "<memory>", "; ".join(errors)))
        descriptor = provider_descriptor(data, source)
        if descriptor.id in self._providers:
            raise ValueError(
                "Duplicate provider ID '%s' in %s" % (descriptor.id, source or "<memory>")
            )
        self._providers[descriptor.id] = descriptor
        return descriptor

    def load_directory(self, providers_dir: Path) -> List[ProviderDescriptor]:
        loaded = []
        if not providers_dir.exists():
            return loaded
        for json_file in sorted(providers_dir.rglob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                loaded.append(self.register_record(data, str(json_file)))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self.load_errors.append({"path": str(json_file), "error": str(exc)})
        return loaded

    PROVIDER_ALIASES = {
        "toolchain.python-version": "toolchain.python-version-file",
    }

    @classmethod
    def resolve_id(cls, provider_id: str) -> str:
        """Resolve friendly aliases to canonical provider IDs without mutating canonical names."""
        return cls.PROVIDER_ALIASES.get(provider_id, provider_id)

    def get(self, provider_id: str) -> Optional[ProviderDescriptor]:
        descriptor = self._providers.get(provider_id)
        if descriptor is not None:
            return descriptor
        return self._providers.get(self.resolve_id(provider_id))

    def list(self, kind: Optional[str] = None) -> List[ProviderDescriptor]:
        providers = list(self._providers.values())
        if kind is not None:
            providers = [provider for provider in providers if provider.kind == kind]
        return sorted(providers, key=lambda provider: provider.id)

    def validate_selection(self, provider_ids: List[str]) -> List[str]:
        """Return dependency/conflict errors for a proposed provider composition."""
        selected = set(provider_ids)
        errors = []
        for provider_id in sorted(selected):
            provider = self.get(provider_id)
            if provider is None:
                errors.append("Unknown provider: " + provider_id)
                continue
            missing = sorted(set(provider.requires) - selected)
            collisions = sorted(set(provider.conflicts) & selected)
            if missing:
                errors.append("%s requires: %s" % (provider_id, ", ".join(missing)))
            if collisions:
                errors.append("%s conflicts with: %s" % (provider_id, ", ".join(collisions)))
        return errors
