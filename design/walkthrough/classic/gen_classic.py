"""Generate seqmock/classic.svg: the polished classic sequence diagram for block 01."""
from pathlib import Path

OUT = Path(__file__).resolve().parent / "classic.svg"
W = 600
CW = {"lb": 6.4, "sb": 6.4, "mono": 7.8, "nm": 7.6}
P, AB, G, C, M, T, B = 44, 148, 246, 148, 246, 410, 534
K = "mk-classic"

def tw(cls, s):
    return len(s) * (7.8 if "mono" in cls.split() else CW[cls.split()[0]])

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def txt(cls, x, y, s, anchor=None):
    a = f' text-anchor="{anchor}"' if anchor else ""
    return f'<text class="{cls}" x="{x:.0f}" y="{y:.0f}"{a}>{esc(s)}</text>'

MARK = {"": "a", "blue": "b", "red": "r", "green": "g", "amber": "m"}

def arrow(x1, x2, y, col="", dash=False, start_gap=0):
    d = 1 if x2 > x1 else -1
    cls = "ar" + (f" {col}" if col else "") + (" dash" if dash else "")
    return f'<line class="{cls}" x1="{x1 + d * start_gap:.0f}" y1="{y:.0f}" x2="{x2 - d * 1:.0f}" y2="{y:.0f}" marker-end="url(#{K}-{MARK[col]})"/>'

def chip(xa, xb, ay, lines, col=""):
    """A payload chip resting on the arrow at ay, centred between lanes xa and xb."""
    w = max(tw(c, s) for c, s in lines) + 18
    h = 18 * len(lines) + 7
    mid = (xa + xb) / 2
    x, y = mid - w / 2, ay - 2 - h
    out = [f'<rect class="{K}-chip{(" " + col) if col else ""}" x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h}" rx="6"/>']
    for i, (c, s) in enumerate(lines):
        out.append(txt(c, mid, y + 17 + 18 * i, s, "middle"))
    return out

def below(xa, xb, ay, lines):
    mid = (xa + xb) / 2
    return [txt(c, mid, ay + 18 + 18 * i, s, "middle") for i, (c, s) in enumerate(lines)]

def note(cx, y, lines, col="", pad=12, lh=19):
    w = max(tw(c, s) for c, s in lines) + 2 * pad + 6
    h = lh * len(lines) + 12
    x = cx - w / 2
    out = [f'<rect class="bx{(" " + col) if col else ""}" x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h}" rx="8"/>']
    for i, (c, s) in enumerate(lines):
        out.append(txt(c, x + pad, y + 20 + lh * i, s))
    return out, y + h

def badges(cx, y, items):
    """A row of check badges centred on lane cx: items are (col, text)."""
    ws = [tw("lb", s) + 34 for _, s in items]
    total = sum(ws) + 8 * (len(ws) - 1)
    x = cx - total / 2
    out = []
    for (col, s), w in zip(items, ws):
        out.append(f'<rect class="bx {col}" x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="28" rx="14"/>')
        out.append(txt(f"lb {col}", x + 12, y + 19, s))
        x += w + 8
    return out, y + 28

def num(cx, cy, n, active=False):
    c = f"{K}-num" + (f" {K}-num-now" if active else "")
    return [f'<circle class="{c}" cx="{cx}" cy="{cy:.0f}" r="11"/>',
            f'<text class="{K}-numt" x="{cx}" y="{cy + 4.5:.0f}" text-anchor="middle">{n}</text>']

def head(cx, y, name, role, col, mono=False):
    w = {"Person": 82, "Ask Billpod": 106, "Gemini": 76, "runTool": 92, "bills.pay": 102, "Claude": 92, "/mcp": 86}[name]
    x = cx - w / 2
    return [f'<rect class="bx{(" " + col) if col else ""}" x="{x:.0f}" y="{y}" width="{w:.0f}" height="52" rx="8"/>',
            txt("nm mono" if mono else "nm", cx, y + 22, name, "middle"),
            txt(f"sb{(' ' + col) if col else ''}", cx, y + 42, role, "middle")]

def life(x, y1, y2):
    return f'<line class="{K}-life" x1="{x}" y1="{y1:.0f}" x2="{x}" y2="{y2:.0f}"/>'

svg_body = []
groups = []

# ---- title and lane heads
svg_body.append(txt("ttl", 20, 36, "Both doors run mark_paid through one runner,"))
svg_body.append(txt("ttl", 20, 64, "and bills.pay refuses the second payment"))
HY = 84
heads = []
heads += head(P, HY, "Person", "the payer", "")
heads += head(AB, HY, "Ask Billpod", "in-app door", "blue")
heads += head(G, HY, "Gemini", "46 tools", "blue")
heads += head(T, HY, "runTool", "one runner", "red", mono=True)
heads += head(B, HY, "bills.pay", "the service", "green", mono=True)

