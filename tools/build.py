# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown-it-py==3.0.0", "mdit-py-plugins==0.4.2", "pygments==2.18.0"]
# ///
"""Generate the static site from the knowledge store.

Run: uv run tools/build.py [--out DIR] [--only BLOCK ...]
The markdown files stay the single source. Never edit the generated site.

Every flow (Fn) becomes a sequence diagram and every lifecycle (Ln) a state
diagram, generated from the steps and transition tables that tools/check.py
validates. Every item id is an anchor, and every reference becomes a link.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.deflist import deflist_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check import state_key  # noqa: E402
from store import HEADINGS, ROOT, Block, Flow, Lifecycle, Step, load_all, parse_story  # noqa: E402
import story_page  # noqa: E402

ASSETS = Path(__file__).resolve().parent / "site"
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs"
REPO = "https://github.com/petmakris/ai-building-blocks"


# ---------------------------------------------------------------- markdown

def _highlight(code: str, lang: str, _attrs) -> str:
    try:
        lexer = get_lexer_by_name(lang) if lang else guess_lexer(code)
    except ClassNotFound:
        lexer = get_lexer_by_name("text")
    return highlight(code, lexer, HtmlFormatter(nowrap=True))


MD = MarkdownIt("commonmark", {"html": False, "highlight": _highlight}).enable("table").use(deflist_plugin)


def md(text: str) -> str:
    return MD.render(text or "")


# ---------------------------------------------------------------- linking

def link_ids(fragment: str, block: Block, blocks: dict[str, Block], titles: dict[str, str], up: str = "../") -> str:
    """Turn item ids into links, outside <pre>, <code> and existing <a>."""
    parts = re.split(r"(<pre.*?</pre>|<a\b.*?</a>|<code>.*?</code>|<[^>]+>)", fragment, flags=re.S)
    cross = re.compile(r"\b(?P<blk>[a-z]+)\.(?P<item>[A-Z]\d+(?:\.\d+[a-z]?)?)\b")
    local = re.compile(r"(?<![\w.#/-])(?P<item>[A-Z]\d+(?:\.\d+[a-z]?)?)(?![\w-])")

    def cross_sub(m: re.Match) -> str:
        blk, item = m.group("blk"), m.group("item")
        if blk not in blocks:
            return m.group(0)
        t = html.escape(titles.get(f"{blk}.{item}", ""), quote=True)
        return f'<a class="ref" href="{up}{blk}/reference/#{item}" title="{t}">{blk}.{item}</a>'

    def local_sub(m: re.Match) -> str:
        item = m.group("item")
        if item not in block.ids:
            return m.group(0)
        t = html.escape(titles.get(f"{block.id}.{item}", ""), quote=True)
        return f'<a class="ref" href="#{item}" title="{t}">{item}</a>'

    out = []
    for p in parts:
        if not p or p.startswith("<"):
            out.append(p)
            continue
        p = cross.sub(cross_sub, p)
        # split again so local ids inside the new cross links are untouched
        sub = re.split(r"(<a\b.*?</a>)", p, flags=re.S)
        out.append("".join(s if s.startswith("<a") else local.sub(local_sub, s) for s in sub))
    return "".join(out)


def anchor_rows(fragment: str) -> str:
    """Give a table row whose first cell is an id that id as its anchor."""
    return re.sub(r"<tr>\s*<td>(?P<id>[A-Z]\d+)</td>", r'<tr id="\g<id>"><td class="rid"><a href="#\g<id>">\g<id></a></td>', fragment)


def anchor_list_items(fragment: str) -> str:
    """Give a list item that starts with a step id (F1.3 · ...) that id."""
    return re.sub(r"<li>(\s*<p>)?(?P<id>[A-Z]\d+(?:\.\d+[a-z]?)?)\s*·",
                  lambda m: f'<li id="{m.group("id")}">{m.group(1) or ""}<a class="sid" href="#{m.group("id")}">{m.group("id")}</a> ·',
                  fragment)


# ---------------------------------------------------------------- diagrams

def clean(text: str, limit: int) -> str:
    t = re.sub(r"`", "", text)
    t = re.sub(r"\s+", " ", t).strip()
    t = t.replace(";", ",").replace("#", "nº").replace("<", "‹").replace(">", "›")
    t = t.replace("{", "(").replace("}", ")").replace('"', "'")
    if len(t) > limit:
        t = t[: limit - 1].rstrip() + "…"
    return t


def branch_condition(step: Step) -> tuple[str, str]:
    """Return (condition, effect) for a branch step."""
    if not step.actors:
        body = re.sub(r"^(if|when|on|else|otherwise|unless)\s+", "", step.action, flags=re.I)
        cond, _, effect = body.partition("→")
        return cond.strip(), effect.strip()
    return step.fields.get("condition", "otherwise"), step.action


def components(block: Block) -> dict[str, str]:
    """K id -> short display name, from the Components table."""
    out = {}
    for m in re.finditer(r"^\|\s*(K\d+)\s*\|\s*([^|]+?)\s*\|", block.sections.get("Components", ""), re.M):
        name = re.sub(r"\s*\(`[^)]*`\)", "", m.group(2)).strip().strip("`")
        out[m.group(1)] = name or m.group(1)
    return out


def actor_name(raw: str, comps: dict[str, str]) -> str:
    a = raw.strip()
    m = re.match(r"^(K\d+)\b", a)
    if m and m.group(1) in comps:
        a = comps[m.group(1)]
    a = re.sub(r"\s*\(`[^)]*`\)\s*$", "", a)
    return clean(a, 30)


def sequence(flow: Flow, comps: dict[str, str]) -> str:
    actors: list[str] = []
    for s in flow.steps:
        for a in s.actors:
            name = actor_name(a, comps)
            if name not in actors:
                actors.append(name)
    if not actors:
        return ""
    ids = {a: f"p{i}" for i, a in enumerate(actors)}
    lines = ["sequenceDiagram"]
    for a in actors:
        lines.append(f"    participant {ids[a]} as {a}")
    last_actor = actors[0]

    def arrows(s: Step, label: str) -> list[str]:
        nonlocal last_actor
        acts = [actor_name(a, comps) for a in s.actors]
        out = []
        if len(acts) == 1:
            out.append(f"    {ids[acts[0]]}->>{ids[acts[0]]}: {label}")
        else:
            for x, y in zip(acts, acts[1:]):
                out.append(f"    {ids[x]}->>{ids[y]}: {label}")
        last_actor = acts[-1]
        return out

    def jump_text(s: Step) -> str:
        if s.jumps:
            return " → " + ", ".join(s.jumps)
        return " → ends" if s.ends else ""

    i = 0
    steps = flow.steps
    while i < len(steps):
        s = steps[i]
        if s.branch:  # a branch with no main step before it in this flow
            group = [s]
        else:
            act = re.sub(r"\s*→?\s*(?:continues at|runs|rejoins|returns to)\s+\S+", "", s.action)
            act = re.sub(r"\s*→\s*ends\b", "", act).strip(" →")
            lines += arrows(s, clean(f"{s.id} {act}", 70) + clean(jump_text(s), 30))
            group = []
        j = i + 1
        while j < len(steps) and steps[j].branch and steps[j].id.rstrip("abcdefghijklmnopqrstuvwxyz") == s.id.rstrip("abcdefghijklmnopqrstuvwxyz"):
            group.append(steps[j])
            j += 1
        for b in group:
            cond, effect = branch_condition(b)
            effect = re.sub(r"\s*→?\s*(?:continues at|runs|rejoins|returns to)\s+\S+.*$", "", effect)
            effect = re.sub(r"\s*→\s*ends\b.*$", "", effect).strip(" →")
            lines.append(f"    opt {clean(b.id + ' · ' + cond, 48)}")
            if b.actors:
                lines += arrows(b, clean(effect, 70) + clean(jump_text(b), 30))
            else:
                k = actors.index(last_actor)
                span = f"{ids[actors[k]]},{ids[actors[k + 1]]}" if k + 1 < len(actors) else f"{ids[actors[k - 1]]},{ids[actors[k]]}" if k > 0 else ids[actors[k]]
                lines.append(f"    Note over {span}: {clean(effect, 110)}{clean(jump_text(b), 30)}")
            lines.append("    end")
        i = j
    return "\n".join(lines)


def state_diagram(lc: Lifecycle) -> str:
    if not lc.transitions:
        return ""
    names: dict[str, str] = {}
    for n in lc.states:
        names.setdefault(state_key(n), n)
    sid: dict[str, str] = {}

    def node(raw: str) -> str:
        k = state_key(raw)
        if k in ("none", "start", "—", "-", ""):
            return "[*]"
        if k not in sid:
            sid[k] = f"s{len(sid)}"
        return sid[k]

    edges = []
    for t in lc.transitions:
        srcs = [x for x in re.split(r"\s*(?:,|/|\bor\b)\s*", t.src) if x.strip()]
        for src in srcs:
            chain = [x for x in re.split(r"\s*→\s*", t.dst) if x.strip()]
            prev = node(src)
            label = t.trigger
            if t.guard and t.guard.strip().lower() not in ("none", "—", "–", "-", ""):
                label += f" [{t.guard}]"
            for k, d in enumerate(chain):
                nxt = node(d)
                if nxt == "[*]" and prev == "[*]":
                    continue
                text = clean(label, 46).replace(":", "\ua789") if k == 0 else ""
                edges.append(f"    {prev} --> {nxt}: {text}".rstrip(": "))
                prev = nxt
    lines = ["stateDiagram-v2"]
    for k, s in sid.items():
        lines.append(f'    state "{clean(names.get(k, k), 40)}" as {s}')
    lines += edges
    return "\n".join(lines)


# ---------------------------------------------------------------- page parts

ITEM_HEAD = re.compile(r"^### (?P<id>[A-Z]\d+)\s*·\s*(?P<title>.+)$", re.M)


def split_items(text: str) -> tuple[str, list[tuple[str, str, str]]]:
    """Split a section body into its intro and its '### ID · title' items."""
    parts = ITEM_HEAD.split(text)
    intro = parts[0]
    items = []
    for k in range(1, len(parts), 3):
        items.append((parts[k], parts[k + 1].strip(), parts[k + 2]))
    return intro, items


def render_items(block: Block, section: str, ctx, folded: bool = False, cards: bool = False) -> str:
    intro, items = split_items(block.sections.get(section, ""))
    out = [ctx.post(md(intro))] if intro.strip() else []
    cls = "cards" if cards else "items"
    out.append(f'<div class="{cls}">')
    for iid, title, body in items:
        inner = ctx.post(md(body))
        head = f'<span class="iid">{iid}</span> {html.escape(title)}'
        if folded:
            out.append(f'<details class="item" id="{iid}"><summary>{head}</summary>{inner}</details>')
        else:
            out.append(f'<article class="item" id="{iid}"><h3>{head}</h3>{inner}</article>')
    out.append("</div>")
    return "\n".join(out)


def render_flows(block: Block, ctx) -> str:
    text = block.sections.get("Flows", "")
    intro, items = split_items(text)
    out = [ctx.post(md(intro))] if intro.strip() else []
    flows = {f.id: f for f in block.flows}
    for fid, title, body in items:
        flow = flows.get(fid)
        diagram = sequence(flow, components(block)) if flow else ""
        head_re = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?(purpose|trigger)\b", re.I)
        lines = body.strip("\n").split("\n")
        purpose = "\n".join(l if l.lstrip().startswith(("-", "*")) else "- " + l for l in lines if head_re.match(l))
        steps = "\n".join(l for l in lines if not head_re.match(l))
        out.append(f'<article class="flow" id="{fid}"><h3><span class="iid">{fid}</span> {html.escape(title)}</h3>')
        out.append(f'<div class="purpose">{ctx.post(md(purpose))}</div>')
        if diagram:
            out.append(f'<figure class="diagram"><pre class="mermaid">{html.escape(diagram)}</pre>'
                       f'<figcaption>Sequence of {fid}, generated from its {len(flow.steps)} steps. Each step id links to its full text below.</figcaption></figure>')
        out.append(f'<details class="steps" open><summary>All steps of {fid}</summary>{ctx.post(md(steps))}</details></article>')
    return "\n".join(out)


def render_states(block: Block, ctx) -> str:
    intro, items = split_items(block.sections.get("States", ""))
    out = [ctx.post(md(intro))] if intro.strip() else []
    lcs = {l.id: l for l in block.lifecycles}
    for lid, title, body in items:
        lc = lcs.get(lid)
        diagram = state_diagram(lc) if lc else ""
        out.append(f'<article class="flow" id="{lid}"><h3><span class="iid">{lid}</span> {html.escape(title)}</h3>')
        if diagram:
            out.append(f'<figure class="diagram"><pre class="mermaid">{html.escape(diagram)}</pre>'
                       f'<figcaption>States of {lid}, generated from its {len(lc.transitions)} transitions.</figcaption></figure>')
        out.append(f'<details class="steps"><summary>States and transitions of {lid}</summary>{ctx.post(md(body))}</details></article>')
    return "\n".join(out)


class Ctx:
    def __init__(self, block: Block, blocks: dict[str, Block], titles: dict[str, str], up: str = "../../"):
        self.block, self.blocks, self.titles, self.up = block, blocks, titles, up

    def post(self, fragment: str) -> str:
        return link_ids(anchor_list_items(anchor_rows(fragment)), self.block, self.blocks, self.titles, self.up)


SECTION_IDS = {h: re.sub(r"[^a-z]+", "-", h.lower()).strip("-") for h in HEADINGS}


def block_page(block: Block, blocks: dict[str, Block], titles: dict[str, str], order: list[str]) -> str:
    ctx = Ctx(block, blocks, titles)
    f = block.front
    status = f.get("lomem_status", "").strip("'\"")
    deps = [d.strip() for d in f.get("depends_on", "").strip("[]").split(",") if d.strip()]
    rel = [d.strip() for d in f.get("related", "").strip("[]").split(",") if d.strip()]
    i = order.index(block.id)
    prev_b = blocks[order[i - 1]] if i > 0 else None
    next_b = blocks[order[i + 1]] if i + 1 < len(order) else None

    def chips(ids: list[str]) -> str:
        return " ".join(f'<a class="chip" href="../../{d}/">{html.escape(blocks[d].front.get("title", d))}</a>' for d in ids if d in blocks) or '<span class="dim">none</span>'

    body = []
    for h in HEADINGS:
        sid = SECTION_IDS[h]
        if h == "Concepts":
            inner = render_items(block, h, ctx, cards=True)
        elif h == "Flows":
            inner = render_flows(block, ctx)
        elif h == "States":
            inner = render_states(block, ctx)
        elif h == "Code in Lomem":
            inner = render_items(block, h, ctx, folded=True)
        elif h == "Worked examples":
            inner = render_items(block, h, ctx, folded=True)
        else:
            inner = ctx.post(md(block.sections.get(h, "")))
        body.append(f'<section class="sec" id="{sid}"><h2>{h}</h2>{inner}</section>')

    counts = [("Concepts", len([1 for _ in ITEM_HEAD.finditer(block.sections.get('Concepts', ''))])),
              ("Flows", len(block.flows)), ("States", len(block.lifecycles)),
              ("Code in Lomem", len([1 for _ in ITEM_HEAD.finditer(block.sections.get('Code in Lomem', ''))]))]
    toc = "".join(f'<a href="#{SECTION_IDS[h]}">{h}' + (f' <span class="n">{dict(counts).get(h)}</span>' if h in dict(counts) else "") + "</a>" for h in HEADINGS)
    flow_toc = "".join(f'<a class="sub" href="#{fl.id}">{fl.id} · {html.escape(fl.title[:48])}</a>' for fl in block.flows)
    life_toc = "".join(f'<a class="sub" href="#{lc.id}">{lc.id} · {html.escape(lc.title[:48])}</a>' for lc in block.lifecycles)
    toc = toc.replace(f'<a href="#flows">', f'<a href="#flows">', 1)
    nav = "".join(
        f'<a class="{"on" if b == block.id else ""}" href="../../{b}/reference/"><span class="num">{blocks[b].number:02d}</span> {html.escape(blocks[b].front.get("title", b))}</a>'
        for b in order)
    pager = (f'<nav class="pager">'
             + (f'<a href="../../{prev_b.id}/reference/">← {html.escape(prev_b.front.get("title", ""))}</a>' if prev_b else "<span></span>")
             + (f'<a href="../../{next_b.id}/reference/">{html.escape(next_b.front.get("title", ""))} →</a>' if next_b else "<span></span>")
             + "</nav>")
    main = f"""
