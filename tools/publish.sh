#!/usr/bin/env bash
# Build the site and publish it to the gh-pages branch, which GitHub Pages serves.
# The gh-pages branch holds only generated files and is replaced on every publish.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${TMPDIR:-/tmp}/ai-building-blocks-site"
uv run -q tools/build.py --out "$OUT" "$@"
# Maps and walkthroughs drawn by the shared library: check every frame, export the PNGs.
VZ="${VZ_HOME:-$HOME/projects/claude-annotate}/tools/vz_check.py"
shopt -s nullglob
svgs=("$OUT"/diagrams/*.map.svg "$OUT"/diagrams/*.seq.svg)
if [ ${#svgs[@]} -gt 0 ]; then
  uv run -q "$VZ" check "${svgs[@]}" --out "$OUT/diagrams/png"
  for f in "$OUT"/diagrams/*.map.svg; do
    id=$(basename "$f" .map.svg)
    cp "$OUT/diagrams/png/$id.map-light.png" "$OUT/diagrams/$id.png"
    cp "$OUT/diagrams/png/$id.map-dark.png" "$OUT/diagrams/$id-dark.png"
    uv run -q "$VZ" frames "$f" --out "$OUT/diagrams/frames" --mode build >/dev/null
    uv run -q "$VZ" frames "$f" --out "$OUT/diagrams/frames" --mode route >/dev/null
  done
fi
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
