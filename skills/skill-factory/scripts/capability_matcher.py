#!/usr/bin/env python3
"""
capability_matcher.py - Skill-Agnostic, Context-Aware Capability Resolution & Intent Engine
Part of the 'skill-factory' meta-skill.

Core 3-Layer Architecture:
1. Universal Capability Layer: Decoupled functional vocabulary (Research, Creation, Analysis, Validation, etc.)
   with zero hardcoded external skill names or project bindings.
2. Dynamic Discovery Layer: Discovers skills, MCPs, and tools from the actual environment by inspecting
   SKILL.md frontmatter, description, and metadata.
3. Adaptive Selection Layer: Matches capabilities dynamically against discovered tools based on semantic fit,
   reporting uninstalled capabilities honestly without hardcoded fallbacks.
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Reconfigure stdout/stderr on Windows to handle unicode cleanly
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 10 Universal Capabilities Vocabulary (Completely decoupled from specific tool/skill names)
UNIVERSAL_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "planning": {
        "id": "planning",
        "name": "Planning & Requirements",
        "description": "Requirement clarification, ambiguity resolution, user interviews, specification breakdown, and scope definition.",
        "keywords": [
            "plan",
            "scope",
            "requirements",
            "specification",
            "breakdown",
            "roadmap",
            "outline",
            "user stories",
            "architecture plan",
            "prd",
            "spec",
            "interview",
            "clarify",
        ],
        "builtin_tool": "Interactive planning and task specification tools",
    },
    "research": {
        "id": "research",
        "name": "Research & Knowledge",
        "description": "Codebase survey, deep literature search, documentation review, historical inquiry, and technical exploration.",
        "keywords": [
            "search",
            "explore",
            "research",
            "survey",
            "documentation",
            "investigate",
            "history",
            "\u0e1b\u0e23\u0e30\u0e27\u0e31\u0e15\u0e34",
            "literature",
            "inquiry",
            "api reference",
            "background",
            "source",
        ],
        "builtin_tool": "Web search and repository inspection tools",
    },
    "design": {
        "id": "design",
        "name": "Design & Modeling",
        "description": "System architecture diagrams, data schemas, database modeling, and interface wireframing.",
        "keywords": [
            "diagram",
            "diagrams",
            "architecture",
            "wireframe",
            "schema",
            "data schema",
            "layout",
            "flowchart",
            "ui design",
            "wireframing",
            "mockup",
            "system design",
            "data model",
            "uml",
            "sequence diagram",
            "erd",
            "mermaid",
            "excalidraw",
            "drawio",
            "blueprint",
            "draw",
            "chart",
            "visual",
            "\u0e27\u0e32\u0e14",
            "\u0e41\u0e1c\u0e19\u0e1c\u0e31\u0e07",
            "\u0e1c\u0e31\u0e07\u0e23\u0e30\u0e1a\u0e1a",
            "\u0e44\u0e14\u0e2d\u0e30\u0e41\u0e01\u0e23\u0e21",
            "\u0e2a\u0e16\u0e32\u0e1b\u0e31\u0e15\u0e22\u0e01\u0e23\u0e23\u0e21",
            "\u0e2d\u0e2d\u0e01\u0e41\u0e1a\u0e1a",
            "\u0e1e\u0e34\u0e21\u0e1e\u0e4c\u0e40\u0e02\u0e35\u0e22\u0e27",
        ],
        "builtin_tool": "Structured architectural diagrams and layout modeling tools",
    },
    "creation": {
        "id": "creation",
        "name": "Creation & Implementation",
        "description": "Code authoring, skill synthesis, component implementation, and creative content generation.",
        "keywords": [
            "create",
            "implement",
            "build",
            "code",
            "write code",
            "generate code",
            "synthesize",
            "author",
            "\u0e2a\u0e23\u0e49\u0e32\u0e07",
            "component",
            "module",
            "service",
            "routine",
        ],
        "builtin_tool": "Native code authoring and file generation tools",
    },
    "validation": {
        "id": "validation",
        "name": "Validation & Testing",
        "description": "Automated test suites, unit testing, integration tests, regression checks, assertion validation, and linters.",
        "keywords": [
            "test",
            "run tests",
            "unit test",
            "integration test",
            "smoke test",
            "regression test",
            "assertion",
            "test runner",
            "linter",
            "verify",
            "validation suite",
            "test fixture",
            "spec test",
        ],
        "builtin_tool": "Standard test runners and verification harnesses",
    },
    "analysis": {
        "id": "analysis",
        "name": "Analysis & Evaluation",
        "description": "Code review, static typing, performance/memory profiling, data analysis, metrics calculation, and audit.",
        "keywords": [
            "profile",
            "benchmark",
            "review",
            "audit",
            "memory",
            "performance",
            "analyze",
            "analysis",
            "anomaly",
            "metrics",
            "data",
            "throughput",
            "latency",
            "evaluation",
            "calculate",
        ],
        "builtin_tool": "Static code analyzers, performance profilers, and quantitative metrics calculators",
    },
    "orchestration": {
        "id": "orchestration",
        "name": "Automation & Orchestration",
        "description": "Subagent delegation, multi-agent teamwork, background batch workers, hardware communication, and pipelines.",
        "keywords": [
            "delegate",
            "subagent",
            "teamwork",
            "batch",
            "parallel",
            "pipeline",
            "worker",
            "automate",
            "schedule",
            "cron",
            "orchestrate",
            "dispatch",
            "flashing",
            "serial communication",
            "hardware access",
        ],
        "builtin_tool": "Subagent delegation and process automation tools",
    },
    "security": {
        "id": "security",
        "name": "Security & Governance",
        "description": "Static vulnerability analysis, secrets detection, AST threat checking, sandbox policy enforcement, and audit.",
        "keywords": [
            "security",
            "audit security",
            "secret",
            "vulnerability",
            "threat",
            "cve",
            "leak",
            "permission",
            "scan",
            "token leak",
            "exfiltration",
            "sandbox",
            "taint",
            "access control",
        ],
        "builtin_tool": "Static AST security scanner and credential protection filters",
    },
    "delivery": {
        "id": "delivery",
        "name": "Communication & Delivery",
        "description": "Changelog updates, release notes, user-facing summary reports, documentation publishing, and article writing.",
        "keywords": [
            "changelog",
            "release",
            "ship",
            "deliver",
            "publish",
            "readme",
            "report",
            "summary",
            "summarize",
            "findings",
            "communicate",
            "article",
            "\u0e1a\u0e17\u0e04\u0e27\u0e32\u0e21",
            "write an article",
            "documentation",
        ],
        "builtin_tool": "Structured summary reports and documentation publishing tools",
    },
    "learning": {
        "id": "learning",
        "name": "Learning & Continuous Improvement",
        "description": "Fact-based post-mortems, repetitive workflow synthesis, 3-repeat rule deduplication, and reflective feedback.",
        "keywords": [
            "post-mortem",
            "repeat",
            "synthesize",
            "improve",
            "dedup",
            "reflect",
            "lesson learned",
            "retrospective",
            "continuous improvement",
        ],
        "builtin_tool": "Workflow synthesis and post-mortem evaluation tools",
    },
}


# Known software code extensions and manifests for evidence-based context classification
SOFTWARE_CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".rs",
    ".go",
    ".cs",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".java",
    ".kt",
    ".rb",
    ".php",
    ".swift",
    ".scala",
    ".zig",
    ".lua",
    ".sh",
}
SOFTWARE_MANIFEST_NAMES = {
    "package.json",
    "cargo.toml",
    "pyproject.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "requirements.txt",
    "gemfile",
    "cmakelists.txt",
    "makefile",
    "composer.json",
    "manifest.json",
}

NON_SOFTWARE_INTENTS = {
    "CREATIVE_WRITING",
    "SURVEY_WRITING",
    "LEGAL_POLICY_RESEARCH",
    "MARKET_BUSINESS_ANALYSIS",
    "FINANCIAL_BUSINESS_ANALYSIS",
    "PLANNING_LOGISTICS",
    "GENERAL_KNOWLEDGE_TASK",
}


def has_software_evidence(repo_path: Optional[Path]) -> bool:
    """Checks if repository contains concrete software source files or build manifests."""
    if repo_path is None or not repo_path.exists():
        return False
    try:
        for p in repo_path.iterdir():
            if p.name.lower() in SOFTWARE_MANIFEST_NAMES:
                return True
            if p.is_file() and p.suffix.lower() in SOFTWARE_CODE_EXTENSIONS:
                return True
            if p.is_dir() and p.name not in {
                ".git",
                ".venv",
                "venv",
                "node_modules",
                "__pycache__",
                "dist",
                "build",
                "logs",
                "Library",
            }:
                for sub in p.iterdir():
                    if sub.name.lower() in SOFTWARE_MANIFEST_NAMES or (
                        sub.is_file() and sub.suffix.lower() in SOFTWARE_CODE_EXTENSIONS
                    ):
                        return True
    except (PermissionError, OSError):
        pass
    return False


# Facet-level functional intent verbs (open-domain). These map generic ACTIONS to the
# 10 universal capability facets; they deliberately say nothing about subject domains,
# so a task from a domain the factory has never seen still resolves to useful facets.
FACET_INTENT_VERBS: Dict[str, List[str]] = {
    "planning": [
        "plan",
        "organi[sz]",
        "arrang",
        "schedul",
        "outlin",
        "prioriti",
        "\u0e27\u0e32\u0e07\u0e41\u0e1c\u0e19",
        "\u0e08\u0e31\u0e14\u0e23\u0e30\u0e40\u0e1a\u0e35\u0e22\u0e1a",
        "\u0e08\u0e31\u0e14\u0e40\u0e23\u0e35\u0e22\u0e07",
        "\u0e08\u0e31\u0e14\u0e01\u0e32\u0e23",
    ],
    "research": [
        "research",
        "find out",
        "look up",
        "investigat",
        "stud(?:y|ies)",
        "explor",
        "gather",
        "\u0e04\u0e49\u0e19\u0e04\u0e27\u0e49\u0e32",
        "\u0e2a\u0e37\u0e1a\u0e04\u0e49\u0e19",
        "\u0e2b\u0e32\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25",
    ],
    "design": [
        "design",
        "diagram",
        "draw",
        "sketch",
        "wirefram",
        "map out",
        "visuali[sz]",
        "\u0e27\u0e32\u0e14",
        "\u0e2d\u0e2d\u0e01\u0e41\u0e1a\u0e1a",
        "\u0e17\u0e33\u0e1c\u0e31\u0e07",
        "\u0e23\u0e48\u0e32\u0e07\u0e1c\u0e31\u0e07",
    ],
    "creation": [
        "draft",
        "write",
        "compos",
        "creat",
        "prepar",
        "produc",
        "generat",
        "\u0e40\u0e02\u0e35\u0e22\u0e19",
        "\u0e23\u0e48\u0e32\u0e07",
        "\u0e41\u0e15\u0e48\u0e07",
        "\u0e2a\u0e23\u0e49\u0e32\u0e07",
    ],
    "analysis": [
        "review",
        "evaluat",
        "assess",
        "compar",
        "analy[sz]",
        "examin",
        "\u0e27\u0e34\u0e40\u0e04\u0e23\u0e32\u0e30\u0e2b\u0e4c",
        "\u0e1b\u0e23\u0e30\u0e40\u0e21\u0e34\u0e19",
        "\u0e40\u0e1b\u0e23\u0e35\u0e22\u0e1a\u0e40\u0e17\u0e35\u0e22\u0e1a",
    ],
    "delivery": [
        "report",
        "summari[sz]",
        "present",
        "publish",
        "deliver",
        "\u0e23\u0e32\u0e22\u0e07\u0e32\u0e19",
        "\u0e2a\u0e23\u0e38\u0e1b",
        "\u0e19\u0e33\u0e40\u0e2a\u0e19\u0e2d",
    ],
}


def infer_facets_from_intent(task_text: str) -> List[str]:
    """Infers universal capability facets from generic action verbs (domain-independent)."""
    text = task_text.lower()
    facets: List[str] = []
    for facet, stems in FACET_INTENT_VERBS.items():
        for stem in stems:
            is_ascii = stem.isascii()
            pattern = (r"\b" + stem) if is_ascii else re.escape(stem)
            if re.search(pattern, text):
                facets.append(facet)
                break
    return facets


def classify_domain_class(task_context: str, repo_path: Optional[Path] = None) -> str:
    """
    Three-state domain class: 'software', 'non_software', or 'unknown'.
    'unknown' means the task carries too little signal to decide; it must never be
    silently treated as software (or as non-software).
    """
    profile = ContextAwareCapabilityResolver(task_context).classify_context_profile()
    intent = profile["intent"]
    if intent == "AMBIGUOUS_OR_UNSPECIFIED":
        return "unknown"
    if profile["is_software"]:
        return "software"
    # Explicit software-authoring instruction overrides a non-software intent
    code_words = [
        "write code",
        "implement api",
        "build app",
        "python script",
        "compile",
        "dockerfile",
        "\u0e40\u0e02\u0e35\u0e22\u0e19\u0e42\u0e04\u0e49\u0e14",
    ]
    if any(w in task_context.lower() for w in code_words):
        return "software"
    return "non_software"


def is_non_software_context(task_context: str, repo_path: Optional[Path] = None) -> bool:
    """True only when the task is positively classified as non-software (unknown is NOT non-software)."""
    return classify_domain_class(task_context, repo_path) == "non_software"


def discover_local_mcp_configs(workspace_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Discovers locally configured MCP (Model Context Protocol) servers from standard configuration files.
    Eliminates reliance on hardcoded external catalogs.
    """
    import json

    home = Path.home()
    possible_config_paths = [
        home / ".claude" / "claude_desktop_config.json",
        home / ".gemini" / "antigravity" / "mcp_config.json",
        home / ".cursor" / "mcp.json",
    ]
    if workspace_path:
        possible_config_paths.extend(
            [workspace_path / ".cursor" / "mcp.json", workspace_path / "mcp.json"]
        )

    discovered_mcps = []
    for cfg_path in possible_config_paths:
        if cfg_path.exists() and cfg_path.is_file():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8", errors="ignore"))
                servers = data.get("mcpServers", {})
                for server_name, server_def in servers.items():
                    discovered_mcps.append(
                        {
                            "name": server_name,
                            "source": str(cfg_path),
                            "command": server_def.get("command", ""),
                            "args": server_def.get("args", []),
                            "status": "CONFIGURED",
                        }
                    )
            except Exception:
                pass
    return discovered_mcps


