Name: Polished classic

Idea: Keep today's vertical sequence diagram in the sticky column, but draw it to the overview's standard: coloured lane heads, payload chips, check badges, two request bands and a red outcome box.

Fixes:
- Lane heads are anonymous grey chips: each head is now an overview box with a name and a role line, coloured by zone (blue for Ask Billpod, Gemini, Claude and /mcp, red for runTool, green for bills.pay). Gemini gets its own lane, and the reader sees it pick `mark_paid` from 46 tools.
- Labels spill across other lanes: every payload sits in a chip on its arrow, inside the gap between the two lanes it joins. Long calls such as `bills.pay(household, bill, body)` wrap over two or three lines. Return values sit under dashed replies. Lifelines exist only where their lane is live: Ask Billpod and Gemini end with request 1, and Claude and /mcp start in request 2, so a long arrow crosses no idle lifeline.
- The two journeys are not separated: two shaded bands, "Request 1 · in-app chat · Ask Billpod" and "An hour later · Claude over MCP". Claude and /mcp have their heads at the top of the second band.
- Checks are a tiny loop and outcomes are faint: green ✓ badges (scopes, input, household, not paid yet) and a red ✗ badge (already paid) sit on the lane that runs the check. "paid" is a bold green reply, and the refusal ends the diagram in a full-width red box.
- Text is 11-12 px grey, and future steps are unreadable at 25%: all text is 13 px or larger in full ink. Steps ahead fade only to 55%, and each step number sits on the lane where its step starts.

Costs:
- The diagram is about 2.9 times as tall as it is wide (viewBox 600 × 1756). At 570 px it is about 1670 px tall, so it no longer fits the sticky column in one view.
- `diagram()` needs a rewrite: lane widths, live ranges per lane, chip wrapping, badges and bands. The layout is not uniform any more.
- On a phone the column shrinks to about 360 px. The 13 px text then renders at about 8 px, so the phone needs the steps shown one at a time or the diagram drawn larger and scrolled sideways.

Scroll behaviour: each step is a `<g data-step>`. Steps already read stay at full ink, the step being read gets an accent outline and number, and the steps ahead drop to 55%. The stage scrolls its own content so the active step stays in view.

Store changes: lane lines carry a role and a zone colour (`Gemini | 46 tools | blue`). Marks gain `Check: lane: ✓ text` and `Check: lane: ✗ text`, a `Band:` line before steps 1 and 5, and an `Outcome:` line for the closing box. Lanes are live only between their first and last mark, which can be derived from the steps.
