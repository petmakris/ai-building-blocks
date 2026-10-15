"""Render a block's Story section as the reader-facing page.

The page reads top to bottom: hook, the block's map (diagrams/<block>.map.json),
idea, the walkthrough as a lane sequence (diagrams/<block>.seq.json) with its
steps in full below it, takeaways, the trap, the smallest version as code, and
the way on. Both diagrams are drawn by the shared library (tools/vzlib.py).
"""
from __future__ import annotations

import html
import re

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from store import ROOT, Block, Story
import vzlib

E = lambda s: html.escape(s or "", quote=True)  # noqa: E731


def inline(text: str) -> str:
    """Escape, then render `code` and ==mark== spans."""
    t = E(text)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"==(.+?)==", r"<mark>\1</mark>", t)
    return t


def headline(text: str) -> str:
    t = E(text)
    return re.sub(r"==(.+?)==", r"<em>\1</em>", t)


# ---------------------------------------------------------------- diagram

CHAR = {"lbl": 8.6, "tag": 8.7}   # average glyph width at the stylesheet's sizes (16px Inter, 14px mono)


GUTTER = 44   # the step numbers live left of this line; no label may enter it


def code_block(lang: str, code: str) -> str:
    try:
        lexer = get_lexer_by_name(lang or "text")
    except ClassNotFound:
        lexer = get_lexer_by_name("text")
    out = highlight(code, lexer, HtmlFormatter(nowrap=True))
    lines = out.split("\n")
    res = []
    for ln in lines:
        if re.search(r"\[\d+\]", ln):
            ln = re.sub(r"\[(\d+)\]", r'<span class="tag">\1</span>', ln)
            ln = f'<span class="h">{ln}</span>'
        res.append(ln)
    return "\n".join(res).rstrip()


# ---------------------------------------------------------------- page

def ref_links(refs: list[str]) -> str:
    return " · ".join(f'<a href="reference/#{E(r)}">{E(r)}</a>' for r in refs)


