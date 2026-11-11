"""Release Manager CLI for jak-plugins.

Cross-platform release orchestration and packaging tool providing manifest version
checking and synchronization, bundle zip packaging, changelog promotion, release
notes generation, index updating, and GitHub release body formatting.
"""

## ---------- (01) STANDARD LIBRARY IMPORTS ----------------------------------------- ##
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Tuple

## ---------- (02) THIRD-PARTY IMPORTS ---------------------------------------------- ##
## ---------- (03) LOCAL APPLICATION/LIBRARY-SPECIFIC IMPORTS ----------------------- ##
## ---------- (04) CONSTANTS -------------------------------------------------------- ##
DEFAULT_CHANGELOG_PATH: str = "CHANGELOG.md"
DEFAULT_NOTES_DIR: str = "docs/release-notes"
DEFAULT_NOTES_INDEX: str = "docs/release-notes/README.md"
DEFAULT_CHECKSUMS_PATH: str = "dist/SHA256SUMS.txt"
DEFAULT_RELEASE_BODY_PATH: str = "dist/RELEASE_BODY.md"
MANIFEST_FILES: Tuple[str, ...] = (
    "plugin.json",
    "gemini-extension.json",
    ".claude-plugin/plugin.json",
)
ARCHIVE_EXCLUDED_ROOTS: Tuple[str, ...] = (".git", ".github", "dist", "build", "docs")
ARCHIVE_EXCLUDED_PARTS: Tuple[str, ...] = ("__pycache__", ".pytest_cache", ".ruff_cache")

## ---------- (05) ENUMS ------------------------------------------------------------ ##
# No module-level enums required.

## ---------- (06) CLASS DEFINITIONS ------------------------------------------------ ##
# No module-level classes required.

