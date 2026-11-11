#!/usr/bin/env python3
"""
skill_synthesizer.py - Atomic Autonomous Skill Synthesis & Rollback Engine
Part of the 'skill-factory' meta-skill.

Capabilities:
1. 100% Self-Contained: Zero external template file dependencies (pure dynamic generation).
2. Skill Name Validation: Enforces strict kebab-case slug standards (e.g., telemetry-dashboard).
3. Strict Path Traversal & Symlink Escape Prevention:
   - Rejects absolute paths, parent directory traversal (..), null bytes, Windows reserved device names, and symlink escapes.
   - Prohibits destination targets that are symbolic links, preventing arbitrary target overwrites.
   - Enforces that every file target strictly resolves within the skill root directory.
4. Staged Isolation:
   - Synthesizes inside an isolated temporary staging directory on the same volume.
   - Target destination is NEVER touched until all validation and security scans pass.
5. True Atomic Directory Replacement & Non-Destructive Rollback:
   - Atomic directory rename / swap.
   - For existing skills with --force: full pre-flight backup; atomically restores if any error occurs.
   - Failsafe data loss prevention: if both deployment and restore fail, the backup is strictly PRESERVED on disk.
   - Obsolete files not in the new set are purged cleanly without leaving partial remnants.
   - For new skills: cleans up all created artifacts on failure, leaving zero partial files behind.
6. Immediate Multi-Layer Security Scan:
   - Runs AST, data-flow, and pattern scans on staged files before committing.
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Local imports
sys.dont_write_bytecode = True
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from security_scanner import scan_skill_directory


def read_skill_version(skill_dir: Optional[Path] = None, default: str = "1.0.0") -> str:
    """Reads metadata.version from SKILL.md frontmatter as the Single Source of Truth (SSOT)."""
    target_dir = Path(skill_dir).resolve() if skill_dir is not None else SCRIPT_DIR.parent
    manifest = target_dir / "SKILL.md"
    if not manifest.is_file():
        return default
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except OSError:
        return default
    if not lines or lines[0].strip() != "---":
        return default
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^\s*version\s*:\s*['\"]?([0-9]+\.[0-9]+\.[0-9]+)['\"]?\s*$", line)
        if m:
            return m.group(1)
    return default


def bump_semver_patch(version_str: str) -> str:
    """Increments the patch component of a semantic version string (e.g. 1.0.0 -> 1.0.1)."""
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", (version_str or "").strip())
    if not m:
        return "1.0.1"
    return f"{int(m.group(1))}.{int(m.group(2))}.{int(m.group(3)) + 1}"


def validate_skill_name(name: str) -> Tuple[bool, str]:
    """Validates skill name adheres to kebab-case slug standard."""
    if not name:
        return False, "Skill name cannot be empty."
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
        return (
            False,
            f"Invalid skill name '{name}'. Must be lowercase kebab-case (e.g. 'telemetry-dashboard').",
        )
    if len(name) < 3 or len(name) > 50:
        return False, f"Skill name length must be between 3 and 50 characters (got {len(name)})."
    return True, "Valid"


def resolve_safe_rel_path(base_dir: Path, rel_path_str: str) -> Path:
    """
    Validates and resolves a relative path strictly within base_dir.
    Eliminates Path Traversal (e.g., ../../escaped.txt) and symlink escapes.

    Raises:
        ValueError: If path is absolute, contains traversal sequences,
                    uses reserved device names, contains symlinks, or resolves outside base_dir.
    """
    if not rel_path_str or not rel_path_str.strip():
        raise ValueError("Relative file path cannot be empty.")

    # 1. Reject null bytes or control characters
    if "\0" in rel_path_str:
        raise ValueError("Security violation: null byte in file path.")

    # 2. Reject absolute paths across platforms
    if os.path.isabs(rel_path_str) or rel_path_str.startswith("/") or rel_path_str.startswith("\\"):
        raise ValueError(f"Security violation: absolute path prohibited: '{rel_path_str}'.")

    # Windows drive letter check (e.g., C:file.txt)
    if re.match(r"^[a-zA-Z]:", rel_path_str):
        raise ValueError(f"Security violation: drive letter prohibited in path: '{rel_path_str}'.")

    # 3. Reject Windows reserved device names (e.g., CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    reserved_names = (
        {"con", "prn", "aux", "nul"}
        | {f"com{i}" for i in range(1, 10)}
        | {f"lpt{i}" for i in range(1, 10)}
    )
    path_obj = Path(rel_path_str)
    for part in path_obj.parts:
        stem = Path(part).stem.lower()
        if stem in reserved_names:
            raise ValueError(
                f"Security violation: Windows reserved device name '{part}' prohibited in path."
            )

    # 4. Normalize path and reject parent traversal tokens
    normalized = os.path.normpath(rel_path_str)
    parts = Path(normalized).parts
    if ".." in parts:
        raise ValueError(
            f"Security violation: directory traversal '..' detected in: '{rel_path_str}'."
        )

    # 5. Resolve absolute target and verify it remains strictly within base_dir
    base_resolved = base_dir.resolve()
    target_candidate = base_resolved / normalized
    target_resolved = target_candidate.resolve()

    try:
        target_resolved.relative_to(base_resolved)
    except ValueError:
        raise ValueError(
            f"Security violation: path '{rel_path_str}' escapes root boundary '{base_dir}'."
        )

    # 6. Check for symlink escapes along existing intermediate path components
    curr = target_candidate
    while curr != base_resolved and curr != curr.parent:
        if curr.is_symlink() or os.path.islink(str(curr)):
            raise ValueError(
                f"Security violation: symlink escape prohibited in path component: '{curr.name}'."
            )
        curr = curr.parent

    return target_resolved


def format_yaml_description(desc: str) -> str:
    """Safely formats task description as an indented YAML folded block scalar to prevent field injection."""
    clean_lines = [line.strip() for line in desc.strip().splitlines() if line.strip()]
    if not clean_lines:
        return "description: ''"
    formatted = ["description: >-"]
    for line in clean_lines:
        formatted.append(f"  {line}")
    return "\n".join(formatted)


def sanitize_tool_identifier(tool: str) -> str:
    """
    Sanitizes and validates an allowed-tools identifier.
    Supports bare tool identifiers (e.g. 'read_file') and scoped tool specifiers
    (e.g. 'Bash(python scripts/*)') while rejecting YAML injection vectors,
    control characters, shell chaining operators, and unscoped wildcards.
    """
    if not tool or not isinstance(tool, str):
        raise ValueError("Tool identifier must be a non-empty string.")
    cleaned = tool.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ("'", '"'):
        cleaned = cleaned[1:-1].strip()
    if re.fullmatch(r"[a-zA-Z0-9_\-]+", cleaned):
        if cleaned.lower() == "all":
            raise ValueError(f"Security violation: Wildcard tool identifier '{tool}' is prohibited.")
        return cleaned
    scoped = re.fullmatch(r"([a-zA-Z0-9_\-]+)\(([a-zA-Z0-9_./:* \-]+)\)", cleaned)
    if scoped:
        specifier = scoped.group(2).strip()
        if specifier and re.search(r"[a-zA-Z0-9]", specifier):
            return f"{scoped.group(1)}({specifier})"
    raise ValueError(
        f"Security violation: Invalid tool identifier '{tool}'. "
        "Allowed tools must be alphanumeric identifiers or scoped 'Tool(specifier)' expressions."
    )


def generate_skill_content(
    skill_name: str,
    task_description: str,
    rules: Optional[List[str]] = None,
    allowed_tools: Optional[List[str]] = None,
    dry_run_verified: bool = False,
    security_scan_verified: Optional[bool] = None,
    lifecycle_status: str = "Generated",
    functional_tests_verified: bool = False,
    runtime_permissions_verified: bool = False,
    version: str = "1.0.0",
) -> str:
    """Generates standard SKILL.md content dynamically without static template files."""
    rule_bullets = (
        "\n".join([f"- [ ] {r}" for r in rules])
        if rules
        else "- [ ] Adhere to project architecture and clean separation of concerns."
    )
    tools_list = allowed_tools if allowed_tools is not None else ["read_file"]
    clean_tools = [sanitize_tool_identifier(t) for t in tools_list]
    tools_yaml = "\n".join(
        [f'  - "{t}"' if any(c in t for c in " ()*:") else f"  - {t}" for t in clean_tools]
    )
    desc_yaml = format_yaml_description(task_description)

    # Lifecycle taxonomy: Generated, Validated, Tested, Verified.
    # Static scanning and a no-write synthesis dry-run do not prove functional behavior.
    sec_verified = bool(security_scan_verified)
    actual_lifecycle = lifecycle_status
    if actual_lifecycle not in ("Generated", "Validated", "Tested", "Verified"):
        actual_lifecycle = "Generated"
    if actual_lifecycle == "Verified":
        if (
            functional_tests_verified
            and dry_run_verified
            and sec_verified
            and runtime_permissions_verified
        ):
            actual_lifecycle = "Verified"
        elif functional_tests_verified:
            actual_lifecycle = "Tested"
        elif sec_verified:
            actual_lifecycle = "Validated"
        else:
            actual_lifecycle = "Generated"
    elif actual_lifecycle == "Tested" and not functional_tests_verified:
        actual_lifecycle = "Validated" if sec_verified else "Generated"
    elif actual_lifecycle == "Validated" and not sec_verified:
        actual_lifecycle = "Generated"

    return f"""---
