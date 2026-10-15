"""Parse the knowledge store into Python objects.

One block file (NN-<id>.md) becomes a Block. The parser follows the format
described in README.md section 1. It is shared by check.py (format gate) and
build.py (site generator), so both read the files the same way.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HEADINGS = [
    "Summary", "Problem", "Concepts", "Components", "Flows", "States",
    "Worked examples", "Variants and options", "Facts and numbers",
    "Code in Lomem", "Analogy to classic backend", "Pitfalls",
    "Misconceptions", "Open questions", "Sources",
]

STEP_ID = r"F\d+\.\d+[a-z]?"
# "1. F1.3 · Gateway → K5: get lead model | condition: ... | ref: X8"
# "   - F1.2a · if no context → throw ... → ends | ref: X4"
STEP_RE = re.compile(rf"^(?P<indent>\s*)(?:\d+\.|[-*])?\s*\**(?P<id>{STEP_ID})\**\s*·\s*(?P<rest>.+)$")
FLOW_RE = re.compile(r"^### (?P<id>F\d+)\s*·\s*(?P<title>.+)$")
LIFE_RE = re.compile(r"^### (?P<id>L\d+)\s*·\s*(?P<title>.+)$")
ITEM_RE = re.compile(r"^### (?P<id>[A-Z]\d+)\s*·\s*(?P<title>.+)$")
JUMP_RE = re.compile(rf"(?:continues at|runs|→ goes to|returns to|rejoins)\s+(?P<to>(?:[a-z]+\.)?F\d+(?:\.\d+[a-z]?)?)")
ENDS_RE = re.compile(r"(?:→|\b)\s*ends\b")
ARROW = "→"


@dataclass
class Step:
    id: str
    line: int
    raw: str
    branch: bool
    actors: list[str]          # [] for a condition-style branch ("if ... → ...")
    action: str
    fields: dict[str, str]
    jumps: list[str]
    ends: bool


@dataclass
class Flow:
    id: str
    title: str
    purpose: str
    steps: list[Step] = field(default_factory=list)


@dataclass
class Transition:
    src: str
    trigger: str
    guard: str
    dst: str
    effect: str
    ref: str
    line: int


@dataclass
class Lifecycle:
    id: str
    title: str
    states: dict[str, str] = field(default_factory=dict)
    transitions: list[Transition] = field(default_factory=list)


@dataclass
class Block:
    path: Path
    number: int
    id: str
    front: dict[str, str]
    sections: dict[str, str]
    section_lines: dict[str, int]
    flows: list[Flow]
    lifecycles: list[Lifecycle]
    ids: set[str]
    problems: list[str] = field(default_factory=list)   # parse problems for check.py


def split_fields(text: str) -> tuple[str, dict[str, str]]:
    """Split 'action | condition: x | data: y | ref: z' into action and fields."""
    parts = [p.strip() for p in re.split(r"\s+\|\s+", text)]
    head, fields = parts[0], {}
    for p in parts[1:]:
        m = re.match(r"^(condition|data|ref|refs|guard|effect|note|source)\s*:\s*(.*)$", p, re.I)
        if m:
            fields[m.group(1).lower()] = m.group(2)
        else:
            fields.setdefault("extra", "")
            fields["extra"] = (fields["extra"] + " | " + p).strip(" |")
    return head, fields


def parse_step(m: re.Match, lineno: int) -> tuple[Step | None, str | None]:
    sid, rest = m.group("id"), m.group("rest").strip()
    branch = sid[-1].isalpha()
    body, fields = split_fields(rest)
    jumps = [j.group("to") for j in JUMP_RE.finditer(rest)]
    ends = bool(ENDS_RE.search(rest))
    # Condition-style branch: "if ... → effect"
    if branch and re.match(r"^(if|when|on|else|otherwise|unless)\b", body, re.I):
        return Step(sid, lineno, rest, True, [], body, fields, jumps, ends), None
    # Step form: "<actor> [→ <actor> ...]: action"
    # The head ends at the first ': ' that is not inside backticks.
    head, action = None, None
    depth = 0
    for i, ch in enumerate(body):
        if ch == "`":
            depth ^= 1
        elif ch == ":" and depth == 0 and (i + 1 == len(body) or body[i + 1] == " "):
            head, action = body[:i], body[i + 1:].strip()
            break
    if head is None or not head.strip():
        return None, f"{sid}: no 'actor: action' head and not an 'if …' branch"
    actors = [a.strip() for a in head.split(ARROW) if a.strip()]
    if not actors or any(len(a) > 60 for a in actors):
        return None, f"{sid}: actor names missing or too long: {head[:80]!r}"
    return Step(sid, lineno, rest, branch, actors, action, fields, jumps, ends), None


def parse_table(lines: list[str], start: int) -> tuple[list[str], list[list[str]], int]:
    """Read a markdown table starting at lines[start]; return header, rows, next index."""
    def cells(s: str) -> list[str]:
        s = s.strip()
        if s.startswith("|"):
            s = s[1:]
        if s.endswith("|"):
            s = s[:-1]
        # split on | not inside backticks
        out, cur, tick = [], "", False
        for ch in s:
            if ch == "`":
                tick = not tick
            if ch == "|" and not tick:
                out.append(cur.strip())
                cur = ""
            else:
                cur += ch
        out.append(cur.strip())
        return out
    header = [c.lower() for c in cells(lines[start])]
    i = start + 2
    rows = []
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        rows.append(cells(lines[i]))
        i += 1
    return header, rows, i


def load(path: Path) -> Block:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    problems: list[str] = []
    front: dict[str, str] = {}
    if lines[0] == "---":
        end = lines.index("---", 1)
        for l in lines[1:end]:
            if ":" in l:
                k, v = l.split(":", 1)
                front[k.strip()] = v.strip()
    sections: dict[str, str] = {}
    section_lines: dict[str, int] = {}
    cur = None
    buf: list[str] = []
    for i, l in enumerate(lines):
        m = re.match(r"^## (.+)$", l)
        if m:
            if cur:
                sections[cur] = "\n".join(buf)
            cur, buf = m.group(1).strip(), []
            section_lines[cur] = i + 1
        elif cur:
            buf.append(l)
    if cur:
        sections[cur] = "\n".join(buf)

    # Flows
    flows: list[Flow] = []
    base = section_lines.get("Flows", 0)
    for j, l in enumerate(sections.get("Flows", "").split("\n")):
        lineno = base + j + 1
        fm = FLOW_RE.match(l)
        if fm:
            flows.append(Flow(fm.group("id"), fm.group("title").strip(), ""))
            continue
        if flows and not flows[-1].steps and l.lower().startswith("purpose"):
            flows[-1].purpose = l.split(":", 1)[1].strip() if ":" in l else l
            continue
        sm = STEP_RE.match(l)
        if sm and flows:
            step, err = parse_step(sm, lineno)
            if err:
                problems.append(f"line {lineno}: {err}")
            elif not step.id.startswith(flows[-1].id + "."):
                problems.append(f"line {lineno}: step {step.id} is under flow {flows[-1].id}")
            else:
                flows[-1].steps.append(step)

    # States
    lifecycles: list[Lifecycle] = []
    base = section_lines.get("States", 0)
    slines = sections.get("States", "").split("\n")
    j = 0
    mode = None
    while j < len(slines):
        l = slines[j]
        lm = LIFE_RE.match(l)
        if lm:
            lifecycles.append(Lifecycle(lm.group("id"), lm.group("title").strip()))
            mode = None
        elif lifecycles and re.match(r"^-\s*States\s*:", l):
            mode = "states"
        elif lifecycles and re.match(r"^-\s*Transitions\s*:", l):
            mode = "transitions"
        elif lifecycles and l.lstrip().startswith("|") and j + 1 < len(slines) and re.match(r"^\s*\|\s*:?-", slines[j + 1]):
            header, rows, nxt = parse_table(slines, j)
            want = ["from", "trigger", "guard", "to", "effect", "ref"]
            if header[:6] != want:
                problems.append(f"line {base + j + 1}: {lifecycles[-1].id} transition table header is {header}, want {want}")
            else:
                for r_i, r in enumerate(rows):
                    r = (r + [""] * 6)[:6]
                    lifecycles[-1].transitions.append(Transition(*r, line=base + j + 3 + r_i))
            j = nxt
            continue
        elif lifecycles and mode == "states":
            sm = re.match(r"^\s+[-*]\s+`?(?P<name>[^:`·—]+?)`?\s*(?::|·|—)\s*(?P<desc>.*)$", l)
            if sm:
                lifecycles[-1].states[sm.group("name").strip()] = sm.group("desc").strip()
        j += 1

    ids = set()
    for l in lines:
        im = ITEM_RE.match(l)
        if im:
            ids.add(im.group("id"))
        for tm in re.finditer(r"^\|\s*(?P<id>[A-Z]\d+)\s*\|", l):
            ids.add(tm.group("id"))
        for pm in re.finditer(r"^\s*[-*]\s+(?P<id>P\d+)\s*·", l):
            ids.add(pm.group("id"))
    for f in flows:
        ids.add(f.id)
        for s in f.steps:
            ids.add(s.id)
    for lc in lifecycles:
        ids.add(lc.id)

    number = int(front.get("number", path.name[:2]))
    return Block(path, number, front.get("id", path.stem[3:]), front, sections,
                 section_lines, flows, lifecycles, ids, problems)


def load_all() -> list[Block]:
    return [load(p) for p in sorted(ROOT.glob("[0-9][0-9]-*.md"))]
