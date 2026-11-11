#!/usr/bin/env bash
# Resolves the previous git tag safely before the current release tag.
set -euo pipefail

CURRENT_TAG="${1:-}"
if [[ -n "$CURRENT_TAG" ]]; then
  git describe --tags --abbrev=0 "${CURRENT_TAG}^" 2>/dev/null || echo ""
else
  git describe --tags --abbrev=0 2>/dev/null || echo ""
fi