name: {skill_name}
{desc_yaml}
allowed-tools:
{tools_yaml}
metadata:
  synthesized_by: skill-factory
  version: {version}
  lifecycle_status: {actual_lifecycle}
  dry_run_verified: {str(dry_run_verified).lower()}
  security_scan_verified: {str(sec_verified).lower()}
  functional_tests_verified: {str(bool(functional_tests_verified)).lower()}
  runtime_permissions_verified: {str(bool(runtime_permissions_verified)).lower()}
---

# {skill_name}

## Purpose
{task_description}

## When to Use
- When executing tasks matching the capabilities of `{skill_name}`.
- When deterministic, verified workflows are required.

## When NOT to Use
- Do NOT use for out-of-scope tasks or unrelated domain operations.
- Do NOT use when simpler direct command line or built-in IDE actions suffice.

## Operational Workflow
1. **Context Verification**: Inspect workspace prerequisites and file manifests.
2. **Deterministic Execution**: Execute task via `scripts/run.py` or defined tools.
3. **Evidence Validation**: Validate outputs and assertions.

## Verification Checklist
{rule_bullets}
- [ ] Static security scan confirmed 100% clean with zero critical findings.
"""


def extract_task_stages(task_description: str) -> List[str]:
    """Extracts operational stages from task description bullets or numbered items."""
    stages = []
    if task_description:
        for line in task_description.splitlines():
            line = line.strip()
            m = re.match(r"^(?:\d+[\.\)]|\-|\*)\s*(.+)$", line)
            if m:
                item = m.group(1).strip()
                if not any(
                    item.lower().startswith(p) for p in ["when not to use", "do not use", "not for"]
                ):
                    stages.append(item)
    if not stages:
        stages = [
            "Context & Prerequisite Discovery",
            "Core Domain Operations",
            "Output Verification & Artifact Delivery",
        ]
    return stages


def generate_script_content(skill_name: str, task_description: str = "") -> str:
    """Generates standard executable script with task-specific stages for the synthesized skill."""
    extracted_stages = extract_task_stages(task_description)
    stages_json = json.dumps(
        [{"stage": s, "status": "PENDING_IMPLEMENTATION"} for s in extracted_stages], indent=8
    )

    return f"""#!/usr/bin/env python3
