#!/usr/bin/env python3
"""
audit_engine.py - Generic 20-Category Scaffolding Auditor
Part of the 'project-scaffolder' skill.

Rule 1 & Rule 2 Compliance:
- Evaluates compliance against StackAdapter contract.
- Zero stack-specific if/else branches.
- Respects N/A exemptions defined in the active adapter.
"""

import re
import subprocess
from pathlib import Path
from typing import List

from core.contract import AuditItemResult, StackAdapter
from core.io_utils import check_crlf_files


def run_audit(
    target_path: Path, adapter: StackAdapter, topology: str = "unknown"
) -> List[AuditItemResult]:
    """Evaluates workspace against 20 scaffolding categories via Adapter contract."""
    results: List[AuditItemResult] = []
    na_set = set(adapter.get_na_categories())
    mandatory_set = set(adapter.get_mandatory_categories())

    def record(num: int, pillar: str, name: str, status: str, details: str):
        if num in na_set:
            status = "NOT APPLICABLE"
        elif num not in mandatory_set:
            details = (
                f"Optional finding (excluded from score): {details}"
                if status == "FAIL"
                else "Not selected as mandatory by the active profile"
            )
            status = "NOT APPLICABLE"
        results.append(
            AuditItemResult(num=num, pillar=pillar, name=name, status=status, details=details)
        )

    # --- PILLAR A: Project Foundation ---
    # 01. Domain & Stack Alignment
    record(
        1,
        "A. Project Foundation",
        "Domain & Stack Alignment",
        "NOT VERIFIED",
        f"Profile selected by marker evidence: {adapter.domain.upper()}/{adapter.stack_id.upper()} ({adapter.display_name}); user intent/alignment was not confirmed",
    )

    # 02. Project & Engine Configuration (Delegated to Adapter)
    has_cfg, cfg_msg = adapter.check_config_manifest(target_path)
    record(
        2,
        "A. Project Foundation",
        "Project & Engine Configuration",
        "NOT VERIFIED" if has_cfg else "FAIL",
        cfg_msg + (" (presence only; validity not checked)" if has_cfg else ""),
    )

    # 03. Asset & Resource Management
    if 3 in na_set:
        record(
            3,
            "A. Project Foundation",
            "Asset & Resource Management",
            "NOT APPLICABLE",
            "Profile explicitly exempts specialized binary asset management",
        )
    elif not adapter.get_gitattributes_lfs_patterns():
        record(
            3,
            "A. Project Foundation",
            "Asset & Resource Management",
            "NOT VERIFIED",
            "Profile declares no LFS patterns; project asset requirements were not assessed",
        )
    else:
        gitattr = target_path / ".gitattributes"
        has_lfs = gitattr.exists() and "filter=lfs" in gitattr.read_text(
            encoding="utf-8", errors="ignore"
        )
        record(
            3,
            "A. Project Foundation",
            "Asset & Resource Management",
            "NOT VERIFIED" if has_lfs else "FAIL",
            "LFS rule is present; tracked asset coverage and Git LFS operation were not verified"
            if has_lfs
            else "Expected Git LFS rules are missing",
        )

    # --- PILLAR B: Architecture ---
    # 04. Separation of Concerns
    dir_candidates = [p for p in target_path.iterdir() if p.is_dir() and not p.name.startswith(".")]
    record(
        4,
        "B. Architecture",
        "Separation of Concerns",
        "NOT VERIFIED",
        f"Found {len(dir_candidates)} top-level directories; boundaries and dependency direction were not analyzed",
    )

    # 05. Modular Boundaries (Delegated to Adapter)
    if 5 in na_set:
        record(
            5,
            "B. Architecture",
            "Modular Assembly / Boundaries",
            "NOT APPLICABLE",
            "Single package module architecture",
        )
    else:
        has_boundary, boundary_msg = adapter.check_module_boundaries(target_path, topology)
        record(
            5,
            "B. Architecture",
            "Modular Assembly / Boundaries",
            "NOT VERIFIED" if has_boundary else "FAIL",
            boundary_msg
            + ("; static presence is not dependency validation" if has_boundary else ""),
        )

    # 06. Architecture & Coding Standards
    has_editorconfig = (target_path / ".editorconfig").exists()
    has_agents_rules = False
    if (target_path / "AGENTS.md").exists():
        txt = (target_path / "AGENTS.md").read_text(encoding="utf-8", errors="ignore")
        has_agents_rules = (
            "Coding" in txt
            or "Rules" in txt
            or "Universal Line Endings" in txt
            or "Conventions" in txt
        )
    record(
        6,
        "B. Architecture",
        "Architecture & Coding Standards",
        "NOT VERIFIED" if (has_editorconfig or has_agents_rules) else "FAIL",
        "Guidance files exist; consistency with the selected architecture was not reviewed"
        if (has_editorconfig or has_agents_rules)
        else "No coding-standard guidance files found",
    )

    # --- PILLAR C: Quality Assurance ---
    # 07. Smoke Tests
    test_files = [
        p
        for p in target_path.glob("**/*")
        if p.is_file()
        and ("test" in p.name.lower() or "spec" in p.name.lower())
        and not any(k in str(p) for k in [".git", "Library", "node_modules", ".venv"])
    ]
    record(
        7,
        "C. Quality Assurance",
        "Smoke Tests (Runner Verification)",
        "NOT VERIFIED" if test_files else "FAIL",
        f"Found {len(test_files)} possible test source file(s); source inspection is not a test execution"
        if test_files
        else "No candidate test source files found",
    )

    # 08. Multi-Tier QA Strategy
    has_tiered = (
        any(
            "unit" in str(p).lower()
            or "integration" in str(p).lower()
            or "editmode" in str(p).lower()
            for p in test_files
        )
        or len(test_files) >= 1
    )
    record(
        8,
        "C. Quality Assurance",
        "Multi-Tier QA Strategy",
        "NOT VERIFIED" if has_tiered else "FAIL",
        "Test files found; tier coverage and execution were not verified",
    )

    # 09. Error Handling & Runtime Logging
    agents_file = target_path / "AGENTS.md"
    record(
        9,
        "C. Quality Assurance",
        "Error Handling & Runtime Logging",
        "NOT VERIFIED",
        "Keyword presence in AGENTS.md is not enough to verify logging/error behavior",
    )

    # --- PILLAR D: Development Workflow ---
    # 10. Pre-commit Hooks
    pc_cfg = target_path / ".pre-commit-config.yaml"
    record(
        10,
        "D. Development Workflow",
        "Pre-commit Hooks",
        "NOT VERIFIED" if pc_cfg.exists() else "FAIL",
        ".pre-commit-config.yaml present; hook execution was not performed by this audit"
        if pc_cfg.exists()
        else ".pre-commit-config.yaml is missing",
    )

    # 11. Git Hygiene & Strict LF
    crlf_files = check_crlf_files(target_path)
    unreadable_line_endings = [item for item in crlf_files if item.startswith("UNREADABLE: ")]
    actual_crlf_files = [item for item in crlf_files if not item.startswith("UNREADABLE: ")]
    line_ending_status = (
        "NOT VERIFIED" if unreadable_line_endings else ("FAIL" if actual_crlf_files else "PASS")
    )
    line_ending_details = (
        "Unable to inspect line endings: " + ", ".join(unreadable_line_endings[:5])
        if unreadable_line_endings
        else (
            f"{len(actual_crlf_files)} file(s) with CRLF detected"
            if actual_crlf_files
            else "Strict LF verified across all text files"
        )
    )
    record(
        11,
        "D. Development Workflow",
        "Git Hygiene (Strict LF)",
        line_ending_status,
        line_ending_details,
    )

    # 12. GitHub Community & CI Parity
    ci_file = target_path / ".github" / "workflows" / "ci.yml"
    record(
        12,
        "D. Development Workflow",
        "GitHub Community & CI Parity",
        "NOT VERIFIED" if ci_file.exists() else "FAIL",
        "CI workflow exists; command parity with local hooks was not compared"
        if ci_file.exists()
        else "GitHub Actions CI pipeline is missing",
    )

    # 13. Build & Deployment Pipeline
    build_cmds = adapter.get_build_commands()
    if 13 in na_set:
        record(
            13,
            "D. Development Workflow",
            "Build Pipeline",
            "NOT APPLICABLE",
            "No compilation step required for this stack",
        )
    elif not build_cmds:
        record(
            13,
            "D. Development Workflow",
            "Build Pipeline",
            "FAIL",
            "No build command is declared by the selected profile",
        )
    else:
        record(
            13,
            "D. Development Workflow",
            "Build Pipeline",
            "NOT VERIFIED",
            f"Build command configured but not executed: {' && '.join(build_cmds)}",
        )

    # --- PILLAR E: AI Operations ---
    # 14. Operational Runbook
    record(
        14,
        "E. AI Operations",
        "Operational Runbook (AGENTS.md)",
        "NOT VERIFIED" if agents_file.exists() else "FAIL",
        "AGENTS.md exists; scope and accuracy of its operational instructions were not reviewed"
        if agents_file.exists()
        else "AGENTS.md is missing",
    )

    # 15. Operational Logbook
    logbook_dir = target_path / "logbook"
    current_log = logbook_dir / "current.md"
    if logbook_dir.is_symlink() or current_log.is_symlink() or not current_log.is_file():
        logbook_status = "FAIL"
        logbook_details = "logbook/current.md is missing, is not a regular file, or crosses a symlink"
    else:
        try:
            has_content = current_log.stat().st_size > 0
        except OSError as exc:
            logbook_status = "NOT VERIFIED"
            logbook_details = f"logbook/current.md metadata could not be read safely: {type(exc).__name__}"
        else:
            if not has_content:
                logbook_status = "FAIL"
                logbook_details = "logbook/current.md is empty; no operational log data was found"
            else:
                logbook_status = "NOT VERIFIED"
                logbook_details = (
                    "logbook/current.md is non-empty, but append-only behavior and "
                    "preservation of prior records cannot be established from file presence/content alone"
                )
    record(
        15,
        "E. AI Operations",
        "Operational Logbook (Append-Only)",
        logbook_status,
        logbook_details,
    )

    # --- PILLAR F: Project Management ---
    # 16. Changelog Tracking
    changelog = target_path / "CHANGELOG.md"
    record(
        16,
        "F. Project Management",
        "Changelog Tracking",
        "NOT VERIFIED" if changelog.exists() else "FAIL",
        "CHANGELOG.md exists; format and update policy were not checked"
        if changelog.exists()
        else "CHANGELOG.md is missing",
    )

    # 17. Tailored Documentation Suite
    docs_dir = target_path / "Docs"
    has_docs = docs_dir.exists() and any(docs_dir.glob("*.md"))
    record(
        17,
        "F. Project Management",
        "Tailored Documentation Suite",
        "NOT VERIFIED" if has_docs else "FAIL",
        "Markdown exists under Docs/; relevance and completeness were not assessed"
        if has_docs
        else "No Markdown documentation found under Docs/",
    )

    # --- PILLAR G: Performance & Security ---
    # 18. Scoped Performance & Resource Profiling (Universal / Non-game-biased)
    if 18 in na_set:
        record(
            18,
            "G. Performance & Security",
            "Scoped Performance & Resource Profiling",
            "NOT APPLICABLE",
            "Domain does not mandate strict zero-allocation / hardware profiling",
        )
    else:
        record(
            18,
            "G. Performance & Security",
            "Scoped Performance & Resource Profiling",
            "NOT VERIFIED",
            "Performance constraints are relevant, but no measurements or profiling evidence were collected",
        )

    # 19. Security & Secret Hygiene
    tracked_sensitive = []
    git_dir = target_path / ".git"
    if git_dir.exists():
        try:
            listed = subprocess.run(
                ["git", "ls-files", "-z"],
                cwd=target_path,
                capture_output=True,
                check=True,
                timeout=10,
                shell=False,
            )
            paths = listed.stdout.decode("utf-8", errors="replace").split("\0")
            sensitive_tokens = (".env", "credentials", "secret", "id_rsa", ".pem", ".p12", ".pfx")
            tracked_sensitive = [
                p
                for p in paths
                if p
                and any(token in Path(p).name.lower() for token in sensitive_tokens)
                and not Path(p).name.lower().endswith((".example", ".sample", ".template"))
            ]
            sec_status = "FAIL" if tracked_sensitive else "NOT VERIFIED"
            sec_details = (
                f"Potentially sensitive tracked paths: {', '.join(tracked_sensitive[:5])}"
                if tracked_sensitive
                else "No sensitive filenames found in Git index; file contents were not secret-scanned"
            )
        except (OSError, subprocess.SubprocessError) as exc:
            sec_status, sec_details = "NOT VERIFIED", f"Git index inspection unavailable: {exc}"
    else:
        sec_status, sec_details = (
            "NOT VERIFIED",
            "No Git index available for tracked-file inspection",
        )
    record(19, "G. Performance & Security", "Security & Secret Hygiene", sec_status, sec_details)

    # --- PILLAR H: Documentation Standards ---
    # 20. Markdown Standards
    md_files = list(target_path.glob("**/*.md"))
    has_checkboxes = True
    has_emojis = False
    md_read_error = False
    emoji_pattern = re.compile(r"[\U0001F000-\U0001FAFF\U0001F1E6-\U0001F1FF\u2600-\u27BF]")
    for mf in md_files:
        if any(part in mf.parts for part in [".git", "node_modules", "Library", ".venv"]):
            continue
        try:
            mtxt = mf.read_text(encoding="utf-8", errors="ignore")
            if emoji_pattern.search(mtxt):
                has_emojis = True
            for line in mtxt.splitlines():
                if re.search(r"\b(?:TODO|FIXME)\b", line, re.IGNORECASE) and not re.match(
                    r"^\s*- \[ \] ", line
                ):
                    has_checkboxes = False
                    break
        except (OSError, UnicodeError):
            md_read_error = True

    md_status = "NOT VERIFIED" if md_read_error else ("FAIL" if has_emojis or not has_checkboxes else "PASS")
    if md_read_error:
        md_msg = "One or more Markdown files could not be read; standards result is incomplete"
    elif has_emojis:
        md_msg = "Discovered emojis in markdown documentation"
    elif not has_checkboxes:
        md_msg = "Found actionable TODO text without checkbox formatting"
    else:
        md_msg = "Static scan found no configured emoji patterns or malformed TODO checklists"
    record(
        20,
        "H. Documentation Standards",
        "Markdown Standards (Zero Emojis / Checkboxes)",
        md_status,
        md_msg,
    )

    return results
