"""Evidence-based generic resolution for declarative capability providers."""

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from contracts.models import CandidateScore, Evidence, ProjectContext, ResolutionReport

from core.capability_registry import CapabilityRegistry


class CapabilityResolver:
    """Resolve one provider per requested capability kind without stack defaults."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        minimum_confidence: float = 0.6,
        ambiguity_margin: float = 0.15,
    ):
        self.registry = registry
        self.minimum_confidence = minimum_confidence
        self.ambiguity_margin = ambiguity_margin

    def resolve(
        self,
        root: Path,
        kinds: Sequence[str],
        explicit: Optional[Dict[str, str]] = None,
        context: Optional[ProjectContext] = None,
    ) -> ResolutionReport:
        explicit = explicit or {}
        candidates: List[CandidateScore] = []
        selected = []
        unresolved = []
        errors = []

        for kind in kinds:
            providers = self.registry.list(kind)
            scored = [self._score(root, provider) for provider in providers]
            candidates.extend(scored)
            requested_id = explicit.get(kind)
            if requested_id:
                provider = self.registry.get(requested_id)
                if provider is None or provider.kind != kind:
                    errors.append(
                        "Explicit provider '%s' is not registered for kind '%s'"
                        % (requested_id, kind)
                    )
                    unresolved.append(kind)
                    continue
                selected.append(provider)
                continue

            ranked = sorted(scored, key=lambda item: (-item.score, item.provider_id))
            if not ranked or ranked[0].confidence < self.minimum_confidence:
                unresolved.append(kind)
                continue
            if (
                len(ranked) > 1
                and ranked[0].confidence - ranked[1].confidence < self.ambiguity_margin
            ):
                unresolved.append(kind)
                errors.append(
                    "Ambiguous %s providers: %s"
                    % (
                        kind,
                        ", ".join(
                            "%s (%.2f)" % (item.provider_id, item.confidence) for item in ranked[:3]
                        ),
                    )
                )
                continue
            selected.append(self.registry.get(ranked[0].provider_id))

        selected_ids = [provider.id for provider in selected]
        for error in self.registry.validate_selection(selected_ids):
            # Explicit selection does not bypass provider dependencies or conflicts.
            errors.append(error)
        status = (
            "resolved"
            if not unresolved and not errors
            else ("ambiguous" if any("Ambiguous" in e for e in errors) else "incomplete")
        )
        return ResolutionReport(
            status=status,
            selected=selected,
            candidates=candidates,
            errors=errors,
            unresolved_kinds=unresolved,
        )

    def _score(self, root: Path, provider) -> CandidateScore:
        evidence = []
        reasons = []
        total_weight = sum(int(rule.get("weight", 1)) for rule in provider.matches)
        matched_weight = 0.0
        quality_factor = {"observed": 1.0, "declared": 0.85, "inferred": 0.65, "weak": 0.4}
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
            weight = int(rule.get("weight", 1))
            quality = rule.get("quality", "observed")
            matched_weight += weight * quality_factor.get(quality, 0.0)
            evidence.append(
                Evidence(
                    source=str(marker),
                    claim="provider-match",
                    value=provider.id,
                    quality=quality,
                    weight=weight,
                )
            )
            reasons.append("matched %s" % rule["path"])
        confidence = matched_weight / float(total_weight) if total_weight else 0.0
        return CandidateScore(
            provider_id=provider.id,
            kind=provider.kind,
            score=int(round(matched_weight)),
            confidence=confidence,
            evidence=evidence,
            reasons=reasons,
        )