class ContextAwareCapabilityResolver:
    """
    Skill-Agnostic Capability Resolver.
    Understands task context, decouples Domain, Task Type, and Required Capabilities,
    detects multi-domain hybrid workflows, handles ambiguity gracefully,
    and resolves capability requirements with confidence.
    """

    def __init__(
        self,
        task_description: str,
        explicit_facets: Optional[List[str]] = None,
        excluded_facets: Optional[List[str]] = None,
        explicit_intent: Optional[str] = None,
    ):
        self.raw_task = task_description
        self.task_lower = task_description.lower().strip()
        self.explicit_facets = [f.strip().lower() for f in (explicit_facets or []) if f.strip()]
        self.excluded_facets = [f.strip().lower() for f in (excluded_facets or []) if f.strip()]
        self.explicit_intent = explicit_intent.strip().upper() if explicit_intent else None
        self.positive_task, self.negative_clauses = self._partition_negation(self.task_lower)

    @staticmethod
    def _partition_negation(text: str) -> Tuple[str, List[str]]:
        """Separates negative clauses (e.g. 'do not run tests', 'ไม่ต้องรันเทสต์') from positive task text."""
        neg_patterns = [
            r"(?:do not|don't|never|without)\s+([^,.;\n]+)",
            r"(?:\u0e44\u0e21\u0e48\u0e15\u0e49\u0e2d\u0e07|\u0e2b\u0e49\u0e32\u0e21|\u0e42\u0e14\u0e22\u0e44\u0e21\u0e48\u0e15\u0e49\u0e2d\u0e07)\s*([^,.;\n]+)",
        ]
        neg_clauses: List[str] = []
        pos_text = text
        for pat in neg_patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                neg_clauses.append(m.group(1).strip().lower())
                pos_text = pos_text.replace(m.group(0), " ")
        return pos_text.strip(), neg_clauses

    def classify_context_profile(self) -> Dict[str, Any]:
        """
        Decoupled Context & Domain Classifier.
        Analyzes functional intent, domain noun-verb pairings, multi-domain signals,
        and ambiguity levels without relying on isolated generic keywords like 'create'.
        """
        if self.explicit_intent:
            return {
                "primary_domain": self.explicit_intent.lower(),
                "detected_domains": [self.explicit_intent.lower()],
                "task_type": "ai_semantic_resolved",
                "intent": self.explicit_intent,
                "is_software": True,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }

        task_text = self.positive_task
        detected_domains: Set[str] = set()

        # 1. Creative Writing & Literary Arts
        if any(
            w in task_text
            for w in [
                "poem",
                "poetry",
                "lyrics",
                "creative writing",
                "fiction",
                "prose",
                "short story",
                "verse",
                "ballad",
                "novel",
                "screenplay",
                "rhyme",
                "\u0e01\u0e25\u0e2d\u0e19",
                "\u0e01\u0e27\u0e35",
                "\u0e01\u0e27\u0e35\u0e19\u0e34\u0e1e\u0e19\u0e18\u0e4c",
                "\u0e41\u0e15\u0e48\u0e07\u0e01\u0e25\u0e2d\u0e19",
                "\u0e40\u0e02\u0e35\u0e22\u0e19\u0e01\u0e25\u0e2d\u0e19",
                "\u0e1a\u0e17\u0e1b\u0e23\u0e30\u0e1e\u0e31\u0e19\u0e18\u0e4c",
                "\u0e19\u0e34\u0e22\u0e32\u0e22",
                "\u0e40\u0e23\u0e37\u0e48\u0e2d\u0e07\u0e2a\u0e31\u0e49\u0e19",
                "\u0e1a\u0e17\u0e40\u0e1e\u0e25\u0e07",
                "\u0e40\u0e19\u0e37\u0e49\u0e2d\u0e40\u0e1e\u0e25\u0e07",
            ]
        ):
            detected_domains.add("creative")

        # 2. Legal, Policy & Regulatory Research
        if any(
            w in task_text
            for w in [
                "\u0e01\u0e0e\u0e2b\u0e21\u0e32\u0e22",
                "\u0e41\u0e23\u0e07\u0e07\u0e32\u0e19",
                "\u0e01\u0e0e\u0e2b\u0e21\u0e32\u0e22\u0e41\u0e23\u0e07\u0e07\u0e32\u0e19",
                "\u0e1e\u0e23\u0e30\u0e23\u0e32\u0e0a\u0e1a\u0e31\u0e0d\u0e0d\u0e31\u0e15\u0e34",
                "\u0e02\u0e49\u0e2d\u0e1a\u0e31\u0e07\u0e04\u0e31\u0e1a",
                "\u0e23\u0e30\u0e40\u0e1a\u0e35\u0e22\u0e1a",
                "\u0e19\u0e42\u0e22\u0e1a\u0e32\u0e22",
                "\u0e23\u0e31\u0e10\u0e18\u0e23\u0e23\u0e21\u0e19\u0e39\u0e0d",
                "labor law",
                "law",
                "legal",
                "statute",
                "regulation",
                "policy",
                "compliance",
                "constitution",
                "jurisdiction",
            ]
        ):
            detected_domains.add("legal_policy")

        # 3. Market, Industry & Competitor Analysis
        if any(
            w in task_text
            for w in [
                "\u0e41\u0e19\u0e27\u0e42\u0e19\u0e49\u0e21\u0e15\u0e25\u0e32\u0e14",
                "\u0e15\u0e25\u0e32\u0e14",
                "\u0e04\u0e39\u0e48\u0e41\u0e02\u0e48\u0e07",
                "business analysis",
                "market trend",
                "market research",
                "market overview",
                "competitive analysis",
                "industry trend",
                "business plan",
            ]
        ):
            detected_domains.add("market_business")

        # 4. Financial & Quantitative Balance Sheet Analysis
        if any(
            w in task_text
            for w in [
                "balance sheet",
                "quarterly earnings",
                "financial statement",
                "monte carlo",
                "executive summary",
                "revenue",
                "profit margin",
                "\u0e01\u0e32\u0e23\u0e40\u0e07\u0e34\u0e19",
                "\u0e23\u0e32\u0e22\u0e44\u0e14\u0e49",
                "\u0e01\u0e33\u0e44\u0e23",
                "\u0e15\u0e49\u0e19\u0e17\u0e38\u0e19",
                "\u0e1a\u0e31\u0e0d\u0e0a\u0e35",
                "\u0e07\u0e1a\u0e01\u0e32\u0e23\u0e40\u0e07\u0e34\u0e19",
                "valuation",
            ]
        ):
            detected_domains.add("finance_accounting")

        # 5. Planning, Logistics, Budgeting & Travel
        has_budget = any(
            w in task_text
            for w in ["\u0e07\u0e1a\u0e1b\u0e23\u0e30\u0e21\u0e32\u0e13", "\u0e07\u0e1a\u0e1b\u0e23\u0e30\u0e21\u0e32\u0e13\u0e04\u0e23\u0e2d\u0e1a\u0e04\u0e23\u0e31\u0e27", "budget", "family budget", "cost estimation"]
        )
        has_travel = any(
            w in task_text
            for w in [
                "\u0e40\u0e17\u0e35\u0e48\u0e22\u0e27",
                "\u0e17\u0e48\u0e2d\u0e07\u0e40\u0e17\u0e35\u0e48\u0e22\u0e27",
                "\u0e40\u0e14\u0e34\u0e19\u0e17\u0e32\u0e07",
                "\u0e17\u0e23\u0e34\u0e1b",
                "itinerary",
                "vacation",
                "trip planning",
                "travel",
                "\u0e41\u0e1c\u0e19\u0e01\u0e32\u0e23\u0e40\u0e14\u0e34\u0e19\u0e17\u0e32\u0e07",
            ]
        )
        has_planning = any(
            w in task_text
            for w in [
                "\u0e27\u0e32\u0e07\u0e41\u0e1c\u0e19",
                "schedule planning",
                "event planning",
                "logistics",
                "\u0e08\u0e31\u0e14\u0e2a\u0e23\u0e23\u0e40\u0e27\u0e25\u0e32",
                "\u0e08\u0e31\u0e14\u0e17\u0e33\u0e07\u0e1a\u0e1b\u0e23\u0e30\u0e21\u0e32\u0e13",
            ]
        )
        if (has_budget or has_travel or has_planning) and not any(
            w in task_text for w in ["code", "software", "api", "compile"]
        ):
            detected_domains.add("planning_logistics")

        # 6. Data Science & Machine Learning
        if any(
            w in task_text
            for w in [
                "deep learning",
                "machine learning",
                "dataset",
                "tensor",
                "model training",
                "data pipeline",
                "pytorch",
                "tensorflow",
                "scikit-learn",
                "dataframe",
                "pandas",
            ]
        ):
            detected_domains.add("data_science")

        # 7. Interactive Graphics & Simulation Software
        if any(
            w in task_text
            for w in [
                "interactive simulation",
                "game project",
                "graphical simulation",
                "scene graph",
                "visual software",
                "canvas rendering",
                "shader pipeline",
            ]
        ):
            detected_domains.add("graphics_simulation")

        # 8. Embedded Systems & Firmware
        if any(
            w in task_text
            for w in [
                "firmware",
                "serial communication",
                "flashing",
                "microcontroller",
                "embedded environment",
                "arduino",
                "esp32",
                "stm32",
                "rtos",
            ]
        ):
            detected_domains.add("embedded_firmware")

        # 9. Low-level Systems & CLI
        if any(
            w in task_text
            for w in [
                "high-throughput",
                "proxy",
                "systems programming",
                "cli utility",
                "concurrency",
                "memory profiling",
                "clippy",
                "cargo test",
                "syscall",
            ]
        ):
            detected_domains.add("systems_cli")

        # 10. Security Incident Response & Audit
        if any(
            w in task_text
            for w in [
                "token leak",
                "breach",
                "cve",
                "incident response",
                "vulnerability",
                "secret leak",
                "exfiltration",
            ]
        ):
            detected_domains.add("security_incident")

        # 11. Pure Testing & Verification
        if any(
            w in task_text
            for w in [
                "run test",
                "verify test",
                "assert",
                "fix test",
                "test suite execution",
                "unit test suite",
            ]
        ) and not any(w in task_text for w in ["poem", "law", "market", "budget", "travel"]):
            detected_domains.add("testing_execution")

        # 12. Software Project Scaffolding & Bootstrap
        # 12. Software Development & Repository Operations
        # Scoped strictly to software artifacts without assuming external project scaffolder
        has_prog_lang = bool(
            re.search(
                r"\b(python|rust|typescript|javascript|golang|cpp|c\+\+|java|c#|sql)\b", task_text
            )
        )
        has_sw_noun = bool(
            re.search(
                r"\b(backend|frontend|api|endpoint|microservice|service|database|server|client|component|algorithm|repo|repository|codebase|workspace)\b",
                task_text,
            )
        )
        has_code_verb = any(
            w in task_text
            for w in [
                "code",
                "implement",
                "develop",
                "build",
                "write",
                "refactor",
                "debug",
                "compile",
                "initialize",
                "bootstrap",
                "setup",
                "\u0e40\u0e02\u0e35\u0e22\u0e19\u0e42\u0e04\u0e49\u0e14",
                "\u0e1e\u0e31\u0e12\u0e19\u0e32",
                "\u0e15\u0e31\u0e49\u0e07\u0e15\u0e49\u0e19",
                "\u0e40\u0e0b\u0e47\u0e15\u0e2d\u0e31\u0e1e",
            ]
        )

        is_software_coding = (
            (has_prog_lang and (has_sw_noun or has_code_verb))
            or (has_sw_noun and has_code_verb)
            or any(
                re.search(pat, task_text)
                for pat in [
                    r"\b(initialize|bootstrap|setup)\s+(new\s+)?(software\s+)?(repo|repository|codebase|app|application|workspace)\b",
                    r"\b(create|setup)\s+(new\s+)?(software\s+)?(repo|repository|codebase|web\s+app)\b",
                    r"\b(\u0e2a\u0e23\u0e49\u0e32\u0e07|\u0e15\u0e31\u0e49\u0e07\u0e15\u0e49\u0e19|\u0e40\u0e0b\u0e47\u0e15\u0e2d\u0e31\u0e1e)\s*(\u0e04\u0e25\u0e31\u0e07\u0e42\u0e04\u0e49\u0e14|\u0e41\u0e2d\u0e1b\u0e1e\u0e25\u0e34\u0e40\u0e04\u0e0a\u0e31\u0e19|\u0e23\u0e30\u0e1a\u0e1a\u0e0b\u0e2d\u0e1f\u0e15\u0e4c\u0e41\u0e27\u0e23\u0e4c)\b",
                ]
            )
            or any(
                w in task_text
                for w in [
                    "write code",
                    "implement api",
                    "backend endpoint",
                    "frontend component",
                    "python script",
                    "rest api",
                    "refactor code",
                    "debug function",
                    "\u0e40\u0e02\u0e35\u0e22\u0e19\u0e42\u0e04\u0e49\u0e14",
                ]
            )
        )
        if is_software_coding:
            detected_domains.add("software_development")

        # 14. Historical, Humanities, Survey Writing
        if (
            any(
                w in task_text
                for w in [
                    "\u0e1a\u0e17\u0e04\u0e27\u0e32\u0e21",
                    "article",
                    "history of",
                    "\u0e1b\u0e23\u0e30\u0e27\u0e31\u0e15\u0e34",
                    "survey of",
                    "overview of",
                    "literature review",
                    "\u0e2a\u0e32\u0e23\u0e04\u0e14\u0e35",
                    "\u0e04\u0e49\u0e19\u0e04\u0e27\u0e49\u0e32",
                    "\u0e2a\u0e37\u0e1a\u0e04\u0e49\u0e19",
                    "humanities survey",
                    "academic inquiry",
                ]
            )
            and "legal_policy" not in detected_domains
        ):
            detected_domains.add("survey_writing")

        # 15. Architecture, Diagramming & Visual Modeling
        if any(
            w in task_text
            for w in [
                "diagram",
                "diagrams",
                "flowchart",
                "sequence diagram",
                "architecture diagram",
                "uml",
                "erd",
                "wireframe",
                "mermaid",
                "excalidraw",
                "drawio",
                "system design",
                "blueprint",
                "\u0e27\u0e32\u0e14\u0e41\u0e1c\u0e19\u0e1c\u0e31\u0e07",
                "\u0e41\u0e1c\u0e19\u0e1c\u0e31\u0e07",
                "\u0e1c\u0e31\u0e07\u0e23\u0e30\u0e1a\u0e1a",
                "\u0e44\u0e14\u0e2d\u0e30\u0e41\u0e01\u0e23\u0e21",
                "\u0e27\u0e32\u0e14 diagram",
                "\u0e1e\u0e34\u0e21\u0e1e\u0e4c\u0e40\u0e02\u0e35\u0e22\u0e27",
                "\u0e2a\u0e16\u0e32\u0e1b\u0e31\u0e15\u0e22\u0e01\u0e23\u0e23\u0e21",
            ]
        ):
            detected_domains.add("architecture_design")

        # Ambiguity / Insufficient Information Check
        words = re.findall(r"\b\w+\b", task_text)
        has_action_signals = any(
            w in task_text
            for w in [
                "\u0e40\u0e02\u0e35\u0e22\u0e19",
                "\u0e08\u0e31\u0e14\u0e17\u0e33",
                "\u0e23\u0e32\u0e22\u0e07\u0e32\u0e19",
                "\u0e2a\u0e23\u0e38\u0e1b",
                "\u0e27\u0e34\u0e40\u0e04\u0e23\u0e32\u0e30\u0e2b\u0e4c",
                "\u0e04\u0e49\u0e19\u0e04\u0e27\u0e49\u0e32",
                "\u0e27\u0e32\u0e07\u0e41\u0e1c\u0e19",
                "write",
                "draft",
                "document",
                "summarize",
                "plan",
                "research",
                "audit",
                "test",
            ]
        )
        has_action_signals = has_action_signals or bool(infer_facets_from_intent(task_text))
        is_ambiguous = (len(detected_domains) == 0 and not has_action_signals) or (
            len(words) < 2 and len(detected_domains) == 0
        )

        if is_ambiguous:
            return {
                "primary_domain": "unspecified",
                "detected_domains": [],
                "task_type": "unspecified",
                "intent": "AMBIGUOUS_OR_UNSPECIFIED",
                "is_software": False,
                "confidence": "LOW",
                "ambiguity_reason": "Task description has insufficient domain signals or context. Clarification recommended.",
            }

        # Multi-domain Hybrid Workflow Resolution
        software_domains = {
            "data_science",
            "graphics_simulation",
            "embedded_firmware",
            "systems_cli",
            "software_development",
            "testing_execution",
        }
        non_software_domains = {
            "creative",
            "legal_policy",
            "market_business",
            "finance_accounting",
            "planning_logistics",
            "survey_writing",
        }

        has_sw = bool(detected_domains.intersection(software_domains))
        has_non_sw = bool(detected_domains.intersection(non_software_domains))

        if has_sw and has_non_sw:
            return {
                "primary_domain": "hybrid",
                "detected_domains": sorted(list(detected_domains)),
                "task_type": "hybrid_workflow",
                "intent": "HYBRID_WORKFLOW",
                "is_software": True,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }

        # Single Domain Intent Mapping
        if "creative" in detected_domains:
            return {
                "primary_domain": "creative",
                "detected_domains": ["creative"],
                "task_type": "creative_authoring",
                "intent": "CREATIVE_WRITING",
                "is_software": False,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }
        if "legal_policy" in detected_domains:
            return {
                "primary_domain": "legal_policy",
                "detected_domains": ["legal_policy"],
                "task_type": "research_inquiry",
                "intent": "LEGAL_POLICY_RESEARCH",
                "is_software": False,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }
        if "market_business" in detected_domains:
            return {
                "primary_domain": "market_business",
                "detected_domains": ["market_business"],
                "task_type": "market_analysis",
                "intent": "MARKET_BUSINESS_ANALYSIS",
                "is_software": False,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }
        if "finance_accounting" in detected_domains:
            return {
                "primary_domain": "finance_accounting",
                "detected_domains": ["finance_accounting"],
                "task_type": "financial_analysis",
                "intent": "FINANCIAL_BUSINESS_ANALYSIS",
                "is_software": False,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }
        if "planning_logistics" in detected_domains:
            return {
                "primary_domain": "planning_logistics",
                "detected_domains": ["planning_logistics"],
                "task_type": "planning_allocation",
                "intent": "PLANNING_LOGISTICS",
                "is_software": False,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }
        if "data_science" in detected_domains:
            return {
                "primary_domain": "data_science",
                "detected_domains": ["data_science"],
                "task_type": "data_modeling",
                "intent": "DATA_SCIENCE_ML",
                "is_software": True,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }
        if "graphics_simulation" in detected_domains:
            return {
                "primary_domain": "graphics_simulation",
                "detected_domains": ["graphics_simulation"],
                "task_type": "simulation_design",
                "intent": "GRAPHICS_INTERACTIVE_SOFTWARE",
                "is_software": True,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }
        if "embedded_firmware" in detected_domains:
            return {
                "primary_domain": "embedded_firmware",
                "detected_domains": ["embedded_firmware"],
                "task_type": "firmware_engineering",
                "intent": "EMBEDDED_FIRMWARE",
                "is_software": True,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }
        if "systems_cli" in detected_domains:
            return {
                "primary_domain": "systems_cli",
                "detected_domains": ["systems_cli"],
                "task_type": "systems_programming",
                "intent": "SYSTEMS_CLI",
                "is_software": True,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }
        if "security_incident" in detected_domains:
            return {
                "primary_domain": "security_incident",
                "detected_domains": ["security_incident"],
                "task_type": "security_response",
                "intent": "SECURITY_INCIDENT_AUDIT",
                "is_software": True,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }
        if "testing_execution" in detected_domains:
            return {
                "primary_domain": "testing_execution",
                "detected_domains": ["testing_execution"],
                "task_type": "quality_verification",
                "intent": "TESTING_EXECUTION",
                "is_software": True,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }
        if "architecture_design" in detected_domains:
            return {
                "primary_domain": "architecture_design",
                "detected_domains": ["architecture_design"],
                "task_type": "architecture_diagramming",
                "intent": "ARCHITECTURE_VISUAL_DESIGN",
                "is_software": True,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }
        if "software_development" in detected_domains:
            return {
                "primary_domain": "software_development",
                "detected_domains": ["software_development"],
                "task_type": "software_engineering",
                "intent": "SOFTWARE_DEVELOPMENT",
                "is_software": True,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }
        if "survey_writing" in detected_domains:
            return {
                "primary_domain": "survey_writing",
                "detected_domains": ["survey_writing"],
                "task_type": "survey_authoring",
                "intent": "SURVEY_WRITING",
                "is_software": False,
                "confidence": "HIGH",
                "ambiguity_reason": "",
            }

        # General Knowledge Task Fallback
        return {
            "primary_domain": "general_knowledge",
            "detected_domains": ["general_knowledge"],
            "task_type": "general_authoring",
            "intent": "GENERAL_KNOWLEDGE_TASK",
            "is_software": False,
            "confidence": "MEDIUM",
            "ambiguity_reason": "",
        }

    def classify_primary_intent(self) -> str:
        """Classifies high-level intent slug for backwards compatibility."""
        return self.classify_context_profile()["intent"]

    def resolve_capabilities(self) -> Dict[str, Any]:
        """Resolves required, recommended, and disqualified capabilities with decoupled domain profiling."""
        profile = self.classify_context_profile()
        intent = profile["intent"]
        scored_caps: Dict[str, Dict[str, Any]] = {}

        # 1. Base keyword and pattern matching against positive task text
        for cap_id, cap_info in UNIVERSAL_CAPABILITIES.items():
            score = 0
            matched_kws = []
            for kw in cap_info["keywords"]:
                is_ascii = kw.isascii()
                pattern = (r"\b" + re.escape(kw) + r"\b") if (is_ascii and " " not in kw) else re.escape(kw)
                if re.search(pattern, self.positive_task):
                    score += 2 if " " in kw else 1
                    matched_kws.append(kw)

            scored_caps[cap_id] = {
                "id": cap_id,
                "name": cap_info["name"],
                "score": score,
                "matched_keywords": matched_kws,
                "description": cap_info["description"],
                "builtin_tool": cap_info["builtin_tool"],
                "classification": "OPTIONAL",
                "confidence": "LOW",
                "rationale": "Base keyword presence",
            }

        # 2. Context Profile Driven Capability Routing
        if intent == "SURVEY_WRITING":
            scored_caps["research"]["score"] += 5
            scored_caps["research"]["classification"] = "REQUIRED"
            scored_caps["research"]["confidence"] = "HIGH"
            scored_caps["research"]["rationale"] = (
                "Task involves researching domain knowledge and literature"
            )

            scored_caps["delivery"]["score"] += 5
            scored_caps["delivery"]["classification"] = "REQUIRED"
            scored_caps["delivery"]["confidence"] = "HIGH"
            scored_caps["delivery"]["rationale"] = (
                "Task requires authoring and delivering structured informational content"
            )

            scored_caps["validation"]["score"] = 0
            scored_caps["validation"]["classification"] = "DISQUALIFIED"
            scored_caps["validation"]["confidence"] = "HIGH"
            scored_caps["validation"]["rationale"] = (
                "Disqualified by negative context: task is an article/historical overview, "
                "not execution of a test runner."
            )

        elif intent == "CREATIVE_WRITING":
            scored_caps["creation"]["score"] += 6
            scored_caps["creation"]["classification"] = "REQUIRED"
            scored_caps["creation"]["confidence"] = "HIGH"
            scored_caps["creation"]["rationale"] = "Authoring literary, poetic, or creative content"

            scored_caps["delivery"]["score"] += 4
            scored_caps["delivery"]["classification"] = "REQUIRED"
            scored_caps["delivery"]["confidence"] = "HIGH"
            scored_caps["delivery"]["rationale"] = (
                "Formatting, stylizing, and delivering creative writing"
            )

            scored_caps["planning"]["score"] += 3
            scored_caps["planning"]["classification"] = "RECOMMENDED"
            scored_caps["planning"]["rationale"] = "Structure, rhythm, and thematic planning"

            scored_caps["validation"]["classification"] = "DISQUALIFIED"
            scored_caps["validation"]["rationale"] = (
                "Disqualified: Creative writing does not require software unit test runners."
            )
            scored_caps["security"]["classification"] = "DISQUALIFIED"
            scored_caps["security"]["rationale"] = (
                "Disqualified: Creative writing does not require AST threat scanning."
            )
            scored_caps["orchestration"]["classification"] = "DISQUALIFIED"
            scored_caps["orchestration"]["rationale"] = (
                "Disqualified: Creative writing does not require CI/CD orchestration."
            )

        elif intent == "LEGAL_POLICY_RESEARCH":
            scored_caps["research"]["score"] += 6
            scored_caps["research"]["classification"] = "REQUIRED"
            scored_caps["research"]["confidence"] = "HIGH"
            scored_caps["research"]["rationale"] = (
                "Legal statute, regulatory compliance, and policy literature research"
            )

            scored_caps["delivery"]["score"] += 5
            scored_caps["delivery"]["classification"] = "REQUIRED"
            scored_caps["delivery"]["confidence"] = "HIGH"
            scored_caps["delivery"]["rationale"] = (
                "Structured legal brief and findings report delivery"
            )

            scored_caps["analysis"]["score"] += 3
            scored_caps["analysis"]["classification"] = "RECOMMENDED"
            scored_caps["analysis"]["rationale"] = (
                "Statutory interpretation and regulatory impact analysis"
            )

            scored_caps["validation"]["classification"] = "DISQUALIFIED"
            scored_caps["validation"]["rationale"] = (
                "Disqualified: Legal research does not require software unit test runners."
            )
            scored_caps["security"]["classification"] = "DISQUALIFIED"
            scored_caps["security"]["rationale"] = (
                "Disqualified: Legal research does not require AST threat scanning."
            )

        elif intent == "MARKET_BUSINESS_ANALYSIS":
            scored_caps["research"]["score"] += 5
            scored_caps["research"]["classification"] = "REQUIRED"
            scored_caps["research"]["confidence"] = "HIGH"
            scored_caps["research"]["rationale"] = (
                "Market data, competitor trends, and industry landscape research"
            )

            scored_caps["analysis"]["score"] += 6
            scored_caps["analysis"]["classification"] = "REQUIRED"
            scored_caps["analysis"]["confidence"] = "HIGH"
            scored_caps["analysis"]["rationale"] = (
                "Market metrics, qualitative synthesis, and competitive analysis"
            )

            scored_caps["delivery"]["score"] += 5
            scored_caps["delivery"]["classification"] = "REQUIRED"
            scored_caps["delivery"]["confidence"] = "HIGH"
            scored_caps["delivery"]["rationale"] = "Market analysis and strategic report delivery"

            scored_caps["planning"]["score"] += 3
            scored_caps["planning"]["classification"] = "RECOMMENDED"

            scored_caps["validation"]["classification"] = "DISQUALIFIED"
            scored_caps["validation"]["rationale"] = (
                "Disqualified: Market analysis does not require software unit test runners."
            )

        elif intent == "FINANCIAL_BUSINESS_ANALYSIS":
            scored_caps["analysis"]["score"] += 6
            scored_caps["analysis"]["classification"] = "REQUIRED"
            scored_caps["analysis"]["confidence"] = "HIGH"
            scored_caps["analysis"]["rationale"] = (
                "Core analytical balance sheet and quantitative modeling"
            )

            scored_caps["delivery"]["score"] += 4
            scored_caps["delivery"]["classification"] = "REQUIRED"
            scored_caps["delivery"]["confidence"] = "HIGH"
            scored_caps["delivery"]["rationale"] = "Executive summaries and report delivery"

            scored_caps["planning"]["score"] += 3
            scored_caps["planning"]["classification"] = "RECOMMENDED"

            scored_caps["validation"]["classification"] = "DISQUALIFIED"
            scored_caps["validation"]["rationale"] = (
                "Disqualified: Non-software financial domain does not use unit test harnesses."
            )
            scored_caps["creation"]["classification"] = "DISQUALIFIED"
            scored_caps["creation"]["rationale"] = (
                "Disqualified: Non-software task does not require code creation."
            )

        elif intent == "PLANNING_LOGISTICS":
            scored_caps["planning"]["score"] += 6
            scored_caps["planning"]["classification"] = "REQUIRED"
            scored_caps["planning"]["confidence"] = "HIGH"
            scored_caps["planning"]["rationale"] = (
                "Itinerary structuring, budget allocation, and task scoping"
            )

            scored_caps["analysis"]["score"] += 5
            scored_caps["analysis"]["classification"] = "REQUIRED"
            scored_caps["analysis"]["confidence"] = "HIGH"
            scored_caps["analysis"]["rationale"] = (
                "Budget calculation, expense estimation, and resource constraints"
            )

            scored_caps["delivery"]["score"] += 4
            scored_caps["delivery"]["classification"] = "REQUIRED"
            scored_caps["delivery"]["confidence"] = "HIGH"
            scored_caps["delivery"]["rationale"] = (
                "Delivery of finalized itinerary and travel budget report"
            )

            scored_caps["research"]["score"] += 3
            scored_caps["research"]["classification"] = "RECOMMENDED"

            scored_caps["validation"]["classification"] = "DISQUALIFIED"
            scored_caps["validation"]["rationale"] = (
                "Disqualified: Logistics/travel budget planning does not require software unit test runners."
            )
            scored_caps["security"]["classification"] = "DISQUALIFIED"
            scored_caps["security"]["rationale"] = (
                "Disqualified: Travel planning does not require AST threat scanning."
            )

        elif intent == "HYBRID_WORKFLOW":
            # Multi-domain hybrid task requires capabilities from both domains
            scored_caps["research"]["score"] += 5
            scored_caps["research"]["classification"] = "REQUIRED"
            scored_caps["research"]["rationale"] = "Domain knowledge and external data research"

            scored_caps["analysis"]["score"] += 5
            scored_caps["analysis"]["classification"] = "REQUIRED"
            scored_caps["analysis"]["rationale"] = (
                "Analytical evaluation across hybrid domain facets"
            )

            scored_caps["creation"]["score"] += 5
            scored_caps["creation"]["classification"] = "REQUIRED"
            scored_caps["creation"]["rationale"] = (
                "Authoring deliverables and code/script components"
            )

            scored_caps["validation"]["score"] += 4
            scored_caps["validation"]["classification"] = "RECOMMENDED"
            scored_caps["validation"]["rationale"] = (
                "Validation of technical and domain deliverables"
            )

        elif intent == "AMBIGUOUS_OR_UNSPECIFIED":
            # Ambiguous tasks must not mandate destructive or rigid tooling
            scored_caps["planning"]["score"] += 4
            scored_caps["planning"]["classification"] = "RECOMMENDED"
            scored_caps["planning"]["confidence"] = "MEDIUM"
            scored_caps["planning"]["rationale"] = (
                "Clarification and scoping recommended due to ambiguous task input"
            )

            scored_caps["research"]["score"] += 3
            scored_caps["research"]["classification"] = "RECOMMENDED"
            scored_caps["research"]["confidence"] = "MEDIUM"
            scored_caps["research"]["rationale"] = "Context survey to determine task requirements"

        elif intent == "DATA_SCIENCE_ML":
            scored_caps["research"]["score"] += 5
            scored_caps["research"]["classification"] = "REQUIRED"
            scored_caps["research"]["rationale"] = (
                "Library exploration, algorithmic references, and research documentation"
            )

            scored_caps["analysis"]["score"] += 6
            scored_caps["analysis"]["classification"] = "REQUIRED"
            scored_caps["analysis"]["rationale"] = (
                "Dataset evaluation, tensor metrics, and data transformation"
            )

            scored_caps["creation"]["score"] += 3
            scored_caps["creation"]["classification"] = "RECOMMENDED"

            scored_caps["design"]["classification"] = "DISQUALIFIED"
            scored_caps["design"]["rationale"] = (
                "Disqualified: Data science model pipeline does not require UI wireframing."
            )

        elif intent == "GRAPHICS_INTERACTIVE_SOFTWARE":
            scored_caps["creation"]["score"] += 5
            scored_caps["creation"]["classification"] = "REQUIRED"
            scored_caps["creation"]["rationale"] = (
                "Interactive software architecture, scene assets, and component implementation"
            )

            scored_caps["validation"]["score"] += 5
            scored_caps["validation"]["classification"] = "REQUIRED"
            scored_caps["validation"]["rationale"] = (
                "Validation suite, regression testing, and visual assertion capabilities"
            )

            scored_caps["analysis"]["score"] += 4
            scored_caps["analysis"]["classification"] = "REQUIRED"
            scored_caps["analysis"]["rationale"] = (
                "Profiling hot paths, memory, and performance analysis"
            )

        elif intent == "EMBEDDED_FIRMWARE":
            scored_caps["orchestration"]["score"] += 5
            scored_caps["orchestration"]["classification"] = "REQUIRED"
            scored_caps["orchestration"]["rationale"] = (
                "Device orchestration, serial communication, and hardware flashing"
            )

            scored_caps["creation"]["score"] += 4
            scored_caps["creation"]["classification"] = "REQUIRED"
            scored_caps["creation"]["rationale"] = "Low-level firmware implementation"

            scored_caps["validation"]["score"] += 3
            scored_caps["validation"]["classification"] = "RECOMMENDED"

        elif intent == "SYSTEMS_CLI":
            scored_caps["analysis"]["score"] += 5
            scored_caps["analysis"]["classification"] = "REQUIRED"
            scored_caps["analysis"]["rationale"] = (
                "Static analysis, code audit, and throughput profiling"
            )

            scored_caps["validation"]["score"] += 5
            scored_caps["validation"]["classification"] = "REQUIRED"
            scored_caps["validation"]["rationale"] = (
                "Automated test suite execution and verification"
            )

            scored_caps["security"]["score"] += 3
            scored_caps["security"]["classification"] = "RECOMMENDED"

        elif intent == "SECURITY_INCIDENT_AUDIT":
            scored_caps["security"]["score"] += 6
            scored_caps["security"]["classification"] = "REQUIRED"
            scored_caps["security"]["confidence"] = "HIGH"
            scored_caps["security"]["rationale"] = "Incident response and credential/secret audit"

            scored_caps["research"]["score"] += 4
            scored_caps["research"]["classification"] = "REQUIRED"
            scored_caps["research"]["rationale"] = (
                "VCS history survey and vulnerability database exploration"
            )

            scored_caps["delivery"]["score"] += 3
            scored_caps["delivery"]["classification"] = "RECOMMENDED"
            scored_caps["delivery"]["rationale"] = "Post-incident analysis and report generation"

        elif intent == "ARCHITECTURE_VISUAL_DESIGN":
            scored_caps["design"]["score"] += 6
            scored_caps["design"]["classification"] = "REQUIRED"
            scored_caps["design"]["confidence"] = "HIGH"
            scored_caps["design"]["rationale"] = (
                "Architecture diagramming, visual system modeling, and schema layout"
            )

            scored_caps["creation"]["score"] += 3
            scored_caps["creation"]["classification"] = "RECOMMENDED"
            scored_caps["creation"]["rationale"] = (
                "Generating diagram source artifacts (Mermaid, SVG, HTML, Draw.io)"
            )

        elif intent == "SOFTWARE_DEVELOPMENT":
            scored_caps["creation"]["score"] += 6
            scored_caps["creation"]["classification"] = "REQUIRED"
            scored_caps["creation"]["rationale"] = (
                "Source code creation, implementation, and modification"
            )

            scored_caps["analysis"]["score"] += 4
            scored_caps["analysis"]["classification"] = "REQUIRED"
            scored_caps["analysis"]["rationale"] = (
                "Architecture analysis, dependency inspection, and code review"
            )

            scored_caps["validation"]["score"] += 3
            scored_caps["validation"]["classification"] = "RECOMMENDED"
            scored_caps["validation"]["rationale"] = (
                "Test suite execution and implementation verification"
            )

        # 3. Open-domain facet inference from functional intent verbs.
        # Applies when no predefined domain profile claimed the task, so novel domains
        # still receive capabilities derived from what the user wants DONE.
        inferred_facets = infer_facets_from_intent(self.positive_task)
        if intent in ("GENERAL_KNOWLEDGE_TASK", "AMBIGUOUS_OR_UNSPECIFIED") and inferred_facets:
            for facet in inferred_facets:
                entry = scored_caps[facet]
                if entry["classification"] == "DISQUALIFIED":
                    continue
                entry["score"] += 3
                entry["classification"] = "REQUIRED"
                entry["confidence"] = "MEDIUM"
                entry["rationale"] = (
                    "Inferred from the task's functional intent (action verbs), independent of any predefined domain"
                )
        elif intent == "GENERAL_KNOWLEDGE_TASK":
            scored_caps["planning"]["classification"] = "RECOMMENDED"
            scored_caps["planning"]["rationale"] = (
                "Scope the task first; no specific action facet could be inferred"
            )

        # 4. Negative clause disqualification (e.g., 'do not run tests' -> disqualify 'validation')
        if self.negative_clauses:
            neg_joined = " ".join(self.negative_clauses)
            for cap_id, cap_info in UNIVERSAL_CAPABILITIES.items():
                extra_kws = ["test", "tests", "testing", "\u0e40\u0e17\u0e2a\u0e15\u0e4c", "\u0e23\u0e31\u0e19\u0e40\u0e17\u0e2a\u0e15\u0e4c"] if cap_id == "validation" else []
                for kw in cap_info["keywords"] + extra_kws:
                    is_ascii = kw.isascii()
                    pat = (r"\b" + re.escape(kw) + r"\b") if (is_ascii and " " not in kw) else re.escape(kw)
                    if re.search(pat, neg_joined):
                        scored_caps[cap_id]["score"] = 0
                        scored_caps[cap_id]["classification"] = "DISQUALIFIED"
                        scored_caps[cap_id]["confidence"] = "HIGH"
                        scored_caps[cap_id]["rationale"] = (
                            f"Explicitly excluded by negative instruction: '{neg_joined}'"
                        )
                        break

        # 5. AI Semantic Thinking Overrides (--facets & --exclude-facets, including open-domain custom facets)
        for ex_facet in self.excluded_facets:
            if ex_facet in scored_caps:
                scored_caps[ex_facet]["score"] = 0
                scored_caps[ex_facet]["classification"] = "DISQUALIFIED"
                scored_caps[ex_facet]["confidence"] = "HIGH"
                scored_caps[ex_facet]["rationale"] = "Explicitly excluded by AI Semantic Thinking step"

        if self.explicit_facets:
            if intent == "AMBIGUOUS_OR_UNSPECIFIED":
                intent = "AI_SEMANTIC_RESOLVED"
                profile["confidence"] = "HIGH"
            for req_facet in self.explicit_facets:
                if req_facet in scored_caps:
                    scored_caps[req_facet]["score"] = max(scored_caps[req_facet]["score"] + 8, 10)
                    scored_caps[req_facet]["classification"] = "REQUIRED"
                    scored_caps[req_facet]["confidence"] = "HIGH"
                    scored_caps[req_facet]["rationale"] = (
                        "Resolved directly via AI Semantic Thinking (Step 0)"
                    )
                else:
                    # Open-domain custom facet outside the 10 standard ones!
                    scored_caps[req_facet] = {
                        "id": req_facet,
                        "name": f"Custom Domain Facet: {req_facet.replace('_', ' ').title()}",
                        "score": 10,
                        "matched_keywords": [req_facet],
                        "description": f"Open-domain capability dynamically resolved by AI Thinking for '{req_facet}'.",
                        "builtin_tool": "Dynamic open-domain web & registry search",
                        "classification": "REQUIRED",
                        "confidence": "HIGH",
                        "rationale": "Open-domain facet dynamically defined by AI Semantic Thinking",
                    }

        # General score-based classification for untouched capabilities
        for cap_id, data in scored_caps.items():
            if data["classification"] in ("REQUIRED", "DISQUALIFIED"):
                continue
            if data["score"] >= 2:
                data["classification"] = "REQUIRED"
                data["confidence"] = "HIGH"
                data["rationale"] = (
                    f"Strong evidence from keywords: {', '.join(data['matched_keywords'])}"
                )
            elif data["score"] == 1:
                data["classification"] = "RECOMMENDED"
                data["confidence"] = "MEDIUM"
                data["rationale"] = (
                    f"Supporting evidence from keyword: {data['matched_keywords'][0]}"
                )

        # Organize into final lists
        required = [c for c in scored_caps.values() if c["classification"] == "REQUIRED"]
        recommended = [c for c in scored_caps.values() if c["classification"] == "RECOMMENDED"]
        disqualified = [c for c in scored_caps.values() if c["classification"] == "DISQUALIFIED"]

        required.sort(key=lambda x: x["score"], reverse=True)
        recommended.sort(key=lambda x: x["score"], reverse=True)

        return {
            "intent": intent,
            "domain": profile["primary_domain"],
            "detected_domains": profile["detected_domains"],
            "task_type": profile["task_type"],
            "is_software": profile["is_software"],
            "domain_class": (
                "unknown"
                if intent == "AMBIGUOUS_OR_UNSPECIFIED"
                else "software"
                if profile["is_software"]
                else "non_software"
            ),
            "confidence": profile["confidence"],
            "ambiguity_reason": profile.get("ambiguity_reason", ""),
            "raw_task": self.raw_task,
            "required_capabilities": required,
            "recommended_capabilities": recommended,
            "disqualified_capabilities": disqualified,
            "all_capabilities": scored_caps,
        }


