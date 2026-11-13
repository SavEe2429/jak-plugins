#!/usr/bin/env python3
"""
agent_adapter.py - Ports & Adapters Architecture for AI Agent Environments
Part of the 'skill-factory' meta-skill.

Capabilities:
1. Environment Ports & Adapters Pattern (Claude, Gemini, Cursor, Copilot, Local).
2. Four Explicit Status States:
   - ACTIVE: Currently running agent harness (verified by env variables or active process markers).
   - INSTALLED: Global CLI/Desktop app installed on system, but not currently the active harness.
   - DETECTED: Workspace configuration files present, but runner is passive.
   - SUPPORTED: Known agent format supported by engine, not present.
3. Declarative Capability, Skill Format & Permission Models per adapter.
4. Unified Discovery Priority & Installation Target Resolution.
"""

import abc
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Reconfigure stdout/stderr on Windows to handle unicode cleanly
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

VALID_INSTALL_SCOPES = frozenset({"project", "workspace", "user", "global"})


def normalize_install_scope(scope: str = "workspace") -> str:
    """
    Normalize installation scope aliases into canonical adapter scopes:
    - 'project' / 'workspace' -> 'workspace' (project-level directory)
    - 'user' / 'global'       -> 'global'    (user-level home directory)
    """
    if not isinstance(scope, str):
        raise ValueError(
            "Installation scope must be a string ('project'/'workspace' or 'user'/'global')."
        )
    cleaned = scope.strip().lower()
    if cleaned in ("project", "workspace"):
        return "workspace"
    if cleaned in ("user", "global"):
        return "global"
    raise ValueError(
        f"Unsupported installation scope: {scope!r}. Expected 'project'/'workspace' or 'user'/'global'."
    )



class AgentEnvironmentPort(abc.ABC):
    """Abstract port defining the interface for all AI Agent runtime adapters."""

    @property
    @abc.abstractmethod
    def agent_id(self) -> str:
        """Unique identifier (e.g. 'gemini', 'claude', 'cursor', 'copilot')."""
        pass

    @property
    @abc.abstractmethod
    def display_name(self) -> str:
        """Human-readable name."""
        pass

    @property
    @abc.abstractmethod
    def supported_skill_format(self) -> str:
        """Skill specification format (e.g. 'agent-skill-md', 'cursor-rules', 'copilot-instructions')."""
        pass

    @abc.abstractmethod
    def inspect(self, workspace: Path) -> Dict[str, Any]:
        """
        Inspects environment state.
        Returns dictionary with keys:
        - status: 'ACTIVE', 'INSTALLED', 'DETECTED', or 'SUPPORTED'
        - global_skills: Optional[Path]
        - workspace_skills: Optional[Path]
        - active_runtime_evidence: List[str]
        """
        pass

    @abc.abstractmethod
    def resolve_discovery_paths(self, workspace: Path) -> List[Path]:
        """Returns all directories where skills can be discovered for this agent."""
        pass

    @abc.abstractmethod
    def resolve_install_path(self, workspace: Path, scope: str = "workspace") -> Path:
        """Returns target directory where a skill should be installed."""
        pass

    @abc.abstractmethod
    def get_permission_model(self) -> Dict[str, Any]:
        """Returns security and permission model for this agent."""
        pass


