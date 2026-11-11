#!/usr/bin/env bash
# Extracts standalone release notes for the given version.
set -euo pipefail

VERSION="${1:?Version argument required}"
CHANGELOG="${2:-CHANGELOG.md}"
OUT_DIR="${3:-docs/release-notes}"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/release_ops.py" generate-notes "$VERSION" --changelog "$CHANGELOG" --out-dir "$OUT_DIR"
