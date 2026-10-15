"""Turn a flow (Fn) of the store into a lane sequence spec for the shared diagram library.

Every word on the drawing comes from the flow's own steps and the block's Components table:

- actors are the parts the flow's steps name, in the order they first appear. A `K` id takes the
  component's name; its role line is the K id plus the component's role when that is four words or
  fewer, else its code name from the name column.
- each numbered step (F1.5) is one row badged with its number, carrying the step's text; so badge n is
  always step F#.n. A step 0 (set-up before step 1) has no badge and stays on screen while stepping. A step with
  one actor is a self step; a step with a chain (A → B → C) is an arrow per hop. A step whose text
  starts with "return" is drawn as a reply (`event`), as is one that answers an earlier call and says
  it returns.
- the step's `condition`, when it is not "always", is a ✓ badge (or a line of the chip when long);
  a short `ref` is the chip's mono line.
- a lettered branch (F1.5a) is an amber chip beside the lane where the numbered step left the flow,
  its id first; a branch that names actors is drawn as their arrows, in amber.
- the route captions are the step texts, one per step number, so "Step through" reads the flow.

A flow whose steps name fewer than two parts gets no diagram: its step list says it all.
Run `python3 tools/flowseq.py OUT_DIR` to write every spec and SVG for vz_check.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import Block, Flow, Step  # noqa: E402
import vzlib  # noqa: E402
from visuals.map_svg import _width  # noqa: E402

CHIP_W = 380        # px: chip lines wrap to this width
HEAD_W = 200        # px: a lane name longer than this takes two lines
CHECK_MAX = 56      # chars: a longer condition goes into the chip instead of a badge
REF_MAX = 24        # chars: a longer ref is left to the step list
BRANCH = re.compile(r"^(if|when|on|else|otherwise|unless)\b", re.I)
KID = re.compile(r"^(K\d+)\b")


# ---------------------------------------------------------------- components

def components(block: Block) -> dict[str, dict]:
    """K id -> {name, alias, role} from the Components table (id | name | role | ...)."""
    out = {}
    for m in re.finditer(r"^\|\s*(K\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|", block.sections.get("Components", ""), re.M):
        raw = m.group(2).strip()
        alias = ""
        am = re.search(r"\((`[^)]*`)\)", raw)
        if am:
            alias = am.group(1)
        name = re.sub(r"\s*\(`[^)]*`\)", "", raw).strip()
        out[m.group(1)] = {"name": name or m.group(1), "alias": alias, "role": m.group(3).strip()}
    return out


def words(text: str) -> int:
    return len(re.sub(r"`", "", text).split())


# ---------------------------------------------------------------- text

def wrap(text: str, width: float = CHIP_W, style: str = "vz-sb") -> str:
    """Wrap on spaces to `width` px, keeping every `code` span closed on its own line."""
    text = re.sub(r"\s+", " ", text).strip()
    lines: list[str] = []
    cur = ""
    for w in text.split(" "):
        cand = f"{cur} {w}" if cur else w
        if cur and _width(_closed(cand), style) > width:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    out = []
    carry = False
    for ln in lines:
        if carry:
            ln = "`" + ln
        carry = ln.count("`") % 2 == 1
        out.append(ln + "`" if carry else ln)
    return "\n".join(out)


def _closed(s: str) -> str:
    return s + "`" if s.count("`") % 2 else s


def split_head(label: str) -> str:
    """A lane name wider than HEAD_W goes on two lines, split near the middle."""
    if _width(label, "vz-nm") <= HEAD_W or " " not in label:
        return label
    ws = label.split(" ")
    best = min(range(1, len(ws)), key=lambda k: abs(_width(" ".join(ws[:k]), "vz-nm") - _width(" ".join(ws[k:]), "vz-nm")))
    return _closed(" ".join(ws[:best])) + "\n" + ("`" if " ".join(ws[:best]).count("`") % 2 else "") + " ".join(ws[best:])


# ---------------------------------------------------------------- actors

def actor_key(raw: str, comps: dict[str, dict] | None = None, local: frozenset = frozenset()) -> str:
    """One key per part: its K id when the step names it ("K5", "Chat panel (K1)", the component's own
    name), or when the flow names that K elsewhere and this is the start of its name ("Tool runner" for
    "K9 Tool runner and write tools"); else its words in lower case."""
    a = raw.strip()
    m = KID.match(a) or re.search(r"\((K\d+)\)", a)
    if m:
        return m.group(1)
    low = re.sub(r"\s+", " ", a.lower()).strip("`")
    for kid, c in (comps or {}).items():
        name = re.sub(r"\s*\([^)]*\)", "", c["name"]).lower().strip("`")
        if name == low or (kid in local and name.startswith(low + " ")):
            return kid
    return low


def actor_spec(raw: str, comps: dict[str, dict], aid: str, k: str) -> dict:
    a = raw.strip()
    m = re.match(r"(K\d+)$", k)
    if m and m.group(1) in comps:
        c = comps[m.group(1)]
        label = c["name"]
        if 0 < words(c["role"]) <= 4:
            role = f'{m.group(1)} · {c["role"]}'
        elif c["alias"] and _width(c["alias"], "vz-sb") <= 150:
            role = f'{m.group(1)} · {c["alias"]}'
        else:
            role = m.group(1)
    else:
        label, role = a, ""
    out = {"id": aid}
    if re.fullmatch(r"`[^`]+`", label):
        out["label"], out["mono"] = split_head(label.strip("`")), True
    else:
        out["label"] = split_head(label)
    if role:
        out["role"] = role
    return out


def is_situation(step: Step, keys_used: dict[str, int], key) -> bool:
    """A single 'actor' that is really a situation ("next deploy with a changed constant: ..."), not a part."""
    if len(step.actors) != 1:
        return False
    a = step.actors[0]
    if KID.match(a):
        return False
    return bool(BRANCH.match(a)) or (keys_used.get(key(a), 0) == 1 and words(a) >= 4)


def hops(step: Step) -> list[list[str]]:
    """The step's actors as hops; a 'K6, K7' target fans out to each."""
    out = []
    for a in step.actors:
        parts = [p.strip() for p in a.split(",")] if re.fullmatch(r"K\d+(\s*,\s*K\d+)+", a.strip()) else [a]
        out.append(parts)
    return out