def generate_agent_search_queries(
    required_caps: List[Dict[str, Any]],
    raw_task: str = "",
    custom_queries: Optional[List[str]] = None,
) -> Dict[str, List[str]]:
    """
    Generates Dual-Track Agent-First Search Queries for unmet capabilities:
    - Track A: Native Agent Skills (SKILL.md, npx skills add, GitHub agent-skills)
    - Track B: Model Context Protocol (MCP servers)
    """
    track_a: List[str] = []
    track_b: List[str] = []

    if custom_queries:
        for q in custom_queries:
            q_clean = q.strip()
            if q_clean:
                track_a.append(f'"{q_clean}" ("SKILL.md" OR "npx skills add" OR "agent skill") site:github.com')
                track_b.append(f'"{q_clean}" ("mcp server" OR "modelcontextprotocol") site:github.com')

    facet_search_terms = {
        "design": ["diagram-design", "architecture diagram", "mermaid", "drawio-skill"],
        "planning": ["prd", "task-planner", "requirements"],
        "research": ["deep-research", "literature-review", "web-research"],
        "creation": ["code-generator", "scaffold", "authoring"],
        "validation": ["visual-qa", "test-runner", "playwright"],
        "analysis": ["code-review", "profiler", "data-analysis"],
        "orchestration": ["workflow-orchestrator", "ci-cd", "subagent"],
        "security": ["security-audit", "secret-scanner", "vulnerability"],
        "delivery": ["changelog", "release-notes", "documentation"],
        "learning": ["post-mortem", "skill-creator", "retrospective"],
    }

    for cap in required_caps:
        cid = cap.get("id", "")
        terms = facet_search_terms.get(cid, [cid.replace("_", " ")])
        primary_term = terms[0]
        secondary_term = terms[1] if len(terms) > 1 else primary_term
        track_a.append(
            f'"{primary_term}" OR "{secondary_term}" ("SKILL.md" OR "npx skills add" OR "agent skill") site:github.com'
        )
        track_b.append(
            f'"{primary_term}" OR "{secondary_term}" ("mcp server" OR "modelcontextprotocol") site:github.com'
        )

    return {"track_a_agent_skills": track_a, "track_b_mcp_servers": track_b}


