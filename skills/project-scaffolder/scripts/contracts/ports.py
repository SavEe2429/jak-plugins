"""Small capability contracts used by the composition orchestrator.

Providers implement only ports they actually support; the generic core does
not require one God interface for every kind of adapter.
"""

from pathlib import Path
from typing import Protocol, Sequence

from contracts.models import (
    ArchitectureOption,
    ComponentRequest,
    DirectorySpec,
    Evidence,
    FileSpec,
    ProjectContext,
    ProviderDescriptor,
    VerificationCheck,
)


class Provider(Protocol):
    @property
    def descriptor(self) -> ProviderDescriptor: ...


class DiscoveryPort(Protocol):
    def discover(self, root: Path) -> ProjectContext: ...


class ArchitecturePort(Protocol):
    def options(
        self, context: ProjectContext, component: ComponentRequest
    ) -> Sequence[ArchitectureOption]: ...


class StandardsPort(Protocol):
    def resolve_standards(
        self, context: ProjectContext, component: ComponentRequest
    ) -> Sequence[ProviderDescriptor]: ...


class ToolchainPort(Protocol):
    def requirements(
        self, context: ProjectContext, component: ComponentRequest
    ) -> Sequence[ProviderDescriptor]: ...


class DependencyPort(Protocol):
    def plan_dependencies(
        self, context: ProjectContext, component: ComponentRequest
    ) -> ProviderDescriptor: ...


class TemplatePort(Protocol):
    def render(
        self, context: ProjectContext, component: ComponentRequest
    ) -> Sequence[FileSpec]: ...


class VerificationPort(Protocol):
    def checks(
        self, context: ProjectContext, component: ComponentRequest
    ) -> Sequence[VerificationCheck]: ...


class GenerationPort(Protocol):
    def directories(
        self, context: ProjectContext, component: ComponentRequest
    ) -> Sequence[DirectorySpec]: ...


class EvidencePort(Protocol):
    def collect(
        self, context: ProjectContext, component: ComponentRequest
    ) -> Sequence[Evidence]: ...
