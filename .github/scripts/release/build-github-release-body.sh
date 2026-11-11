#!/usr/bin/env bash
# Constructs the final release body markdown for GitHub Releases.
set -euo pipefail

VERSION="${1:?Version argument required}"
NOTES_FILE="${2:-docs/release-notes/v${VERSION}.md}"
CHECKSUM_FILE="${3:-dist/SHA256SUMS.txt}"
OUTPUT_FILE="${4:-dist/RELEASE_BODY.md}"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/release_ops.py" build-body "$VERSION" --notes "$NOTES_FILE" --checksums "$CHECKSUM_FILE" --out "$OUTPUT_FILE"