<header class="hero">
  <p class="eyebrow"><a href="../">← Read the story</a> · Reference for block {block.number:02d} of {len(blocks)} · <span class="status s-{status.replace(' ', '-')}">Lomem: {html.escape(status)}</span></p>
  <h1>{html.escape(f.get("title", block.id))}</h1>
  <p class="lede">{html.escape(f.get("summary", ""))}</p>
  <dl class="meta"><dt>Learn first</dt><dd>{chips(deps)}</dd><dt>Related</dt><dd>{chips(rel)}</dd>
  <dt>Source</dt><dd><a href="{REPO}/blob/main/{block.path.name}">{block.path.name}</a></dd></dl>
</header>
{''.join(body)}
{pager}"""
    side = f"""<div class="toc"><p class="toc-h">On this page</p>{toc}<p class="toc-h">Flows</p>{flow_toc}<p class="toc-h">Lifecycles</p>{life_toc}</div>"""
    return page(f.get("title", block.id) + " · reference", main, nav, side, depth=2)


ASSET_VERSION = ""


def page(title: str, main: str, nav: str, side: str, depth: int) -> str:
    up = "../" * depth
    v = f"?v={ASSET_VERSION}" if ASSET_VERSION else ""
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · AI Building Blocks</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="{up}assets/site.css{v}">
</head><body>
<header class="top"><a class="brand" href="{up}">AI Building Blocks</a>
<div class="search"><input id="q" type="search" placeholder="Search concepts, flows, ids…" autocomplete="off" aria-label="Search"><div id="results" hidden></div></div>
<nav class="links"><a href="{up}glossary/">Glossary</a><a href="{REPO}">GitHub</a>
<button id="theme" type="button" aria-label="Switch light or dark">Theme</button></nav></header>
<div class="layout"><nav class="blocks" aria-label="Building blocks">{nav}</nav>
<main>{main}</main><aside>{side}</aside></div>
<script>window.SITE_ROOT = "{up}";</script>
<script src="{up}assets/site.js{v}"></script>
<script type="module">import mermaid from "{MERMAID}"; window.__mermaid = mermaid; window.dispatchEvent(new Event("mermaid-ready"));</script>
</body></html>"""