# ---- band 1
b1 = HY + 52 + 14
band1_label_y = b1 + 22
y = b1 + 40
lifes = []
seg_start = {P: HY + 52, AB: HY + 52, G: HY + 52, T: HY + 52, B: HY + 52}

def gap_lifelines(top, bot, xs):
    for x in xs:
        lifes.append(life(x, seg_start[x], top))
        seg_start[x] = bot

gap_lifelines(b1 + 2, b1 + 34, [P, AB, G, T, B])

def step(n, items, state):
    groups.append(f'<g class="{K}-{state}" data-step="{n}">' + "".join(items) + "</g>")

# Step 1
g = []
ay = y + 58
g += chip(P, AB, ay, [("lb", "“I paid the"), ("lb", "electricity"), ("lb", "bill”")])
g += num(P, ay, 1)
g.append(arrow(P, AB, ay, start_gap=11))
n1, yb = note(AB, ay + 10, [("lb", "ctx = person, household,"), ("lb", "all 3 scopes,"), ("lb", "caller “assistant”")])
g += n1
step(1, g, "done")
y = yb + 16

# Step 2
g = []
ay = y + 40
g += chip(AB, G, ay, [("lb", "message +"), ("lb", "46 tools")], "blue")
g += num(AB, ay, 2)
g.append(arrow(AB, G, ay, "blue", start_gap=11))
ry = ay + 22
g.append(arrow(G, AB, ry, "blue", dash=True))
g += below(AB, G, ry, [("mono blue", "mark_paid")])
bd, yb = note(AB, ry + 26, [("lb", "on the confirm list (31)")], "blue", lh=19)
g += bd
ey = yb + 16
g.append(arrow(AB, P, ey, "blue", dash=True))
card_y = ey + 8
g.append(f'<rect class="bx blue" x="6" y="{card_y}" width="140" height="70" rx="8"/>')
g.append(txt("sb", 16, card_y + 20, "card · example"))
g.append(txt("lb", 16, card_y + 40, "Mark the electricity"))
g.append(txt("lb", 16, card_y + 58, "bill paid today?"))
ay = card_y + 70 + 32
g += chip(P, AB, ay, [("lb", "Approve")], "green")
g.append(arrow(P, AB, ay, "green"))
step(2, g, "done")
y = ay + 14

# Step 3
g = []
ay = y + 40
g += chip(G, T, ay, [("lb mono", "runTool(mark_paid,"), ("lb mono", "args, ctx)")])
g += num(AB, ay, 3)
g.append(arrow(AB, T, ay, "blue", start_gap=11))
bd, yb = badges(T - 42, ay + 10, [("green", "✓ scopes"), ("green", "✓ input")])
g += bd
g.append(txt("lb", T - 42 + (tw("lb", "✓ scopes") + tw("lb", "✓ input") + 76) / 2 + 8, yb - 9, "→ handler"))
step(3, g, "done")
y = yb + 16

# Step 4 (active)
s4_top = y - 2
g = []
ay = y + 64
g += chip(T, B, ay, [("lb mono", "bills.pay("), ("lb mono", "household,"), ("lb mono", "bill, body)")], "red")
g += num(T, ay, 4, active=True)
g.append(arrow(T, B, ay, "red", start_gap=11))
bd, yb = badges(B - 18, ay + 10, [("green", "✓ household")])
g += bd
bd, yb = badges(B - 18, yb + 6, [("green", "✓ not paid yet")])
g += bd
ry = yb + 14
g.append(arrow(B, T, ry, "green", dash=True))
g += below(T, B, ry, [("nm green", "paid")])
ry2 = ry + 36
g.append(arrow(T, AB, ry2, "blue", dash=True))
g += below(G, T, ry2, [("lb mono", "{ ok: true, data }")])
s4_bot = ry2 + 30
g.insert(0, f'<rect class="{K}-lit" x="10" y="{s4_top:.0f}" width="{W - 20}" height="{s4_bot - s4_top:.0f}" rx="10"/>')
step(4, g, "now")
y = s4_bot + 8
b1_end = y

# ---- band 2
b2 = b1_end + 12
for x in (AB, G):
    lifes.append(life(x, seg_start[x], b1_end))
    del seg_start[x]
gap_lifelines(b2 + 2, b2 + 34, [P, T, B])
band2_label_y = b2 + 22
heads2 = []
H2 = b2 + 36
heads2 += head(C, H2, "Claude", "own model", "blue")
heads2 += head(M, H2, "/mcp", "MCP door", "blue", mono=True)
seg_start[C] = H2 + 52
seg_start[M] = H2 + 52
y = H2 + 52 + 6

