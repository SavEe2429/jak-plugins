#!/usr/bin/env python3
"""Validate Markdown relative reference links across all skills and docs.

Ensures that no broken relative links exist in SKILL.md or reference files,
preventing AI agents from failing when following markdown documentation links.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def validate_links(scan_dirs: list[str]) -> int:
    broken: list[tuple[str, str, str]] = []
    total_checked = 0

    for scan_dir in scan_dirs:
        dir_path = ROOT / scan_dir
        if not dir_path.exists():
            continue

        for md in sorted(dir_path.rglob("*.md")):
            try:
                text = md.read_text(encoding="utf-8")
            except Exception as e:
                print(f"ERROR reading {md}: {e}", file=sys.stderr)
                broken.append((str(md), "<read-error>", str(e)))
                continue

            # Match standard Markdown links: [title](target)
            matches = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)
            for _, link in matches:
                # Strip potential surrounding whitespace
                link_clean = link.strip()
                # Skip external, anchor-only, mailto, or special schemas
                if any(
                    link_clean.startswith(prefix)
                    for prefix in ("http://", "https://", "#", "mailto:", "ftp://", "file://")
                ):
                    continue

                # Strip anchor fragment
                rel_path = link_clean.split("#")[0].strip()
                if not rel_path:
                    continue

                total_checked += 1
                resolved_target = (md.parent / rel_path).resolve()
                if not resolved_target.exists():
                    rel_src = md.relative_to(ROOT)
                    broken.append((str(rel_src), link_clean, str(resolved_target)))

    if broken:
        print(f"FAILED: Found {len(broken)} broken Markdown reference links:", file=sys.stderr)
        for src, link, resolved in broken:
            print(f"  - {src} -> {link} (resolved: {resolved})", file=sys.stderr)
        return 1

    print(f"PASSED: Verified {total_checked} Markdown reference links cleanly across {scan_dirs}.")
    return 0


if __name__ == "__main__":
    dirs_to_scan = sys.argv[1:] if len(sys.argv) > 1 else ["skills", "docs"]
    sys.exit(validate_links(dirs_to_scan))
