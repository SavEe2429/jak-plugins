#!/usr/bin/env bash
# Updates docs/release-notes/README.md with the newly published version row.
set -euo pipefail

VERSION="${1:?Version argument required}"
DATE="${2:?Date argument required}"
INDEX_FILE="${3:-docs/release-notes/README.md}"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/release_ops.py" update-index "$VERSION" "$DATE" --file "$INDEX_FILE"