## ---------- (07) PUBLIC FUNCTIONS ------------------------------------------------- ##
def check_manifests() -> str:
    """Verify all plugin manifest JSON files are valid and share the same version."""
    versions = {}
    for rel_path in MANIFEST_FILES:
        path = Path(rel_path)
        if not path.is_file():
            raise FileNotFoundError(f"Missing required manifest: {rel_path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        version = data.get("version")
        if not isinstance(version, str) or not version.strip():
            raise ValueError(f"Missing or empty 'version' field in {rel_path}")
        versions[rel_path] = version.strip()

    unique_versions = set(versions.values())
    if len(unique_versions) != 1:
        details = ", ".join(f"{name}={ver}" for name, ver in versions.items())
        raise ValueError(f"Plugin manifest version mismatch: {details}")

    resolved_version = next(iter(unique_versions))
    print(f"All plugin manifests match version {resolved_version}")
    return resolved_version


def sync_manifests(version: str) -> None:
    """Synchronize the version field across all plugin manifest JSON files."""
    for rel_path in MANIFEST_FILES:
        path = Path(rel_path)
        if not path.is_file():
            raise FileNotFoundError(f"Missing required manifest: {rel_path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["version"] = version
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Updated version to {version} in {rel_path}")


def build_archive(version: str, out_dir: str = "dist") -> Path:
    """Package the distributable plugin bundle into a zip archive."""
    root = Path.cwd().resolve()
    dest_dir = Path(out_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    archive_path = dest_dir / f"jak-plugins-v{version}.zip"

    file_count = 0
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if not rel.parts:
                continue
            if rel.parts[0] in ARCHIVE_EXCLUDED_ROOTS:
                continue
            if any(part in ARCHIVE_EXCLUDED_PARTS for part in rel.parts):
                continue
            if path.suffix in {".pyc", ".pyo"}:
                continue
            zf.write(path, arcname=rel.as_posix())
            file_count += 1

    print(f"Built bundle archive {archive_path} ({file_count} files)")
    return archive_path


def update_changelog(
    version: str, date: str, changelog_path: str = DEFAULT_CHANGELOG_PATH
) -> None:
    """Promote [Unreleased] section to version header and insert new empty [Unreleased]."""
    path = Path(changelog_path)
    if not path.is_file():
        raise FileNotFoundError(f"{changelog_path} not found")

    content = path.read_text(encoding="utf-8")
    target = "## [Unreleased]"
    replacement = f"## [Unreleased]\n\n## [{version}] - {date}"

    if target not in content:
        raise ValueError("'## [Unreleased]' section not found in CHANGELOG.md")

    path.write_text(content.replace(target, replacement, 1), encoding="utf-8")
    print(f"Promoted [Unreleased] section to [{version}] - {date} in {changelog_path}")


def generate_release_notes(
    version: str,
    changelog_path: str = DEFAULT_CHANGELOG_PATH,
    output_dir: str = DEFAULT_NOTES_DIR,
) -> None:
    """Extract version section from CHANGELOG.md into standalone markdown file."""
    path = Path(changelog_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"v{version}.md"

    if not path.is_file():
        body = f"# Release Notes - v{version}\n\nAutomated release build for version {version}.\n"
    else:
        text = path.read_text(encoding="utf-8")
        pattern = rf"## \[{re.escape(version)}\][^\n]*\n(.*?)(?=\n## \[|\Z)"
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            body = (
                f"# Release Notes - v{version}\n\n"
                f"Automated release build for version {version}.\n"
            )
        else:
            body_content = match.group(1).strip()
            body = f"# Release Notes - v{version}\n\n{body_content}\n"

    out_file.write_text(body, encoding="utf-8")
    print(f"Generated release notes file at {out_file}")


def update_release_notes_index(
    version: str, date: str, index_file: str = DEFAULT_NOTES_INDEX
) -> None:
    """Update release notes index README table with latest version link."""
    path = Path(index_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    header = (
        "# Release Notes Index\n\n"
        "This directory archives standalone release notes for each published version of `jak-plugins`.\n\n"
        "| Version | Release Date | Release Notes Document |\n"
        "| :--- | :--- | :--- |\n"
    )

    if not path.is_file():
        content = header
    else:
        content = path.read_text(encoding="utf-8")
        if "| Version |" not in content:
            content = header + content

    new_row = f"| v{version} | {date} | [v{version}.md](v{version}.md) |"
    if f"v{version}.md" not in content:
        content = content.rstrip() + f"\n{new_row}\n"
        path.write_text(content, encoding="utf-8")
        print(f"Added v{version} to {index_file}")
    else:
        print(f"v{version} already indexed in {index_file}")


def build_release_body(
    version: str,
    notes_file: str = "",
    checksum_file: str = DEFAULT_CHECKSUMS_PATH,
    output_file: str = DEFAULT_RELEASE_BODY_PATH,
) -> None:
    """Build release markdown body combining notes and SHA-256 checksums."""
    if not notes_file:
        notes_file = f"{DEFAULT_NOTES_DIR}/v{version}.md"

    body_parts = []
    notes_path = Path(notes_file)
    if notes_path.is_file():
        body_parts.append(notes_path.read_text(encoding="utf-8").strip())
    else:
        body_parts.append(f"# Release Notes - v{version}\n\nAutomated production release.")

    checksum_path = Path(checksum_file)
    if checksum_path.is_file():
        checksums = checksum_path.read_text(encoding="utf-8").strip()
        body_parts.append(
            f"## Release Verification & Checksums (SHA-256)\n\n```text\n{checksums}\n```"
        )

    final_body = "\n\n".join(body_parts) + "\n"
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(final_body, encoding="utf-8")
    print(f"Generated GitHub release body at {output_file}")


## ---------- (08) PRIVATE FUNCTIONS ------------------------------------------------ ##
def _parse_args() -> argparse.Namespace:
    """Parse CLI release operation subcommands."""
    parser = argparse.ArgumentParser(description="jak-plugins Release Manager CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    subparsers.add_parser("check-manifests")

    p_sync = subparsers.add_parser("sync-manifests")
    p_sync.add_argument("version", help="Version string (e.g. 0.4.0)")

    p_archive = subparsers.add_parser("build-archive")
    p_archive.add_argument("version", help="Version string (e.g. 0.4.0)")
    p_archive.add_argument("--out-dir", default="dist", help="Output directory")

    p_changelog = subparsers.add_parser("update-changelog")
    p_changelog.add_argument("version", help="Version string (e.g. 0.4.0)")
    p_changelog.add_argument("date", help="Release date (e.g. 2026-11-10)")
    p_changelog.add_argument("--file", default=DEFAULT_CHANGELOG_PATH, help="Path to CHANGELOG.md")

    p_notes = subparsers.add_parser("generate-notes")
    p_notes.add_argument("version", help="Version string (e.g. 0.4.0)")
    p_notes.add_argument("--changelog", default=DEFAULT_CHANGELOG_PATH, help="Path to CHANGELOG.md")
    p_notes.add_argument("--out-dir", default=DEFAULT_NOTES_DIR, help="Output directory")

    p_index = subparsers.add_parser("update-index")
    p_index.add_argument("version", help="Version string (e.g. 0.4.0)")
    p_index.add_argument("date", help="Release date (e.g. 2026-11-10)")
    p_index.add_argument("--file", default=DEFAULT_NOTES_INDEX, help="Path to index README.md")

    p_body = subparsers.add_parser("build-body")
    p_body.add_argument("version", help="Version string (e.g. 0.4.0)")
    p_body.add_argument("--notes", default="", help="Path to version notes markdown")
    p_body.add_argument("--checksums", default=DEFAULT_CHECKSUMS_PATH, help="Path to SHA256SUMS.txt")
    p_body.add_argument("--out", default=DEFAULT_RELEASE_BODY_PATH, help="Output release body file")

    return parser.parse_args()


## ---------- (09) MAIN EXECUTION --------------------------------------------------- ##
def main() -> int:
    """Execute the requested release operation subcommand."""
    args = _parse_args()
    try:
        if args.subcommand == "check-manifests":
            check_manifests()
        elif args.subcommand == "sync-manifests":
            sync_manifests(args.version)
        elif args.subcommand == "build-archive":
            build_archive(args.version, args.out_dir)
        elif args.subcommand == "update-changelog":
            update_changelog(args.version, args.date, args.file)
        elif args.subcommand == "generate-notes":
            generate_release_notes(args.version, args.changelog, args.out_dir)
        elif args.subcommand == "update-index":
            update_release_notes_index(args.version, args.date, args.file)
        elif args.subcommand == "build-body":
            build_release_body(args.version, args.notes, args.checksums, args.out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