# Step 5
g = []
ay = y + 58
g += chip(P, C, ay, [("lb", "“pay the"), ("lb", "electricity"), ("lb", "bill”")])
g += num(P, ay, 5)
g.append(arrow(P, C, ay, start_gap=11))
ay = ay + 70
g += chip(C, M, ay, [("lb mono", "tools/call"), ("lb mono", "mark_paid"), ("lb", "+ token")], "blue")
g.append(arrow(C, M, ay, "blue"))
n5, yb = note(M + 20, ay + 10, [("lb", "ctx = token’s person,"), ("lb", "same household, token’s scopes,"), ("lb", "caller “mcp”")])
g += n5
step(5, g, "next")
y = yb + 14

# Step 6
g = []
n6, yb = note(C + 8, y, [("mono amber", "destructiveHint"), ("lb", "ask the person first?"), ("sb", "Claude decides, not Billpod")], "amber")
g += n6
g += num(P, (y + yb) / 2, 6)
step(6, g, "next")
y = yb + 14

# Step 7
g = []
ay = y + 40
g += chip(M, T, ay, [("lb mono", "runTool(mark_paid,"), ("lb mono", "args, ctx)")])
g += num(M, ay, 7)
g.append(arrow(M, T, ay, "blue", start_gap=11))
bd, yb = badges(T - 42, ay + 10, [("green", "✓ scopes"), ("green", "✓ input")])
g += bd
g.append(txt("lb", T - 42 + (tw("lb", "✓ scopes") + tw("lb", "✓ input") + 76) / 2 + 8, yb - 9, "→ handler"))
ay2 = yb + 64
g += chip(T, B, ay2, [("lb mono", "bills.pay("), ("lb mono", "household,"), ("lb mono", "bill, body)")], "red")
g.append(arrow(T, B, ay2, "red"))
bd, yb = badges(B - 18, ay2 + 10, [("red", "✗ already paid")])
g += bd
ry = yb + 14
g.append(arrow(B, T, ry, "red", dash=True))
g += below(T, B, ry, [("lb red", "“This bill is"), ("lb red", "already paid.”")])
ry2 = ry + 50
g.append(arrow(T, M, ry2, "red", dash=True))
g += below(M, T, ry2, [("mono red", "{ ok: false }")])
ry3 = ry2 + 36
g.append(arrow(M, C, ry3, "red", dash=True))
g += below(C, M, ry3, [("mono red", "isError:"), ("mono red", "true")])
b2_end = ry3 + 50
for x in list(seg_start):
    lifes.append(life(x, seg_start[x], b2_end))
oy = b2_end + 12
g.append(f'<rect class="bx red" x="4" y="{oy}" width="{W - 8}" height="76" rx="10"/>')
g.append(txt("nm red", 20, oy + 26, "Refused: “This bill is already paid.”"))
g.append(txt("lb", 20, oy + 47, "The rule lives in bills.pay, so no door can skip it."))
g.append(txt("sb", 20, oy + 66, "The Pay button on the screen gets the same answer."))
step(7, g, "next")
H = oy + 76 + 8

bands = [
    f'<rect class="{K}-band" x="4" y="{b1}" width="{W - 8}" height="{b1_end - b1}" rx="12"/>',
    txt("zl", 20, band1_label_y, "REQUEST 1 · IN-APP CHAT · ASK BILLPOD"),
    f'<rect class="{K}-band" x="4" y="{b2}" width="{W - 8}" height="{b2_end - b2}" rx="12"/>',
    txt("zl", 20, band2_label_y, "AN HOUR LATER · CLAUDE OVER MCP"),
]

markers = "".join(
    f'<marker id="{K}-{m}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    f'<path d="M0,0 L10,5 L0,10 z" class="ah{(" " + c) if c else ""}"/></marker>' for c, m in MARK.items())

label = ("Mark the electricity bill paid, twice. Request 1, in the app's chat: the person writes to Ask Billpod, which builds a context "
         "with caller assistant; Gemini, offered 46 tools, picks mark_paid; it is on the confirm list of 31, so the person sees a card and approves; "
         "Ask Billpod calls runTool, which checks scopes and input; the handler calls bills.pay, which pays the bill. "
         "An hour later, Claude calls tools/call mark_paid on /mcp with an access token; the MCP door builds the same kind of context with caller mcp; "
         "destructiveHint leaves asking the person to Claude; the same runner and the same bills.pay refuse: This bill is already paid.")

svg = (f'<svg class="ov-svg {K}" viewBox="0 0 {W} {H:.0f}" role="img" aria-label="{esc(label)}">\n'
       f'<defs>{markers}</defs>\n' + "\n".join(svg_body) + "\n" + "\n".join(bands) + "\n" + "\n".join(lifes) + "\n" + "\n".join(heads) + "\n"
       + "\n".join(heads2) + "\n" + "\n".join(groups) + "\n</svg>\n")
OUT.write_text(svg)
print(OUT, H)