def topo_order(blocks: dict[str, Block]) -> list[str]:
    deps = {b: [d.strip() for d in blk.front.get("depends_on", "").strip("[]").split(",") if d.strip() in blocks]
            for b, blk in blocks.items()}
    order, seen = [], set()
    for b in sorted(blocks, key=lambda x: blocks[x].number):
        def visit(x):
            if x in seen:
                return
            seen.add(x)
            for d in sorted(deps[x], key=lambda y: blocks[y].number):
                visit(d)
            order.append(x)
        visit(b)
    return order


def readme_section(n: int) -> str:
    t = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(rf"^## {n}\. .*?$(.*?)(?=^## \d+\. |\Z)", t, re.S | re.M)
    return m.group(1) if m else ""


def home_page(blocks: dict[str, Block], titles, order) -> str:
    path_md = readme_section(4)
    rows = re.findall(r"^\|\s*(R\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", path_md, re.M)
    fc = ["flowchart TD"]
    prev = None
    for rid, step, blks in rows:
        name = clean(step.split(":")[0], 40)
        fc.append(f'    {rid}["{rid} · {name}"]')
        if prev and int(rid[1:]) <= 13:
            fc.append(f"    {prev} --> {rid}")
        prev = rid
    fc.append("    classDef cross stroke-dasharray: 4 3")
    fc.append("    class " + ",".join(r for r, _, _ in rows if int(r[1:]) > 13) + " cross")
    cards = []
    for b in order:
        blk = blocks[b]
        st = blk.front.get("lomem_status", "").strip("'\"")
        nc = len(ITEM_HEAD.findall(blk.sections.get("Concepts", "")))
        cards.append(f'''<a class="bcard" href="{b}/"><span class="num">{blk.number:02d}</span>
<h3>{html.escape(blk.front.get("title", b))}</h3><p>{html.escape(blk.front.get("summary", ""))}</p>
<p class="stats">{nc} concepts · {len(blk.flows)} flows · {len(blk.lifecycles)} lifecycles · <span class="status s-{st.replace(' ', '-')}">Lomem: {html.escape(st)}</span></p></a>''')
    ctx = Ctx(next(iter(blocks.values())), blocks, titles)
    table = ctx.post(md(path_md))
    table = re.sub(r'href="\.\./', 'href="', table)
    nav = "".join(f'<a href="{b}/"><span class="num">{blocks[b].number:02d}</span> {html.escape(blocks[b].front.get("title", b))}</a>' for b in order)
    main = f"""
<header class="hero"><p class="eyebrow">A knowledge store, rendered</p>
<h1>Sixteen building blocks turn one unreliable model call into software you can depend on</h1>
<p class="lede">Each block is stored as items with stable ids: concepts, flows, lifecycles, worked examples, numbers with sources, verbatim code from a real codebase, pitfalls and misconceptions. Every flow and lifecycle below is drawn from those items. The <a href="{REPO}">markdown files</a> are the source.</p></header>
<section class="sec" id="blocks"><h2>The blocks, in learning order</h2><div class="bgrid">{''.join(cards)}</div></section>
<section class="sec" id="request-path"><h2>One request passes through the blocks in this order</h2>
<figure class="diagram"><pre class="mermaid">{html.escape(chr(10).join(fc))}</pre><figcaption>R1–R13 run on every request. Dashed steps R14–R20 run across requests or between releases.</figcaption></figure>
<details class="steps" open><summary>Every step, with the blocks and flows it maps to</summary>{table}</details></section>"""
    return page("Home", main, nav, "", depth=0)


