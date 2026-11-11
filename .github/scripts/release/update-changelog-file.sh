#!/usr/bin/env bash
# Promotes [Unreleased] to [version] - date in CHANGELOG.md.
set -euo pipefail

VERSION="${1:?Version argument required}"
DATE="${2:?Date argument required}"
FILE="${3:-CHANGELOG.md}"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/release_ops.py" update-changelog "$VERSION" "$DATE" --file "$FILE"
