# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright==1.55.0"]
# ///
"""Check and export the overview diagrams in diagrams/<block>.svg.

Run: uv run tools/diagrams.py check [BLOCK ...]   find layout faults, write PNGs to inspect
     uv run tools/diagrams.py export --out DIR     write slide PNGs into DIR/diagrams/

Each SVG is drawn in Chromium with the site's own stylesheet, so the check sees
what a reader sees. A fault is text that leaves its box, two labels that touch,
an arrow that runs through text or through a box, or anything outside the canvas.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "tools" / "site" / "story.css"
FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800'
         '&family=JetBrains+Mono:wght@400;500;600&display=swap">')

PROBE = r"""
() => {
  const svg = document.querySelector('svg.ov-svg');
  const vb = svg.viewBox.baseVal;
  const faults = [];
  const boxes = [...svg.querySelectorAll('rect.bx')].map(r => ({r, b: r.getBBox()}));
  const texts = [...svg.querySelectorAll('text')].map(t => ({t, b: t.getBBox(), s: t.textContent.trim()}));
  const inside = (p, b, pad = 0) => p.x >= b.x - pad && p.x <= b.x + b.width + pad && p.y >= b.y - pad && p.y <= b.y + b.height + pad;
  const area = (b) => b.width * b.height;
  for (const {b, s} of texts) {
    if (b.x < vb.x || b.y < vb.y || b.x + b.width > vb.x + vb.width || b.y + b.height > vb.y + vb.height)
      faults.push(`off canvas: "${s}"`);
    // the smallest box that holds the text's start is its box
    const start = {x: b.x + 1, y: b.y + b.height / 2};
    const own = boxes.filter(x => inside(start, x.b)).sort((p, q) => area(p.b) - area(q.b))[0];
    if (own) {
      const over = b.x + b.width - (own.b.x + own.b.width - 10);
      if (over > 0) faults.push(`leaves its box by ${Math.ceil(over)}px: "${s}"`);
      if (b.y < own.b.y + 2 || b.y + b.height > own.b.y + own.b.height - 2) faults.push(`touches its box's top or bottom: "${s}"`);
    }
  }
  for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
    const a = texts[i].b, c = texts[j].b;
    if (a.x < c.x + c.width - 1 && c.x < a.x + a.width - 1 && a.y < c.y + c.height - 2 && c.y < a.y + a.height - 2)
      faults.push(`labels overlap: "${texts[i].s}" and "${texts[j].s}"`);
  }
  for (const el of svg.querySelectorAll('.ar')) {
    if (getComputedStyle(el).fill !== 'none') faults.push(`arrow is filled, not a line: ${el.getAttribute('d') || el.getAttribute('class')}`);
    const len = el.getTotalLength();
    const pts = [];
    for (let d = 10; d < len - 12; d += 3) pts.push(el.getPointAtLength(d));
    const id = el.getAttribute('d') || `${el.getAttribute('x1')},${el.getAttribute('y1')}`;
    for (const {b, s} of texts) if (pts.some(p => inside(p, b, 2))) faults.push(`arrow ${id} runs through text "${s}"`);
    for (const {r, b} of boxes) {
      const inner = {x: b.x + 4, y: b.y + 4, width: b.width - 8, height: b.height - 8};
      const n = pts.filter(p => inside(p, inner)).length;
      if (n > 2) faults.push(`arrow ${id} runs through a box at ${b.x},${b.y}`);
    }
  }
  for (const t of svg.querySelectorAll('text')) {
    const c = getComputedStyle(t).fill;
    if (c === 'none' || c === getComputedStyle(svg.closest('figure')).backgroundColor) faults.push(`text has no visible colour: "${t.textContent.trim()}"`);
  }
  if (!svg.querySelector('text.ttl')) faults.push('no title: add <text class="ttl">');
  return faults;
}
"""


def page(svg: str, theme: str) -> str:
    return (f'<!doctype html><html data-theme="{theme}"><head><meta charset="utf-8">{FONTS}'
            f'<link rel="stylesheet" href="{CSS.as_uri()}"><style>body{{padding:0;margin:0}} .ov-fig{{margin:0;border:0;border-radius:0}}'
            f' .ov-svg{{min-width:0}}</style></head><body><figure class="ov-fig">{svg}</figure></body></html>')


def shoot(pw_page, svg: str, theme: str, png: Path, width: int = 1600) -> list[str]:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(page(svg, theme))
    pw_page.set_viewport_size({"width": width, "height": 900})
    pw_page.goto(Path(f.name).as_uri())
    pw_page.evaluate("document.fonts.ready")
    pw_page.wait_for_timeout(300)
    faults = pw_page.evaluate(PROBE)
    png.parent.mkdir(parents=True, exist_ok=True)
    pw_page.locator("figure.ov-fig").screenshot(path=str(png))
    return faults


def chromium() -> str | None:
    """The newest Chromium that Playwright already downloaded, so no extra install is needed."""
    cache = Path.home() / "Library" / "Caches" / "ms-playwright"
    if not cache.exists():
        cache = Path.home() / ".cache" / "ms-playwright"
    shells = sorted(cache.glob("chromium_headless_shell-*/*/chrome-headless-shell"),
                    key=lambda x: int(x.parts[-3].rsplit("-", 1)[1]))
    return str(shells[-1]) if shells else None


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("blocks", nargs="*")
    c.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "ai-building-blocks-diagrams"))
    e = sub.add_parser("export")
    e.add_argument("--out", required=True)
    a = ap.parse_args()

    files = sorted((ROOT / "diagrams").glob("*.svg"))
    if a.cmd == "check" and a.blocks:
        files = [f for f in files if f.stem in a.blocks]
    bad = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium())
        pg = browser.new_page(device_scale_factor=2)
        for f in files:
            svg = f.read_text()
            if a.cmd == "check":
                out = Path(a.out)
                faults = shoot(pg, svg, "light", out / f"{f.stem}-light.png")
                shoot(pg, svg, "dark", out / f"{f.stem}-dark.png")
                bad += len(faults)
                print(f"{f.stem}: {len(faults)} faults  {out / f.stem}-light.png")
                for x in faults:
                    print("   ", x)
            else:
                out = Path(a.out) / "diagrams"
                shoot(pg, svg, "light", out / f"{f.stem}.png")
                shoot(pg, svg, "dark", out / f"{f.stem}-dark.png")
        browser.close()
    if a.cmd == "check":
        print(f"{bad} faults")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