def story_page(block: Block, story: Story, blocks: dict[str, Block], order: list[str], stories: dict, counts: dict, version: str) -> str:
    f = block.front
    i = order.index(block.id)
    nxt = blocks[order[i + 1]] if i + 1 < len(order) else None
    total = len(order)
    pos = i + 1
    h, p, idea, w, tr, b = story.hook, story.panel, story.idea, story.walk, story.trap, story.build

    panel = ""
    if p.get("rows"):
        rows = []
        for label, value, note, style in p["rows"]:
            cls = {"struck": "down", "accent": "up", "big": "big"}.get(style.strip(), "")
            rows.append(f'<div class="row {cls}"><span class="m">{inline(label)}</span><span class="p">{E(value)}</span>'
                        + (f'<span class="why">{inline(note)}</span>' if note else "") + "</div>")
        panel = (f'<aside class="bill"><h3>{inline(p.get("title", ""))}</h3>{"".join(rows)}'
                 f'<p class="src">{inline(p.get("source", ""))}</p></aside>')

    ov = story.overview or {}
    overview = ""
    map_fig = vzlib.map_figure(block.id)
    if ov and map_fig:
        fig = map_fig
        overview = (f'<section class="ov"><p class="kicker">The whole picture</p>'
                    f'<figure class="ov-fig">{fig}'
                    f'<figcaption>{inline(ov.get("caption", ""))}</figcaption>'
                    f'<p class="ov-get">For slides: <a href="../diagrams/{block.id}.png" download>PNG light</a>'
                    f' · <a href="../diagrams/{block.id}-dark.png" download>PNG dark</a>'
                    f' · <a href="../slides/#{block.id}">present all</a></p></figure></section>')

    steps = []
    for s in story.steps:
        fact = f'<p class="fact">{inline(s.fact)}</p>' if s.fact else ""
        steps.append(f'<article class="step" data-step="{s.n}"><span class="n">Step {s.n}</span><h3>{inline(s.title)}</h3>'
                     f'<p>{inline(s.text)}</p>{fact}<p class="refs">{ref_links(s.refs)}</p></article>')

    walk_body = (f'<figure class="seq-fig">{vzlib.sequence_figure(block.id)}</figure>'
                 f'<details class="walk-detail"><summary>Each step in full, with its sources</summary>'
                 f'<div class="steps flat">{"".join(steps)}</div></details>')

    cards = "".join(
        f'<div class="card"><span class="n">{k}</span><h3>{inline(t)}</h3><p>{inline(x)}</p><span class="id">{ref_links(r)}</span></div>'
        for k, (t, x, r) in enumerate(story.takeaways, 1))

    a_h, a_t = tr.get("assume", ("", ""))
    c_h, c_t = tr.get("actually", ("", ""))
    trap_refs = [r.strip() for r in re.split(r"[,\s]+", tr.get("refs", "")) if r.strip()]

    nxt_card = ""
    if nxt:
        teaser = stories[nxt.id].hook.get("teaser", "") if stories.get(nxt.id) else nxt.front.get("summary", "")
        nxt_card = (f'<a class="go primary" href="../{nxt.id}/"><span class="lbl">Next · Block {nxt.number:02d}</span>'
                    f'<h3>{E(nxt.front.get("title", ""))}</h3><p>{inline(teaser)}</p></a>')
    else:
        nxt_card = '<a class="go primary" href="../"><span class="lbl">The end</span><h3>Back to all blocks</h3><p>See how one request passes through every block.</p></a>'
    c = counts
    deeper = (f'<a class="go" href="reference/"><span class="lbl">Go deeper</span><h3>{E(f.get("title", ""))}: reference</h3>'
              f'<p>{c["concepts"]} concepts, {c["flows"]} flows, {c["lifecycles"]} lifecycles, {c["code"]} excerpts of real code, every number with its source.</p></a>')

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(f.get("title", ""))} · AI Building Blocks</title>
<meta name="description" content="{E(re.sub('==', '', h.get('headline', '')))}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap">
<link rel="stylesheet" href="../assets/story.css?v={version}">
<link rel="stylesheet" href="../assets/vz.css?v={version}">
</head><body>
<div class="bar"><div class="bar-in"><a class="brand" href="../">AI Building Blocks</a><span class="count">{pos:02d} / {total}</span>
<span class="prog"><i style="width:{100 * pos / total:.2f}%"></i></span><a class="ref" href="reference/">Reference</a>
<button id="theme" type="button" aria-label="Switch light or dark">Theme</button></div></div>
<div class="wrap">
<header class="hook{' solo' if not panel else ''}"><div><p class="kicker">Block {block.number:02d} · {E(f.get("title", ""))}</p>
<h1>{headline(h.get("headline", ""))}</h1><p class="sub">{inline(h.get("setup", ""))}</p></div>{panel}</header>
{overview}
<section class="idea"><p class="kicker">The idea</p><p class="big">{inline(idea.get("sentence", ""))}</p>
<p class="ana">{inline(idea.get("analogy", ""))}</p></section>
<section class="walk"><p class="kicker">Watch it happen</p><h2>{inline(w.get("title", ""))}</h2><p class="lead">{inline(w.get("lead", ""))}</p>
{walk_body}</section>
<section class="take"><p class="kicker">Take away</p><h2>{len(story.takeaways)} things to remember</h2><div class="cards">{cards}</div></section>
<section class="trap"><p class="kicker">The trap</p><h2>{inline(tr.get("title", ""))}</h2>
<div class="trap-box"><div class="wrong"><span class="lbl">What people assume</span><h3>{inline(a_h)}</h3><p>{inline(a_t)}</p></div>
<div class="right"><span class="lbl">What actually happens</span><h3>{inline(c_h)}</h3><p>{inline(c_t)}</p></div></div>
<p class="refs">{ref_links(trap_refs)}</p></section>
<section class="build"><p class="kicker">Build it</p><h2>{inline(b.get("title", ""))}</h2><p class="lead">{inline(b.get("lead", ""))}</p>
<pre class="code"><code>{code_block(b.get("lang", ""), b.get("code", ""))}</code></pre><p class="note">{inline(b.get("note", ""))}</p></section>
<nav class="next" aria-label="Continue">{deeper}{nxt_card}</nav>
</div>
<script src="../assets/story.js?v={version}"></script>
<script src="../assets/vz-reveal.js?v={version}"></script>
</body></html>"""


WORDS = {n: w for n, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}


def home(blocks: dict[str, Block], order: list[str], stories: dict, path_rows: list[tuple[str, str, str]], version: str, repo: str) -> str:
    word = WORDS.get(len(order), str(len(order)))
    Word = word.capitalize()
    cards = []
    for b in order:
        blk, st = blocks[b], stories.get(b)
        head = headline(st.hook.get("headline", "")) if st else E(blk.front.get("title", ""))
        teaser = inline(st.hook.get("teaser", "")) if st else E(blk.front.get("summary", ""))
        cards.append(f'<a class="hc" href="{b}/"><span class="hn">{blk.number:02d} · {E(blk.front.get("title", ""))}</span>'
                     f'<h3>{head}</h3><p>{teaser}</p><span class="go-on">Read →</span></a>')
    stops = []
    for rid, step, blks in path_rows:
        name, _, rest = step.partition(":")
        chips = " ".join(f'<a class="chip" href="{x.strip()}/">{E(blocks[x.strip()].front.get("title", x.strip()))}</a>'
                         for x in blks.split(",") if x.strip() in blocks)
        cross = int(rid[1:]) > 13
        stops.append(f'<li class="{"cross" if cross else ""}"><span class="rid">{rid}</span><div><h3>{E(name.strip())}</h3>'
                     f'<p>{E(rest.strip())}</p><p class="chips">{chips}</p></div></li>')
    first = order[0]
    journey = vzlib.home_figure()
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Building Blocks</title>
<meta name="description" content="The {word} building blocks of software built around language models, each taught from a real failure.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap">
<link rel="stylesheet" href="assets/story.css?v={version}">
<link rel="stylesheet" href="assets/vz.css?v={version}">
</head><body>
<div class="bar"><div class="bar-in"><a class="brand" href="./">AI Building Blocks</a><a class="ref" href="slides/">Slides</a><a class="ref" href="glossary/">Glossary</a>
<a class="ref2" href="{repo}">GitHub</a><button id="theme" type="button" aria-label="Switch light or dark">Theme</button></div></div>
<div class="wrap">
<header class="hook solo home-hero"><div><p class="kicker">For engineers putting AI into real software</p>
<h1>One model call is easy. <em>Depending on it is engineering.</em></h1>
<p class="sub">{Word} building blocks turn an unreliable, paid, non-deterministic model call into software you can run. Each one starts from a real failure, shows the mechanism step by step, and ends with the smallest version you can build today.</p>
<p class="cta"><a class="btn" href="{first}/">Start with block 01 →</a><a class="btn ghost" href="#journey">See one request pass through all {word}</a></p></div></header>
<section class="hooks"><p class="kicker">{Word} building blocks of a modern AI application</p><h2>Pick the one you need</h2><div class="hgrid">{"".join(cards)}</div></section>
<section class="journey" id="journey"><p class="kicker">The whole picture</p><h2>One request passes through the blocks in this order</h2>
<p class="lead">Steps R0 to R13 run on every request. The rest run across requests or between releases.</p>
{f'<figure class="seq-fig">{journey}</figure><details class="walk-detail"><summary>Every step, with the blocks it belongs to</summary><ol class="path">{"".join(stops)}</ol></details>' if journey else f'<ol class="path">{"".join(stops)}</ol>'}</section>
<footer class="foot"><p>Built as a <a href="{repo}">knowledge store</a> of plain markdown: every concept, flow and number has an id and a source. Licensed CC BY 4.0.</p></footer>
</div>
<script src="assets/story.js?v={version}"></script>
<script src="assets/vz-reveal.js?v={version}"></script>
</body></html>"""


