#!/usr/bin/env python3
"""Check that every block file follows the store format, so tools can read it.

Run: python3 tools/check.py [-v] [file-or-block-id ...]
Exits 1 when any problem is found. build.py refuses to build until this passes.

Checks:
- front matter has id, number, title, summary, lomem_status, depends_on, related
- the 15 section headings are present, in order
- every flow step parses as "Fn.m · actor [→ actor]: action | field: value"
  or, for a branch, "Fn.ma · if … → …"
- every "continues at" / "runs" jump points at a flow or step that exists
- every transition table has the columns from|trigger|guard|to|effect|ref
- every state named in a transition is declared in that lifecycle's States list
- every cross-block reference "<block>.<item>" points at an item that exists
- the Story section (the reader-facing layer) is complete and its refs resolve
"""
from __future__ import annotations

import re
import sys

from store import HEADINGS, load_all, parse_story

FRONT_KEYS = ["id", "number", "title", "summary", "lomem_status", "depends_on", "related"]


def state_key(name: str) -> str:
    """'trying(i+1)' and '`trying(i)`' are the same state 'trying'."""
    n = name.strip().strip("`").strip()
    n = re.sub(r"\(.*\)$", "", n).strip()
    return n.lower()


def main() -> int:
    verbose = "-v" in sys.argv
    blocks = load_all()
    by_id = {b.id: b for b in blocks}
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    if only:
        blocks = [b for b in blocks if b.path.name in only or b.id in only]
    total = 0
    for b in blocks:
        probs = list(b.problems)
        for k in FRONT_KEYS:
            if k not in b.front:
                probs.append(f"front matter: missing '{k}'")
        found = [h for h in b.sections if h in HEADINGS]
        if found != HEADINGS:
            probs.append(f"headings: {found}")
        story = parse_story(b)
        if story is None:
            probs.append("Story: no '## Story' section")
        else:
            probs += story.problems
        steps = {s.id for f in b.flows for s in f.steps} | {f.id for f in b.flows}
        for f in b.flows:
            if not f.steps:
                probs.append(f"{f.id}: flow has no steps")
            for s in f.steps:
                for j in s.jumps:
                    if "." in j and not j.startswith("F"):
                        blk, item = j.split(".", 1)
                        if blk not in by_id or item not in by_id[blk].ids:
                            probs.append(f"line {s.line}: {s.id} jumps to unknown {j}")
                    elif j not in steps:
                        probs.append(f"line {s.line}: {s.id} jumps to unknown {j}")
        for lc in b.lifecycles:
            declared = {state_key(k) for k in lc.states}
            if not lc.states:
                probs.append(f"{lc.id}: no '- States:' list")
            if not lc.transitions:
                probs.append(f"{lc.id}: no transition table")
            for t in lc.transitions:
                for side in (t.src, t.dst):
                    for name in re.split(r"\s*(?:,|/|\bor\b|→)\s*", side):
                        k = state_key(name)
                        if k and k not in declared and k not in ("any", "*", "(any)", "any state", "start", "end", "—", "-"):
                            probs.append(f"line {t.line}: {lc.id} state '{name.strip()}' not declared")
        text = b.path.read_text(encoding="utf-8")
        for m in re.finditer(r"\b(?P<blk>[a-z]+)\.(?P<item>(?:[A-Z]\d+)(?:\.\d+[a-z]?)?)\b", text):
            blk, item = m.group("blk"), m.group("item")
            if blk in by_id and item not in by_id[blk].ids:
                line = text.count("\n", 0, m.start()) + 1
                probs.append(f"line {line}: reference {blk}.{item} points at nothing")
        total += len(probs)
        nsteps = sum(len(f.steps) for f in b.flows)
        ntr = sum(len(l.transitions) for l in b.lifecycles)
        print(f"{b.path.name:22} flows={len(b.flows):3} steps={nsteps:4} lifecycles={len(b.lifecycles):3} transitions={ntr:4} problems={len(probs)}")
        if verbose:
            for p in probs:
                print(f"    {p}")
    print(f"\n{total} problems")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
