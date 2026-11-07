#!/usr/bin/env python3
"""
scaffold_skill.py - Universal Agent Capability Lifecycle Orchestrator
Part of the 'skill-factory' meta-skill.

Core Architectural Capabilities:
1. Context Discovery: Identifies workspace, task, and multi-agent runtime environments.
2. Capability Modeling: Maps tasks to the 10 Universal Capabilities (Planning, Research, Design, Creation, Validation, Analysis, Orchestration, Security, Delivery, Learning).
3. Evidence-Based Security: Static AST parsing + regex threat detection + NVIDIA SkillSpector verification.
4. Autonomous Skill Synthesis: 4-Gate Deduplication, safe generation, dry-run, rollback, zero static template dependencies.
5. Optional Readiness Audit: Offers a limited software-oriented audit when explicitly requested.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

# Local imports
sys.dont_write_bytecode = True
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from agent_adapter import AgentEnvironmentAdapter
from capability_composer import CapabilityCompositionEngine
from capability_matcher import (
    analyze_task_capabilities,
    generate_agent_search_queries,
    is_non_software_context,
    map_installed_skills_to_capabilities,
    match_skill_candidates_to_capabilities,
)
from deduplication_engine import check_4gate_deduplication
from security_scanner import scan_all_installed_skills
from skill_synthesizer import synthesize_skill

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def audit_project_infrastructure_evidence(
    repo_path: Path, task_context: str = ""
) -> List[Dict[str, Any]]:
    """
    Audits project infrastructure using 4 contextual statuses:
    EVIDENCED, MISSING, UNKNOWN, NOT APPLICABLE
    Eliminates superficial file-existence false positives and blanket mandates.
    Contextually evaluates whether software engineering checks are applicable.
    """
    checks = []
    task_lower = task_context.lower()
    is_non_software = is_non_software_context(task_context, repo_path)
    is_exploratory = any(
        w in task_lower
        for w in ["explore", "exploratory", "investigate", "prototype", "idea", "experiment"]
    )

    # 1. Dependency Lockfile
    lockfiles = [
        "uv.lock",
        "poetry.lock",
        "package-lock.json",
        "pnpm-lock.yaml",
        "Cargo.lock",
        "go.sum",
        "packages-lock.json",
        "Packages/packages-lock.json",
        "Packages/manifest.json",
        "manifest.json",
        "requirements.txt",
        "pyproject.toml",
    ]
    found_locks = [
        f for f in lockfiles if (repo_path / f).exists() or (repo_path / "frontend" / f).exists()
    ]
    if is_non_software:
        lock_status = "NOT APPLICABLE"
        lock_details = "Not applicable for non-software / analytical deliverables."
    elif found_locks:
        lock_status = "EVIDENCED"
        lock_details = f"Found: {', '.join(found_locks)}"
    else:
        lock_status = "MISSING"
        lock_details = "No version lockfile or manifest detected; dependency locking recommended for software builds."

    checks.append(
        {
            "id": "lockfile",
            "name": "Dependency Lockfile & Manifest",
            "status": lock_status,
            "details": lock_details,
        }
    )

    # 2. Automated Test Framework
    test_files = [
        p
        for p in repo_path.glob("**/*")
        if p.is_file()
        and ("test" in p.name.lower() or "spec" in p.name.lower())
        and not any(k in str(p) for k in [".git", "Library", "node_modules", ".venv"])
    ]
    has_test_results = (
        any(repo_path.glob("Logs/*results*.xml"))
        or any(repo_path.glob(".pytest_cache"))
        or any(repo_path.glob("target/debug/deps/*"))
    )

    if is_non_software:
        t_status = "NOT APPLICABLE"
        t_details = "Automated test fixtures not applicable for non-software domain."
    elif test_files and has_test_results:
        t_status = "EVIDENCED"
        t_details = f"Test fixtures exist ({len(test_files)} files) and execution logs confirmed."
    elif test_files:
        t_status = "UNKNOWN"
        t_details = f"Test fixtures exist ({len(test_files)} files), but test runner execution not yet verified."
    elif is_exploratory:
        t_status = "NOT APPLICABLE"
        t_details = (
            "No automated tests found; relevance depends on the project's deliverables and risk."
        )
    else:
        t_status = "MISSING"
        t_details = (
            "No automated test fixtures found; automated tests recommended for production software."
        )

    checks.append(
        {
            "id": "tests",
            "name": "Automated Testing Framework",
            "status": t_status,
            "details": t_details,
        }
    )

    # 3. Linter & Formatter Configuration
    linters = [
        ".editorconfig",
        ".prettierrc",
        ".markdownlint.json",
        "ruff.toml",
        "biome.json",
        ".eslintrc.json",
    ]
    found_linters = [
        f for f in linters if (repo_path / f).exists() or (repo_path / "frontend" / f).exists()
    ]
    if is_non_software:
        l_status = "NOT APPLICABLE"
        l_details = "Code linters not applicable for document/analytical workflow."
    elif len(found_linters) >= 1:
        l_status = "EVIDENCED"
        l_details = f"Active configs: {', '.join(found_linters)}"
    else:
        l_status = "MISSING"
        l_details = "No linter/formatter config detected."

    checks.append(
        {
            "id": "linter",
            "name": "Code Linter & Formatter Config",
            "status": l_status,
            "details": l_details,
        }
    )

    # 4. Git & Pre-commit Hooks
    has_git = (repo_path / ".git").exists()
    has_hook = (repo_path / ".git" / "hooks" / "pre-commit").exists()
    has_cfg = (repo_path / ".pre-commit-config.yaml").exists()
    if is_non_software:
        g_status = "NOT APPLICABLE"
        g_details = "Pre-commit hooks not required for analytical / document tasks."
    elif has_git and has_hook and has_cfg:
        g_status = "EVIDENCED"
        g_details = "Pre-commit hook installed in .git/hooks/pre-commit and configured."
    elif has_cfg:
        g_status = "UNKNOWN"
        g_details = ".pre-commit-config.yaml present, but hook not installed in .git/hooks/ (run `pre-commit install`)."
    elif is_exploratory:
        g_status = "NOT APPLICABLE"
        g_details = "Pre-commit hooks optional for exploratory prototyping."
    else:
        g_status = "MISSING"
        g_details = "Missing git repository or pre-commit hook configuration."

    checks.append(
        {
            "id": "git_precommit",
            "name": "Git Hygiene & Pre-commit Hooks",
            "status": g_status,
            "details": g_details,
        }
    )

    # 5. Operational AI Context (AGENTS.md)
    has_agents = (repo_path / "AGENTS.md").exists()
    checks.append(
        {
            "id": "ai_context",
            "name": "Operational Runbook (AGENTS.md)",
            "status": "EVIDENCED" if has_agents else "NOT APPLICABLE",
            "details": "AGENTS.md operational runbook active at root"
            if has_agents
            else "Optional operational runbook; not required unless team agent coordination is requested.",
        }
    )

    # 6. Operational Logbook
    has_logbook = (repo_path / "logbook" / "current.md").exists()
    checks.append(
        {
            "id": "logbook",
            "name": "Operational Logbook (Append-Only)",
            "status": "EVIDENCED" if has_logbook else "NOT APPLICABLE",
            "details": "logbook/current.md tracking active"
            if has_logbook
            else "Operational logbook optional.",
        }
    )

    # 7. Domain-Specific Readiness Criteria for Non-Software Deliverables
    if is_non_software:
        has_spec = bool(task_context and len(task_context.split()) >= 2) or any(
            (repo_path / f).exists() for f in ["brief.md", "spec.md", "outline.md", "README.md"]
        )
        checks.append(
            {
                "id": "deliverable_brief",
                "name": "Deliverable Specification & Brief",
                "status": "EVIDENCED" if has_spec else "MISSING",
                "details": "Task specification and outcome scope defined"
                if has_spec
                else "Scope or specification brief not yet established.",
            }
        )

        has_refs = (
            (repo_path / "references").exists()
            or any(repo_path.glob("*.md"))
            or any(repo_path.glob("*.txt"))
            or any(repo_path.glob("*.pdf"))
        )
        checks.append(
            {
                "id": "source_materials",
                "name": "Source Materials & Knowledge Evidence",
                "status": "EVIDENCED" if has_refs else "NOT APPLICABLE",
                "details": "Domain references or source documents located"
                if has_refs
                else "External references optional; ad-hoc authoring.",
            }
        )

    return checks


def _iter_audit_files(repo_path: Path):
    """Yield project files while excluding common generated/vendor directories."""
    excluded = {".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist"}
    for path in repo_path.rglob("*"):
        if path.is_file():
            try:
                relative = path.relative_to(repo_path)
            except ValueError:
                continue
            if not any(part in excluded for part in relative.parts):
                yield path, relative


def audit_data_science_controls(repo_path: Path) -> Dict[str, Any]:
    """Inspect concrete evidence for dataset hashes, dependency locks, and test harnesses."""
    files = list(_iter_audit_files(repo_path))
    hash_evidence = []
    checksum_pattern = re.compile(r"^[0-9a-fA-F]{64}\s+\*?\S+", re.MULTILINE)

    for path, relative in files:
        if path.suffix.lower() in (".sha256", ".sha256sum") or path.name.lower() in (
            "checksums.txt", "sha256sums.txt"
        ):
            try:
                if checksum_pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
                    hash_evidence.append(str(relative))
            except OSError:
                continue
        elif path.suffix.lower() == ".py":
            try:
                source = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "hashlib.sha256" in source and "hexdigest" in source:
                hash_evidence.append(str(relative))

    lock_names = {
        "uv.lock", "poetry.lock", "pipfile.lock", "conda-lock.yml",
        "conda-lock.yaml", "pixi.lock", "pdm.lock"
    }
    lock_evidence = [str(rel) for path, rel in files if path.name.lower() in lock_names]
    test_evidence = [
        str(rel) for path, rel in files
        if path.suffix.lower() in (".py", ".ipynb")
        and ("test" in path.stem.lower() or "spec" in path.stem.lower())
        and any(part.lower() in ("test", "tests") for part in rel.parts)
    ]

    def finding(items):
        return {"status": "EVIDENCED" if items else "MISSING", "evidence": items}

    return {
        "dataset_hashing": finding(hash_evidence),
        "dependency_locking": finding(lock_evidence),
        "test_harness": finding(test_evidence),
    }


def audit_embedded_project_evidence(repo_path: Path) -> Dict[str, Any]:
    """Inspect PlatformIO and hardware/test configuration without requiring a vendor runner."""
    files = list(_iter_audit_files(repo_path))
    platformio = repo_path / "platformio.ini"
    platformio_valid = False
    if platformio.is_file():
        try:
            content = platformio.read_text(encoding="utf-8", errors="ignore")
            platformio_valid = bool(
                re.search(r"^\s*\[env:[^\]]+\]", content, re.MULTILINE)
                and re.search(r"^\s*platform\s*=", content, re.MULTILINE)
                and re.search(r"^\s*board\s*=", content, re.MULTILINE)
            )
        except OSError:
            platformio_valid = False

    hardware_names = {
        "sdkconfig", "idf_component.yml", "CMakeLists.txt", "west.yml"
    }
    hardware_evidence = [
        str(rel) for path, rel in files
        if path.name in hardware_names
        or path.suffix.lower() in (".ioc", ".overlay", ".dts")
        or (
            path.suffix.lower() == ".json"
            and (
                "board" in path.stem.lower()
                or any(part.lower() in ("board", "boards") for part in rel.parts[:-1])
            )
        )
    ]
    test_evidence = [
        str(rel) for path, rel in files
        if path.suffix.lower() in (".c", ".cc", ".cpp", ".h", ".hpp", ".py")
        and ("test" in path.stem.lower() or "spec" in path.stem.lower())
        and any(part.lower() in ("test", "tests") for part in rel.parts)
    ]

    return {
        "platformio_ini": {
            "status": "EVIDENCED" if platformio_valid else "MISSING",
            "evidence": ["platformio.ini"] if platformio_valid else [],
        },
        "hardware_configuration": {
            "status": "EVIDENCED" if hardware_evidence else "MISSING",
            "evidence": hardware_evidence,
        },
        "unit_test_harness": {
            "status": "EVIDENCED" if test_evidence else "MISSING",
            "evidence": test_evidence,
        },
        "runner_policy": "CONTEXTUAL_NO_PROPRIETARY_RUNNER_MANDATE",
    }


def print_infrastructure_report(checks: List[Dict[str, Any]], repo_path: Path):
    print("\n--------------------------------------------------------------------------------")
    print(f"             PROJECT INFRASTRUCTURE AUDIT: {repo_path.name}                   ")
    print("--------------------------------------------------------------------------------")
    missing_count = 0
    for c in checks:
        status = c["status"]
        if status in ("EVIDENCED", "VERIFIED"):
            sym = "[x] EVIDENCED  "
        elif status in ("UNKNOWN", "UNTESTED"):
            sym = "[?] UNKNOWN    "
        elif status == "NOT APPLICABLE":
            sym = "[-] N/A        "
        else:
            sym = "[ ] MISSING    "
            missing_count += 1

        print(f"  {sym} - {c['name']:<35} | {c['details']}")

    if missing_count > 0:
        print("\n[NOTE] Missing items are candidates for review, not automatic defects.")
        print("  Assess relevance against the project's domain, task, and existing conventions.")
    else:
        print("\n[NOTE] This limited filesystem audit found no missing listed items.")


def main():
    parser = argparse.ArgumentParser(
        description="Universal Agent Capability Lifecycle Orchestrator (Skill Factory)"
    )
    parser.add_argument("--target-dir", default=".", help="Workspace target directory")
    parser.add_argument(
        "--agent", "--active-agent", dest="active_agent",
        choices=("gemini", "claude", "codex", "cursor", "copilot", "local"),
        help="Explicit active agent runtime identity (never inferred from installed applications)",
    )
    parser.add_argument("--task", default="", help="Task or workflow description to analyze")
    parser.add_argument(
        "--facets",
        default="",
        help="Comma-separated capability facets resolved by AI Semantic Thinking (supports custom open-domain facets)",
    )
    parser.add_argument(
        "--exclude-facets",
        dest="exclude_facets",
        default="",
        help="Comma-separated capability facets explicitly excluded by AI Semantic Thinking",
    )
    parser.add_argument(
        "--intent",
        default="",
        help="Explicit canonical intent resolved by AI Semantic Thinking",
    )
    parser.add_argument(
        "--queries",
        default="",
        help="Comma-separated custom search keywords generated by AI Semantic Thinking",
    )
    parser.add_argument(
        "--audit", action="store_true", help="Run the optional software-oriented filesystem audit"
    )
    parser.add_argument(
        "--scan", action="store_true", help="Run multi-layer security scan on installed skills"
    )
    parser.add_argument(
        "--match", action="store_true", help="Match capabilities and skills for a task"
    )
    parser.add_argument(
        "--compose", action="store_true", help="Compose verified workflow pipeline and contracts"
    )
    parser.add_argument("--synthesize", action="store_true", help="Synthesize a new skill")
    parser.add_argument("--name", default="", help="Skill slug name for synthesis")
    parser.add_argument("--desc", default="", help="Skill description for synthesis")
    parser.add_argument("--rule", action="append", help="Extra rule bullets for synthesized skill")
    parser.add_argument("--dry-run", action="store_true", help="Preview synthesis without writing")
    parser.add_argument("--update-existing", dest="update_existing", action="store_true", help="Update an existing generated skill after safety checks")
    parser.add_argument(
        "--dedup-override",
        action="store_true",
        help="Explicit administrative override to bypass deduplication gates",
    )
    parser.add_argument("--skills-dir", help="Explicit override for skills directory")
    parser.add_argument(
        "--capabilities-file",
        help="JSON input containing specific Core/Supporting capability records",
    )
    parser.add_argument(
        "--min-capability-match-score",
        type=int,
        default=2,
        help="Minimum lexical evidence score for specific capability matching",
    )
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args()
    workspace_path = Path(args.target_dir).resolve()
    custom_skills_dir = Path(args.skills_dir).resolve() if args.skills_dir else None

    adapter = AgentEnvironmentAdapter(
        workspace_path, custom_skills_dir, active_agent=args.active_agent
    )
    skills_roots = adapter.resolve_skills_discovery_roots()

    if not args.json:
        print("================================================================================")
        print("       SKILL FACTORY: UNIVERSAL AGENT CAPABILITY LIFECYCLE ORCHESTRATOR         ")
        print("================================================================================")
        print(f"Workspace Directory : {workspace_path}")
        print(f"Primary Skills Root : {skills_roots[0] if skills_roots else 'None'}")
        print("--------------------------------------------------------------------------------")

    # Command: Compose Workflow Pipeline
    if args.compose:
        task_desc = args.task.strip() if args.task else ""
        if task_desc:
            matched = analyze_task_capabilities(task_desc)
            if matched:
                cap_ids = [c["id"] for c in matched]
            else:
                from capability_matcher import classify_domain_class

                dom_class = classify_domain_class(task_desc, workspace_path)
                if dom_class == "software":
                    cap_ids = ["research", "analysis", "security", "validation", "delivery"]
                else:
                    cap_ids = ["planning", "research", "delivery"]
        else:
            # When task description is omitted, do not inject canned software prompts
            cap_ids = ["planning", "research", "delivery"]
        composer = CapabilityCompositionEngine()
        flow = composer.compose_workflow_for_task(cap_ids, domain="auto", task_context=task_desc)

        if args.json:
            print(json.dumps(flow, indent=2))
            return

        print("\n--------------------------------------------------------------------------------")
        print("             CAPABILITY WORKFLOW COMPOSITION PIPELINE                           ")
        print("--------------------------------------------------------------------------------")
        if flow.get("requires_more_info"):
            print(
                "[!] NOTICE: Missing required user/environment inputs. Additional information needed."
            )
            print(
                "    Please provide a task description via --task to supply required inputs and validate stages.\n"
            )
        print(f"Workflow Domain       : {flow.get('domain', 'unknown').upper()}")
        print(f"Task Context Status   : {flow.get('task_context_status', 'UNKNOWN')}")
        print(f"Workflow Stages Count : {flow['stages_count']}")
        print(
            f"Contract Continuity   : {'CONTINUOUS' if flow['is_continuous'] else 'INPUT GAP DETECTED'}"
        )
        if flow["missing_inputs"]:
            print("Unmet Input Handoffs  :")
            for m in flow["missing_inputs"]:
                stat_str = f" [{m.get('status')}]" if m.get("status") else ""
                print(
                    f"  - Stage {m['stage']} ({m['contract']}){stat_str} missing: {', '.join(m['unmet_inputs'])}"
                )

        print("\nSequential Pipeline Stages:")
        for s in flow["stages"]:
            if s["status"] == "READY":
                sym = "[x]"
            elif s["status"] == "BLOCKED":
                sym = "[-]"
            else:
                sym = "[!]"
            exec_str = f" (Exec: {s.get('execution_status', 'PENDING')})"
            print(
                f"  Stage {s['stage']:02d}: {sym} {s['name']} ({s['facet'].upper()}) [{s['status']}]{exec_str}"
            )
            print(f"            Inputs : {', '.join(s['inputs'])}")
            print(f"            Outputs: {', '.join(s['outputs'])}")
            print(f"            Verify : {s['verification']}")

        if flow.get("parallel_batches"):
            print("\nParallel Execution Batches (DAG Concurrency):")
            for b_idx, batch in enumerate(flow["parallel_batches"], 1):
                print(f"  Batch {b_idx:02d}: {', '.join(batch)}")

        if flow.get("intent_alignment") and not flow["intent_alignment"].get("aligned", True):
            print("\n[!] Intent Alignment Warning:")
            for w in flow["intent_alignment"].get("warnings", []):
                print(f"  - {w}")

        print("\nMermaid Workflow Diagram:")
        print("```mermaid")
        print(flow["mermaid_diagram"])
        print("```")
        print("================================================================================\n")
        return

    # Command: Security Scan
    if args.scan:
        print("\n[Executing Multi-Layer Security Scan across Installed Skills...]")
        for root in skills_roots:
            if root.exists():
                audit = scan_all_installed_skills(root)
                print(f"\nSkills Root: {root} ({audit['scanned_count']} skills)")
                print(f"Static Threat Findings: {audit['total_findings']}")
                print(f"SkillSpector Status   : {audit['skillspector']['status']}")
                for s in audit["results"]:
                    sym = "[x] CLEAN " if s["status"] == "CLEAN" else "[!] FLAGGED"
                    print(
                        f"  {sym} - {s['skill']:<30} | Files: {s['scanned_files']:<2} | Findings: {len(s['findings'])}"
                    )
        return

    # Command: Synthesize Skill
    if args.synthesize:
        if not args.name or not args.desc:
            print("[ERROR] Synthesis requires --name <slug> and --desc <description>.")
            sys.exit(1)

        # --target-dir selects the workspace root; the active adapter chooses
        # its native install directory. --skills-dir remains the explicit
        # destination override and is handled by AgentEnvironmentAdapter.
        target_install_dir = adapter.resolve_target_install_directory("workspace")
        if (
            args.name == "skill-factory"
            or (target_install_dir / args.name).resolve() == SCRIPT_DIR.parent.resolve()
        ):
            msg = "Security boundary: Cannot synthesize or overwrite 'skill-factory' meta-skill itself."
            if args.json:
                print(
                    json.dumps({"success": False, "error": msg, "stage": "self_preservation_guard"})
                )
            else:
                print(f"[ERROR] {msg}")
            sys.exit(1)
        existing_skills = (
            [p for p in target_install_dir.iterdir() if p.is_dir()]
            if target_install_dir.exists()
            else []
        )

        pass_dedup, dedup_msg, conflicting_skill = check_4gate_deduplication(
            args.name, args.desc, existing_skills, ignore_exact_name=args.update_existing
        )
        if not pass_dedup and not args.dedup_override:
            if args.json:
                print(
                    json.dumps(
                        {
                            "success": False,
                            "error": dedup_msg,
                            "stage": "deduplication",
                            "conflict": conflicting_skill,
                        }
                    )
                )
                sys.exit(1)
            print(f"[DEDUPLICATION REJECTION] {dedup_msg}")
            print(
                f"  -> Recommended: Extend or use existing skill '{conflicting_skill}' instead of creating a micro-skill."
            )
            sys.exit(1)

        if not pass_dedup and args.dedup_override:
            if not args.json:
                print(
                    f"  [!] WARNING: Deduplication gates bypassed via --dedup-override: {dedup_msg}"
                )
        else:
            if not args.json:
                print(f"  [x] Deduplication Gate: {dedup_msg}")

        if not args.json:
            print(f"\n[Synthesizing Skill into {target_install_dir} (Dry-Run={args.dry_run})...]")

        res = synthesize_skill(
            args.name,
            args.desc,
            target_install_dir,
            rules=args.rule,
            dry_run=args.dry_run,
            force=args.update_existing,
        )
        if args.json:
            print(json.dumps(res, indent=2))
            sys.exit(0 if res.get("success") else 1)

        if res.get("success"):
            print("[SUCCESS] Skill synthesis completed cleanly.")
            print(f"  Destination : {res.get('destination')}")
            print(f"  Security    : {res.get('security_status', 'N/A')}")
            for f in res.get("files_created", res.get("files_to_create", [])):
                print(f"  + {f}")
        else:
            print(f"[FAILED] {res.get('error')}")
            sys.exit(1)
        return

    # Default / Audit Mode
    task_desc = args.task or "General task; infer its context from the workspace and user request"
    if not args.json:
        print(f'\nTask Context: "{task_desc}"')

    # Infrastructure audit is opt-in. Its current checks are software-oriented
    # and should not be imposed on other domains or on ordinary capability lookup.
    if args.audit:
        infra_checks = audit_project_infrastructure_evidence(workspace_path, task_context=task_desc)
        print_infrastructure_report(infra_checks, workspace_path)

    # 2. Dynamic Capability Matching (Supports AI Semantic Thinking Step 0 Overrides)
    print("\n--------------------------------------------------------------------------------")
    print("             TASK CAPABILITY REQUIREMENTS & MATCHED AGENT TOOLS                 ")
    print("--------------------------------------------------------------------------------")
    explicit_facets = [f.strip() for f in args.facets.split(",") if f.strip()] if args.facets else None
    excluded_facets = [f.strip() for f in args.exclude_facets.split(",") if f.strip()] if args.exclude_facets else None
    custom_queries = [q.strip() for q in args.queries.split(",") if q.strip()] if args.queries else None

    matched_caps = analyze_task_capabilities(
        task_desc,
        explicit_facets=explicit_facets,
        excluded_facets=excluded_facets,
        explicit_intent=args.intent or None,
    )

    # Collect all installed skills
    installed_skill_dirs = []
    for r in skills_roots:
        if r.exists():
            for d in r.iterdir():
                if d.is_dir():
                    installed_skill_dirs.append(d)

    if args.capabilities_file:
        capability_file = Path(args.capabilities_file).resolve()
        try:
            capability_payload = json.loads(capability_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"Cannot read capability JSON file: {exc}")
        capability_items = (
            capability_payload.get("capabilities", [])
            if isinstance(capability_payload, dict)
            else capability_payload
        )
        if not isinstance(capability_items, list):
            parser.error("Capability JSON must be an array or an object with a 'capabilities' array")
        try:
            capability_result = match_skill_candidates_to_capabilities(
                capability_items,
                installed_skill_dirs,
                min_score=args.min_capability_match_score,
            )
        except ValueError as exc:
            parser.error(str(exc))
        if args.json:
            print(json.dumps(capability_result, indent=2, ensure_ascii=False))
            return
        print("\nSPECIFIC PROJECT CAPABILITY TO INSTALLED SKILL MATCHES")
        for capability in capability_result["capabilities"]:
            print(
                f"\n[{capability['capability_role']}] {capability['capability_id']} "
                f"({capability['level']}) - {capability['capability_statement']}"
            )
            print(f"  Source work items : {', '.join(str(v) for v in capability['source_work_items']) or 'Unknown'}")
            print(f"  Levels            : {', '.join(capability.get('levels', [])) or capability['level']}")
            print(f"  Lifecycle         : {capability['lifecycle_stage']}")
            print(f"  Importance        : {capability['importance']}")
            if capability["candidates"]:
                for candidate in capability["candidates"]:
                    print(
                        f"  - {candidate['resource_name']} [{candidate['match_type']}] "
                        f"score={candidate['score']} | Verification={candidate['verification']} "
                        f"| Practical Test={candidate['practical_test']}"
                    )
                    print(f"      Rationale: {candidate['match_rationale']}")
            else:
                print("  - No matching installed Skill (No Resource Found)")
        print(
            f"\nCandidate matches: {capability_result['candidate_count']} | "
            f"Unmatched Capabilities: {len(capability_result['unmatched_capability_ids'])}"
        )
        return

    cap_to_skills = map_installed_skills_to_capabilities(installed_skill_dirs)
    unmet_caps = []

    for idx, c in enumerate(matched_caps, 1):
        cap_id = c["id"]
        installed_matching = cap_to_skills.get(cap_id, [])
        if not installed_matching:
            unmet_caps.append(c)
        status_str = (
            f"[x] SATISFIED ({', '.join(installed_matching)})"
            if installed_matching
            else "[ ] UNMET (No matching installed skill)"
        )

        print(f"  {idx:02d}. [{c['name']}]")
        print(f"      Status   : {status_str}")
        print(f"      Purpose  : {c['description']}")
        print(f"      Built-in : {c['builtin_tool']}")

    if unmet_caps or custom_queries:
        print("\n--------------------------------------------------------------------------------")
        print("             DUAL-TRACK AGENT-FIRST ONLINE SEARCH QUERIES (FOR UNMET GAPS)      ")
        print("--------------------------------------------------------------------------------")
        queries_dict = generate_agent_search_queries(unmet_caps, task_desc, custom_queries)
        print("  Track A (Native Agent Skills - Highest Priority):")
        for qa in queries_dict["track_a_agent_skills"]:
            print(f"    -> {qa}")
        print("  Track B (MCP Servers - Secondary Priority):")
        for qb in queries_dict["track_b_mcp_servers"]:
            print(f"    -> {qb}")

    # 3. Security Status of Installed Skills
    print("\n--------------------------------------------------------------------------------")
    print("             INSTALLED SKILLS SECURITY & TRUST STATUS                           ")
    print("--------------------------------------------------------------------------------")
    active_root = skills_roots[0] if skills_roots else None
    if active_root and active_root.exists():
        audit = scan_all_installed_skills(active_root)
        print(f"Root: {active_root} ({audit['scanned_count']} skills installed)")
        print(f"Overall Static Threat Status : {audit['overall_status']}")
        print(f"NVIDIA SkillSpector Engine   : {audit['skillspector']['status']}")
    else:
        print("No installed skills directory found to scan.")

    print("\n================================================================================\n")


if __name__ == "__main__":
    main()
