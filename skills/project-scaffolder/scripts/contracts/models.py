"""Typed data models shared by capability providers and the generic core.

These contracts intentionally contain no language, framework, domain, or
package-manager-specific behavior.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

CONTRACT_VERSION = 1
PROVIDER_KINDS = {
    "language",
    "framework",
    "package_manager",
    "toolchain",
    "domain",
    "architecture",
    "standards",
    "template",
    "verification",
}


@dataclass(frozen=True)
class Evidence:
    source: str
    claim: str
    value: str
    quality: str = "observed"
    weight: int = 1


@dataclass
class FileSpec:
    rel_path: str
    content: str
    description: str = ""


@dataclass(frozen=True)
class DirectorySpec:
    rel_path: str
    reason: str = ""
    required: bool = True


@dataclass(frozen=True)
class ProviderDescriptor:
    id: str
    kind: str
    schema_version: int
    capabilities: List[str] = field(default_factory=list)
    matches: List[Dict[str, Any]] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
    source: str = ""


@dataclass(frozen=True)
class ComponentRequest:
    id: str
    role: str
    root: str = "."
    selectors: Dict[str, str] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectContext:
    root: Path
    purpose: str = ""
    domain: str = "unknown"
    topology: str = "unknown"
    components: List[ComponentRequest] = field(default_factory=list)
    requirements: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    evidence: List[Evidence] = field(default_factory=list)


@dataclass(frozen=True)
class CandidateScore:
    provider_id: str
    kind: str
    score: int
    confidence: float = 0.0
    evidence: List[Evidence] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


@dataclass
class ResolutionReport:
    status: str
    selected: List[ProviderDescriptor] = field(default_factory=list)
    candidates: List[CandidateScore] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    unresolved_kinds: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ArchitectureOption:
    id: str
    description: str
    constraints: List[str] = field(default_factory=list)
    tradeoffs: List[str] = field(default_factory=list)
    directory_specs: List[DirectorySpec] = field(default_factory=list)
    template_ids: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class VerificationCheck:
    id: str
    capability: str
    command: List[str] = field(default_factory=list)
    required: bool = True
    expected_evidence: Dict[str, Any] = field(default_factory=dict)
    execution_policy: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VerificationEvidence:
    check_id: str
    status: str
    required: bool = True
    command: List[str] = field(default_factory=list)
    exit_code: Optional[int] = None
    tool_version: Optional[str] = None
    output_summary: str = ""
    evidence_refs: List[str] = field(default_factory=list)
    message: str = ""


@dataclass
class CompositionPlan:
    schema_version: int = CONTRACT_VERSION
    context: Optional[ProjectContext] = None
    selected_provider_ids: List[str] = field(default_factory=list)
    directories: List[DirectorySpec] = field(default_factory=list)
    files: List[FileSpec] = field(default_factory=list)
    verification_checks: List[VerificationCheck] = field(default_factory=list)
    unresolved: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    requires_confirmation: bool = True