# ---------------------------------------------------------------- steps

def number(step: Step) -> int:
    return int(re.match(r"F\d+\.(\d+)", step.id).group(1))


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("`", "")).strip()


def ref_of(step: Step) -> str:
    r = (step.fields.get("ref") or step.fields.get("refs") or "").strip().strip("[]").strip()
    return r if r and len(r) <= REF_MAX else ""


def condition_of(step: Step) -> str:
    c = (step.fields.get("condition") or "").strip()
    return "" if not c or c.lower() == "always" else c


def flow_spec(flow: Flow, block: Block) -> dict | None:
    comps = components(block)
    steps = flow.steps
    if not steps:
        return None
    local = frozenset(m.group(1) for s in steps for a in s.actors
                      for m in [KID.match(a.strip()) or re.search(r"\((K\d+)\)", a)] if m)
    key = lambda a: actor_key(a, comps, local)  # noqa: E731
    used: dict[str, int] = {}
    for s in steps:
        for a in s.actors:
            used[key(a)] = used.get(key(a), 0) + 1
    situation = {s.id for s in steps if is_situation(s, used, key)}

    actors: dict[str, dict] = {}

    def aid(raw: str) -> str:
        k = key(raw)
        if k not in actors:
            actors[k] = actor_spec(raw, comps, f"a{len(actors)}", k)
        return actors[k]["id"]

    for s in steps:
        if s.id in situation:
            continue
        for hop in hops(s):
            for a in hop:
                aid(a)
    if len(actors) < 2:
        return None

    out_steps: list[dict] = []
    calls: set[tuple[str, str]] = set()
    here = next(iter(actors.values()))["id"]   # the lane the flow is at
    uses_branch_tone = False
    k = 0

    def sid() -> str:
        nonlocal k
        k += 1
        return f"s{k}"

    for s in steps:
        n = number(s) or None   # a step 0 (set-up before step 1) stays on screen, unnumbered
        cond = condition_of(s)
        ref = ref_of(s)
        if not s.actors or s.id in situation:
            text = s.action if not s.actors else s.raw.split(" | ")[0]
            label = wrap(f"{s.id} · {text}")
            st = {"id": sid(), "from": here, "to": here, "arrow": "self", "label": label}
            if n:
                st["n"] = n
            if ref:
                st["sub"] = ref
            if s.branch:
                st["tone"] = "amber"
                uses_branch_tone = True
            out_steps.append(st)
            continue
        label_text = f"{s.id} · {s.action}" if s.branch else s.action
        tone = "amber" if s.branch else None
        uses_branch_tone |= s.branch
        chain = [[aid(a) for a in hop] for hop in hops(s)]
        long_cond = cond if cond and len(cond) > CHECK_MAX else ""
        label = wrap(label_text) + (("\n" + wrap(f"condition: {long_cond}")) if long_cond else "")
        first = True
        if len(chain) == 1:
            st = {"id": sid(), "from": chain[0][0], "to": chain[0][0], "arrow": "self", "label": label}
            here = chain[0][0]
            new = [st]
        else:
            pairs = [(x, y) for xs, ys in zip(chain, chain[1:]) for x in xs for y in ys]
            new = []
            for x, y in pairs:
                if x == y:
                    continue
                answers = (y, x) in calls
                reply = bool(re.match(r"returns?\b", s.action, re.I)) or (answers and re.search(r"\breturns?\b", s.action, re.I))
                st = {"id": sid(), "from": x, "to": y, "arrow": "event" if reply else "request"}
                if first:
                    st["label"] = label
                calls.add((x, y))
                new.append(st)
                first = False
                here = y
            if not new:   # a chain that only names one part twice
                new = [{"id": sid(), "from": chain[0][0], "to": chain[0][0], "arrow": "self", "label": label}]
        if n:
            for st in new:
                st["n"] = n
        if ref:
            new[0]["sub"] = ref
        if cond and not long_cond:
            new[0]["checks"] = [{"label": plain(cond), "ok": True}]
        if tone:
            for st in new:
                st["tone"] = tone
        out_steps.extend(new)

    caps: dict[int, list[str]] = {}
    for s in steps:
        n = number(s)
        if not n:
            continue
        text = plain(s.raw.split(" | ")[0])
        cond = condition_of(s)
        caps.setdefault(n, []).append(f"{s.id} · {text}" + (f" (condition: {plain(cond)})" if cond else ""))
    last = max(caps)
    captions = []
    for n in range(1, last + 1):
        lines = caps.get(n)
        if not lines:
            captions.append({"title": f"{flow.id}.{n}", "text": ""})
            continue
        title, *rest = lines
        captions.append({"title": title, "text": " ".join(rest)})

    spec = {"title": f"{flow.id} · {flow.title}", "actors": list(actors.values()), "steps": out_steps, "captions": captions}
    if uses_branch_tone:
        spec["legend"] = [{"tone": "amber", "label": "a lettered branch of the numbered step"}]
    return spec


def flow_svg(flow: Flow, block: Block) -> tuple[str, dict] | None:
    spec = flow_spec(flow, block)
    if not spec:
        return None
    return vzlib.sequence_svg.render(spec, f"{block.id}-{flow.id}"), spec


def flow_figure(flow: Flow, block: Block) -> tuple[str, int]:
    """The player for the flow, with the drawing's natural width in px; ("", 0) when it has no diagram."""
    got = flow_svg(flow, block)
    if not got:
        return "", 0
    svg, spec = got
    width = int(float(re.search(r'viewBox="0 0 ([\d.]+) ', svg).group(1)))
    return vzlib.player.figure(svg, {"route": spec["captions"]}), width


def main() -> int:
    from store import load_all
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "flows")
    out.mkdir(parents=True, exist_ok=True)
    drawn, skipped = 0, []
    for b in load_all():
        for f in b.flows:
            got = flow_svg(f, b)
            if not got:
                skipped.append(f"{b.id}.{f.id}")
                continue
            svg, spec = got
            (out / f"{b.id}-{f.id}.svg").write_text(svg)
            (out / f"{b.id}-{f.id}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1))
            drawn += 1
    print(f"{drawn} drawn in {out}; no diagram (fewer than two parts): {', '.join(skipped) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