\"\"\"
Main execution script for {skill_name}.
Auto-synthesized by skill-factory.

Capabilities:
1. Environment and prerequisite verification.
2. Structured deterministic workflow execution.
3. Output validation and evidence generation.
\"\"\"

import sys
import argparse
import json
from pathlib import Path


def verify_prerequisites(workspace_path: Path) -> bool:
    \"\"\"Checks workspace prerequisites and accessibility.\"\"\"
    if not workspace_path.exists():
        print(f"[{skill_name}] Error: Workspace path does not exist: {{workspace_path}}", file=sys.stderr)
        return False
    return True


def execute_workflow(workspace_path: Path, dry_run: bool = False) -> dict:
    \"\"\"Executes deterministic workflow stages.\"\"\"
    stages = {stages_json}
    if dry_run:
        print(f"[{skill_name}] [DRY-RUN] Verified execution plan across {{len(stages)}} stages:")
        for s in stages:
            print(f"[{skill_name}]  [PLAN] {{s['stage']}}")
        return {{"status": "DRY_RUN_OK", "stages": stages, "dry_run": True}}

    print(f"[{skill_name}] Executing workflow stages...")
    for s in stages:
        print(f"[{skill_name}]  Stage [{{s['stage']}}] -> {{s['status']}}")

    # Honest execution status: Reports skeleton state until domain logic is provided
    return {{
        "status": "SKELETON_READY",
        "stages": stages,
        "implemented": False,
        "message": "Operational skeleton initialized. To complete automation, implement logic in execute_workflow()."
    }}