def match_capabilities_for_context(
    task_description: str,
    explicit_facets: Optional[List[str]] = None,
    excluded_facets: Optional[List[str]] = None,
    explicit_intent: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Returns relevance-sorted matched capabilities for task context.
    Provides uniform access with both 'id' and 'facet' fields.
    """
    resolver = ContextAwareCapabilityResolver(
        task_description,
        explicit_facets=explicit_facets,
        excluded_facets=excluded_facets,
        explicit_intent=explicit_intent,
    )
    res = resolver.resolve_capabilities()
    matched: List[Dict[str, Any]] = []
    for c in res["required_capabilities"]:
        entry = dict(c)
        entry["facet"] = c["id"]
        matched.append(entry)
    for c in res["recommended_capabilities"]:
        entry = dict(c)
        entry["facet"] = c["id"]
        matched.append(entry)
    return matched


def analyze_task_capabilities(
    task_description: str,
    explicit_facets: Optional[List[str]] = None,
    excluded_facets: Optional[List[str]] = None,
    explicit_intent: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Backwards-compatible API returning relevance-sorted matched capabilities."""
    return match_capabilities_for_context(
        task_description,
        explicit_facets=explicit_facets,
        excluded_facets=excluded_facets,
        explicit_intent=explicit_intent,
    )


def parse_skill_metadata(skill_dir: Path) -> Dict[str, Any]:
    """
    Parses skill metadata into structured positive and negative text partitions.
    Separates what the skill is intended for (WHEN TO USE / description)
    from what it is NOT intended for (WHEN NOT TO USE / negative boundaries).
    """
    skill_name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    content = ""
    desc = ""
    if skill_md.exists():
        try:
            content = skill_md.read_text(encoding="utf-8", errors="ignore")
            desc_match = re.search(
                r"description:\s*>?-?\s*\n?(.*?)(?:\n[a-z\-]+:|\n---)", content, re.DOTALL
            )
            if desc_match:
                desc = desc_match.group(1).strip()
        except Exception:
            pass

    full_text = f"{desc}\n{content}"

    # Extract negative trigger contexts (what the skill explicitly excludes)
    neg_patterns = [
        r"(?:when not to use|do not use for|not for|excludes|never use for|do not use when)[:\s]+(.*?)(?:\n\s*[a-z\-]+:|\n---|\n\n|\.|$)",
        r"(?:do not use|not recommended for)[:\s]+(.*?)(?:\.|\n|$)",
        r"(?:does not|do not|never)\s+(?:design|create|generate|scaffold|implement|build)\s+(.*?)(?:\n|\.|$)",
    ]
    negative_parts: List[str] = []
    for pat in neg_patterns:
        for m in re.finditer(pat, full_text, re.IGNORECASE):
            extracted = m.group(1).strip().lower()
            if extracted and extracted not in ("none", "n/a"):
                negative_parts.append(extracted)
                # Preserve the complete exclusion clause so its action verb is
                # removed from positive matching as well as recorded as a boundary.
                negative_parts.append(m.group(0).strip().lower())

    negative_text = " ".join(negative_parts)

    # Positive context comprises skill name, frontmatter description (excluding negative boundary clause)
    positive_text = f"{skill_name.replace('-', ' ')} {desc}".lower()
    for neg_phrase in negative_parts:
        positive_text = positive_text.replace(neg_phrase, "")

    return {
        "name": skill_name,
        "path": skill_dir,
        "positive_text": positive_text,
        "negative_text": negative_text,
        "raw_description": desc,
    }


def _declared_skill_scope_exclusions() -> List[str]:
    """Read caller-declared skill exclusions from this skill's own instructions."""
    skill_doc = Path(__file__).resolve().parent.parent / "SKILL.md"
    try:
        content = skill_doc.read_text(encoding="utf-8")
    except OSError:
        return []
    patterns = (
        r"do not invoke,\s*hand off to,\s*or depend on a ([a-z0-9][a-z0-9_-]*) skill",
        r"do not invoke or depend on ([a-z0-9][a-z0-9_-]*) skills",
    )
    exclusions = []
    for pattern in patterns:
        exclusions.extend(m.group(1).replace("-", " ").casefold() for m in re.finditer(pattern, content, re.IGNORECASE))
    return exclusions


def _matches_scope_exclusion(skill_name: str, exclusions: List[str]) -> bool:
    """Match declared skill categories by normalized token roots, not fixed names."""
    candidate_tokens = [token for token in re.split(r"[^a-z0-9]+", skill_name.casefold()) if token]
    for exclusion in exclusions:
        excluded_tokens = [token for token in re.split(r"[^a-z0-9]+", exclusion.casefold()) if token]
        if not excluded_tokens:
            continue
        matched = all(
            any(a == b or a.startswith(b[:7]) or b.startswith(a[:7]) for b in candidate_tokens)
            for a in excluded_tokens
        )
        if matched:
            return True
    return False


def map_installed_skills_to_capabilities(installed_skills_dirs: List[Path]) -> Dict[str, List[str]]:
    """
    Dynamically maps installed skills into capability facets based on real metadata inspection.
    Never relies on hardcoded canonical skill names.
    Applies positive vs negative trigger discernment and ranks skills by relevance score.
    """
    capability_map: Dict[str, List[str]] = {k: [] for k in UNIVERSAL_CAPABILITIES}

    # Pre-parse metadata once per canonical directory and skill identity. Discovery
    # roots can overlap (workspace/global/vendor paths), so preserve first-root
    # precedence and avoid returning duplicate skill names to downstream selectors.
    parsed_skills = []
    seen_paths = set()
    seen_names = set()
    for sdir in installed_skills_dirs:
        if not sdir.is_dir():
            continue
        try:
            canonical_path = sdir.resolve()
        except OSError:
            canonical_path = sdir.absolute()
        if canonical_path in seen_paths:
            continue
        seen_paths.add(canonical_path)
        metadata = parse_skill_metadata(sdir)
        identity = metadata.get("name") or sdir.name
        identity = str(identity).strip().casefold()
        if identity in seen_names:
            continue
        seen_names.add(identity)
        parsed_skills.append(metadata)

    scope_exclusions = _declared_skill_scope_exclusions()

    for cap_id, cap_info in UNIVERSAL_CAPABILITIES.items():
        scored_candidates: List[Tuple[str, int]] = []

        for meta in parsed_skills:
            if _matches_scope_exclusion(meta["name"], scope_exclusions):
                continue

            # 1. Negative boundary check: does the skill explicitly exclude this capability?
            neg_matches = [
                kw
                for kw in cap_info["keywords"]
                if re.search(r"\b" + re.escape(kw) + r"\b", meta["negative_text"])
            ]
            if neg_matches:
                # Disqualified by explicit negative boundary
                continue

            # 2. Positive matching: name matches give high score (+3), description matches give (+1)
            name_text = meta["name"].replace("-", " ").lower()
            name_matches = [
                kw
                for kw in cap_info["keywords"]
                if re.search(r"\b" + re.escape(kw) + r"\b", name_text)
            ]
            pos_matches = [
                kw
                for kw in cap_info["keywords"]
                if re.search(r"\b" + re.escape(kw) + r"\b", meta["positive_text"])
            ]

            total_matches = len(set(name_matches + pos_matches))
            if total_matches >= 1:
                score = (len(name_matches) * 3) + len(pos_matches)
                scored_candidates.append((meta["name"], score))

        # Rank candidates by relevance score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        capability_map[cap_id] = [name for name, _ in scored_candidates]

    return capability_map


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Context-aware capability resolution and intent classifier"
    )
    parser.add_argument("task", nargs="*", help="Task description to analyze")
    task = " ".join(parser.parse_args().task)
    resolver = ContextAwareCapabilityResolver(task)
    res = resolver.resolve_capabilities()

    print("================================================================================")
    print("      CONTEXT-AWARE CAPABILITY RESOLUTION & INTENT CLASSIFIER                   ")
    print("================================================================================")
    print(f"Task       : {task or '[none supplied]'}")
    print(f"Intent     : {res['intent']}\n")

    print("Required Capabilities:")
    for c in res["required_capabilities"]:
        print(f"  [x] {c['name']} (Score: {c['score']}, Confidence: {c['confidence']})")
        print(f"      Rationale: {c['rationale']}")
        print(f"      Builtin  : {c['builtin_tool']}")

    if res["recommended_capabilities"]:
        print("\nRecommended Supporting Capabilities:")
        for c in res["recommended_capabilities"]:
            print(f"  [+] {c['name']} (Score: {c['score']}) -> {c['rationale']}")

    if res["disqualified_capabilities"]:
        print("\nDisqualified (Negative Context Matched):")
        for c in res["disqualified_capabilities"]:
            print(f"  [-] {c['name']} -> {c['rationale']}")

    print("================================================================================")


if __name__ == "__main__":
    main()
