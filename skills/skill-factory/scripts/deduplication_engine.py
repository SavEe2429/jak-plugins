#!/usr/bin/env python3
"""
deduplication_engine.py - 4-Gate Anti-Sprawl & Skill Deduplication Engine
Part of the 'skill-factory' meta-skill.

Implements the official 4-Gate Architecture from references/skill_deduplication_framework.md:
- Gate 1: Semantic & Intent Overlap Analysis (>= 80% Discard, 50%-79% Extend/Merge, <50% Proceed)
- Gate 2: Entity Lifecycle Ownership (Consolidate around Domain Entities vs Action-verb micro-skills)
- Gate 3: Complexity & Return on Investment (ROI) (>= 3 deterministic steps; reject trivial one-liners)
- Gate 4: Negative Trigger Boundary (Ensure unambiguous positive/negative activation boundaries)
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Domain entity mappings for lifecycle consolidation (seed reference vocabulary)
COMMON_ENTITY_CLUSTERS: Dict[str, Set[str]] = {
    "git": {
        "git",
        "commit",
        "branch",
        "repo",
        "repository",
        "hygiene",
        "vcs",
        "worktree",
        "stash",
        "checkout",
    },
    "unity": {
        "unity",
        "scene",
        "prefab",
        "asset",
        "gameobject",
        "shader",
        "asmdef",
        "canvas",
        "package",
    },
    "docker": {"docker", "container", "image", "dockerfile", "compose"},
    "testing": {"test", "tdd", "smoke", "unit", "spec", "assert", "coverage", "fixture"},
    "linting": {"lint", "linter", "format", "formatter", "prettier", "style", "check"},
    "database": {"db", "database", "migration", "schema", "sql", "postgres", "sqlite", "query"},
    "telemetry": {"telemetry", "metric", "metrics", "dashboard", "log", "tracing", "stats"},
    "release": {"release", "changelog", "version", "tag", "publish", "ship"},
}

GENERIC_ACTION_VERBS = {
    "skill",
    "skills",
    "tool",
    "tools",
    "util",
    "utils",
    "helper",
    "helpers",
    "cleaner",
    "manager",
    "runner",
    "generator",
    "creator",
    "checker",
    "scanner",
    "builder",
    "deployer",
    "handler",
    "service",
    "manage",
    "clean",
    "run",
    "generate",
    "create",
    "check",
    "scan",
    "build",
    "deploy",
    "handle",
    "existing",
    "another",
    "unbounded",
    "custom",
    "test",
    "mock",
}

# Generic abstract entities that must not be used as sole domain entity owners for lifecycle consolidation
GENERIC_ABSTRACT_ENTITIES = {
    "data",
    "file",
    "files",
    "code",
    "app",
    "text",
    "doc",
    "docs",
    "document",
    "documents",
    "system",
    "systems",
    "project",
    "projects",
    "item",
    "items",
    "task",
    "tasks",
    "workflow",
    "workflows",
    "user",
    "users",
    "content",
    "contents",
    "info",
    "information",
    "asset",
    "assets",
    "page",
    "pages",
    "tool",
    "tools",
    "util",
    "utils",
    "resource",
    "resources",
    "element",
    "elements",
    "object",
    "objects",
    "theme",
    "themes",
}

STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "in",
    "on",
    "at",
    "to",
    "for",
    "with",
    "by",
    "from",
    "about",
    "into",
    "through",
    "during",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "this",
    "that",
    "these",
    "those",
    "my",
    "your",
    "his",
    "her",
    "its",
    "our",
    "their",
    "of",
    "as",
    "if",
}


def extract_keywords(text: str) -> Set[str]:
    """Extracts normalized significant tokens from text, filtering stop words and splitting hyphenated slugs."""
    clean_text = text.lower().replace("-", " ").replace("_", " ")
    words = re.findall(r"\b[a-zA-Z0-9]{3,}\b", clean_text)
    return {w for w in words if w not in STOP_WORDS}


def _strip_negative_clause(text: str) -> str:
    """Removes 'WHEN NOT TO USE:' and negative boundary clauses before entity extraction."""
    return re.split(
        r"(?:when not to use|do not use for|not for|excludes|never use for)[:\s]",
        text,
        flags=re.IGNORECASE,
    )[0]


def extract_domain_entities(name: str, desc: str = "") -> Set[str]:
    """
    Extracts primary domain entities dynamically from skill name and description
    without relying exclusively on pre-configured entity lists.
    Identifies subject nouns (e.g. 'postgres', 'unity', 'git', 'auth', 'docker')
    by parsing slug tokens and filtering out generic action verbs and generic abstract entities.
    """
    clean_name = _strip_negative_clause(name)
    clean_desc = _strip_negative_clause(desc)
    entities = set()
    parts = [p.lower() for p in re.findall(r"[a-zA-Z0-9]{3,}", clean_name)]
    for p in parts:
        if (
            p not in GENERIC_ACTION_VERBS
            and p not in GENERIC_ABSTRACT_ENTITIES
            and p not in STOP_WORDS
        ):
            entities.add(p)

    desc_tokens = extract_keywords(clean_desc)
    for cluster_id, cluster_tokens in COMMON_ENTITY_CLUSTERS.items():
        if desc_tokens.intersection(cluster_tokens):
            entities.add(cluster_id)

    return entities


def extract_entity_cluster(name_or_desc: str) -> Optional[str]:
    """
    Identifies primary domain entity dynamically from text.
    Checks dynamic domain entity tokens in deterministic order, prioritizing the skill slug.
    """
    clean_text = _strip_negative_clause(name_or_desc)
    ordered_parts = [
        p.lower()
        for p in re.findall(r"[a-zA-Z0-9]{3,}", clean_text)
        if p.lower() not in GENERIC_ACTION_VERBS
        and p.lower() not in GENERIC_ABSTRACT_ENTITIES
        and p.lower() not in STOP_WORDS
    ]
    if ordered_parts:
        for ent in ordered_parts:
            if ent in COMMON_ENTITY_CLUSTERS:
                return ent
        return ordered_parts[0]

    tokens = extract_keywords(clean_text)
    for cluster_id, cluster_tokens in COMMON_ENTITY_CLUSTERS.items():
        if tokens.intersection(cluster_tokens):
            return cluster_id
    return None


def calculate_semantic_overlap(candidate_text: str, existing_text: str) -> float:
    """
    Computes lexical / token overlap analysis (Jaccard similarity + Containment coefficient).
    Note: This is an exact lexical token-overlap metric, not an embedding-based neural semantic model.
    - Jaccard similarity of significant keywords
    - Overlap coefficient (containment of candidate inside existing capability)
    """
    cand_tokens = extract_keywords(candidate_text)
    exist_tokens = extract_keywords(existing_text)

    if not cand_tokens or not exist_tokens:
        return 0.0

    intersection = cand_tokens.intersection(exist_tokens)
    union = cand_tokens.union(exist_tokens)

    jaccard = len(intersection) / len(union) if union else 0.0
    # Overlap coefficient: measures if candidate is completely subsumed by existing (or vice versa)
    containment = len(intersection) / min(len(cand_tokens), len(exist_tokens))

    # If almost all tokens of one are contained in the other (>= 85%), it is subsumed
    if containment >= 0.85:
        score = containment
    else:
        # Balanced lexical score: 40% Jaccard + 60% Containment
        score = (0.4 * jaccard) + (0.6 * containment)

    return round(score, 3)


# Backward-compatible alias clarifying token/lexical nature
calculate_lexical_token_overlap = calculate_semantic_overlap


class DeduplicationEngine:
    """Evaluates candidate skills across all 4 deduplication gates."""

    def __init__(self, installed_skills_dirs: Optional[List[Path]] = None):
        self.skills_dirs = installed_skills_dirs or []

    def load_skill_info(self, skill_dir: Path) -> Dict[str, Any]:
        """Loads metadata, description, and keywords from an existing skill."""
        skill_md = skill_dir / "SKILL.md"
        content = ""
        desc = ""
        allowed_tools = []
        if skill_md.exists():
            try:
                content = skill_md.read_text(encoding="utf-8", errors="ignore")
                # Extract description from frontmatter
                desc_match = re.search(
                    r"description:\s*>?-?\s*\n?(.*?)(?:\n[a-z\-]+:|\n---)", content, re.DOTALL
                )
                if desc_match:
                    desc = desc_match.group(1).strip()
            except Exception:
                pass

        return {
            "name": skill_dir.name,
            "path": skill_dir,
            "description": desc or content[:300],
            "full_content": content,
            "tokens": extract_keywords(skill_dir.name + " " + desc + " " + content[:600]),
            "entity": extract_entity_cluster(skill_dir.name + " " + desc),
        }

    def extract_workflow_steps_count(self, text: str) -> int:
        """Estimates deterministic workflow steps count from text structure."""
        # 1. Numbered lists (e.g., 1. 2. 3. or Step 1, Step 2)
        numbered = re.findall(r"(?:^|\n)\s*(?:\d+[\.\)]|step\s+\d+[:\.]?)", text, re.IGNORECASE)
        if len(numbered) >= 2:
            return len(numbered)

        # 2. Sequential transition keywords (first, then, next, verify, finally)
        seq_keywords = ["first", "then", "next", "after that", "subsequently", "verify", "finally"]
        found_seq = sum(
            1 for kw in seq_keywords if re.search(r"\b" + kw + r"\b", text, re.IGNORECASE)
        )
        if found_seq >= 2:
            return found_seq + 1

        # 3. Action checklists (- [ ])
        checklists = re.findall(r"(?:^|\n)\s*-\s*\[\s*\]", text)
        if len(checklists) >= 2:
            return len(checklists)

        return 1

    def extract_skill_triggers(self, skill_info: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """Extracts positive triggers and negative boundary phrases from skill metadata."""
        content = skill_info.get("full_content", "")
        desc = skill_info.get("description", "")

        pos_triggers = []
        neg_boundaries = []

        # Parse 'WHEN TO USE:' and 'WHEN NOT TO USE:'
        pos_match = re.search(r"WHEN TO USE:?\s*([^-\n]+)", desc + " " + content, re.IGNORECASE)
        if pos_match:
            pos_triggers.extend([t.strip() for t in pos_match.group(1).split(",") if t.strip()])

        neg_match = re.search(
            r"WHEN NOT TO USE:?\s*([^-\n\.]+)", desc + " " + content, re.IGNORECASE
        )
        if neg_match:
            neg_boundaries.extend([t.strip() for t in neg_match.group(1).split(",") if t.strip()])

        # If not structured, use skill name and tokens
        if not pos_triggers:
            pos_triggers.append(skill_info["name"].replace("-", " "))

        return pos_triggers, neg_boundaries

    def evaluate_candidate(
        self,
        candidate_name: str,
        candidate_description: str,
        steps_count: Optional[int] = None,
        positive_triggers: Optional[List[str]] = None,
        negative_triggers: Optional[List[str]] = None,
        ignore_exact_name: bool = False,
    ) -> Dict[str, Any]:
        """
        Runs candidate through all 4 gates.
        Returns detailed diagnostic report and actionable decision.
        """
        report: Dict[str, Any] = {
            "candidate_name": candidate_name,
            "decision": "PASS_SYNTHESIS",
            "action": "SYNTHESIZE",
            "gate1_semantic_overlap": {"status": "PASS", "max_overlap": 0.0, "matched_skill": None},
            "gate2_entity_lifecycle": {"status": "PASS", "entity": None, "owner_skill": None},
            "gate3_complexity_roi": {
                "status": "PASS",
                "steps": 0,
                "reason": "Sufficient deterministic depth",
            },
            "gate4_negative_boundary": {
                "status": "PASS",
                "collision_detected": False,
                "conflicting_triggers": [],
            },
            "reasons": [],
        }

        # Check existing skills
        existing_skills = [self.load_skill_info(sd) for sd in self.skills_dirs if sd.is_dir()]

        # Exact Name Collision Check
        if not ignore_exact_name:
            for s in existing_skills:
                if s["name"] == candidate_name:
                    report["decision"] = "REJECT"
                    report["action"] = "DISCARD"
                    report["gate1_semantic_overlap"] = {
                        "status": "FAIL",
                        "max_overlap": 1.0,
                        "matched_skill": s["name"],
                        "reason": f"Exact name collision with existing skill '{s['name']}'",
                    }
                    report["reasons"].append(
                        f"Skill '{candidate_name}' already exists at {s['path']}"
                    )
                    return report
        else:
            # Exclude self when explicitly overwriting same-named skill folder
            existing_skills = [s for s in existing_skills if s["name"] != candidate_name]

        # -------------------------------------------------------------
        # Gate 1: Semantic & Intent Overlap Analysis
        # -------------------------------------------------------------
        max_overlap = 0.0
        most_similar_skill = None

        cand_text = f"{candidate_name} {candidate_description}"

        for s in existing_skills:
            s_text = f"{s['name']} {s['description']}"
            overlap = calculate_semantic_overlap(cand_text, s_text)
            if overlap > max_overlap:
                max_overlap = overlap
                most_similar_skill = s

        report["gate1_semantic_overlap"]["max_overlap"] = max_overlap

        if max_overlap >= 0.80 and most_similar_skill:
            report["gate1_semantic_overlap"]["status"] = "FAIL"
            report["gate1_semantic_overlap"]["matched_skill"] = most_similar_skill["name"]
            report["gate1_semantic_overlap"]["reason"] = (
                f"Overlap is {max_overlap * 100:.1f}% (>= 80%) with existing skill '{most_similar_skill['name']}'. "
                "Capability is already subsumed."
            )
            report["decision"] = "REJECT"
            report["action"] = "REUSE_EXISTING"
            report["reasons"].append(
                f"Gate 1 Reject: Redundant capability with '{most_similar_skill['name']}' ({max_overlap * 100:.1f}% overlap). Guide agent to use existing skill."
            )
            return report

        if 0.50 <= max_overlap < 0.80 and most_similar_skill:
            report["gate1_semantic_overlap"]["status"] = "MERGE_CANDIDATE"
            report["gate1_semantic_overlap"]["matched_skill"] = most_similar_skill["name"]
            report["gate1_semantic_overlap"]["reason"] = (
                f"Overlap is {max_overlap * 100:.1f}% (50%-79%) with '{most_similar_skill['name']}'. "
                "Candidate should extend the existing skill rather than creating a separate skill directory."
            )
            report["decision"] = "CONSOLIDATE"
            report["action"] = "EXTEND_MERGE"
            report["reasons"].append(
                f"Gate 1 Extension: Functional overlap with '{most_similar_skill['name']}'. Recommend adding subcommand/script to existing skill."
            )

        # -------------------------------------------------------------
        # Gate 2: Entity Lifecycle Ownership
        # -------------------------------------------------------------
        cand_entities = extract_domain_entities(candidate_name, candidate_description)
        cand_entity = extract_entity_cluster(cand_text)
        report["gate2_entity_lifecycle"]["entity"] = cand_entity

        for s in existing_skills:
            s_entities = extract_domain_entities(s["name"], s["description"])
            shared = cand_entities.intersection(s_entities)
            cand_overlap = calculate_semantic_overlap(cand_text, f"{s['name']} {s['description']}")

            # Consolidate only if they share a specific, bounded domain entity AND
            # the existing skill is a recognized lifecycle owner for that entity
            if shared and s["name"] != candidate_name:
                matched_ent = next(iter(shared))
                if matched_ent in GENERIC_ABSTRACT_ENTITIES:
                    continue

                s_name_lower = s["name"].lower()
                suite_suffixes = (
                    "-tools",
                    "-manager",
                    "-lifecycle",
                    "-suite",
                    "-orchestrator",
                    "-platform",
                )
                is_lifecycle_owner = (
                    s_name_lower.endswith(suite_suffixes)
                    or s_name_lower == matched_ent
                    or s_name_lower in (f"{matched_ent}{sfx}" for sfx in suite_suffixes)
                )

                if is_lifecycle_owner:
                    report["gate2_entity_lifecycle"]["status"] = "CONSOLIDATE"
                    report["gate2_entity_lifecycle"]["owner_skill"] = s["name"]
                    report["gate2_entity_lifecycle"]["entity"] = matched_ent
                    report["gate2_entity_lifecycle"]["reason"] = (
                        f"Existing skill '{s['name']}' already owns lifecycle for entity '{matched_ent}'. "
                        f"Consolidate candidate '{candidate_name}' into existing '{s['name']}' rather than fragmenting into micro-skills."
                    )
                    report["decision"] = "CONSOLIDATE"
                    report["action"] = "EXTEND_MERGE"
                    report["reasons"].append(
                        f"Gate 2 Ownership: Entity '{matched_ent}' is owned by '{s['name']}'. Consolidate candidate as a subcommand."
                    )
                    break

        if report["action"] == "EXTEND_MERGE":
            return report

        # -------------------------------------------------------------
        # Gate 3: Complexity & Return on Investment (ROI)
        # -------------------------------------------------------------
        # Analyze workflow depth dynamically instead of assuming a default
        estimated_steps = self.extract_workflow_steps_count(candidate_description)
        actual_steps = steps_count if steps_count is not None else estimated_steps
        report["gate3_complexity_roi"]["steps"] = actual_steps

        desc_words = candidate_description.strip().split()
        if len(desc_words) < 6 or actual_steps < 3:
            report["gate3_complexity_roi"]["status"] = "REJECT_TRIVIAL"
            report["gate3_complexity_roi"]["reason"] = (
                f"Task has insufficient deterministic complexity (steps: {actual_steps}, words: {len(desc_words)}). "
                "One-line commands and single-step tasks must be documented in AGENTS.md, not synthesized as skills."
            )
            report["decision"] = "KEEP_AS_INSTRUCTION"
            report["action"] = "SKIP"
            report["reasons"].append(
                "Gate 3 ROI: Trivial one-liner/single-step workflow. Document in AGENTS.md."
            )
            return report

        # -------------------------------------------------------------
        # Gate 4: Negative Trigger Boundary & Collision Analysis
        # -------------------------------------------------------------
        # 1. Trigger Collision Check against existing skills
        cand_triggers = list(positive_triggers or [])
        if not cand_triggers:
            cand_triggers.append(candidate_name.replace("-", " "))

        collisions = []
        for s in existing_skills:
            exist_pos, _ = self.extract_skill_triggers(s)
            for c_trig in cand_triggers:
                for e_trig in exist_pos:
                    # Check substring or high token overlap
                    c_tokens = extract_keywords(c_trig)
                    e_tokens = extract_keywords(e_trig)
                    if (
                        c_tokens
                        and e_tokens
                        and (
                            c_tokens == e_tokens
                            or c_trig.lower() in e_trig.lower()
                            or e_trig.lower() in c_trig.lower()
                        )
                    ):
                        collisions.append(
                            {
                                "candidate_trigger": c_trig,
                                "conflicting_skill": s["name"],
                                "existing_trigger": e_trig,
                            }
                        )

        if collisions:
            report["gate4_negative_boundary"]["status"] = "COLLISION_DETECTED"
            report["gate4_negative_boundary"]["collision_detected"] = True
            report["gate4_negative_boundary"]["conflicting_triggers"] = collisions
            report["decision"] = "RESOLVE_COLLISION"
            report["action"] = "DISAMBIGUATE"
            report["reasons"].append(
                f"Gate 4 Trigger Collision: Trigger '{collisions[0]['candidate_trigger']}' conflicts with existing skill '{collisions[0]['conflicting_skill']}'. Disambiguate boundaries."
            )
            return report

        # 2. Strict Negative Boundary Requirement (must have meaningful content, not empty placeholder)
        def check_meaningful_negative_boundary(desc: str, neg_trigs: Optional[List[str]]) -> bool:
            if neg_trigs:
                valid = [
                    t.strip()
                    for t in neg_trigs
                    if len(t.strip()) >= 3
                    and t.strip().lower() not in ("none", "n/a", "no", "nothing", "not applicable")
                ]
                if valid:
                    return True

            desc_lower = desc.lower()
            markers = [
                "when not to use",
                "do not use for",
                "do not use when",
                "not for",
                "never use for",
            ]
            for m in markers:
                idx = desc_lower.find(m)
                if idx != -1:
                    remainder = desc_lower[idx + len(m) :].lstrip(" :\t--*")
                    clause = re.split(r"\n\s*[a-z\-]+:|\n\n|\.", remainder)[0].strip()
                    tokens = [
                        w
                        for w in re.findall(r"\b[a-z]{3,}\b", clause)
                        if w not in ("none", "applicable", "nothing", "use", "when", "for", "not")
                    ]
                    if len(tokens) >= 2:
                        return True
            return False

        has_negative_boundary = check_meaningful_negative_boundary(
            candidate_description, negative_triggers
        )

        if not has_negative_boundary:
            report["gate4_negative_boundary"]["status"] = "MISSING_NEGATIVE_BOUNDARY"
            report["gate4_negative_boundary"]["reason"] = (
                "Candidate lacks explicit negative trigger boundary. "
                "Declare negative boundary ('when not to use') with meaningful scope boundaries to eliminate model routing ambiguity."
            )
            report["decision"] = "RESOLVE_BOUNDARY"
            report["action"] = "DISAMBIGUATE"
            report["reasons"].append(
                "Gate 4 Boundary: Missing explicit negative trigger boundary ('when not to use')."
            )
            return report

        # Candidate passed all gates!
        report["reasons"].append(
            "Passed all 4 deduplication gates. High ROI, distinct entity, clear boundary."
        )
        return report


def check_4gate_deduplication(
    candidate_name: str,
    candidate_description: str,
    existing_skills_dirs: List[Path],
    steps_count: Optional[int] = None,
    ignore_exact_name: bool = False,
) -> Tuple[bool, str, Optional[str]]:
    """Convenience wrapper maintaining backwards-compatible signature with dynamic step count resolution."""
    engine = DeduplicationEngine(existing_skills_dirs)
    res = engine.evaluate_candidate(
        candidate_name,
        candidate_description,
        steps_count=steps_count,
        ignore_exact_name=ignore_exact_name,
    )

    passed = res["decision"] == "PASS_SYNTHESIS"
    primary_reason = res["reasons"][0] if res["reasons"] else res["decision"]
    matched_target = res["gate1_semantic_overlap"].get("matched_skill") or res[
        "gate2_entity_lifecycle"
    ].get("owner_skill")
    return passed, primary_reason, matched_target
