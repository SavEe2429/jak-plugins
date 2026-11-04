#!/usr/bin/env python3
"""
contract.py - Generic Adapter Contract & Data Models
Part of the 'project-scaffolder' skill.

Enforces strict domain-agnostic separation:
Core Engine interacts ONLY via these abstract interfaces and data containers.
No stack, toolchain, or business domain details are baked into the core engine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from contracts.models import FileSpec


@dataclass
class VerificationResult:
    """Standardized result of a verification step."""

    status: str  # PASS, FAIL, NOT VERIFIED, NOT APPLICABLE
    command: str = ""
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    message: str = ""
    evidence_file: Optional[str] = None
    output_truncated: bool = False


@dataclass
class AuditItemResult:
    """Standardized result of an audit category item."""

    num: int
    pillar: str
    name: str
    status: str  # PASS, FAIL, NOT VERIFIED, NOT APPLICABLE
    details: str


class StackAdapter(ABC):
    """Abstract Base Class for all Tech Stack & Domain Adapters."""

    @property
    @abstractmethod
    def domain(self) -> str:
        """Domain archetype (e.g. game, embedded, web, systems, ai_data, generic)."""
        pass

    @property
    @abstractmethod
    def stack_id(self) -> str:
        """Unique identifier for this tech stack (e.g. unity, rust, fastapi)."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for reporting and UI."""
        pass

    @property
    @abstractmethod
    def markers(self) -> List[str]:
        """File or directory patterns indicating this stack in a workspace."""
        pass

    @abstractmethod
    def matches_workspace(self, root: Path) -> bool:
        """Evaluates whether the workspace matches this adapter's domain/stack."""
        pass

    @abstractmethod
    def get_directories(
        self, topology: str = "unknown", architecture: Optional[str] = None
    ) -> List[str]:
        """Composes directories from explicit architecture and topology choices."""
        pass

    @abstractmethod
    def get_gitattributes_lfs_patterns(self) -> List[str]:
        """Returns Git LFS patterns specific to this stack."""
        pass

    @abstractmethod
    def get_entry_points(
        self, project_name: str, architecture: Optional[str] = None
    ) -> List[FileSpec]:
        """Generates minimal entry files compatible with the selected architecture."""
        pass

    @abstractmethod
    def get_smoke_tests(
        self, project_name: str, architecture: Optional[str] = None
    ) -> List[FileSpec]:
        """Generates minimal test sources compatible with the selected architecture."""
        pass

    @abstractmethod
    def get_supporting_files(
        self,
        topology: str = "unknown",
        architecture: Optional[str] = None,
        include_runbook: bool = True,
    ) -> List[FileSpec]:
        """Generates contributor-operation files declared by the selected profile."""
        pass

    @abstractmethod
    def get_ci_workflow(self, project_name: str) -> str:
        """Returns GitHub Actions CI workflow yaml content."""
        pass

    @abstractmethod
    def get_test_commands(self) -> List[str]:
        """Returns executable test runner command strings."""
        pass

    @abstractmethod
    def get_build_commands(self) -> List[str]:
        """Returns executable build/compilation command strings."""
        pass

    @abstractmethod
    def get_config_manifests(self) -> List[str]:
        """Returns list of expected project configuration files (e.g. Cargo.toml, pyproject.toml)."""
        pass

    @abstractmethod
    def get_mandatory_categories(self) -> List[int]:
        """Returns list of mandatory category numbers for audit."""
        pass

    @abstractmethod
    def get_na_categories(self) -> List[int]:
        """Returns list of Not Applicable category numbers for audit."""
        pass

    @abstractmethod
    def check_config_manifest(self, root: Path) -> Tuple[bool, str]:
        """Inspects if required project/engine configuration files exist."""
        pass

    @abstractmethod
    def check_module_boundaries(self, root: Path, topology: str) -> Tuple[bool, str]:
        """Inspects if modular boundaries or package manifests exist."""
        pass
