#!/usr/bin/env bash
# Build the site and publish it to the gh-pages branch, which GitHub Pages serves.
# The gh-pages branch holds only generated files and is replaced on every publish.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${TMPDIR:-/tmp}/ai-building-blocks-site"
uv run -q tools/build.py --out "$OUT" "$@"
uv run -q tools/diagrams.py check
uv run -q tools/diagrams.py export --out "$OUT"
SRC=$(git rev-parse --short HEAD)
REMOTE=$(git remote get-url origin)
cd "$OUT"
rm -rf .git
git init -q -b gh-pages
git add -A
git commit -q -m "Site built from $SRC"
git push -q --force "$REMOTE" gh-pages
rm -rf .git
echo "published $SRC to gh-pages"
