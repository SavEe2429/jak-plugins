#!/usr/bin/env python3
"""
io_utils.py - Universal LF, Safe Backup, Hashing, and Conflict Inspector
Part of the 'project-scaffolder' skill.
"""

import hashlib
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


def compute_file_hash(path: Path) -> str:
    """Computes SHA-256 hash of a file."""
    if not path.is_file():
        return ""
    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return ""


def write_lf_file(
    file_path: Path, content: str, dry_run: bool = False, backup: bool = False
) -> bool:
    """Writes a text file strictly with LF line endings and UTF-8 encoding with backup support."""
    if dry_run:
        return True

    file_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")

    if backup and file_path.exists():
        backup_stamp = f"{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns() % 1_000_000_000:09d}"
        backup_dir = file_path.parent / ".backup" / backup_stamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, backup_dir / file_path.name)

    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=file_path.parent,
            prefix=f".{file_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as f:
            temp_name = f.name
            f.write(normalized)
            f.flush()
            os.fsync(f.fileno())
        if file_path.exists():
            os.chmod(temp_name, file_path.stat().st_mode)
        else:
            os.chmod(temp_name, 0o644)
        os.replace(temp_name, file_path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return True


def check_crlf_files(target_path: Path, text_extensions: set = None) -> List[str]:
    """Scans text files in target_path for CRLF line endings, respecting common ignores."""
    if text_extensions is None:
        text_extensions = {
            ".cs",
            ".py",
            ".rs",
            ".go",
            ".ts",
            ".js",
            ".json",
            ".yaml",
            ".yml",
            ".md",
            ".txt",
            ".editorconfig",
            ".gitattributes",
            ".gitignore",
            ".toml",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".zig",
            ".gd",
            ".sh",
            ".cfg",
            ".ini",
            ".xml",
            ".html",
            ".css",
            ".scss",
            ".hlsl",
            ".shader",
            ".bat",
            ".ps1",
        }

    ignore_dirs = {
        ".git",
        "Library",
        "node_modules",
        ".venv",
        "target",
        "bin",
        "obj",
        ".backup",
        "dist",
        "build",
    }
    crlf_files = []
    text_names = {".editorconfig", ".gitattributes", ".gitignore", ".pre-commit-config.yaml"}

    target_resolved = target_path.resolve()
    for p in target_path.rglob("*"):
        if p.is_file() and (p.suffix.lower() in text_extensions or p.name in text_names):
            try:
                rel = p.resolve().relative_to(target_resolved)
            except (OSError, ValueError):
                continue
            # Check if any parent directory in relative path is in ignore_dirs
            if any(part in ignore_dirs for part in rel.parts[:-1]):
                continue
            try:
                with open(p, "rb") as f:
                    if b"\r\n" in f.read():
                        crlf_files.append(str(rel).replace("\\", "/"))
            except OSError:
                crlf_files.append("UNREADABLE: " + str(rel).replace("\\\\", "/"))

    return crlf_files


def inspect_conflicts(target_path: Path, planned_files: List[Tuple[str, str]]) -> Dict[str, Any]:
    """Checks planned files against existing files to detect potential collisions."""
    conflicts = []
    identical = []
    new_files = []

    for rel_path, planned_content in planned_files:
        fpath = target_path / rel_path
        if fpath.exists():
            norm_planned = planned_content.replace("\r\n", "\n").replace("\r", "\n")
            try:
                existing_content = (
                    fpath.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
                    if fpath.is_file()
                    else None
                )
            except UnicodeDecodeError:
                existing_content = None
            if existing_content is not None and existing_content == norm_planned:
                identical.append(rel_path)
            else:
                conflicts.append(
                    {
                        "path": rel_path,
                        "existing_kind": "file" if fpath.is_file() else "directory_or_special",
                        "existing_size": fpath.stat().st_size if fpath.is_file() else None,
                        "new_size": len(norm_planned.encode("utf-8")),
                        "existing_hash": compute_file_hash(fpath),
                    }
                )
        else:
            new_files.append(rel_path)

    return {"new": new_files, "identical": identical, "conflicts": conflicts}
