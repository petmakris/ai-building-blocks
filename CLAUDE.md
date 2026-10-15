# ai-building-blocks — Claude instructions

This repo is a knowledge store about the 16 building blocks of software built around LLMs. It is storage, not a document. Tools render it on demand: `/talk`, annotate, a terminal answer, a diagram.

- Start from `README.md`. It holds the id scheme, the block table, the dependency order, the request path across blocks, the glossary and the Lomem coverage.
- Each `NN-<id>.md` file holds one block as items with stable ids (C concept, F flow step, L lifecycle, E example, N number, X verbatim Lomem code, M pitfall, Q misconception, S source). Cite and request items as `<block>.<item>`, for example `gateway.F1.3`.
- When explaining or drawing, read only the items asked for. Never invent values: use the item's own facts, and say when an item is marked unverified or made up.
- When editing, keep the format: add items with new ids, never renumber existing ones, keep provenance on every fact, and add no teaching prose or rendered diagrams.
- Code items (X) quote `~/projects/lomem` as read on 2026-10-15. Lomem moves on; when an excerpt no longer matches, update the item and its line numbers.
- `sources/` is the raw research of 14-15.10.2026. The block files win where they disagree.