def main():
    parser = argparse.ArgumentParser(description="{skill_name} execution script")
    parser.add_argument("--workspace", type=str, default=".", help="Target workspace path")
    parser.add_argument("--check", action="store_true", help="Perform prerequisite and environment checks")
    parser.add_argument("--dry-run", action="store_true", help="Simulate workflow without making persistent changes")
    parser.add_argument("--json", action="store_true", help="Output execution summary as JSON")
    args = parser.parse_args()

    ws = Path(args.workspace).resolve()

    if args.check:
        ok = verify_prerequisites(ws)
        print(f"[{skill_name}] Prerequisite checks: {{'OK' if ok else 'FAILED'}}")
        return 0 if ok else 1

    result = execute_workflow(ws, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(result, indent=2))

    if result["status"] == "SKELETON_READY":
        print(
            f"[{skill_name}] Workflow is a generated skeleton, not an implemented task runner.",
            file=sys.stderr,
        )
        return 2
    return 0 if result["status"] in ("DRY_RUN_OK", "SUCCESS") else 1


if __name__ == "__main__":
    sys.exit(main())
"""


def synthesize_skill(
    skill_name: str,
    task_description: str,
    target_dir: Path,
    rules: Optional[List[str]] = None,
    allowed_tools: Optional[List[str]] = None,
    custom_files: Optional[Dict[str, str]] = None,
    dry_run: bool = False,
    force: bool = False,
    version: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Synthesizes a new self-contained skill safely using staged isolation
    and transactional atomic directory replacement.

    Guarantees:
    - Zero modification of target directory if validation or security checks fail in staging.
    - Symlink Destination Guard: Prohibits target paths that are symlinks/junctions.
    - Path Traversal & Symlink Protection: Rejects any custom_files path escaping skill root.
    - True Atomic Directory Replacement: Renames directory atomically on the same filesystem.
    - Non-Destructive Rollback: If both deployment and restore fail, the backup is strictly
      preserved on disk (never deleted in finally).
    - Existing user files in destination folder are 100% preserved if security fails.
    - Obsolete files are purged cleanly on update when --force is used.
    - New skills are completely removed on error, leaving zero partial garbage.
    """
    # 1. Name validation
    valid, msg = validate_skill_name(skill_name)
    if not valid:
        return {"success": False, "error": msg, "stage": "name_validation"}

    target_dir = Path(target_dir).resolve()
    destination_path = target_dir / skill_name

    # 1.1 Strict Symlink Guard at Destination:
    # Reject immediately if destination itself is a symlink or junction
    if destination_path.is_symlink() or os.path.islink(str(destination_path)):
        return {
            "success": False,
            "error": f"Security violation: Target destination '{destination_path}' is a symbolic link. "
            "Synthesizing into or replacing symlink destinations is strictly prohibited.",
            "stage": "symlink_destination_validation",
            "target_untouched": True,
        }

    # 1.2 Boundary check on self-modification (meta-skill self-preservation)
    if skill_name == "skill-factory" or destination_path.resolve() == SCRIPT_DIR.parent.resolve():
        return {
            "success": False,
            "error": "Security boundary: Cannot synthesize or overwrite 'skill-factory' meta-skill itself.",
            "stage": "self_preservation_guard",
            "target_untouched": True,
        }

    # 1.3 Boundary check on destination resolution
    dest_resolved = destination_path.resolve()
    try:
        dest_resolved.relative_to(target_dir)
    except ValueError:
        return {
            "success": False,
            "error": f"Security violation: Target destination '{destination_path}' resolves outside root '{target_dir}'.",
            "stage": "destination_boundary_validation",
            "target_untouched": True,
        }

    destination_folder = destination_path
    target_exists = destination_folder.exists()

    if target_exists and not force:
        return {
            "success": False,
            "error": f"Destination folder already exists at {destination_folder}. Use --force to update.",
            "stage": "destination_check",
            "destination": str(destination_folder),
        }

    previous_version = read_skill_version(destination_folder, default="1.0.0") if target_exists else None
    target_version = version if version else (bump_semver_patch(previous_version) if target_exists else "1.0.0")

    # 2. Content Preparation
    content = generate_skill_content(
        skill_name,
        task_description,
        rules or [],
        allowed_tools,
        dry_run_verified=dry_run,
        security_scan_verified=False,
        lifecycle_status="Validated" if dry_run else "Generated",
        version=target_version,
    )
    run_py_content = generate_script_content(skill_name, task_description)

    planned_files = {"SKILL.md": content, "scripts/run.py": run_py_content}
    if custom_files:
        planned_files.update(custom_files)

    # 3. Path Traversal & Safety Pre-Flight Check
    for rel_path in planned_files.keys():
        try:
            resolve_safe_rel_path(destination_folder, rel_path)
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "stage": "path_traversal_validation",
                "violating_path": rel_path,
                "target_untouched": True,
            }

    if dry_run:
        # Pre-validate security in isolated temporary staging before confirming dry-run readiness
        with tempfile.TemporaryDirectory(prefix="sf_dry_run_") as td_dry:
            temp_dry_dir = Path(td_dry) / skill_name
            for rel_path, f_content in planned_files.items():
                out_f = temp_dry_dir / rel_path
                out_f.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(f_content, bytes):
                    out_f.write_bytes(f_content)
                else:
                    out_f.write_text(f_content, encoding="utf-8")
            dry_scan = scan_skill_directory(temp_dry_dir)
            if dry_scan["status"] == "FAIL":
                return {
                    "success": False,
                    "error": "Dry-run rejected: Security scanner detected critical vulnerabilities in planned files.",
                    "stage": "dry_run_security_validation",
                    "findings": dry_scan["findings"],
                    "target_untouched": True,
                }

        is_dry_clean = (
            dry_scan["status"] == "CLEAN"
            and dry_scan.get("coverage_status") == "COMPLETE"
            and dry_scan.get("permission_declaration", {}).get("status") == "DECLARED"
        )
        return {
            "success": True,
            "dry_run": True,
            "dry_run_verified": True,
            "version": target_version,
            "previous_version": previous_version,
            "functional_tests_verified": False,
            "runtime_permissions_verified": False,
            "lifecycle_status": "Validated" if is_dry_clean else "Generated",
            "permission_declaration": dry_scan.get("permission_declaration", {}),
            "security_status": dry_scan["status"],
            "security_scan_verified": is_dry_clean,
            "uninspected_files": dry_scan.get("uninspected_files", []),
            "destination": str(destination_folder),
            "files_to_create": [str(destination_folder / p) for p in planned_files.keys()],
            "target_already_exists": target_exists,
        }

    # 4. Stage in an isolated temporary directory on the SAME parent directory/volume
    # This guarantees os.rename() will be an instant atomic operation.
    target_dir.mkdir(parents=True, exist_ok=True)
    unique_token = uuid.uuid4().hex[:8]
    staging_skill_dir = target_dir / f".tmp_{skill_name}_{unique_token}"
    backup_dir: Optional[Path] = None
    deployment_succeeded = False
    restored_successfully = False

    try:
        staging_skill_dir.mkdir(parents=True, exist_ok=True)

        # Write files into staging with strict safe path validation
        for rel_path, f_content in planned_files.items():
            out_file = resolve_safe_rel_path(staging_skill_dir, rel_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            normalized_content = f_content.replace("\r\n", "\n")
            out_file.write_text(normalized_content, encoding="utf-8", newline="\n")

        # 5. Security & Static Analysis on Staging Directory
        scan_res = scan_skill_directory(staging_skill_dir)
        if scan_res["status"] == "FAIL":
            # Security scan failed in staging!
            # The real destination_folder was NEVER touched!
            return {
                "success": False,
                "error": "Synthesis rejected: Security scanner detected critical vulnerabilities in staged code.",
                "stage": "security_validation",
                "findings": scan_res["findings"],
                "destination": str(destination_folder),
                "target_untouched": True,
                "rolled_back": True,
            }

        # 5.1 Update metadata in staging to confirm verified status before deployment
        is_scan_clean = (
            scan_res["status"] == "CLEAN"
            and scan_res.get("coverage_status") == "COMPLETE"
        )
        permission_audit = scan_res.get("permission_declaration", {})
        permission_declared = permission_audit.get("status") == "DECLARED"
        security_verified = is_scan_clean and permission_declared
        lifecycle_stat = "Validated" if security_verified else "Generated"
        verified_skill_md = generate_skill_content(
            skill_name,
            task_description,
            rules or [],
            allowed_tools,
            dry_run_verified=False,
            security_scan_verified=security_verified,
            lifecycle_status=lifecycle_stat,
            functional_tests_verified=False,
            runtime_permissions_verified=False,
            version=target_version,
        )
        (staging_skill_dir / "SKILL.md").write_text(
            verified_skill_md, encoding="utf-8", newline="\n"
        )

        # 6. Atomic Directory Replacement to Target Directory
        if target_exists:
            backup_dir = target_dir / f".backup_{skill_name}_{unique_token}"
            # 1. Instant atomic rename of existing destination to backup
            os.rename(str(destination_folder), str(backup_dir))

            try:
                # 2. Instant atomic rename of staging to destination
                os.rename(str(staging_skill_dir), str(destination_folder))
                deployment_succeeded = True
            except Exception as deploy_err:
                # Rollback on deployment failure: restore original from backup
                try:
                    if not destination_folder.exists() and backup_dir.exists():
                        os.rename(str(backup_dir), str(destination_folder))
                        restored_successfully = True
                except Exception:
                    restored_successfully = False

                if restored_successfully:
                    return {
                        "success": False,
                        "error": f"Deployment failed; atomically restored pre-flight backup: {deploy_err}",
                        "stage": "atomic_deployment",
                        "rolled_back": True,
                    }
                else:
                    # CRITICAL FAIL-SAFE:
                    # Restore failed! Preserve backup_dir completely. DO NOT DELETE in finally!
                    emergency_backup = target_dir / f"emergency_backup_{skill_name}_{unique_token}"
                    try:
                        if backup_dir.exists():
                            os.rename(str(backup_dir), str(emergency_backup))
                            backup_dir = emergency_backup
                    except Exception:
                        pass
                    return {
                        "success": False,
                        "error": f"CRITICAL: Deployment failed ({deploy_err}) AND rollback restore failed. "
                        f"Original files safely preserved in backup at: {backup_dir}",
                        "stage": "atomic_deployment",
                        "rolled_back": False,
                        "emergency_backup": str(backup_dir),
                        "data_loss_prevented": True,
                    }

            # 3. Clean up backup after successful replacement
            if backup_dir.exists():
                shutil.rmtree(str(backup_dir), ignore_errors=True)
        else:
            try:
                # Instant atomic rename of staging to destination
                os.rename(str(staging_skill_dir), str(destination_folder))
                deployment_succeeded = True
            except Exception as deploy_err:
                if destination_folder.exists():
                    shutil.rmtree(str(destination_folder), ignore_errors=True)
                return {
                    "success": False,
                    "error": f"Deployment failed; cleaned up target directory: {deploy_err}",
                    "stage": "atomic_deployment",
                    "cleaned_up": True,
                }

        # Collect created files
        created_files = [str(f) for f in destination_folder.rglob("*") if f.is_file()]

        return {
            "success": True,
            "destination": str(destination_folder),
            "version": target_version,
            "previous_version": previous_version,
            "security_status": scan_res["status"],
            "security_scan_verified": security_verified,
            "permission_declaration": permission_audit,
            "lifecycle_status": lifecycle_stat,
            "functional_tests_verified": False,
            "runtime_permissions_verified": False,
            "dry_run_verified": False,
            "uninspected_files": scan_res.get("uninspected_files", []),
            "files_created": created_files,
            "overwritten": target_exists,
        }

    finally:
        # 1. Clean up temporary staging directory if it still exists
        if staging_skill_dir.exists():
            shutil.rmtree(str(staging_skill_dir), ignore_errors=True)

        # 2. CRITICAL: ONLY delete backup_dir if deployment succeeded OR restore succeeded!
        # If neither succeeded, NEVER delete backup_dir to prevent data loss.
        if (deployment_succeeded or restored_successfully) and backup_dir and backup_dir.exists():
            shutil.rmtree(str(backup_dir), ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description="Skill Synthesizer Engine (Atomic Directory Replacement)"
    )
    parser.add_argument("--name", required=True, help="Skill slug name (e.g. telemetry-dashboard)")
    parser.add_argument("--desc", required=True, help="Skill description")
    parser.add_argument("--target-dir", default="./.agents/skills", help="Target skills directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument(
        "--update-existing",
        dest="update_existing",
        action="store_true",
        help="Update an existing generated skill with atomic replacement",
    )

    args = parser.parse_args()
    res = synthesize_skill(
        args.name,
        args.desc,
        Path(args.target_dir).resolve(),
        dry_run=args.dry_run,
        force=args.update_existing,
    )

    print("================================================================================")
    print("         AUTONOMOUS SKILL SYNTHESIS ENGINE (ATOMIC DEPLOYMENT)                  ")
    print("================================================================================")
    print(f"Status      : {'SUCCESS' if res.get('success') else 'FAILED'}")
    if res.get("dry_run"):
        print("Dry-Run     : True")
        print(f"Planned Dir : {res.get('destination')}")
        print(f"Target Exists: {res.get('target_already_exists')}")
        for f in res.get("files_to_create", []):
            print(f"  + {f}")
    elif res.get("success"):
        print(f"Destination : {res.get('destination')}")
        print(f"Security    : {res.get('security_status')}")
        print(f"Overwritten : {res.get('overwritten')}")
        for f in res.get("files_created", []):
            print(f"  + {f}")
    else:
        print(f"Error       : {res.get('error')}")
        if res.get("target_untouched"):
            print("Safety Note : Target directory was preserved untouched. Zero data loss.")
        if res.get("data_loss_prevented"):
            print(f"Backup Saved: {res.get('emergency_backup')}")
        if res.get("findings"):
            print("Findings    :")
            for finding in res.get("findings", []):
                print(
                    f"  - [{finding.get('severity')}] {finding.get('file')}: {finding.get('issue')}"
                )
    print("================================================================================")


if __name__ == "__main__":
    main()
