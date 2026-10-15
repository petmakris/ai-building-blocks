Name: Route on the map

Idea: Drop the lanes and draw the walkthrough as numbered stops on the overview's own map, so the reader sees each request travel through the real boxes to the same runner and service.

Fixes:
- Anonymous grey lane chips become the overview's coloured boxes in its four columns (who asks, entry point, tool layer, services), so the walkthrough and the overview read as one picture.
- Gemini gets its own box inside Ask Billpod ("picks `mark_paid` of 46 tools"), next to the confirm list (31 tools), so the actor that picks the tool is visible.
- The two journeys sit in their own labelled zones (09:00 app's chat, steps 1-4; 10:00 Claude over MCP, steps 5-7) and travel as solid and dashed routes, so the request boundaries are plain.
- Step numbers move from a detached gutter to badges on the arrows, each with its payload beside it (`runTool(mark_paid, args, ctx)`, `bills.pay(household, bill, body)`).
- Outcomes are boxes on the service: green "paid · the 09:00 request" and red "This bill is already paid."; the runner's checks (scopes ✓ input ✓) are box text at full size. Nothing is faded, so every step stays readable.

Costs:
- `story_page.py` can no longer draw it from Lanes and Steps: each block needs a hand-placed map (or the overview SVG reused with route paths added), which is per-block drawing work.
- At 1120×912 it scales to about 0.5 in the 570 px sticky column, so 13 px text renders near 7 px; it wants a wider sticky column or a full-width figure above the steps. On a phone it needs horizontal scroll or the overview's fixed min-width.
- Self steps (ctx built, Claude's own check) have no arrow, so they show as text inside a box with a badge on its edge, which reads weaker than an arrow.

Scroll behaviour: each step's arrows, badges and callouts sit in one `<g data-step="n">`; story.js moves the class `mk-route-on` (thick accent route, accent badge and payload) to the step being read, and every other step stays at full strength.

Store changes: each step needs the overview boxes its arrows run between (e.g. `Route: ask-billpod → runtool`) and the overview needs ids on its boxes; the payload already exists as the Arrow text.