def slides(blocks: dict[str, Block], order: list[str], version: str) -> str:
    """Every block's map and walkthrough, one per screen, for presenting. The buttons, or the arrow keys,
    step through a diagram while it plays, and move to the next screen when it is done or not playing."""
    out = []
    for b in order:
        head = f'{blocks[b].number:02d} · {E(blocks[b].front.get("title", ""))}'
        fig = vzlib.map_figure(b)
        if fig:
            out.append(f'<section class="slide" id="{b}"><span class="sn">{head}</span><div class="sl-fig">{fig}</div></section>')
        seq = vzlib.sequence_figure(b)
        if seq:
            out.append(f'<section class="slide" id="{b}-walk"><span class="sn">{head} · walkthrough</span><div class="sl-fig">{seq}</div></section>')
    return f"""<!doctype html>
<html lang="en" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Slides · AI Building Blocks</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap">
<link rel="stylesheet" href="../assets/story.css?v={version}">
<link rel="stylesheet" href="../assets/vz.css?v={version}">
</head><body class="deck">
{"".join(out)}
<nav class="deck-nav"><a href="../">Site</a><button type="button" id="prev">Previous slide</button><span id="pos"></span><button type="button" id="next">Next slide</button><button type="button" id="theme">Theme</button></nav>
<script src="../assets/vz-reveal.js?v={version}"></script>
<script>
(() => {{
  const s = [...document.querySelectorAll('.slide')];
  let i = Math.max(0, s.findIndex(x => '#' + x.id === location.hash));
  const show = (k) => {{ i = Math.min(s.length - 1, Math.max(0, k)); s.forEach((x, j) => x.hidden = j !== i);
    document.getElementById('pos').textContent = (i + 1) + ' / ' + s.length; history.replaceState(null, '', '#' + s[i].id); }};
  const player = () => s[i].querySelector('[data-vz-player]');
  addEventListener('keydown', (e) => {{
    if (e.target instanceof Element && e.target.closest('button, input')) return;
    const p = player(), st = p && p.vz && p.vz.state();
    if (['ArrowRight', 'PageDown', ' '].includes(e.key)) {{
      e.preventDefault();
      if (st && st.mode && st.cur < st.last) p.vz.go(st.cur + 1); else show(i + 1);
    }}
    if (['ArrowLeft', 'PageUp'].includes(e.key)) {{
      e.preventDefault();
      if (st && st.mode && st.cur > 0) p.vz.go(st.cur - 1); else show(i - 1);
    }}
  }});
  document.getElementById('next').onclick = () => show(i + 1);
  document.getElementById('prev').onclick = () => show(i - 1);
  document.getElementById('theme').onclick = () => {{ const r = document.documentElement; r.dataset.theme = r.dataset.theme === 'dark' ? 'light' : 'dark'; }};
  show(i);
}})();
</script>
</body></html>"""
