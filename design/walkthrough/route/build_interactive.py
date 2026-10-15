"""Build the interactive route-map prototype as one page in the site's theme."""
import json
from pathlib import Path

HERE = Path(__file__).parent
CSS = Path.home() / "projects/ai-building-blocks/tools/site/story.css"

STEPS = [
    ("The map", "Who asks, where they come in, the tool layer and the services. Nothing has happened yet."),
    ("The app's chat builds the caller's context",
     "A person tells Ask Billpod, the app's own assistant, that they paid the electricity bill. Before any tool runs, "
     "Ask Billpod builds one context: who asks, which household, which permissions (scopes), and that the caller is the assistant."),
    ("A card before any change",
     "Gemini picks `mark_paid` from the 46 tools Ask Billpod offers. `mark_paid` is on the confirm list of 31 tools, so nothing runs yet. "
     "The person sees a card built from the stored bill and presses Approve."),
    ("The approved call goes into the one runner",
     "Every AI entry point hands its calls to `runTool`. It checks the scopes and the input against the tool's schema, then runs `mark_paid`'s handler."),
    ("The handler calls the service the Pay button calls",
     "The handler calls `bills.pay`, the same function the screen's REST route calls. The rules live there: the household filter and \"already paid\". The bill is now paid."),
    ("An hour later, Claude calls the same tool",
     "The person forgot and asks Claude to pay the bill. Claude runs its own model and calls `mark_paid` over MCP with an access token. "
     "`/mcp` builds the same kind of context. Only the scopes and the caller differ."),
    ("Here the confirmation is Claude's choice",
     "Billpod draws no card inside Claude. `mark_paid` carries `destructiveHint: true`, so Claude decides whether to ask first. "
     "The scopes, the input check and the service's rules still apply."),
    ("Same runner, same service, same refusal",
     "The call goes through the same `runTool` to the same `bills.pay`, and the service refuses: \"This bill is already paid.\" "
     "Claude gets it back as `isError: true`. The Pay button would get the same answer."),
]

