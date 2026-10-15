# Walkthrough diagram designs

Mockups for redrawing the story pages' walkthrough diagram, drawn on block 01's real walkthrough. Both pass `uv run tools/diagrams.py check --file <svg> --css <css>`.

- `classic/`: option A, chosen as the standard sequence diagram. Vertical lanes headed by overview-style boxes, a lane for the model, payload chips on the arrows, request bands, ✓ and ✗ badges, and the outcome in a box. `gen_classic.py` draws it from a script. To become a shared library for every sequence diagram Claude draws (this site, annotate, talk).
- `route/`: option C, the walkthrough as a route over the overview map. `route-steps.svg` tags each piece with the step where it first appears (`data-s`), and `build_interactive.py` builds the page that reveals one step at a time.