def glossary_page(blocks, titles, order) -> str:
    g = readme_section(5)
    from types import SimpleNamespace
    ctx = Ctx(SimpleNamespace(ids=set(), id=""), blocks, titles, up="../")
    nav = "".join(f'<a href="../{b}/"><span class="num">{blocks[b].number:02d}</span> {html.escape(blocks[b].front.get("title", b))}</a>' for b in order)
    main = f'<header class="hero"><p class="eyebrow">Glossary</p><h1>Every concept in the store, with the block that defines it</h1></header><section class="sec">{ctx.post(md(g))}</section>'
    return page("Glossary", main, nav, "", depth=1)


def item_titles(blocks: dict[str, Block]) -> tuple[dict[str, str], list[dict]]:
    titles, index = {}, []
    for b in blocks.values():
        text = b.path.read_text(encoding="utf-8")
        for m in ITEM_HEAD.finditer(text):
            iid, title = m.group("id"), m.group("title").strip()
            titles[f"{b.id}.{iid}"] = title
            index.append({"id": f"{b.id}.{iid}", "t": title, "b": b.front.get("title", b.id), "u": f"{b.id}/#{iid}"})
        for f in b.flows:
            for s in f.steps:
                titles[f"{b.id}.{s.id}"] = f"{s.id} · {s.action[:120]}"
    return titles, index


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path("/tmp") / "ai-building-blocks-site"))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--no-check", action="store_true")
    a = ap.parse_args()
    if not a.no_check:
        r = subprocess.run([sys.executable, str(Path(__file__).parent / "check.py")], capture_output=True, text=True)
        if r.returncode:
            print(r.stdout)
            print("check.py failed: fix the store before building (or pass --no-check for a draft).")
            return 1
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    global ASSET_VERSION
    import hashlib
    h = hashlib.sha256()
    for p in sorted(ASSETS.iterdir()):
        shutil.copy(p, out / "assets" / p.name)
        h.update(p.read_bytes())
    ASSET_VERSION = h.hexdigest()[:10]
    (out / "assets" / "pygments.css").write_text(HtmlFormatter(style="friendly").get_style_defs(".hl"))
    blocks = {b.id: b for b in load_all()}
    order = topo_order(blocks)
    titles, index = item_titles(blocks)
    (out / "assets" / "search.json").write_text(json.dumps(index, ensure_ascii=False))
    stories = {b: parse_story(blk) for b, blk in blocks.items()}
    stories = {b: s for b, s in stories.items() if s and not s.problems}
    path_rows = re.findall(r"^\|\s*(R\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", readme_section(4), re.M)
    (out / "assets" / "code.css").write_text("")
    (out / "index.html").write_text(story_page.home(blocks, order, stories, path_rows, ASSET_VERSION, REPO))
    (out / "glossary").mkdir()
    (out / "glossary" / "index.html").write_text(glossary_page(blocks, titles, order))
    for b in order:
        if a.only and b not in a.only:
            continue
        (out / b / "reference").mkdir(parents=True)
        ref = block_page(blocks[b], blocks, titles, order)
        (out / b / "reference" / "index.html").write_text(ref)
        blk = blocks[b]
        counts = {"concepts": len(ITEM_HEAD.findall(blk.sections.get("Concepts", ""))), "flows": len(blk.flows),
                  "lifecycles": len(blk.lifecycles), "code": len(ITEM_HEAD.findall(blk.sections.get("Code in Lomem", "")))}
        if b in stories:
            (out / b / "index.html").write_text(story_page.story_page(blk, stories[b], blocks, order, stories, counts, ASSET_VERSION))
        else:
            (out / b / "index.html").write_text(ref.replace('href="../../', 'href="../').replace('src="../../', 'src="../'))
    (out / ".nojekyll").write_text("")
    print(f"built {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
