#!/usr/bin/env python3
"""Shared safe generation engine for legacy adapters and composed plans."""

import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from contracts.models import CompositionPlan, DirectorySpec

from core.contract import FileSpec, StackAdapter
from core.io_utils import inspect_conflicts, write_lf_file


def generate_tailored_gitattributes(lfs_patterns: List[str]) -> str:
    """Generates standard gitattributes with targeted LFS rules."""
    lines = ["# Auto-normalize text line endings to LF", "* text=auto eol=lf"]

    if lfs_patterns:
        lines.append("")
        lines.append("# Git LFS Binary Assets")
        for pat in lfs_patterns:
            lines.append(f"{pat} filter=lfs diff=lfs merge=lfs -text")

    return "\n".join(lines) + "\n"


def scaffold_project(
    target_path: Path,
    adapter: StackAdapter,
    topology: str = "unknown",
    architecture: str = None,
    project_name: str = "MyProject",
    dry_run: bool = False,
    backup: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Executes universal scaffolding sequence using the provided adapter.
    Core contains zero stack-specific branches.
    """
    dirs = adapter.get_directories(topology=topology, architecture=architecture)
    lfs_patterns = adapter.get_gitattributes_lfs_patterns()
    planned_files = [
        FileSpec(
            ".gitattributes",
            generate_tailored_gitattributes(lfs_patterns),
            "Repository line ending and LFS rules",
        )
    ]
    planned_files.extend(
        adapter.get_entry_points(project_name=project_name, architecture=architecture)
    )
    planned_files.extend(
        adapter.get_smoke_tests(project_name=project_name, architecture=architecture)
    )
    planned_files.extend(adapter.get_supporting_files(topology=topology, architecture=architecture))
    ci_content = adapter.get_ci_workflow(project_name=project_name)
    if ci_content:
        planned_files.append(FileSpec(".github/workflows/ci.yml", ci_content, "CI workflow"))
    plan = CompositionPlan(directories=[DirectorySpec(path) for path in dirs], files=planned_files)
    return scaffold_composition_plan(
        target_path, plan, dry_run=dry_run, backup=backup, force=force, project_name=project_name
    )


def scaffold_composition_plan(
    target_path: Path,
    plan: CompositionPlan,
    dry_run: bool = False,
    backup: bool = False,
    force: bool = False,
    project_name: str = "MyProject",
) -> Dict[str, Any]:
    """Apply any composed plan through the shared safe preflight and writer."""
    results = {
        "directories_created": [],
        "files_written": [],
        "new_files": [],
        "conflicts": [],
        "identical": [],
        "blocked": False,
        "dry_run": dry_run,
    }

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", project_name):
        raise ValueError(
            "Project name must be a safe identifier of 1-64 letters, digits, underscores, or hyphens, starting with a letter or underscore."
        )

    dirs = [item.rel_path for item in plan.directories]
    preflight_conflicts = []
    if len(dirs) != len(set(dirs)):
        raise ValueError("Composition plan contains duplicate directory destinations")
    for rel_path in dirs:
        dpath = _safe_target_path(target_path, rel_path)
        if dpath.exists() and not dpath.is_dir():
            preflight_conflicts.append({"path": rel_path, "existing_kind": "file_blocks_directory"})
        elif not _nearest_existing_writable(dpath if dpath.exists() else dpath.parent):
            preflight_conflicts.append({"path": rel_path, "existing_kind": "permission_denied"})

    planned_files: List[FileSpec] = list(plan.files)
    results["planned_files"] = [spec.rel_path for spec in planned_files]
    if plan.conflicts or plan.unresolved:
        raise ValueError(
            "Composition plan is incomplete: %s" % "; ".join(plan.conflicts + plan.unresolved)
        )
    destinations = [spec.rel_path for spec in planned_files]
    if len(destinations) != len(set(destinations)):
        raise ValueError("Composition plan contains duplicate file destinations")
    file_paths = {Path(path) for path in destinations}
    for rel_path in dirs:
        if Path(rel_path) in file_paths:
            raise ValueError(
                "Composition plan assigns a path as both file and directory: %s" % rel_path
            )
    for file_path in file_paths:
        parent = file_path.parent
        while str(parent) not in (".", ""):
            if parent in file_paths:
                raise ValueError(
                    "Composition plan places a file beneath another planned file: %s" % file_path
                )
            parent = parent.parent

    # Validate all planned destinations before creating any directories or files.
    root_resolved = target_path.resolve()
    for spec in planned_files:
        fpath = _safe_target_path(target_path, spec.rel_path)
        parent = fpath.parent
        while parent != root_resolved:
            try:
                parent.relative_to(root_resolved)
            except ValueError:
                break
            if parent.exists() and not parent.is_dir():
                preflight_conflicts.append(
                    {"path": spec.rel_path, "existing_kind": "file_blocks_parent_directory"}
                )
                break
            parent = parent.parent
        nearest = fpath.parent
        while not nearest.exists() and nearest != root_resolved:
            nearest = nearest.parent
        if not _nearest_existing_writable(nearest):
            preflight_conflicts.append(
                {"path": spec.rel_path, "existing_kind": "permission_denied"}
            )
    if preflight_conflicts:
        results["conflicts"] = preflight_conflicts
        results["blocked"] = True
        return results

    conflict_data = inspect_conflicts(target_path, [(f.rel_path, f.content) for f in planned_files])
    results["conflicts"] = conflict_data["conflicts"]
    results["identical"] = conflict_data["identical"]
    results["new_files"] = conflict_data["new"]

    for conflict in results["conflicts"]:
        if conflict.get("existing_kind") == "file" and not os.access(
            _safe_target_path(target_path, conflict["path"]), os.W_OK
        ):
            preflight_conflicts.append(
                {"path": conflict["path"], "existing_kind": "permission_denied"}
            )
    if preflight_conflicts:
        results["conflicts"] = preflight_conflicts
        results["blocked"] = True
        return results

    # Existing different content is preserved by default. --force is the
    # explicit overwrite authorization; overwritten files are always backed up.
    if results["conflicts"] and (
        not force or any(item.get("existing_kind") != "file" for item in results["conflicts"])
    ):
        results["blocked"] = True
        return results

    if dry_run:
        results["directories_created"] = list(dirs)
        return results

    conflicting_paths = {item["path"] for item in results["conflicts"]}
    identical_paths = set(results["identical"])
    pending = [spec for spec in planned_files if spec.rel_path not in identical_paths]
    originals = {}
    for spec in pending:
        fpath = _safe_target_path(target_path, spec.rel_path)
        if fpath.is_file():
            originals[spec.rel_path] = (fpath.read_bytes(), stat.S_IMODE(fpath.stat().st_mode))
        else:
            originals[spec.rel_path] = None

    created_directories = set()
    target_created = not target_path.exists()
    created_gitkeeps = []
    attempted_files = []
    try:
        for rel_path in dirs:
            dpath = _safe_target_path(target_path, rel_path)
            missing = []
            parent = dpath
            while not parent.exists() and parent != root_resolved:
                missing.append(parent)
                parent = parent.parent
            created_directories.update(missing)
            dpath.mkdir(parents=True, exist_ok=True)
            gitkeep = dpath / ".gitkeep"
            if not gitkeep.exists() and not any(dpath.iterdir()):
                created_gitkeeps.append(gitkeep)
                write_lf_file(gitkeep, "\n", dry_run=False)
            results["directories_created"].append(rel_path)

        for spec in pending:
            fpath = _safe_target_path(target_path, spec.rel_path)
            should_backup = force and spec.rel_path in conflicting_paths
            attempted_files.append(spec.rel_path)
            write_lf_file(fpath, spec.content, dry_run=False, backup=backup or should_backup)
            results["files_written"].append(spec.rel_path)
    except (OSError, ValueError, UnicodeEncodeError) as write_error:
        rollback_errors = []
        for rel_path in reversed(attempted_files):
            try:
                fpath = _safe_target_path(target_path, rel_path)
                original = originals.get(rel_path)
                if original is None:
                    if fpath.exists():
                        fpath.unlink()
                else:
                    _restore_file(fpath, original[0], original[1])
            except OSError as exc:
                rollback_errors.append(str(exc))
        for gitkeep in created_gitkeeps:
            try:
                if gitkeep.exists():
                    gitkeep.unlink()
            except OSError as exc:
                rollback_errors.append(str(exc))
        for directory in sorted(
            created_directories, key=lambda path: len(path.parts), reverse=True
        ):
            try:
                directory.rmdir()
            except OSError:
                pass
        if target_created:
            try:
                target_path.rmdir()
            except OSError:
                pass
        if rollback_errors:
            raise RuntimeError(
                "Generation failed and rollback was incomplete: %s" % "; ".join(rollback_errors)
            ) from write_error
        raise

    return results


def _safe_target_path(root: Path, rel_path: str) -> Path:
    """Resolve a generated path and reject absolute paths or traversal."""
    candidate = Path(rel_path)
    if candidate.is_absolute():
        raise ValueError(f"Generated path must be relative: {rel_path}")
    root_resolved = root.resolve()
    probe = root_resolved
    for part in candidate.parts:
        if part in ("", "."):
            continue
        probe = probe / part
        if probe.is_symlink():
            raise ValueError("Generated path crosses an existing symlink: %s" % rel_path)
    target_resolved = (root_resolved / candidate).resolve()
    try:
        target_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"Generated path escapes target directory: {rel_path}") from exc
    return target_resolved


def _nearest_existing_writable(path: Path) -> bool:
    candidate = path
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return candidate.is_dir() and os.access(candidate, os.W_OK)


def _restore_file(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=".%s." % path.name, suffix=".rollback", delete=False
        ) as target:
            temporary = target.name
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