svg = (HERE / "route-steps.svg").read_text()
page = f"""<meta charset="utf-8">
<title>Route Map Walkthrough</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap">
<style>
{CSS.read_text()}
{(HERE / "rp.css").read_text()}
/* Prototype page: one stage card, controls under it, the caption beside the controls. */
body {{ padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 36px 72px; font-size: 16px }}
.page {{ max-width: 1160px; margin: 0 auto; display: grid; gap: 22px }}
.kick {{ font: 600 12.5px var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--accent) }}
h1 {{ font-size: clamp(26px, 3.2vw, 36px); font-weight: 800; line-height: 1.12; margin-top: 6px }}
.intro {{ color: var(--dim); max-width: 50em; margin-top: 10px }}
.rpstage {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 18px 18px 14px }}
.rpstage .scroll {{ overflow-x: auto }}
.rpstage .ov-svg {{ min-width: 760px }}
.ctl {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 14px }}
.ctl button {{ font: 500 14px var(--sans); color: var(--fg); background: var(--sunk); border: 1px solid var(--line); border-radius: 8px; padding: 7px 12px; cursor: pointer }}
.ctl button:hover {{ border-color: var(--dim) }}
.ctl button:focus-visible, .chips button:focus-visible, .opt input:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px }}
.ctl button.primary {{ background: var(--accent); border-color: var(--accent); color: var(--card); font-weight: 600 }}
.ctl button:disabled {{ opacity: .45; cursor: default }}
.chips {{ display: flex; gap: 6px; margin-inline: 6px }}
.chips button {{ width: 34px; height: 34px; border-radius: 50%; font: 600 13px var(--mono); color: var(--dim); background: var(--card); border: 1.5px solid var(--line); cursor: pointer; padding: 0 }}
.chips button.seen {{ color: var(--blue); border-color: var(--blue) }}
.chips button.cur {{ color: var(--card); background: var(--accent); border-color: var(--accent) }}
.opt {{ margin-left: auto; display: flex; align-items: center; gap: 8px; font-size: 14px; color: var(--dim) }}
.opt input {{ width: 18px; height: 18px; accent-color: var(--accent) }}
.rpcap {{ margin-top: 14px; display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 16px; align-items: baseline; border-top: 1px solid var(--line); padding-top: 14px }}
.rpcap .n {{ font: 700 13px var(--mono); color: var(--accent); white-space: nowrap }}
.rpcap h2 {{ font-size: 21px; font-weight: 700 }}
.rpcap p {{ grid-column: 2; color: var(--fg); max-width: 62em; min-height: 3.3em }}
.rpcap code, .notes code {{ font-family: var(--mono); font-size: .9em; background: var(--sunk); border-radius: 4px; padding: 1px 4px }}
.notes {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px }}
.notes h3 {{ font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--dim) }}
.notes ul {{ margin: 8px 0 0; padding-left: 20px; display: grid; gap: 6px }}
@media (max-width: 760px) {{ .notes {{ grid-template-columns: 1fr }} .opt {{ margin-left: 0 }} }}

/* Reveal: a piece is still to come (fut), new in this step (now) or already seen. */
.ov-svg.rp [data-s] {{ transition: opacity .45s ease }}
.ov-svg.rp .fut {{ opacity: 0 }}
.rpstage.outline .ov-svg.rp rect.bx.fut, .rpstage.outline .ov-svg.rp rect.zone.fut {{ opacity: 1; fill: none; stroke: var(--line); stroke-width: 1.2; stroke-dasharray: 4 4 }}
.ov-svg.rp .ar.now {{ stroke: var(--accent); stroke-width: 3.2 }}
.ov-svg.rp .rp-bd.now {{ stroke: var(--accent); stroke-width: 3 }}
.ov-svg.rp .rp-n.now {{ fill: var(--accent) }}
.ov-svg.rp rect.bx.now {{ stroke: var(--accent); stroke-width: 2.4 }}
.ov-svg.rp text.lb.now {{ fill: var(--accent); font-weight: 600 }}
.ov-svg.rp .draw {{ transition: stroke-dashoffset .7s ease }}
@media (prefers-reduced-motion: reduce) {{ .ov-svg.rp [data-s], .ov-svg.rp .draw {{ transition: none }} }}
</style>
<div class="page">
<header><p class="kick">AI Building Blocks · block 01 · direction C, interactive</p>
<h1>The route map, one step at a time</h1>
<p class="intro">The walkthrough draws itself on the architecture map. Each step adds only the boxes and the route it needs. The step being read is in the accent colour, and the steps before it stay at full strength. Use the buttons or the arrow keys.</p></header>
<section class="rpstage outline" id="stage">
<div class="scroll">{svg}</div>
<div class="ctl">
<button type="button" id="restart">Start over</button>
<button type="button" id="prev">Previous</button>
<div class="chips" id="chips"></div>
<button type="button" class="primary" id="next">Next</button>
<button type="button" id="play">Play</button>
<button type="button" id="all">Show all</button>
<label class="opt"><input type="checkbox" id="ghost" checked> Show the boxes still to come as outlines</label>
</div>
<div class="rpcap"><span class="n" id="capn"></span><h2 id="capt"></h2><p id="capx"></p></div>
</section>
<section class="notes">
<div><h3>On the story page</h3><ul>
<li>The map sits in a full-width sticky band, and scrolling the step text plays the steps, as the buttons do here.</li>
<li>For slides, each step becomes one slide that adds to the last.</li>
<li>On a phone the map scrolls sideways inside its box and the caption stays under it.</li></ul></div>
<div><h3>What the store needs</h3><ul>
<li>The map is the block's overview SVG. Each piece gets the step where it first appears (<code>data-s</code>).</li>
<li>The step text already exists in each block's <code>### Walkthrough</code>.</li>
<li>Option A stays the standard sequence diagram. This route map is a second view of the same steps.</li></ul></div>
</section>
</div>
<script>
(() => {{
  const STEPS = {json.dumps(STEPS)};
  const svg = document.querySelector('.ov-svg.rp');
  const items = [...svg.querySelectorAll('[data-s]')];
  const last = STEPS.length - 1;
  const still = matchMedia('(prefers-reduced-motion: reduce)');
  let cur = 0, timer = null;
  items.forEach(el => {{ if (el.hasAttribute('marker-end')) el.dataset.mk = el.getAttribute('marker-end'); }});

  const chips = document.getElementById('chips');
  STEPS.forEach((s, i) => {{
    const b = document.createElement('button');
    b.type = 'button'; b.textContent = i; b.title = i ? 'Step ' + i + ': ' + s[0] : 'The empty map';
    b.setAttribute('aria-label', b.title);
    b.addEventListener('click', () => {{ stop(); show(i); }});
    chips.appendChild(b);
  }});

  const esc = (t) => t.replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}})[c]).replace(/`([^`]+)`/g, '<code>$1</code>');

  function draw(el) {{
    if (still.matches || el.classList.contains('dash') || !el.getTotalLength) return;
    const len = el.getTotalLength();
    el.classList.remove('draw');
    el.style.strokeDasharray = len; el.style.strokeDashoffset = len;
    el.getBoundingClientRect();
    el.classList.add('draw'); el.style.strokeDashoffset = 0;
    setTimeout(() => {{ el.style.strokeDasharray = ''; el.style.strokeDashoffset = ''; el.classList.remove('draw'); }}, 800);
  }}

  function show(n) {{
    const fwd = n === cur + 1;
    cur = Math.max(0, Math.min(last, n));
    items.forEach(el => {{
      const s = +el.dataset.s;
      el.classList.toggle('fut', s > cur);
      el.classList.toggle('now', s === cur);
      if (el.dataset.mk) el.setAttribute('marker-end', s === cur ? 'url(#rp-on)' : el.dataset.mk);
      if (s === cur && fwd && el.classList.contains('ar')) draw(el);
    }});
    [...chips.children].forEach((b, i) => {{ b.classList.toggle('cur', i === cur); b.classList.toggle('seen', i < cur); b.setAttribute('aria-current', i === cur ? 'step' : 'false'); }});
    document.getElementById('capn').textContent = cur ? 'Step ' + cur + ' of ' + last : 'Start';
    document.getElementById('capt').textContent = STEPS[cur][0];
    document.getElementById('capx').innerHTML = esc(STEPS[cur][1]);
    document.getElementById('prev').disabled = cur === 0;
    document.getElementById('next').disabled = cur === last;
  }}
  function stop() {{ clearInterval(timer); timer = null; document.getElementById('play').textContent = 'Play'; }}
  document.getElementById('next').onclick = () => {{ stop(); show(cur + 1); }};
  document.getElementById('prev').onclick = () => {{ stop(); show(cur - 1); }};
  document.getElementById('restart').onclick = () => {{ stop(); show(0); }};
  document.getElementById('all').onclick = () => {{ stop(); show(last); }};
  document.getElementById('play').onclick = () => {{
    if (timer) return stop();
    if (cur === last) show(0);
    document.getElementById('play').textContent = 'Pause';
    timer = setInterval(() => {{ if (cur >= last) return stop(); show(cur + 1); }}, 2600);
  }};
  document.getElementById('ghost').onchange = (e) => document.getElementById('stage').classList.toggle('outline', e.target.checked);
  addEventListener('keydown', (e) => {{
    if (e.target.closest('input, textarea')) return;
    if (e.key === 'ArrowRight') {{ stop(); show(cur + 1); }}
    if (e.key === 'ArrowLeft') {{ stop(); show(cur - 1); }}
  }});
  show(0);
}})();
</script>
"""
(HERE / "route-map.html").write_text(page)
print(HERE / "route-map.html")