class GeminiAntigravityAdapter(AgentEnvironmentPort):
    """Adapter for Google Antigravity and Gemini CLI Agent Skills."""

    @property
    def agent_id(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return "Google Antigravity / Gemini CLI"

    @property
    def supported_skill_format(self) -> str:
        return "agent-skill-md (SKILL.md with YAML frontmatter)"

    def inspect(self, workspace: Path) -> Dict[str, Any]:
        home = Path.home()
        global_paths = [home / ".gemini" / "skills", home / ".agents" / "skills"]
        workspace_paths = [
            workspace / ".agents" / "skills",
            workspace / ".gemini" / "skills",
        ]
        builtin_skills = home / ".gemini" / "antigravity" / "builtin" / "skills"
        existing_global = next((path for path in global_paths if path.is_dir()), None)
        existing_workspace = next((path for path in workspace_paths if path.is_dir()), None)
        is_installed = (
            existing_global is not None
            or builtin_skills.is_dir()
            or shutil.which("gemini") is not None
            or shutil.which("agy") is not None
        )
        status = "INSTALLED" if is_installed else (
            "DETECTED" if existing_workspace else "SUPPORTED"
        )
        return {
            "id": self.agent_id,
            "name": self.display_name,
            "status": status,
            "format": self.supported_skill_format,
            "global_skills": existing_global,
            "global_skill_paths": [path for path in global_paths if path.is_dir()],
            "builtin_skills": builtin_skills if builtin_skills.is_dir() else None,
            "workspace_skills": existing_workspace,
            "workspace_skill_paths": [path for path in workspace_paths if path.is_dir()],
            "active_evidence": [],
        }

    def resolve_discovery_paths(self, workspace: Path) -> List[Path]:
        home = Path.home()
        candidates = [
            workspace / ".agents" / "skills",
            workspace / ".gemini" / "skills",
            home / ".gemini" / "skills",
            home / ".agents" / "skills",
            home / ".gemini" / "antigravity" / "builtin" / "skills",
        ]
        return [path for path in candidates if path.is_dir()]

    def resolve_install_path(self, workspace: Path, scope: str = "workspace") -> Path:
        if normalize_install_scope(scope) == "global":
            return Path.home() / ".gemini" / "skills"
        return workspace / ".agents" / "skills"

    def get_permission_model(self) -> Dict[str, Any]:
        return {
            "sandbox": "Gemini CLI host sandbox and approval settings; must be verified at runtime",
            "allowed_tools_declaration": False,
            "network_policy": "Host configuration and tool approval dependent",
        }


class OpenAICodexAdapter(AgentEnvironmentPort):
    """Adapter for OpenAI Codex CLI/IDE filesystem-based Agent Skills."""

    @property
    def agent_id(self) -> str:
        return "codex"

    @property
    def display_name(self) -> str:
        return "OpenAI Codex CLI / IDE"

    @property
    def supported_skill_format(self) -> str:
        return "agent-skill-md (SKILL.md with YAML frontmatter)"

    def inspect(self, workspace: Path) -> Dict[str, Any]:
        home = Path.home()
        global_skills = home / ".agents" / "skills"
        workspace_skills = workspace / ".agents" / "skills"
        is_installed = global_skills.is_dir() or shutil.which("codex") is not None
        status = "INSTALLED" if is_installed else (
            "DETECTED" if workspace_skills.is_dir() else "SUPPORTED"
        )
        return {
            "id": self.agent_id,
            "name": self.display_name,
            "status": status,
            "format": self.supported_skill_format,
            "global_skills": global_skills if global_skills.is_dir() else None,
            "workspace_skills": workspace_skills if workspace_skills.is_dir() else None,
            "active_evidence": [],
        }

    def resolve_discovery_paths(self, workspace: Path) -> List[Path]:
        candidates = [workspace / ".agents" / "skills", Path.home() / ".agents" / "skills"]
        return [path for path in candidates if path.is_dir()]

    def resolve_install_path(self, workspace: Path, scope: str = "workspace") -> Path:
        if normalize_install_scope(scope) == "global":
            return Path.home() / ".agents" / "skills"
        return workspace / ".agents" / "skills"

    def get_permission_model(self) -> Dict[str, Any]:
        return {
            "sandbox": "Codex sandbox and approval policy configured by the host",
            "allowed_tools_declaration": False,
            "network_policy": "Host sandbox and approval policy dependent",
        }


class ClaudeCodeAdapter(AgentEnvironmentPort):
    """Adapter for Anthropic Claude Code CLI."""

    @property
    def agent_id(self) -> str:
        return "claude"

    @property
    def display_name(self) -> str:
        return "Anthropic Claude Code"

    @property
    def supported_skill_format(self) -> str:
        return "agent-skill-md (Anthropic standard SKILL.md)"

    def inspect(self, workspace: Path) -> Dict[str, Any]:
        home = Path.home()
        claude_global = home / ".claude" / "skills"
        workspace_skills = workspace / ".claude" / "skills"
        is_installed = claude_global.is_dir() or shutil.which("claude") is not None
        has_workspace = workspace_skills.is_dir()
        status = "INSTALLED" if is_installed else (
            "DETECTED" if has_workspace else "SUPPORTED"
        )
        return {
            "id": self.agent_id,
            "name": self.display_name,
            "status": status,
            "format": self.supported_skill_format,
            "global_skills": claude_global if claude_global.is_dir() else None,
            "workspace_skills": workspace_skills if has_workspace else None,
            "active_evidence": [],
        }

    def resolve_discovery_paths(self, workspace: Path) -> List[Path]:
        candidates = [workspace / ".claude" / "skills", Path.home() / ".claude" / "skills"]
        return [path for path in candidates if path.is_dir()]

    def resolve_install_path(self, workspace: Path, scope: str = "workspace") -> Path:
        if normalize_install_scope(scope) == "global":
            return Path.home() / ".claude" / "skills"
        return workspace / ".claude" / "skills"

    def get_permission_model(self) -> Dict[str, Any]:
        return {
            "sandbox": "Local CLI with user approval prompt on bash execution",
            "allowed_tools_declaration": True,
            "network_policy": "Host network inheritance",
        }


class CursorAdapter(AgentEnvironmentPort):
    """Adapter for Cursor Editor (.cursor/rules, .cursor/skills)."""

    @property
    def agent_id(self) -> str:
        return "cursor"

    @property
    def display_name(self) -> str:
        return "Cursor Editor"

    @property
    def supported_skill_format(self) -> str:
        return "cursor-rules (.cursor/rules/*.mdc) + skills"

    def inspect(self, workspace: Path) -> Dict[str, Any]:
        home = Path.home()
        cursor_skills = workspace / ".cursor" / "skills"
        cursor_rules = workspace / ".cursor" / "rules"

        evidence = []
        is_active = False

        is_installed = (home / ".cursor").exists() or shutil.which("cursor") is not None
        has_workspace = cursor_skills.exists() or cursor_rules.exists()

        if is_active:
            status = "ACTIVE"
        elif is_installed:
            status = "INSTALLED"
        elif has_workspace:
            status = "DETECTED"
        else:
            status = "SUPPORTED"

        return {
            "id": self.agent_id,
            "name": self.display_name,
            "status": status,
            "format": self.supported_skill_format,
            "global_skills": None,
            "workspace_skills": cursor_skills if cursor_skills.exists() else None,
            "workspace_rules": cursor_rules if cursor_rules.exists() else None,
            "active_evidence": evidence,
        }

    def resolve_discovery_paths(self, workspace: Path) -> List[Path]:
        paths = []
        cs = workspace / ".cursor" / "skills"
        if cs.exists():
            paths.append(cs)
        cr = workspace / ".cursor" / "rules"
        if cr.exists():
            paths.append(cr)
        return paths

    def resolve_install_path(self, workspace: Path, scope: str = "workspace") -> Path:
        if normalize_install_scope(scope) == "global":
            return Path.home() / ".cursor" / "skills"
        return workspace / ".cursor" / "skills"

    def get_permission_model(self) -> Dict[str, Any]:
        return {
            "sandbox": "IDE integrated editor permissions",
            "allowed_tools_declaration": False,
            "network_policy": "IDE environment permissions",
        }


class GitHubCopilotAdapter(AgentEnvironmentPort):
    """Adapter for GitHub Copilot Workspace and Instructions."""

    @property
    def agent_id(self) -> str:
        return "copilot"

    @property
    def display_name(self) -> str:
        return "GitHub Copilot"

    @property
    def supported_skill_format(self) -> str:
        return "copilot-instructions (.github/copilot-instructions.md, .github/skills)"

    def inspect(self, workspace: Path) -> Dict[str, Any]:
        copilot_dir = workspace / ".github" / "skills"
        copilot_file = workspace / ".github" / "copilot-instructions.md"

        evidence = []
        is_active = False

        has_workspace = copilot_dir.exists() or copilot_file.exists()

        if is_active:
            status = "ACTIVE"
        elif has_workspace:
            status = "DETECTED"
        else:
            status = "SUPPORTED"

        return {
            "id": self.agent_id,
            "name": self.display_name,
            "status": status,
            "format": self.supported_skill_format,
            "global_skills": None,
            "workspace_skills": copilot_dir if copilot_dir.exists() else None,
            "instructions_file": copilot_file if copilot_file.exists() else None,
            "active_evidence": evidence,
        }

    def resolve_discovery_paths(self, workspace: Path) -> List[Path]:
        paths = []
        cs = workspace / ".github" / "skills"
        if cs.exists():
            paths.append(cs)
        return paths

    def resolve_install_path(self, workspace: Path, scope: str = "workspace") -> Path:
        if normalize_install_scope(scope) == "global":
            return Path.home() / ".agents" / "skills"
        return workspace / ".github" / "skills"

    def get_permission_model(self) -> Dict[str, Any]:
        return {
            "sandbox": "GitHub Codespaces / VS Code Sandboxed",
            "allowed_tools_declaration": False,
            "network_policy": "Repository scoped",
        }


class LocalWorkspaceAdapter(AgentEnvironmentPort):
    """Generic fallback adapter for repository workspace skills (.agents/skills, .skills)."""

    @property
    def agent_id(self) -> str:
        return "local"

    @property
    def display_name(self) -> str:
        return "Local Repository Workspace"

    @property
    def supported_skill_format(self) -> str:
        return "universal-agent-skill"

    def inspect(self, workspace: Path) -> Dict[str, Any]:
        ws1 = workspace / ".agents" / "skills"
        ws2 = workspace / ".skills"
        has_skills = ws1.is_dir() or ws2.is_dir()

        return {
            "id": self.agent_id,
            "name": self.display_name,
            "status": "DETECTED" if has_skills else "SUPPORTED",
            "format": self.supported_skill_format,
            "global_skills": None,
            "workspace_skills": ws1 if ws1.is_dir() else (ws2 if ws2.is_dir() else None),
            "active_evidence": ["Repository skill directory present"] if has_skills else [],
        }

    def resolve_discovery_paths(self, workspace: Path) -> List[Path]:
        paths = []
        for cand in [workspace / ".agents" / "skills", workspace / ".skills"]:
            if cand.exists():
                paths.append(cand)
        return paths

    def resolve_install_path(self, workspace: Path, scope: str = "workspace") -> Path:
        if normalize_install_scope(scope) == "global":
            return Path.home() / ".agents" / "skills"
        return workspace / ".agents" / "skills"

    def get_permission_model(self) -> Dict[str, Any]:
        return {
            "sandbox": "Local filesystem workspace boundary",
            "allowed_tools_declaration": True,
            "network_policy": "Unrestricted local execution",
        }


class AgentEnvironmentAdapter:
    """Orchestrates ports & adapters across all agent runtime environments."""

    def __init__(
        self,
        workspace_path: Optional[Path] = None,
        custom_skills_dir: Optional[Path] = None,
        active_agent: Optional[str] = None,
    ):
        ws = (workspace_path or Path.cwd()).resolve()
        # If current workspace is a parent directory without .git (e.g. C:\Users\nongs\Desktop\TD)
        # but contains a child repository with .git and .agents (e.g. TowerFight),
        # automatically anchor to the real project repository to prevent polluting the parent folder.
        if not (ws / ".git").exists():
            try:
                for child in ws.iterdir():
                    if (
                        child.is_dir()
                        and (child / ".git").exists()
                        and (child / ".agents").exists()
                    ):
                        ws = child
                        break
            except Exception:
                pass
        self.workspace = ws
        self.custom_skills_dir = custom_skills_dir.resolve() if custom_skills_dir else None
        valid_agent_ids = {"gemini", "claude", "codex", "cursor", "copilot", "local"}
        if active_agent is not None and active_agent not in valid_agent_ids:
            raise ValueError(f"Unsupported active agent id: {active_agent}")
        self.active_agent = active_agent
        self.adapters: List[AgentEnvironmentPort] = [
            GeminiAntigravityAdapter(),
            ClaudeCodeAdapter(),
            OpenAICodexAdapter(),
            CursorAdapter(),
            GitHubCopilotAdapter(),
            LocalWorkspaceAdapter(),
        ]

    def detect_available_environments(self) -> List[Dict[str, Any]]:
        """Scans for active, installed, and detected agent environments with evidence."""
        results = []
        for adapter in self.adapters:
            info = adapter.inspect(self.workspace)
            if self.active_agent == adapter.agent_id:
                info["status"] = "ACTIVE"
                info["active_evidence"] = ["Explicit runtime identity supplied by caller"]
            # Only include if active, installed, or detected in workspace
            if info["status"] in ("ACTIVE", "INSTALLED", "DETECTED"):
                results.append(info)
        return results

    def resolve_skills_discovery_roots(self) -> List[Path]:
        """
        Resolve every existing path declared by each adapter.

        Priority is: explicit override, active-agent workspace paths, other
        workspace paths, then global and built-in paths. Adapter path lists
        are authoritative; singular inspect() fields are not sufficient for
        adapters that expose multiple supported roots (for example Gemini).
        """
        roots: List[Path] = []

        def append_unique(paths):
            for path in paths:
                if path and path.is_dir() and path not in roots:
                    roots.append(path)

        if self.custom_skills_dir:
            append_unique([self.custom_skills_dir])

        adapters_by_id = {adapter.agent_id: adapter for adapter in self.adapters}
        envs = self.detect_available_environments()
        resolved = []
        for env in envs:
            adapter = adapters_by_id.get(env["id"])
            if adapter is None:
                continue
            workspace_paths = []
            global_paths = []
            for path in adapter.resolve_discovery_paths(self.workspace):
                try:
                    path.relative_to(self.workspace)
                    workspace_paths.append(path)
                except ValueError:
                    global_paths.append(path)
            # Preserve host-provided built-in roots, which may not be included
            # by every adapter's discovery implementation.
            builtin = env.get("builtin_skills")
            if builtin:
                global_paths.append(builtin)
            resolved.append((env, workspace_paths, global_paths))

        for env, workspace_paths, _ in resolved:
            if env["status"] == "ACTIVE":
                append_unique(workspace_paths)

        for env, workspace_paths, _ in resolved:
            if env["status"] != "ACTIVE":
                append_unique(workspace_paths)

        for _, _, global_paths in resolved:
            append_unique(global_paths)

        return roots

    def resolve_target_install_directory(self, install_scope: str = "workspace") -> Path:
        """Determines target directory for new skills based on active adapter and scope ('project'/'workspace' or 'user'/'global')."""
        normalized_scope = normalize_install_scope(install_scope)
        if self.custom_skills_dir:
            return self.custom_skills_dir

        envs = self.detect_available_environments()
        # Find active adapter first
        active_env = next((e for e in envs if e["status"] == "ACTIVE"), None)

        target_adapter = None
        if active_env:
            target_adapter = next(
                (a for a in self.adapters if a.agent_id == active_env["id"]), None
            )

        if not target_adapter:
            target_adapter = next(a for a in self.adapters if a.agent_id == "local")

        return target_adapter.resolve_install_path(self.workspace, normalized_scope)


def main():
    target = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    adapter = AgentEnvironmentAdapter(target)
    envs = adapter.detect_available_environments()
    roots = adapter.resolve_skills_discovery_roots()

    print("================================================================================")
    print("      AGENT ENVIRONMENT PORTS & ADAPTERS (STATUS MATRIX)                        ")
    print("================================================================================")
    print(f"Workspace Directory : {target}\n")

    print("Detected Agent Environments:")
    for e in envs:
        status_tag = f"[{e['status']}]"
        print(f"  {status_tag:<12} {e['name']}")
        print(f"               Format  : {e['format']}")
        if e.get("active_evidence"):
            print(f"               Evidence: {', '.join(e['active_evidence'])}")
        if e.get("workspace_skills"):
            print(f"               Workspace: {e['workspace_skills']}")
        if e.get("global_skills"):
            print(f"               Global   : {e['global_skills']}")

    print("\nResolved Skill Discovery Roots (in priority order):")
    for idx, r in enumerate(roots, 1):
        print(f"  {idx:02d}. {r}")

    print("================================================================================")


if __name__ == "__main__":
    main()
