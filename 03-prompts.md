---
id: prompts
number: 3
title: Prompts as versioned configuration
summary: A prompt is the plain-language text that steers a model feature on every call, so it is configuration that changes behaviour and must be kept in one copy, tested as exact text, stamped on every result and rolled back like code.
lomem_status: partly
depends_on: [gateway]
related: [context, structured, tools, memory, evals, observability, caching, governance, rollout, guardrails]
---

# Prompts as versioned configuration

## Story

### Hook
- Headline: Treat prompts as versioned configuration. ==Keep each one in one place, with a version.==
- Setup: Tunatutor, a language-tutor app in the Lomem repo, sends a block of teaching rules to the model, the AI that writes the replies, on every call. That text is the first block of the prompt; code adds more blocks after it. The rules live in code and also in a database row, so an admin can edit them. A seed script, the SQL that fills a fresh database, had put an old copy in that row. At startup the app preferred the database copy. Builds passed, tests passed and the replies stayed fluent. Only a linguist reviewing replies noticed that two rules never showed up.
- Teaser: Calling a model is the easy part. Keeping the words you send in one place, with a version on them, is where this app went wrong.

### Panel
- Title: The July 2026 stale prompt row
- Row: Numbered rules in the code copy | 15 | DEFAULT_LAYER1_TEMPLATE | accent
- Row: Rules 14 and 15 in the copy the model read | missing | old row from the seed SQL | struck
- Row: Tests that failed | 0 | the golden tests, which compare the prompt with a saved file, read the code copy | big
- Row: Found by | a linguist, 2026-07-10 | reviewing replies |
- Source: All values are real, from tunatutor's code and the July 2026 incident record (E1).
- Refs: N1, N2, N16, E1, X22, X27, C12

### Overview
- Title: Two copies of one prompt: a startup heal decides which one the model reads
- Caption: Tunatutor's Layer 1 prompt lives as a constant in code, with 15 rules and 8 slots, and as a database row that the seed SQL and the admin screen can write. In July 2026 the seed wrote an old copy without rules 14 and 15, the app preferred the row, and the golden tests stayed green because they render only the code copy. Now a startup heal resets the row to the code copy unless the archive shows a person edited it, and it writes no archive row itself. Each process caches the text, and code fills the slots and sends the whole prompt on every call. Only lesson notes carry a prompt version and model id; tutor replies carry none.
- Refs: C24, C26, C27, C44, C13, C15, C17, C19, F1, F2, F11, E1, E2, L1, N1, N2, N15, N16, N20, X17, X22, X27, X40, M3, M8, M9

### Idea
- Sentence: A prompt is configuration that changes what the feature does, so keep ==one copy==, test the exact text the model reads, stamp its version on every result, and be able to roll it back.
- Analogy: A prompt template is like a string in an i18n message file: text with named slots filled per request. The difference is that the model decides what the text means, not your code. So you learn what an edit did only by running many inputs.

### Walkthrough
- Title: The stale row is still in the database. Here is every step the fixed startup takes.
- Lead: A replay of today's fixed startup against the July row. The steps follow the real code and its test case for a stale, never-edited row (E5 Case A).
- Lanes: App, Database, Cache, Model
- Step 1 · Register the code copy before reading anything | refs: F1.1, C42, X18, X2, C8
  - Self: App: register ai-tutor-layer1 · 8 slots
  - Text: The app records the prompt's key, its default text in code, and the 8 placeholders (`{{name}}` slots) that code fills. Engineers review this code copy in git.
- Step 2 · Load the database row into the cache | refs: F1.2, F1.3, C44, F11.2, N2
  - Arrow: App → Database: read row ai-tutor-layer1
  - Reply: Database → App: old text · no rules 14, 15 | bad
  - Arrow: App → Cache: keep the row's text
  - Text: Each process keeps the row's text in memory, so building a prompt reads the cache, not the table. Before the fix, startup ended here and the row won. Steps 3 to 5 are the fix.
- Step 3 · Compare the cached text with the code copy | refs: F1.5, F1.5a, C26
  - Self: App: cached text ≠ code default
  - Text: If the two are equal there is nothing to heal. Here they differ, so the app must decide which copy wins.
- Step 4 · Ask whether a person ever edited the row | refs: F1.7, F1.7a, C27, X14, E5
  - Arrow: App → Database: count archived versions
  - Reply: Database → App: 0 → never edited by an admin | ok
  - Text: Every admin save that changes the text first copies the old text into an archive table. Zero archived versions means no person changed it, so the code copy wins. A count above zero keeps the admin's text.
- Step 5 · Reset the row without writing an archive | refs: F1.8, F1.9, X13, E6, M3
  - Arrow: App → Database: write code default · archive: false
  - Arrow: App → Cache: reload the healed text
  - Text: The heal writes the code copy over the row. It writes no archive row, because an archive row would make the row look admin-edited and stop later heals.
- Step 6 · Fill the slots and send the whole prompt on each turn | refs: F2.0, F2.3, F2.4, F2.8, C7, C6, N16
  - Arrow: Cache → App: rules text, at session start
  - Arrow: App → Model: rendered prompt with all 15 rules
  - Reply: Model → App: a fluent reply | ok
  - Text: A session reads the rules from the cache once, when it is created or reopened. On every turn, code computes the 8 slot values from the learner's level and the practice scene. The filled text goes to the model with every call.
- Step 7 · Stamp the prompt version and model on the result | refs: F8.4, C13, C14, C15, X32
  - Event: App → Database: note · prompt "v1" · model id
  - Text: Tutor replies carry no stamp today. Tunatutor's other prompt, the lesson-note writer, does. It saves its prompt version and the model id (the vendor's exact model name) in two columns on each note. Months later you can see which prompt and which model wrote a bad note.

### Takeaways
1. A prompt edit changes behaviour | The model reads the text on every call. No compiler or type check sees an edit, and a wrong prompt still gives fluent replies. | C9, C12, P1, P4
2. Keep one copy, decide who wins | Tunatutor's rule: the code copy wins unless an admin edited the row. A startup heal resets unedited stale rows. | C24, C26, X17
3. Version the rendered text | Change the version on any change to the text the model reads, including the code that fills a slot. Store the model id in its own field. | C13, C14, M4, M5
4. Golden tests pin text only | A golden test compares the rendered prompt byte for byte with a saved file. To learn whether replies got better, run an eval, a scored run of fixed inputs on old and new versions, or have a domain expert read replies from both. | C17, C19, M9

### Trap
- Title: Trusting golden tests to catch a stale copy
- Assume: "The golden tests pin the prompt, so a wrong prompt fails the build." | So the database copy feels covered by the same tests.
- Actually: The golden tests feed in the code copy, never the database row. | In July they stayed green while the model read the stale row. The fix deleted the row from the seed SQL. A drift test now reads that SQL file and fails if it inserts the row, and the startup heal resets a stale row that slips through.
- Refs: M8, Q1, E1, X21, X22, X27, X17

### Build
- Title: The fix is three calls at startup and one small heal function
- Lead: This is tunatutor's real TypeScript from the Lomem repo, trimmed from X18 and X17. The trim drops a one-off check for one legacy row.
- Refs: X17, X18, X16, C16, C13
- Code:
```ts
registerPromptTemplate(LAYER1_KEY, {                    // [1] code copy + its slots
  defaultContent: DEFAULT_LAYER1_TEMPLATE,
  variables: LAYER1_TEMPLATE_VARIABLES,
});
await loadTemplateCache(LAYER1_KEY);                    // [2] row text into the cache
await healStaleTemplate(LAYER1_KEY);

export async function healStaleTemplate(key: string): Promise<void> {
  const registration = getTemplateRegistration(key);
  if (!registration) return;
  const content = getCachedTemplate(key);                // [3] compare cache with code copy
  if (content === registration.defaultContent) return;
  const versionCount = await countTemplateVersions(key); // [4] admin-edited? keep theirs
  if (versionCount > 0) return;
  await resetPromptTemplate(key, { archive: false });   // [5] code copy over row, no archive
  await loadTemplateCache(key);
}
```
- Note: Markers [1] to [5] mark where steps 1 to 5 start. One gap before production: tutor replies carry no prompt version. Stamp each reply with a hash of the text it used, because a constant like the lesson notes' "v1" does not change when an admin edits the row.

## Summary

A product feature built on a language model is steered by a block of plain-language instructions, the prompt, which code sends to the model service with every request (S6).
Editing that text changes the feature's behaviour as surely as editing code, but no compiler, type checker or ordinary unit test notices (S6).
Treating prompts as versioned configuration means keeping one copy, testing the exact rendered text, recording which version produced which result, and being able to roll back (S6).
What is new compared with a classic backend: the model, not your code, decides what the text means; the same text can give different outputs on two calls; a new model can change what an unchanged prompt does; and a wrong prompt fails silently with fluent, plausible output (S6).
Lomem's tunatutor app implements the database-editable path (archive, rollback, startup heal, drift tests, golden tests) and stamps a version only on lesson notes, so its status is partly (X1-X42).

## Problem

- P1 · A prompt edit is a behaviour change that no compiler, type checker or ordinary unit test sees (S6, S5).
- P2 · A one-word prompt change can regress quality (S5).
- P3 · A misspelled placeholder compiles and reaches the model as literal text, and nothing fails (S6, X5).
- P4 · A wrong prompt produces replies that still read as fluent, so only a person reading closely notices; a wrong config value usually breaks something code checks (S6).
- P5 · Model output is not repeatable, so a reply cannot be asserted on the way a return value can (S6).
- P6 · A sentence added for one case is read on every call where it renders, so effects spread to cases nobody tested (S6, X40).
- P7 · Domain experts (non-engineers) need to edit prompts without a deployment (S5, S6).
- P8 · Letting experts edit a database copy creates two copies of the prompt that can disagree (S6, X22).
- P9 · Teams need to know which prompt version and which model produced which output or trace, months later (S5, S6).
- P10 · Switching models can change replies with an unchanged prompt (S6).
- P11 · A behaviour change can come from the code that computes a variable, not only from the template text (S6, X40).
- P12 · A stale database row overriding a code default is a familiar backend bug; what is new is how hard it is to see (S6).

## Concepts

### C1 · Prompt
- Definition: the text your code sends to a model service on a call (S6).
- Facts:
  - A prompt is plain-language instructions plus data (S6).
  - The prompt is sent with every request, because the model service keeps no memory between requests (S6).
  - Editing a prompt changes a feature's behaviour as surely as editing code (S6).
  - The catalogue's backend analogue for prompt management is externalised config and feature flags, with versions and environment labels (S5).
  - Fowler and Subramaniam's first pattern, Direct Prompting, is "Send prompts directly from the user to a Foundation LLM" (S11).
  - Tool descriptions are effectively prompts, so a change to a tool description is a prompt change (S5, tools block).
  - Prompts and outputs carry client data across borders, a governance concern for regulated firms (S5, governance block).
- Relations: C1 contains C3 and C4; C1 is produced as C7; C1 is steered through C5; C1 is versioned by C13.

### C2 · Large language model (model service)
- Definition: a vendor service such as Gemini or Claude that code calls over HTTP, sending text and getting text back (S6).
- Facts:
  - The model service keeps no memory between requests (S6).
  - The model picks each next word at random from a list of likely words (S6).
  - Tunatutor uses Google Gemini 2.5 Flash and 2.5 Flash Lite as its single LLM provider (S14, apps/tunatutor/CLAUDE.md:14).
  - In Lomem, every model call goes through one gateway (S14).
- Relations: C2 reads C7; C2 causes C10; C2 is identified by C14; C2 is reached through gateway.

### C3 · System prompt
- Definition: the part of a chat call that states the rules for the whole conversation (S6).
- Facts:
  - Tunatutor's system prompt is joined from several blocks of text called layers (S6, X7).
  - This block (prompts) is about the system prompt, not the history or the learner's message (S6).
  - Tunatutor's golden tests pin only the system prompt, not the chat history or the user message (X27, X28; reader question in testing).
  - System prompt leakage is entry LLM07 of the OWASP Top 10 for LLM Applications, 2025 edition (S5, guardrails block).
- Relations: C3 is part of C4; C3 is built from C8; C3 is rendered from C5.

### C4 · Chat call composition
- Definition: what every chat call sends: the system prompt, the earlier messages of the chat, and the learner's new message (S6).
- Facts:
  - Because the service keeps no memory, every chat call sends all three parts again (S6).
  - The model reads all three and writes the next reply (S6).
  - Readers without this model of a call found "every call" and "whole conversation" vague (testing).
- Relations: C4 contains C3; C4 is assembled by context (context block); C4 history is handled by memory (memory block).

### C5 · Prompt template
- Definition: the fixed prompt text with placeholders that code fills on each request (S6).
- Facts:
  - Tunatutor's Layer 1 template is the constant DEFAULT_LAYER1_TEMPLATE (X1).
  - The Layer 1 template also lives as a row keyed ai-tutor-layer1 in the prompt_templates table (S6, X18).
  - A template change, a variable-code change and a rendered-text change are three different sources of behaviour change (S6).
  - The catalogue's minimal version keeps prompts as versioned template files in the repo, rendered with typed variables (S5).
- Relations: C5 contains C6; C5 renders into C7; C5 is checked by C23; C5 is stored in C24's two copies.

### C6 · Template variable (placeholder)
- Definition: a {{name}} token in a template that code replaces with a computed value per request (S6).
- Facts:
  - Layer 1 has 8 registered variables: cefrLevel, nativeLanguage, targetLanguage, languageRatio, correctionInstruction, registerRule, vocabularyCompletenessRule, complexityGuidance (X2).
  - Code computes variable values from the learner's level and the practice scene (S6, X4).
  - A placeholder the render code does not know is left in place and reaches the model as literal text (S6, X5).
  - A placeholder written with spaces, such as {{ registerRule }}, passes the save-time check but is not substituted at render time (X10, X5; checked with copies of both regexes in node on 2026-10-15).
- Relations: C6 is part of C5; C6 is checked by C23; C6 values are computed by K3; C6 changes cause C9.

### C7 · Rendered prompt
- Definition: the final string the model actually receives, after placeholders are filled and layers joined (S6).
- Facts:
  - A behaviour change can come from the template, from the variable values, or from the code that computes a variable (S6).
  - Version ids should change on any change to the rendered text (S6, S7).
  - Golden tests pin rendered prompts byte for byte (S6, X27).
- Relations: C7 is produced from C5 + C6; C7 is pinned by C17; C7 is identified by C13 or C16.

### C8 · Layer (layered prompt)
- Definition: one block of text that the prompt builder joins with others to make the system prompt (S6, X7).
- Facts:
  - Layer 1 is the numbered list of teaching rules and is the only layer an admin can edit (S6, X7, X8).
  - Layer 1 is not the whole system prompt; later layers describe identity, tutor model, student state, output format, tools, settings, objectives, the practice scene, memory and more (X7, S14).
  - Layers are joined with the separator "\n\n---\n\n" (X7).
  - The identity layer is built in code, not as a template token, "so it always renders regardless of admin template edits" (X8).
  - The TOOLS layer is rendered from the per-session enabled tool list, which admins toggle in tutor_tool_config without a deploy (X7, X19, S14).
  - Readers did not know what Layer 1 was, or whether it was the whole system prompt (testing).
- Relations: C8 is part of C3; Layer 1 is C5; other layers change C7 without changing C5.

### C9 · Prompt change is a behaviour change
- Definition: any change to the rendered prompt, whether in the template or in the code that fills it, changes what the feature does (S6).
- Facts:
  - LOM-86 changed only the code that computes {{registerRule}}, and the commit records a behaviour change "at every level" (S6, X40).
  - No method signature or type changed in LOM-86 (S6).
  - A change of rendered text should be versioned and its diff reviewed (S6).
- Relations: C9 is caused by C5, C6 or variable code; C9 is detected by C17; C9 is measured by C19.

### C10 · Non-deterministic output
- Definition: the same prompt can give different replies on two calls, because the model samples each next word (S6).
- Facts:
  - A reply cannot be asserted on like a return value (S6).
  - Because replies vary, the release-blocking drop must be decided before an eval runs (S6).
  - Tunatutor's simulated eval calls use temperatures 0.6 to 0.8 (X36).
- Relations: C10 limits unit tests; C10 is why C19 and C20 exist.

### C11 · Effects spread
- Definition: a sentence added for one case is read on every call where it renders, so it can change replies in cases nobody tested (S6).
- Facts:
  - LOM-86 targeted A1/A2 ticket-seller role-play and also made a B1+ peer role turn casual (X40).
- Relations: C11 is a cause of C21; C11 is why C18 matters.

### C12 · Silent, plausible failure
- Definition: a wrong prompt still produces fluent replies, so no check fails and only a close human reader notices (S6).
- Facts:
  - In July 2026 every deployment matched its commit while the model read older instructions than the repository's (S6).
  - A linguist reviewing replies found the July incident, not a test (S6, X22).
- Relations: C12 is why C17, C19 and C22 are needed.

### C13 · Prompt version (version id)
- Definition: an identifier of the exact prompt that produced an output, stored with that output (S6).
- Facts:
  - The smallest version is a version constant in code stamped on every result (S6, X32).
  - Tunatutor's lesson-note writer stamps LESSON_NOTE_PROMPT_VERSION = "v1" as writerPromptVersion (X32).
  - Tunatutor's first-chat note writes writerPromptVersion "first-chat-v1" (X35).
  - Tunatutor's tutor replies carry no prompt version stamp today; only lesson notes do (S6, X35, grep of the repo on 2026-10-15).
  - The version should change on any change to the rendered text, including one-word edits and variable-code changes (S6, S7).
  - The catalogue's minimal version logs the version hash on every call (S5).
  - A version can be bumped by hand or tied by a test to a hash of the golden file (S6, S7).
- Relations: C13 is stored next to C14; C13 can be C16; C13 groups C19 scores; C13 is used by observability and governance.

### C14 · Model id
- Definition: the vendor's name for the exact model, such as gemini-2.5-flash (S6).
- Facts:
  - Switching models can change replies with an unchanged prompt (S6).
  - The model id is stored in its own field, and the prompt version does not change with it (S6, X34).
  - tutor_lesson_notes has separate writer_model and writer_prompt_version columns (S6, X34).
  - The lesson-note writer records the active provider's modelId, or "unknown" when the registry is not initialised (X33).
  - Readers did not know what a model id looks like or that models have versions (testing).
  - Quality drifts as provider models update, even when the prompt is unchanged (S5, observability block).
  - A third-party model that cannot be inspected changes underneath the product (S5, governance block).
- Relations: C14 sits next to C13; C14 is chosen by gateway.

### C15 · Version stamp on output
- Definition: the prompt version and model id saved with each stored result, or put in the log line when the output is not stored (S6).
- Facts:
  - With the stamp, months later you can see which prompt and model wrote a bad note (S6).
  - With the stamp, complaints or eval scores can be grouped by version to find a regression (S6).
  - Made-up log line: llm_call prompt=ai-tutor-layer1 prompt_version=3f9a2c model=gemini-2.5-flash latency_ms=840 (made up) (S6).
  - The catalogue's minimal observability logs model, prompt version, tokens, latency, cost, trace id and tool calls per call (S5).
  - The catalogue's minimal governance keeps an immutable audit log of prompt version, model version, inputs, outputs and approver (S5).
  - In the catalogue's request path, tracing spans per model, tool and agent step carry tokens, cost, prompt version and model version, and that trace is also the governance audit log (S5, request path step 10).
  - The catalogue's mature observability keeps dashboards per prompt version and model (S5, observability block).
- Relations: C15 carries C13 and C14; C15 enables C21 detection; C15 feeds observability.

### C16 · Prompt text hash
- Definition: a hash of the template text a call actually used, as a version id that also covers database edits (S6).
- Facts:
  - On the admin-edit path, a code version constant cannot know about an admin's edit, so each result should carry a hash of the text actually used (S6, S7).
  - Tunatutor computes an md5 of the cached row only for the heal shim, not as a version stamp (X16).
- Relations: C16 is a form of C13; C16 is needed by C24's database path.

### C17 · Golden test (golden file)
- Definition: a test that renders the prompt from fixed inputs and compares it byte for byte with a file saved earlier (S6).
- Facts:
  - A golden test says nothing about reply quality; it tells you whether the text the model will read has changed (S6).
  - Tunatutor's golden files are JSON maps from case name to rendered prompt (S6, X27).
  - Tunatutor has more than one golden file: scenario-prompts.pre-quest.json, topic-prompts.pre-learner-topic.json, and translation-drill stage1-focus.golden.json (S14, X27, X28).
  - Tunatutor's golden tests feed in the code constant through setLayer1Template(DEFAULT_LAYER1_TEMPLATE), so they cannot catch a stale database copy (S6, X27).
  - Tunatutor has no regenerate command; intended changes are re-rendered by calling the builder and noted in the test file's header comment (S6, X27, X28).
  - A common shortcut is an environment variable such as UPDATE_GOLDEN=1 that makes the test write the file; the diff then shows in review (S6).
  - The scenario judge prompt was extracted verbatim into judge-prompt.ts "so its bytes can be pinned by a golden test" (X42).
- Relations: C17 pins C7; C17 coverage is C18; C17 does not measure quality (that is C19); C17 hash can be C13.

### C18 · Golden case coverage of variable branches
- Definition: choosing golden inputs so that every branch of every variable renders at least once (S6).
- Facts:
  - A golden file without a role-play case would not have moved for LOM-86 (S6, S7).
  - A version tied to a golden-file hash moves only for golden cases that exercise the changed branch (testing).
  - LOM-86 moved noTopic and agendaTopic at turns 0 and 3, and not noObjectivesAgendaTopic (X28, X40).
- Relations: C18 limits C17; C18 limits the hash form of C13.

### C19 · Eval
- Definition: a fixed list of test inputs, each sent through the model, with every reply scored by a rule, a person, or a second model asked to grade it (S6).
- Facts:
  - Fowler and Subramaniam define Evals as "Evaluate the responses of an LLM in the context of a specific task" (S11).
  - An eval checks whether replies are good; a golden test checks whether text changed (S6).
  - Run the eval on the old and the new prompt and compare (S6).
  - The catalogue's minimal eval practice runs 50 to 200 cases in CI on every prompt or model change (S5, S12).
  - Tunatutor's real scenario eval uses a simulated learner and a simulated tutor with their own short prompts, not the production tutor prompt (S6, X36).
  - Tunatutor's translation judge gate compares a frozen old prompt (card) with a new prompt (arc) against numeric bars (S14, X38).
  - Without an eval set, a domain expert can read a sample of replies from both versions (S6).
  - Readers could not explain evals in rounds 1 and 2 (testing).
  - Every prompt or model change can silently regress something (S5, evals block).
  - Tunatutor's scenario eval counts a run as passed when enough of the scene's goals were reached and reports the share of passed runs; it tests the judge and the scenes, not the tutor prompt (S6, X36).
  - In the catalogue's request path, production failures flow into offline eval datasets, which gate the next prompt or model change in CI (S5, request path step 10).
  - The system improves only if production failures come back into eval sets and prompts (S5, feedback-loop block).
- Relations: C19 measures C9; C19 needs C20; C19 gates C34; C19 is covered in depth by evals.

### C20 · Blocking threshold set before the run
- Definition: the size of score drop that blocks a release, decided before the eval runs (S6).
- Facts:
  - Because replies vary, a threshold chosen after seeing results is not a gate (S6).
  - Made-up example: require at least 18 of 20 role-play replies to use vous and never tu (made up) (S6).
  - Real example: the translation judge gate's LEVEL_BAR is agree 0.95, place 0.95, wrong 0.9, fast 0.95 (X38).
- Relations: C20 is part of C19; C20 is why C10 matters.

### C21 · Regression (prompt sense)
- Definition: replies that got worse after a prompt or model change, as opposed to a failing test (S6, testing).
- Facts:
  - Grouping complaints or eval scores by prompt version finds regressions (S6).
  - Readers did not know this sense of the word (testing).
- Relations: C21 is detected by C15 + C19; C21 is caused by C9 or C14 change.

### C22 · Drift test
- Definition: a plain unit test that fails when the copies of a prompt could disagree again (S6).
- Facts:
  - Tunatutor's first drift test fails if the seed SQL inserts an ai-tutor-layer1 prompt_templates row (X22).
  - Tunatutor's second drift test fails if the template holds a placeholder that is not a registered variable (X23).
  - A third test asserts the five render tokens that drifted out of the stale row are present (X24).
  - A fourth test asserts no ai-tutor template default hardcodes a language name or a language-specific affirmation (X25).
  - Readers used "drift test" without a definition in round 2 (testing).
- Relations: C22 guards C24; C22 complements C17 (C17 does not see the database copy).

### C23 · Variable hygiene check (unknown placeholder rejection)
- Definition: rejecting a template whose {{tokens}} are not all registered variables (S6, X10).
- Facts:
  - The admin save path runs the check and throws a ValidationError naming the unknown variable(s) (S6, X10, X12).
  - Unregistered templates (no registry entry) skip the check (X12).
  - The check comes from ADR-029 Amendment 1, Gap 3 (X10, X12).
  - The check's regex allows spaces inside braces; the render regex does not (X10, X5).
- Relations: C23 protects C6; C23 runs in K10 and in drift test X23.

### C24 · Two copies and the source of truth
- Definition: the problem that a prompt stored both as a code constant and as a database row can disagree, so code must decide which wins (S6).
- Facts:
  - Before the July 2026 fix, the app read the row and fell back to the constant only when no row existed (S6, X11, X22).
  - After the fix, the code constant wins unless an admin has edited the row (S6, X17).
  - An admin edit wins forever unless someone resets the row (S6, testing).
  - Readers took "decide which wins" as an open question until the section stated Tunatutor's decision (testing).
- Relations: C24 is guarded by C22 and C26; C24 is caused by C39.

### C25 · Seed script (seed SQL)
- Definition: the SQL that fills a fresh database with starting data (S6).
- Facts:
  - Tunatutor's seed file 04-app-settings.sql had inserted an old copy of the Layer 1 prompt (S6, X22).
  - The seed file now carries a comment that Layer 1 is "NOT seeded here" (X21).
  - Readers found "seed" familiar but unexplained (testing).
- Relations: C25 caused the C24 incident; C25 is guarded by drift test X22.

### C26 · Startup self-heal
- Definition: code that at every startup overwrites a stored prompt row with the code constant when the row differs and was never admin-edited (S6, X17).
- Facts:
  - Every instance runs the heal at every startup (S6, X18).
  - Two instances starting together both write the same constant, so the race is harmless (S6) (unverified: follows from reading the code; no concurrent startup was run).
  - The heal writes no archive row (archive: false) (X17, X13).
  - The first version of the heal archived what it overwrote, so healed databases looked admin-edited (S6, X13, X16).
  - A one-time shim recognises that machine-written text by its md5 hash (S6, X16).
  - Readers missed the heal in round 2 and concluded a seed test cannot fix a stale row already in production (testing).
- Relations: C26 uses C27; C26 resolves C24; C26 is tested by X26.

### C27 · Never-admin-edited signal
- Definition: the inference that zero archive rows for a prompt mean no admin ever changed it (S6, X14).
- Facts:
  - Every admin save first copies the old text into prompt_template_versions when the content changes (S6, X12).
  - The signal is only as good as its bookkeeping (S6).
  - The archive table has no author column, so the signal cannot tell an admin edit from an admin reset or a machine write (X34; code reading).
- Relations: C27 is read by C26; C27 is written by C28.

### C28 · Archive (version history)
- Definition: the prompt_template_versions table, one row per previous text of a template (S6, X34).
- Facts:
  - archiveCurrentContent inserts templateKey and content; createdAt defaults to now (X12, X34).
  - An admin reset archives by default; the heal reset does not (X13).
  - The admin page lists versions newest first, shows each text, and offers Activate (X31, X30).
  - The /dump route exports all templates and versions as plain text (X30).
- Relations: C28 enables C29; C28 feeds C27.

### C29 · Rollback
- Definition: returning production to an earlier prompt (S6).
- Facts:
  - Git path: revert the commit and redeploy (S6).
  - Database path: activatePromptTemplateVersion makes an archived text current again, with no deployment (S6, X15).
  - Prompt-service path: move the production label to an earlier version number, with no deployment (S6, S3).
- Relations: C29 uses C28 or C31; C29 is the analogue of flipping a feature flag back.

### C30 · Prompt registry (prompt-management service)
- Definition: a service that stores every save of a prompt as a numbered version and serves it to apps by name and label (S6, S3).
- Facts:
  - Langfuse is an open-source tool for logging and managing LLM calls (S6, S2).
  - Langfuse stores every save of a prompt as a numbered version (S6, S3).
  - The catalogue's mature version has a registry with versions and labels such as production or staging (S5).
  - LangSmith, Braintrust and promptfoo are listed tools for this block (S5).
  - Keeping prompts in git is the default unless non-engineers must edit them (S5).
  - In the catalogue's request path, context assembly fetches the system prompt from the prompt registry and records its version (S5, request path step 5).
- Relations: C30 holds C31; C30 uses C32; C30 links C33.

### C31 · Label
- Definition: a name such as production that points at one prompt version; the app asks for "the production version of prompt X" (S6, S3).
- Facts:
  - Rolling back means moving the label to an earlier number (S6, S3).
  - Readers met "label" in a checklist step before its definition (testing).
- Relations: C31 is part of C30; C31 is like a feature flag; C31 moves after C34.

### C32 · Client-side prompt cache
- Definition: the client library's short cache of fetched prompts, so fetching adds no latency (S5, S4).
- Facts:
  - Langfuse's default cache TTL is 60 seconds (S4, S6).
  - The cache uses stale-while-revalidate (testing fact-check, S4).
  - Running servers pick up a label move within about a minute (S6) (unverified: inferred from the 60 s TTL; the docs do not state propagation time).
- Relations: C32 is part of C30; C32 delays C29 by up to its TTL.

### C33 · Trace linking
- Definition: linking traces of model calls to the prompt version they used (S6, S3).
- Facts:
  - Langfuse docs say traces "can be linked"; linking is optional (testing fact-check).
  - The catalogue's mature version links each version to traces and eval scores (S5).
- Relations: C33 is a form of C15; C33 feeds observability.

### C34 · Eval-gated promotion
- Definition: moving production to a new prompt version only after it passes an eval run (S6, S5).
- Facts:
  - Teams usually move production only after the new version passes an eval run (S6) (unverified: general practice claim; the Langfuse pages do not state it).
  - The catalogue's mature version gates promotion on an eval run, and rollback means moving a label (S5).
  - Tunatutor's TD_JUDGE_MARKS flag is meant to flip only after translation-judge-gate.ts passes (S14, X38, X39).
- Relations: C34 uses C19 + C20; C34 moves C31; rollout covers staged release.

### C35 · Register (linguistics)
- Definition: the choice between a formal and an informal way to say "you", such as vous and tu in French (S6).
- Facts:
  - Tunatutor's level default is informal for A1-A2 and formal for B1+ (X2, X4).
  - In a bound scene the scene decides the register; in a plain chat with a micro-scenario the invented role decides (X4; docs/adr/032-tutor-scenarios.md §9).
  - Readers met "register" in code before its explanation (testing).
- Relations: C35 is the value of variable registerRule (C6); C35 is the subject of E2.

### C36 · Micro-scenario and invented role
- Definition: the prompt's word for a practice scene in a plain chat, where the tutor plays a role it invents, such as a ticket seller (S6, X3, X6).
- Facts:
  - The micro-scenario runs unless reference content is active, the learner chose the topic, or there is no focus objective (X6).
  - The prompt builder records per prompt whether the tutor invents a role (lastPromptInventedRole), and the reply-chip backfill reads it (X6, X40).
  - Readers did not know "micro-scenario" (testing).
- Relations: C36 drives C35 since LOM-86; C36 is a branch C18 must cover.

### C37 · Domain terms of the running example
- Definition: tunatutor vocabulary the examples use (S6, testing).
- Facts:
  - Practice scene: a scripted role-play, such as buying a train ticket (S6).
  - Turn: one learner message and one tutor reply (S6).
  - Scenario or story: a bound practice scene; SCENARIO_PROMPT_STORIES are the golden fixture's stories (X27).
  - Quest: a scenario journey with legs; quest prompt branches are gated on isQuest (X27, X6).
  - CEFR level: A1 to C2 learner level (X2).
  - Reply suggestions (reply chips): suggested learner replies; before LOM-86 the chips offered vous while the tutor said tu (X40).
  - Readers did not know quests, scenario chats, turn, suggested replies, scaffolding, rejectedCorrection, inventedRole or spokenTurn (testing).
- Relations: C37 supports E1-E2.

### C38 · Prompt variant built in code
- Definition: one builder that renders different prompt texts by a parameter, kept in code (S14, X37).
- Facts:
  - buildJudgeTranslationPrompt serves the arc variant and the older card variant, which "stays exactly as it was" (X37).
  - The judge rubric changes with grading leniency: STRICT, BALANCED, RELAXED (S14).
- Relations: C38 is a form of C5; C38 change is gated by C34 (X38).

### C39 · Domain-expert editing
- Definition: letting a non-engineer such as a linguist tune a prompt without a deployment (S6, S5).
- Facts:
  - Tunatutor admins edit Layer 1 from an admin screen (S6, X31).
  - The cost is two copies that can disagree (S6).
- Relations: C39 causes C24; C39 needs C28, C23 and C16.

### C40 · Prompt shape versus wording
- Definition: the distinction the lesson-note comment makes ("bump when the prompt shape changes") that readers could not resolve (X32, testing).
- Facts:
  - The comment's rule is too narrow; bump on any change to the rendered text (S6).
  - Readers were unsure whether "shape" covers every wording change (testing).
- Relations: C40 is a pitfall of C13.

### C41 · Byte-stable system prompt for prompt caching
- Definition: keeping the system prompt and tool definitions identical across calls so the provider's prefix cache hits (S5, S13).
- Facts:
  - Provider prompt caching matches on exact prefix, in the order tools, then system, then messages (S5, S13).
  - The architectural rule is stable content first and variable content last (S5).
  - In tunatutor, rendered Layer 1 contains per-request variables and comes first in the system prompt (X7, X5; code reading).
- Relations: C41 links prompts to caching; C41 is affected by C6 placement.

### C42 · Template registration
- Definition: what the app records at startup for each prompt it knows: the key, the code default and the list of variables the code can fill (S6, X11, X18).
- Facts:
  - Registration lives in an in-process Map named registry (X11).
  - Two keys are registered today: ai-tutor-layer1 and public-demo-tutor (X18).
  - Readers did not know what "registered" meant for a variable (testing).
- Relations: C42 feeds C23 and C26; C42 is K6.

### C43 · Language-neutral template
- Definition: a template that names no concrete language and uses {{targetLanguage}} and {{nativeLanguage}} instead (X25).
- Facts:
  - A drift test forbids names such as French, Spanish, German and affirmations such as "Très bien" in the code defaults (X25).
  - The stale pre-batch-7 defaults carried a French worked example and French affirmations (X25).
- Relations: C43 is enforced by C22.

### C44 · In-memory template cache
- Definition: the per-process Map that holds each prompt's row text so a request does not query the table (S6, X11).
- Facts:
  - Startup loads each registered prompt's own row into the cache (S6, testing fact-check, X18).
  - If no row exists, loadTemplateCache creates it from the code default (X11).
  - A cache miss throws "was loadTemplateCache() called at startup?" (X11).
  - An admin save updates the cache only in the process that handled the save (X12; code reading).
  - A session takes its Layer 1 text from the cache once, when the engine is configured (X19).
- Relations: C44 is K7; C44 holds C5; C44 affects when C39 edits take effect.

### C45 · Prisma
- Definition: the TypeScript database library tunatutor uses, much like a JPA repository (S6).
- Facts:
  - prisma.promptTemplate and prisma.promptTemplateVersion are the two models behind this block (X12, X34).
  - Readers did not know prisma (testing).
- Relations: C45 implements K8 and K9.

## Components

| id | name | role | inputs | outputs | where it lives |
|---|---|---|---|---|---|
| K1 | DEFAULT_LAYER1_TEMPLATE | code default of the Layer 1 teaching rules | none | template text with 8 placeholders | apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-prompt-builder.ts:43-88 |
| K2 | LAYER1_TEMPLATE_VARIABLES | list of variables the code can fill | none | 8 name + description pairs | ai-tutor-prompt-builder.ts:90-99 |
| K3 | resolveLayer1Variables | computes variable values per request | session context, scaffolding, rejectedCorrection, inventedRole, spokenTurn | Layer1Variables | ai-tutor-prompt-builder.ts:138-216 |
| K4 | buildLayer1FromTemplate | substitutes {{name}} tokens | template, context, flags | rendered Layer 1 | ai-tutor-prompt-builder.ts:263-276 |
| K5 | AiTutorPromptBuilder.buildPrompt | assembles all layers into the system prompt | session context, Layer 1 template | system prompt string | ai-tutor-prompt-builder.ts:384-568 |
| K6 | template registry | records key, default and variables per prompt | registerPromptTemplate calls | registration lookups | apps/tunatutor/backend/src/services/prompt-templates.ts:43-63 |
| K7 | in-memory template cache | holds each row's text per process | prompt_templates row | cached text | prompt-templates.ts:65-89 |
| K8 | prompt_templates table | current prompt text per key | admin save, reset, startup create | key, content, updatedAt | apps/tunatutor/backend/prisma/schema.prisma:2075-2084 |
| K9 | prompt_template_versions table | archive of previous texts | archiveCurrentContent | id, templateKey, content, createdAt | schema.prisma:2086-2099 |
| K10 | upsertPromptTemplate | admin save: validate, archive, write, cache | key, content | saved row | prompt-templates.ts:105-131 |
| K11 | resetPromptTemplate | restore code default, archive optional | key, archive flag | none | prompt-templates.ts:145-165 |
| K12 | activatePromptTemplateVersion | make an archived text current | key, versionId | saved row | prompt-templates.ts:190-201 |
| K13 | healStaleTemplate | startup self-heal of an unedited stale row | key | none (row and cache reset) | apps/tunatutor/backend/src/session-types/ai-tutor/index.ts:54-85 |
| K14 | admin prompt-template routes | HTTP API for get, save, reset, versions, activate, dump | admin requests | JSON or text | apps/tunatutor/backend/src/routes/admin/prompt-templates.ts |
| K15 | PromptTemplatesPage | admin screen with editor, CUSTOM/DEFAULT pill, Reset, history | admin input | API calls | apps/tunatutor/admin/src/pages/PromptTemplatesPage.tsx |
| K16 | seed SQL 04-app-settings.sql | fills a fresh database; no longer seeds Layer 1 | none | rows | apps/tunatutor/backend/prisma/seed/04-app-settings.sql |
| K17 | layer1-template-drift.test.ts | drift tests on seed and template tokens | seed SQL, template, variables | pass or fail | ai-tutor/engine/__tests__/layer1-template-drift.test.ts |
| K18 | heal-stale-template.test.ts | tests the heal decision on a mocked store | mocked store, md5 fixture | pass or fail | ai-tutor/engine/__tests__/heal-stale-template.test.ts |
| K19 | golden tests and JSON fixtures | pin rendered prompts byte for byte | fixture inputs, DEFAULT_LAYER1_TEMPLATE | pass or fail | scenario-prompts.golden.test.ts, learner-topic.golden.test.ts, __tests__/fixtures/*.json |
| K20 | configureAiTutorEngine | gives a new or reopened session its Layer 1 text and tools | cached template, tool config | configured engine | ai-tutor/engine/ai-tutor-engine-setup.ts:27-53 |
| K21 | lesson-note writer | writes a lesson note and stamps prompt version and model | transcript, session meta | tutor_lesson_notes row | apps/tunatutor/backend/src/services/tutor-continuity/lesson-note-writer.ts |
| K22 | tutor_lesson_notes stamp columns | stored model id and prompt version | writer output | writer_model, writer_prompt_version | schema.prisma:1758-1760 |
| K23 | eval (generic) | scores replies of a prompt version | fixed inputs, prompt version | score, pass rate | generic (S6, S5) |
| K24 | scenario eval harness | simulated learner and tutor, production judge, pass rate | story, runs | ScenarioEvalRun row | apps/tunatutor/backend/src/session-types/ai-tutor/scenario/run-scenario-eval.ts |
| K25 | translation judge gate | old versus new judge prompt against numeric bars | real rows, fixture | report, gate decision | apps/tunatutor/backend/scripts/translation-judge-gate.ts |
| K26 | prompt registry service | numbered versions, labels, serving | saves, label moves | prompt by name and label | Langfuse, LangSmith, Braintrust (S2, S5) |
| K27 | client prompt cache | caches fetched prompts briefly | registry responses | prompt text | Langfuse client library (S4) |
| K28 | production label | pointer to the live version | label move | version number | Langfuse (S3) |
| K29 | model gateway | sends the rendered prompt to the provider | system prompt, messages | reply | packages/shared/src/llm/gateway (gateway block) |
| K30 | engine preview | renders the prompt skeleton for the admin tutor-tools page | student profile | final prompt, template contents | ai-tutor/engine/engine-preview.ts (X20) |
| K31 | public-demo-tutor template | Layer 1 for public demo sessions | none | template text | ai-tutor/engine/public-demo-prompt.ts (X18, X19) |
| K32 | golden-hash version test | asserts version constant equals hash of the golden file | golden file, version constant | pass or fail | proposed, not in Lomem (S6) |

## Flows

### F1 · Startup registration, load and heal
Purpose: make each process hold a correct Layer 1 text before any session opens. Trigger: backend init() of the ai-tutor session type (X18).
- F1.1 · init → registry: registerPromptTemplate("ai-tutor-layer1", {defaultContent: DEFAULT_LAYER1_TEMPLATE, variables: LAYER1_TEMPLATE_VARIABLES}) | condition: always | data: key, code default, variable list | ref: X18
- F1.2 · init → loadTemplateCache → prompt_templates: findUnique by key | condition: always | data: key | ref: X11
- F1.2a · if no row exists → prompt_templates: create row from registration.defaultContent (no archive row) → continues at F1.3 | ref: X11
- F1.2b · if no row and no registration → throw "No DB row and no registration found" → startup fails | ref: X11
- F1.3 · loadTemplateCache → cache: cache.set(key, row.content) | data: row text | ref: X11
- F1.4 · init → heal: healStaleTemplate(key) | ref: X18, X17
- F1.4a · if key not registered → return (no-op) | ref: X17
- F1.5 · heal → cache: read cached content | ref: X17
- F1.5a · if content === defaultContent → return (nothing to heal) | ref: X17
- F1.6 · heal: compute md5(content) and compare with HEAL_POISONED_LAYER1_MD5 | ref: X16, X17
- F1.6a · if md5 matches → skip the version check → continues at F1.8 | ref: X17
- F1.7 · heal → prompt_template_versions: count rows for key | ref: X14, X17
- F1.7a · if count > 0 → return (an admin edited it: keep theirs) | ref: X17
- F1.8 · heal → resetPromptTemplate(key, {archive: false}): update row content to defaultContent, set cache | data: code default | ref: X13
- F1.9 · heal → loadTemplateCache(key): refresh cache from row | ref: X17
- F1.10 · init: repeats F1.1-F1.9 for "public-demo-tutor" | ref: X18
- F1.11 · init → loadTutorToolConfigCache: pre-warm the tool list rendered into the TOOLS layer | ref: X18, X19

### F2 · Render the system prompt for one tutor turn
Purpose: produce the exact text the model reads. Trigger: a learner message in an AI tutor session (S6, X6).
- F2.0 · session create or reopen → configureAiTutorEngine: setLayer1Template(getCachedTemplate("ai-tutor-layer1" or "public-demo-tutor" when isDemo)) | condition: once per engine | data: cached text | ref: X19
- F2.0a · if the reopen path skipped setLayer1Template → buildPrompt throws on the next turn (the bug that motivated the shared helper) | ref: X19
- F2.1 · engine → buildPrompt: read this.layer1Template | ref: X6
- F2.1a · if template is null → throw "layer1Template is not set — prompt_templates DB row must be loaded at startup" | ref: X6
- F2.2 · buildPrompt: scaffolding from CEFR level; decide inventsRole = no reference content AND no learner-chosen topic AND a focus objective exists | ref: X6
- F2.3 · buildPrompt → resolveLayer1Variables: compute the 8 values | data: level, intensity, story, inventedRole, spokenTurn, rejectedCorrection | ref: X4
- F2.3a · registerRule branch: story bound → scene rule (informal, polite, or prose inference) | ref: X4
- F2.3b · registerRule branch: no story and inventedRole → INVENTED_ROLE_REGISTER_RULE | ref: X3, X4
- F2.3c · registerRule branch: no story, no invented role, level A1 or A2 → informal rule | ref: X4
- F2.3d · registerRule branch: otherwise → formal rule | ref: X4
- F2.4 · buildLayer1FromTemplate: replace each {{name}} with its value | ref: X5
- F2.4a · if {{name}} is not a known variable (typo) → token left in place as literal text → continues at F2.5 (no error) | ref: X5
- F2.4b · if the token has spaces inside the braces → regex does not match → token left as literal text → continues at F2.5 | ref: X5, X10
- F2.5 · buildPrompt: if learner chose the topic → adaptTemplateForLearnerTopic rewrites two exact sentences and appends LEARNER_TOPIC_PRECEDENCE_LINE | ref: X6, X9
- F2.5a · if an admin edited those two sentences → the exact-string rewrite does nothing, the precedence line is still appended | ref: X9 (code reading)
- F2.6 · buildPrompt: push identity, tutor model, student state, output format, TOOLS, settings, objectives (unless story), reference or scene, micro-scenario, adaptive, memory, learner address, continuity, error, learner intelligence, lexicon, session focus layers when present | ref: X7, S14
- F2.7 · buildPrompt: join layers with "\n\n---\n\n" | ref: X7
- F2.8 · engine → gateway → model: system prompt + earlier messages + new message | ref: S6, gateway block
- F2.9 · logging (proposed): log prompt key, prompt version or text hash, and model id with the call | condition: not done in tunatutor today | ref: S6

### F3 · Admin saves a template
Purpose: let an expert change the prompt without a deployment. Trigger: Save on the admin page → PUT /:key (X30, X31).
- F3.1 · admin page → API: PUT /:key with content | ref: X31, X30
- F3.1a · if key not registered → 404 NotFoundError | ref: X30
- F3.1b · if content missing or not a string → ValidationError "content is required" | ref: X30
- F3.1c · if content.length > 100000 → ValidationError "content exceeds maximum length" | ref: X30
- F3.2 · route → upsertPromptTemplate: registration lookup | ref: X12
- F3.2a · if registered → assertVariablesRegistered | ref: X10, X12
- F3.2b · if any unknown token → ValidationError naming the unknown and the registered variables → save rejected, page shows the error | ref: X10, X31
- F3.3 · upsert → prompt_templates: read existing row | ref: X12
- F3.3a · if existing and content differs → archive old content into prompt_template_versions (versionCount +1) | ref: X12
- F3.3b · if content is identical → no archive row | ref: X12
- F3.4 · upsert → prompt_templates: upsert content | ref: X12
- F3.5 · upsert → cache: cache.set(key, content) in this process only | ref: X12
- F3.6 · page: set pill CUSTOM, reload version list | ref: X31
- F3.7 · sessions and processes: new sessions on this process take the new text at F2.0; sessions already configured keep their text; other processes keep the old cache until restart | ref: X19, X11 (code reading)

### F4 · Admin resets a template to the code default
Purpose: take the current code default. Trigger: Reset on the admin page → DELETE /:key (X30, X31).
- F4.1 · page → API: DELETE /:key | ref: X31, X30
- F4.1a · if key not registered → 404 | ref: X30
- F4.2 · route → reset: resetPromptTemplate(key) with archive default true | ref: X13
- F4.3 · reset: if row differs from default → archive old content (versionCount +1) | ref: X13
- F4.4 · reset → prompt_templates: update row to defaultContent; cache.set | ref: X13
- F4.5 · page: set pill DEFAULT | ref: X31
- F4.6 · next deploy with a changed constant: row equals the old default, versionCount ≥ 1 → heal F1.7a returns → row stays on the old default | ref: X17, X13 (code reading, not run)

### F5 · Admin activates an archived version
Purpose: roll back without a deployment. Trigger: Activate in Version History → POST /:key/versions/:versionId/activate (X30, X31).
- F5.1 · page → API: POST activate | ref: X31
- F5.1a · if key not registered → 404 | ref: X30
- F5.1b · if versionId is not a number → ValidationError | ref: X30
- F5.2 · route → activatePromptTemplateVersion: find version by id and key | ref: X15
- F5.2a · if not found → error → route returns 404 | ref: X15, X30
- F5.3 · activate → upsertPromptTemplate(key, version.content): runs F3.2-F3.5 (variable check, archive of current text, write, cache) | ref: X15, X12
- F5.3a · if the archived text holds a token no longer registered → ValidationError → route turns any error into 404 NotFoundError | ref: X15, X30 (code reading)

### F6 · One prompt change, end to end
Purpose: the ordered steps for a safe prompt change (S6). Trigger: a needed change to the template or to variable code.
- F6.1 · engineer or expert: edit the template or the code that computes a variable | ref: S6
- F6.2 · CI: run the test that rejects unknown {{placeholders}} | ref: S6, X23
- F6.3 · engineer: re-render the golden file and read the diff | ref: S6, X27
- F6.3a · if no case changed but one was expected → add a case that covers the branch → back to F6.3 | ref: S6
- F6.4 · engineer: run the eval on the old and new version; compare against the threshold set beforehand | ref: S6
- F6.4a · if no eval set exists → a domain expert reads a sample of replies from both | ref: S6
- F6.4b · if score drops more than the threshold → do not release → back to F6.1 | ref: S6
- F6.5a · git path: update the version constant (to the new golden hash) and deploy | ref: S6
- F6.5b · admin-screen path: save; the archive keeps the old text; results carry the text's hash | ref: S6
- F6.5c · prompt-service path: save a new version and move the label | ref: S6, S3
- F6.6 · runtime: store or log the version id and model id with every output | ref: S6
- F6.7 · rollback: if replies get worse → revert and redeploy, activate the archived text, or move the label back | ref: S6

### F7 · Golden test run and intended re-render
Purpose: detect any change to rendered text. Trigger: test run (X27, X28).
- F7.1 · test → builder: new AiTutorPromptBuilder(); setLayer1Template(DEFAULT_LAYER1_TEMPLATE) | ref: X27
- F7.2 · test → builder: buildPrompt(fixture context for case name and turn 0 or 3) | ref: X27, X29
- F7.3 · test: assert equal to golden["name@turn"] | ref: X27
- F7.3a · if bytes differ and the change was not intended → fix the code | ref: S6
- F7.3b · if bytes differ and the change was intended → re-render the JSON by calling the builder on the fixture inputs, record why in the header comment | ref: S6, X27, X28
- F7.4 · test: also pins the scene-handoff prompt and the judge prompt (scenario file) and the greeting hint (topic file) | ref: X27, X28

### F8 · Lesson note written with a version stamp
Purpose: store which prompt and model wrote each note. Trigger: lesson-note job after a session (X32).
- F8.1 · job → writer: parse payload; load session meta and transcript | ref: X32
- F8.1a · if session missing or transcript empty → return | ref: X32
- F8.2 · writer → model: callLLM(NOTE_WRITER_SYSTEM_PROMPT, prompt, 800 tokens, json, temperature 0.3) | ref: X33
- F8.3 · writer: validate output with zod | ref: X32
- F8.3a · on any failure → log "tutor lesson-note write failed (non-fatal)" and swallow | ref: X32
- F8.4 · writer → tutor_lesson_notes: save with writerModel = deps.model and writerPromptVersion = "v1" | ref: X32, X34

### F9 · Mature registry fetch and label rollback
Purpose: serve the live prompt version without a deployment. Trigger: a model call that needs prompt X (S2, S3, S4).
- F9.1 · app → client library: get prompt X with label production | ref: S3, S6
- F9.2a · if cache hit within TTL (default 60 s) → return cached version | ref: S4
- F9.2b · if cache stale → return cached version and refresh in the background (stale-while-revalidate) | ref: S4, testing
- F9.2c · if cache miss → fetch from the registry | ref: S4
- F9.3 · app → model: call with the rendered prompt | ref: S6
- F9.4 · app → tracing: link the trace to the prompt version (optional) | ref: S3, testing
- F9.5 · rollback: operator moves production to an earlier version number → servers pick it up within about a minute (unverified) | ref: S3, S6

### F10 · Eval-gated release of a prompt variant
Purpose: switch to a new prompt only after measured agreement. Trigger: a developer runs translation-judge-gate.ts (X38).
- F10.1 · script → gateway: judge real rows and fixture rows with the old card prompt and the new arc prompt | ref: X38, X37
- F10.2 · script: compute agreement, placeable share, wrong share (read by hand), latency share | ref: X38
- F10.3a · if every bar is met (0.95, 0.95, 0.9, 0.95; replies within 2500 ms) → TR4's PR may flip TD_JUDGE_MARKS to true | ref: X38, X39
- F10.3b · if any bar is missed → TD_JUDGE_MARKS stays false; parsed replies keep marks: null | ref: X39

### F11 · How the July 2026 stale row reached production
Purpose: the failure path the fix closed. Trigger: database seeded from 04-app-settings.sql (S6, X22).
- F11.1 · seed SQL → prompt_templates: insert an old copy of ai-tutor-layer1 | ref: S6, X22
- F11.2 · startup → loadTemplateCache: row exists → cache the row's text (code default ignored) | ref: X11, X22
- F11.3 · sessions → buildPrompt: render the stale Layer 1 lacking rules 14 and 15 | ref: S6
- F11.4 · golden tests and builds: pass, because they feed the code constant | ref: S6, X27
- F11.5 · linguist: reviewing replies, notices rules 14 and 15 never show up | ref: S6, X22

### F12 · Scenario eval run
Purpose: report how often simulated runs reach a scene's goals. Trigger: admin starts an eval run (X36).
- F12.1 · harness: set run status running; load story and objectives | ref: X36
- F12.1a · if no story → "Scenario not found"; if no objectives → error | ref: X36
- F12.2 · harness: required hits from completionThreshold; maxTurns = max(12, objectives × 2 + 4) | ref: X36
- F12.3 · per run: simulated learner and simulated tutor (own short prompts) talk; production judge grades | ref: X36
- F12.3a · if a conversation throws → count it as not passed | ref: X36
- F12.4 · harness: passRate = passedCount / runs | ref: X36
- F12.5 · note: the production tutor prompt is never called, so this eval cannot score a tutor-prompt change such as LOM-86 | ref: S6, X36

## States

### L1 · prompt_templates row for one key
- States:
  - Absent: no row in prompt_templates.
  - CodeDefault: row equals the current code default; zero archive rows.
  - StaleUnedited: row differs from the current code default; zero archive rows (old seed or older default).
  - HealPoisoned: row equals the one known historical default (md5 46f3013c…); one archive row written by the July-11 heal.
  - AdminEdited: row differs from the default; one or more archive rows.
  - ResetProtected: row equals a code default because of an admin reset; one or more archive rows.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| Absent | startup loadTemplateCache | registration exists | CodeDefault | create row from constant, no archive | X11 |
| Absent | seed SQL insert (before the fix) | seed contains the row | StaleUnedited | old text stored | S6, X22 |
| CodeDefault | deploy with a changed constant, then startup | none | StaleUnedited (momentarily) → CodeDefault | heal resets with archive: false | X17, X26 |
| StaleUnedited | startup heal | versionCount = 0 | CodeDefault | row and cache set to constant | X17 |
| HealPoisoned | startup heal | md5 matches | CodeDefault | reset without version check | X16, X17 |
| CodeDefault | admin save | content differs, variables registered | AdminEdited | archive old text, write new | X12 |
| AdminEdited | admin save | content differs | AdminEdited | archive, write | X12 |
| AdminEdited | startup heal | versionCount > 0 | AdminEdited | none: admin text kept | X17 |
| AdminEdited | admin Reset | none | ResetProtected | archive admin text, write constant | X13 |
| AdminEdited | admin Activate version | variables registered | AdminEdited | archive current, write archived text | X15 |
| ResetProtected | deploy with a changed constant, then startup | versionCount > 0 | ResetProtected (now stale) | none: heal does not fire | X17, X13 (code reading) |
| any | admin save | unknown variable | any (unchanged) | ValidationError, nothing written | X10 |

### L2 · In-memory cache entry, per process
- States:
  - Empty: key not yet loaded.
  - Loaded: holds the row text read at startup.
  - LocallyUpdated: holds text written by a save, reset or activate in this process.
  - Divergent: another process saved a different text; this process still holds the old one.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| Empty | loadTemplateCache | none | Loaded | cache.set(row.content) | X11 |
| Empty | getCachedTemplate | none | Empty | throws "Cache miss" | X11 |
| Loaded | save, reset or activate in this process | none | LocallyUpdated | cache.set(new text) | X12, X13 |
| Loaded | save in another process | none | Divergent | none in this process | X11, X12 (code reading) |
| Divergent | process restart | none | Loaded | reload from row | X18 |

### L3 · A session's Layer 1 text
- States:
  - Unset: engine built, no template set.
  - Set: engine holds the text captured from the cache.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| Unset | configureAiTutorEngine | none | Set | setLayer1Template(getCachedTemplate(key)) | X19 |
| Unset | buildPrompt | none | Unset | throws "layer1Template is not set" | X6 |
| Set | admin save mid-session | none | Set | session keeps its captured text | X19 (code reading) |
| Set | session reopen (rehydrate) | none | Set | text recaptured from the cache | X19 |

### L4 · Code version constant
- States:
  - Current: constant matches the rendered text it stamps.
  - Stale: rendered text changed and the constant did not.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| Current | template or variable code change | constant not bumped | Stale | results stamped with a wrong version | S6 |
| Stale | bump by hand or golden-hash test fails and is fixed | none | Current | new stamp | S6 |
| Current | model switch | none | Current | only writer_model changes | S6 |

### L5 · Registry prompt version and label
- States:
  - Saved: a numbered version with no label.
  - Labelled: a version a label such as staging points at.
  - Production: the version the production label points at.
  - Retired: a former production version, still stored.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| Saved | move production label | eval passed (practice, unverified) | Production | clients pick it up after cache TTL | S3, S4, S6 |
| Production | label moved to another version | none | Retired | rollback or promotion | S3 |
| Retired | label moved back | none | Production | rollback with no deployment | S3, S6 |

### L6 · Golden case
- States:
  - Pinned: rendered text equals the stored text.
  - Broken: rendered text differs.
  - Re-rendered: stored text replaced and reason noted in the header.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| Pinned | code change alters rendered text | branch covered by the case | Broken | test fails | X27 |
| Pinned | code change alters rendered text | branch not covered | Pinned | change goes unseen | S6 |
| Broken | intended change | none | Re-rendered | JSON rewritten, header comment updated | X27, X28 |
| Re-rendered | test run | none | Pinned | none | X27 |

### L7 · Eval-gated prompt switch (TD_JUDGE_MARKS)
- States:
  - Off: marks: null returned; the phone draws nothing.
  - On: marks returned.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| Off | TR4's PR | translation-judge-gate bars met | On | judge marks shown | X38, X39 |

### L8 · Admin page pill
- States:
  - load: page loaded, GET /:key not yet answered.
  - DEFAULT: API returned template null.
  - CUSTOM: API returned a row.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| load | GET /:key | row exists | CUSTOM | Reset button shown | X31 |
| load | GET /:key | no row | DEFAULT | Reset hidden | X31 |
| CUSTOM | Reset | none | DEFAULT (until reload) | page shows default | X31 |

## Worked examples

### E1 · The July 2026 stale Layer 1 row (real)
- Values: real (S6, X21, X22).
- Inputs: seed file 04-app-settings.sql inserts an old ai-tutor-layer1 row; code constant DEFAULT_LAYER1_TEMPLATE includes rules 14 ({{complexityGuidance}}) and 15 (TEACHING TOOLKIT) (S6, X1).
- Steps:
  - F11.1: the seed writes the old text.
  - F11.2: startup finds the row and caches it; the constant is ignored.
  - F11.3: every tutor turn renders the old Layer 1 without rules 14 and 15.
  - F11.4: builds and golden tests stay green, because golden tests use the constant.
  - F11.5: on 2026-07-10 a linguist review (finding #33) notices rules 14 and 15 never show up.
- Fix: delete the seed duplicate (X21), add a startup heal (X17), add drift tests (X22, X23, X24).
- Outcome: each deployment matched its commit, but the instructions the model read were older than the repository's (S6).

### E2 · LOM-86: one variable change shifted register at every level (real)
- Values: real (X3, X4, X28, X29, X40).
- Inputs: golden case noTopic, A2 learner, english → french, focus objective "Work and Study Roles", turns 0 and 3 (X29).
- Before: inventsRole is true (F2.2), but registerRule took the level branch F2.3c: "Choose INFORMAL register (tu, tú, du, etc.) and use it consistently for the ENTIRE session. ..." (X4).
- Symptom: the tutor playing a ticket seller said tu while the reply chips offered vous (X40).
- Change: only the code that computes {{registerRule}}; F2.3b now returns INVENTED_ROLE_REGISTER_RULE (X3, X4).
- Golden effect: noTopic@0, noTopic@3, agendaTopic@0, agendaTopic@3 changed in the register sentence only; noObjectivesAgendaTopic did not move (no objective, no micro-scenario) (X28, X40).
- Outcome: A1/A2 learners meet polite forms in shop, ticket and cafe role-plays; at B1+ a peer role turns casual (X40). The B1+ change was a case nobody had reported (S6) (unverified: neither the commit nor the code records whether anyone reported it). Checks were a unit test that the sentence appears and the golden diff; nobody measured whether replies got better (S6).

### E3 · A misspelled placeholder (made-up typo, real behaviour)
- Values: typo {{registerRul}} is made up (S6); behaviour is real (X5, X10).
- Render path (F2.4a): vars["registerRul"] is undefined, so the text "{{registerRul}}" reaches the model and nothing fails.
- Save path (F3.2b): the admin save throws ValidationError: Template "ai-tutor-layer1" references unregistered variable(s): {{registerRul}}. Registered variables for this template: {{cefrLevel}}, {{nativeLanguage}}, {{targetLanguage}}, {{languageRatio}}, {{correctionInstruction}}, {{registerRule}}, {{vocabularyCompletenessRule}}, {{complexityGuidance}}. (message assembled from X10 and X2; not captured from a running system)
- Code path: drift test X23 fails on the constant.

### E4 · A placeholder with spaces passes the check and leaks (made-up input, verified regexes)
- Values: input "7. REGISTER CONSISTENCY: {{ registerRule }}" is made up.
- Check: the validator regex /\{\{\s*(\w+)\s*\}\}/g extracts registerRule, a registered name, so the save passes (X10).
- Render: the render regex /\{\{(\w+)\}\}/g does not match, so the model reads "{{ registerRule }}" literally (X5).
- Evidence: node run on 2026-10-15 with copies of both regexes printed validator sees [ 'registerRule' ] and rendered "7. REGISTER CONSISTENCY: {{ registerRule }}".

### E5 · Heal decisions (real test fixtures)
- Values: real, from heal-stale-template.test.ts (X26).
- CURRENT_DEFAULT = "You are a tutor. 14. {{complexityGuidance}} 15. {{registerRule}}".
- Case A: cached STALE_FRENCH_CONTENT, versionCount 0 → F1.7 → F1.8 reset with {archive: false}, cache reloaded.
- Case B: cached CURRENT_DEFAULT → F1.5a, no version check, no reset.
- Case C: cached ADMIN_EDITED_CONTENT, versionCount 1 → F1.7a, untouched.
- Case D: cached historical fixture (6259 chars, md5 46f3013c294f78b4c49c93a9ca97d180), versionCount 1 → F1.6a, version count never read, reset with {archive: false}.
- Case E: registration default changed to "You are a tutor. NEW default, edited after the last heal.", cached old default, versionCount 0 → re-heals.
- Case F: unregistered key → no-op.

### E6 · The #100 verifier trap (real)
- Values: real (X13, X16, X26).
- Step 1: the July-11 heal used the archiving resetPromptTemplate, so every database it touched got versionCount 1 with no admin edit.
- Step 2: on the next constant change, F1.7a treated those rows as admin-edited and never healed them.
- Step 3 (fix, #100, 2026-07-16 review): heals now pass archive: false, and HEAL_POISONED_LAYER1_MD5 recognises the one machine-written text.
- Outcome: no future entry is ever needed in the shim, per its comment (X16).

### E7 · Admin edit blocks later code improvements (real mechanism, code reading)
- Values: mechanism real (X12, X13, X17); sequence not run.
- Step 1: an admin saves an edit → one archive row (F3.3a).
- Step 2: a deploy improves the constant → heal sees versionCount 1 → keeps the admin text (F1.7a).
- Step 3: an admin presses Reset → admin text archived, row = current constant (F4.3-F4.4).
- Step 4: a later deploy changes the constant again → row equals the previous constant, versionCount 2 → heal does not fire (F4.6).
- Outcome: Reset takes one code default but does not return the row to automatic healing (code reading; S6 and S7 say the admin edit wins "until someone resets it").

### E8 · Eval for LOM-86 (made up)
- Values: made up (S6).
- Inputs: 20 practice scenes where the tutor plays a ticket seller, waiter or clerk.
- Rule: score 1 if a reply addresses the learner with vous and never tu.
- Steps: run on the old and the new prompt (F6.4); require at least 18 of 20 before release (F6.4b).
- Outcome: a pass gives a measured improvement that the real LOM-86 checks did not provide.

### E9 · Version stamp in a log line (made up)
- Values: made up (S6).
- Line: llm_call prompt=ai-tutor-layer1 prompt_version=3f9a2c model=gemini-2.5-flash latency_ms=840.
- Use: when the output is not stored, such as a chat reply, the log line carries both ids (F2.9).

### E10 · Lesson note stamp (real)
- Values: real (X32, X34).
- Row fields: writer_model = active provider's modelId (for example gemini-2.5-flash, an id seen in Lomem tests), writer_prompt_version = "v1".
- Use: months later, group bad notes by writer_prompt_version and writer_model.

### E11 · Translation judge gate bars (real)
- Values: real (X38).
- Bars: agreement old versus new ≥ 95%; new versus fixture expected ≥ 95% with every paraphrase RIGHT; placeable marks ≥ 95%; truly wrong marked words ≥ 90% (read by hand); arc replies within 2.5 s ≥ 95%.
- Constants: LEVEL_BAR = { agree: 0.95, place: 0.95, wrong: 0.9, fast: 0.95 }, LATENCY_LIMIT_MS = 2500, CONCURRENCY = 3.
- Outcome: only when met may TD_JUDGE_MARKS flip (F10.3a).

### E12 · Scenario eval pass rate (formula real, numbers made up)
- Formula: passRate = passedCount / runs; maxTurns = max(12, objectives × 2 + 4) (X36).
- Made-up numbers: 5 runs, 4 passed → passRate 0.8; 3 objectives → maxTurns max(12, 10) = 12 (made up).

### E13 · Label rollback in a registry (made up)
- Values: made up, mechanism from S3 and S4.
- Prompt "tutor-layer1" has versions 1, 2, 3; production points at 3; replies get worse; operator moves production to 2; servers pick up version 2 once their 60 s cache entry refreshes.

## Variants and options

- Minimal version:
  - Keep the template in the repository next to the code that renders it, as one constant (S6, S5).
  - Git gives history, review and rollback: revert the commit and redeploy (S6).
  - Add a version id and save it with every result (S6, X32).
  - Store the model id in its own field (S6, X34).
  - Put both ids in the log line when the output is not stored (S6).
  - Add a test that rejects unknown placeholders (S6, X23).
  - Render with typed variables and log the version hash on every call (S5).
- Mature version:
  - A prompt registry with numbered versions and labels such as production or staging (S5, S3).
  - Clients cache prompts, so fetching adds no latency; default TTL 60 s (S5, S4).
  - Each version is linked to traces and eval scores (S5, S3).
  - Promotion is gated on an eval run, and rollback means moving a label (S5).
- Options and trade-offs:

| id | option | when to choose | cost / risk |
|---|---|---|---|
| V1 | template in git as one constant | engineers own the prompt | every change needs a deploy; experts cannot edit (S5, S6) |
| V2 | database row editable from an admin screen, with archive | experts must edit without a deploy | two copies that can disagree; a code version cannot stamp admin edits; admin edits block later code improvements (S6, X17) |
| V3 | prompt registry service with labels | many prompts, non-engineer editors, need trace linking | another service; label changes reach servers only after cache TTL (S3, S4) |
| V4 | version id bumped by hand | few prompts, disciplined team | forgetting is silent (S6) |
| V5 | version id tied to a hash of the golden file by a test | want forgetting to fail the build | moves only for covered branches (S6, testing) |
| V6 | stamp a hash of the text actually used | database or registry path | needs the hash computed per call (S6) |
| V7 | database copy wins when present (pre-fix tunatutor) | none recommended | stale seed silently shadows code (S6, X22) |
| V8 | code wins unless an admin edited (post-fix tunatutor) | database path with occasional expert edits | needs reliable edit bookkeeping and a human Reset decision (S6, X17) |
| V9 | golden tests only | pin text cheaply | say nothing about quality (S6) |
| V10 | evals before release | any change whose quality matters | cost and time per run; threshold must be set beforehand (S6) |
| V11 | expert reads a sample of replies from both versions | no eval set yet | subjective, small sample (S6) |
| V12 | prompt variant kept in code by a parameter (arc/card) | old behaviour must stay frozen beside the new | two texts to maintain (X37) |

- Tools and products:

| name | open source or hosted | what it does here | link |
|---|---|---|---|
| Langfuse | open source (also hosted) | prompt versions, labels, client caching, trace linking | https://langfuse.com/docs/prompt-management/overview |
| LangSmith | hosted (unverified) | prompt management and evals (listed by the catalogue) | https://docs.smith.langchain.com/ |
| Braintrust | hosted (unverified) | prompt management and evals (listed by the catalogue) | https://www.braintrust.dev/docs |
| promptfoo | open source | testing prompts in the repository, CI-friendly | https://www.promptfoo.dev/docs/intro/ |
| Git | open source | history, review, rollback for prompts as code | generic |

## Facts and numbers

| id | fact | value | source id | verified |
|---|---|---|---|---|
| N1 | Date of the linguist review that found the stale Layer 1 row | 2026-07-10 (finding #33) | X22 | yes |
| N2 | Rules missing from the stale row | rules 14 (complexity) and 15 (teaching techniques) | S6, X24 | yes |
| N3 | Date of the first layer-1 heal | July 11 (2026) | X13 | yes |
| N4 | Review that found the verifier trap | finding #100, Experience Review v2, 2026-07-16 | X26 | yes |
| N5 | md5 of the heal-poisoned historical default | 46f3013c294f78b4c49c93a9ca97d180 | X16 | yes |
| N6 | Length of the heal-poisoned historical default | 6259 chars | X16, X26 | yes |
| N7 | Commits the shim comment names | 69e2799d and 540a671c | X16 | unverified (not in Lomem history) |
| N8 | LOM-86 commit | 739eb9f7c, 2026-10-12, PR #613 | X40 | yes |
| N9 | Golden prompts changed by LOM-86 | 4 (noTopic and agendaTopic, turns 0 and 3) | X28, X40 | yes |
| N10 | Golden turns per case | 0 and 3 | X29 | yes |
| N11 | Entries in scenario-prompts.pre-quest.json | 10 | X27 | yes |
| N12 | Entries in topic-prompts.pre-learner-topic.json | 9 | X28 | yes |
| N13 | Scenario golden baseline commit | 6f2d612cc (2026-10-06) | X27 | yes |
| N14 | Topic golden baseline commit | 04631ade0 (2026-09-23) | X28 | yes |
| N15 | Registered Layer 1 variables | 8 | X2 | yes |
| N16 | Numbered rules in Layer 1 | 15 | X1 | yes |
| N17 | Registered prompt template keys | 2 (ai-tutor-layer1, public-demo-tutor) | X18 | yes |
| N18 | Maximum template length on save | 100,000 characters | X30 | yes |
| N19 | Layer separator | "\n\n---\n\n" | X7 | yes |
| N20 | Lesson-note prompt version | "v1" | X32 | yes |
| N21 | First-chat note prompt version | "first-chat-v1" | X35 | yes |
| N22 | Lesson-note writer settings | 40 transcript messages, 800 max tokens, temperature 0.3 | X32, X33 | yes |
| N23 | tutor_lesson_notes schema_version default | 1 | X34 | yes |
| N24 | Langfuse prompt cache default TTL | 60 seconds | S4 | yes |
| N25 | Time for a label move to reach servers | about 1 minute | S6 | unverified |
| N26 | Made-up LOM-86 eval size and bar | 20 scenes, at least 18 of 20 | S6 | made up |
| N27 | Translation judge gate bars | agree 0.95, place 0.95, wrong 0.9, fast 0.95 | X38 | yes |
| N28 | Translation judge gate latency limit and concurrency | 2500 ms, 3 | X38 | yes |
| N29 | Scenario eval turn cap | max(12, objectives × 2 + 4) | X36 | yes |
| N30 | Scenario eval simulated call temperatures | learner 0.7, adversary 0.8, tutor 0.6; 150 max tokens | X36 | yes |
| N31 | Eval cases to run in CI on every prompt or model change | 50 to 200 | S12 via S5 | unverified (catalogue summary) |
| N32 | Tunatutor models | Gemini 2.5 Flash, Gemini 2.5 Flash Lite | S14 | yes |
| N33 | Fowler/Subramaniam catalogue | 9 patterns, published 28 Jan to 25 Feb 2025 | S11 | yes |
| N34 | Reader test scores, round 1 (senior and skimmer) | clarity 7, self-contained 6, examples 8; not passed | testing | yes |
| N35 | Reader test scores, round 2 | clarity 7, self-contained 7, examples 8; not passed | testing | yes |
| N36 | Reader test scores, round 3 | senior 7/7/8, skimmer 7/7/7; not passed | testing | yes |
| N37 | Lomem main branch read | 8e3f5d5db (2026-10-14) | S1 | yes |
| N38 | Prompt caching match order | tools, then system, then messages | S13 via S5 | yes |

## Code in Lomem

### X1 · The Layer 1 template: code default with placeholders
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-prompt-builder.ts:41-48, 51-52, 69-70, 88` (Lomem main branch as read on 2026-10-15)
- Implements: C5, C6, C8, K1
```ts
// ─── Default Layer 1 Template ───

export const DEFAULT_LAYER1_TEMPLATE = `You are a skilled, meticulous language tutor who genuinely cares about the student's progress. ACCURACY is your highest value — you would rather say nothing than teach something wrong. Before correcting a student, you mentally verify the grammar rule, consider exceptions and irregular forms, and only correct when you are certain. You treat every correction as a teaching moment that the student will memorize, so you NEVER guess. Your job is to TEACH through structured conversation — every turn should move the student forward. Warm and encouraging, but your primary job is to TEACH, not just chat.

RULES:
1. DRIVE the conversation — you decide what to practice next. Don't just react to the student. Introduce new phrases, steer toward the learning objective, and keep the lesson moving. End with a question or natural prompt — but VARY how you do it. NEVER use "Can you try saying X?" or "Can you say X?" — these are robotic and unnatural. Instead, use diverse natural prompts like: "Now tell me — how are you?", "How would you say that?", "What about your name?", "Your turn!", or simply ask a question IN the target language that requires them to respond.
2. Response length: STRICT MAX 2 sentences for routine practice turns. Up to 3 sentences ONLY when introducing a brand-new concept. If your response has more than 3 sentences, you are over-explaining — cut it down. Brevity is king.
3. {{languageRatio}}
...
6. {{correctionInstruction}}
7. REGISTER CONSISTENCY: {{registerRule}}
...
14. {{complexityGuidance}}
15. TEACHING TOOLKIT — you have several techniques. Use them naturally based on what the student needs. Don't announce switches.
...
RECOGNIZING STUDENT INTENT SHIFTS: The student may express a desire to change focus during the session (e.g., "Can we do some translations?", "I want to practice vocabulary", "Let's just talk freely", "Quiz me"). When you detect this: acknowledge briefly ("Sure, let's try some translations."), adapt your teaching technique, and stay adapted until another shift or session end.`;
```
- Notes:
  - DEFAULT_LAYER1_TEMPLATE is a template literal; the {{...}} tokens are filled per request (F2.4).
  - Rule 14 is entirely a placeholder ({{complexityGuidance}}); rule 15 is the teaching toolkit. Both were missing from the stale July row (E1).
  - Rule 13 ends with {{vocabularyCompletenessRule}} on the same line (not shown), so a variable can extend a rule in place.
  - The template text runs from line 43 to line 88 and has 15 numbered rules.

### X2 · The registered Layer 1 variables
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-prompt-builder.ts:90-99` (Lomem main branch as read on 2026-10-15)
- Implements: C6, C42, K2
```ts
export const LAYER1_TEMPLATE_VARIABLES: PromptTemplateVariable[] = [
  { name: "cefrLevel", description: "Student's CEFR level (A1–C2)" },
  { name: "nativeLanguage", description: "Student's native language name" },
  { name: "targetLanguage", description: "Student's target language name" },
  { name: "languageRatio", description: "Pre-computed language ratio rule (varies by level and pass)" },
  { name: "correctionInstruction", description: "Pre-computed correction mode (flow/balanced/precision)" },
  { name: "registerRule", description: "Register rule (informal A1–A2, formal B1+; scene-derived when a scenario is bound; role-derived when the micro-scenario has the tutor play a role)" },
  { name: "vocabularyCompletenessRule", description: "Rule 13 for A1 vocabulary completeness, empty for higher levels" },
  { name: "complexityGuidance", description: "Level- and pass-aware language complexity guidance" },
];
```
- Notes:
  - Eight names; this list is what the save check (X10) and drift test (X23) compare against.
  - The registerRule description documents all three register branches: level, scene and role (LOM-86).

### X3 · The invented-role register rule added by LOM-86
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-prompt-builder.ts:103-111` (Lomem main branch as read on 2026-10-15)
- Implements: C35, C36, F2.3b, E2
```ts
/**
 * The register rule of a plain chat whose curriculum micro-scenario
 * (buildScenarioLayer) has the tutor play a role it invents. The role decides,
 * as in a bound scene with no register marker. The level default would lock
 * "tu" onto an A1 learner's ticket seller while the reply-chip rule asks for
 * formal forms to a clerk (LOM-86). Names no language: every pair sees it.
 */
const INVENTED_ROLE_REGISTER_RULE =
  "Match the address register to the ROLE you play in this chat's micro-scenario: a service role or a stranger (shopkeeper, waiter, clerk, ticket seller, someone asking for directions) takes the FORMAL / polite-neutral address form where the practice language marks one (vous, usted, Sie, etc.); a peer, friend, classmate, or family member takes the INFORMAL form (tu, tú, du, etc.). Decide the role first, then use its register consistently while you play it — every pronoun, verb form, and possessive. NEVER mix registers.";
```
- Notes:
  - The comment names the contradiction LOM-86 fixed: the level default locked tu on an A1 ticket seller while the reply-chip rule asked for formal forms.
  - The rule names no language, so every language pair sees the same sentence.

### X4 · resolveLayer1Variables: the registerRule branches
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-prompt-builder.ts:133-147, 176-198` (Lomem main branch as read on 2026-10-15)
- Implements: K3, F2.3, F2.3a-F2.3d, C35
```ts
/**
 * @param inventedRole the prompt carries the curriculum micro-scenario, so the
 *   tutor plays a role it invents and that role decides the register. A bound
 *   scene still wins: its own rule comes first.
 */
export function resolveLayer1Variables(
  context: AiTutorSessionContext,
  scaffolding: ScaffoldingLevel = "heavy",
  rejectedCorrection: boolean = false,
  inventedRole: boolean = false,
  spokenTurn: boolean = false,
): Layer1Variables {
  const { studentProfile } = context;
  const level = studentProfile.cefrLevel;
  const intensity = studentProfile.correctionIntensity ?? "balanced";
...
  // #35 — scenario register override: in a bound scenario the SCENE decides the
  // address register, not the CEFR level. The scene text opens with a
  // machine-readable relationship token ("Peers, informal:" / "A service
  // encounter, polite-neutral:") which resolveSceneRegister resolves in CODE,
  // so the model gets ONE unambiguous directive instead of inferring the
  // register from prose (which produced mixed forms). Token-less scenes keep
  // the prose-inference fallback. The rule is REPLACED wholesale — never
  // overlaid with a competing level-keyed instruction. A plain chat whose
  // micro-scenario has the tutor play a role it invents gets the role rule
  // instead (LOM-86): the level default contradicted the reply-chip rule
  // "formal forms to a clerk". Every other plain chat keeps the level-keyed rule.
  const sceneRegister = resolveSceneRegister(studentProfile.story?.sceneText);
  const registerRule = studentProfile.story
    ? sceneRegister === "informal"
      ? "REGISTER (scene-locked): this scene is between PEERS. Use the INFORMAL address form where the practice language marks one (tu, tú, du, etc.) for the ENTIRE session — every pronoun, verb form, and possessive. NEVER mix registers, and never drift into the formal form."
      : sceneRegister === "polite"
        ? "REGISTER (scene-locked): this scene is a SERVICE ENCOUNTER between strangers. Use the FORMAL / polite-neutral address form where the practice language marks one (vous, usted, Sie, etc.) for the ENTIRE session — every pronoun, verb form, and possessive. NEVER mix registers, and never drift into the informal form."
        : "Match the address register the SCENE implies: service encounters and strangers take the FORMAL address form where the practice language marks one (vous, usted, Sie, etc.); peers, friends, and family take the INFORMAL form (tu, tú, du, etc.). Follow the relationship the scene text states and use that register consistently for the ENTIRE session — every pronoun, verb form, and possessive. NEVER mix registers."
    : inventedRole
      ? INVENTED_ROLE_REGISTER_RULE
      : level === "A1" || level === "A2"
        ? "Choose INFORMAL register (tu, tú, du, etc.) and use it consistently for the ENTIRE session. NEVER mix registers — if you start with informal, every pronoun, verb form, and possessive must stay informal."
        : "Choose FORMAL register (vous, usted, Sie, etc.) and use it consistently for the ENTIRE session. NEVER mix registers — if you start with formal, every pronoun, verb form, and possessive must stay formal.";
```
- Notes:
  - A bound story wins first; then inventedRole; then the CEFR level (A1/A2 informal, otherwise formal).
  - LOM-86 changed only this function and the constant in X3; the template (X1) did not change.
  - Line 197 is the informal sentence the beginners' tutor used to receive.

### X5 · buildLayer1FromTemplate: substitution that leaves unknown tokens in place
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-prompt-builder.ts:263-276` (Lomem main branch as read on 2026-10-15)
- Implements: K4, F2.4, F2.4a, F2.4b, C6, C7
```ts
function buildLayer1FromTemplate(
  template: string,
  context: AiTutorSessionContext,
  scaffolding: ScaffoldingLevel = "heavy",
  rejectedCorrection: boolean = false,
  inventedRole: boolean = false,
  spokenTurn: boolean = false,
): string {
  const vars = resolveLayer1Variables(context, scaffolding, rejectedCorrection, inventedRole, spokenTurn);
  return template.replace(/\{\{(\w+)\}\}/g, (match, name: string) => {
    const value = vars[name as keyof Layer1Variables];
    return value !== undefined ? value : match;
  });
}
```
- Notes:
  - `return value !== undefined ? value : match;` keeps an unknown {{token}} as literal text: no error, no log.
  - The render regex `/\{\{(\w+)\}\}/g` allows no spaces inside the braces; the save check in X10 does (E4).

### X6 · buildPrompt: the missing-template guard, the invented-role decision and the learner-topic rewrite
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-prompt-builder.ts:384-389, 411-433` (Lomem main branch as read on 2026-10-15)
- Implements: K5, F2.1, F2.1a, F2.2, F2.5, C36
```ts
  buildPrompt(context: AiTutorSessionContext): string {
    const effectiveTemplate = this.layer1Template;

    if (!effectiveTemplate) {
      throw new Error("[AI Tutor] layer1Template is not set — prompt_templates DB row must be loaded at startup");
    }
...
    // The curriculum micro-scenario runs unless reference content is active
    // (irrelevant) or the learner chose the topic (it would pull the chat off
    // that topic). It needs a focus objective, so this is exactly when
    // buildScenarioLayer renders. It has the tutor play a role it invents, and
    // that role decides the address register in Layer 1 (LOM-86).
    const inventsRole =
      !hasReferenceContent && !learnerChosenTopic(context.studentProfile) && focusedObj !== undefined;
    this.lastPromptInventedRole = inventsRole;

    const renderedLayer1 = buildLayer1FromTemplate(
      effectiveTemplate,
      context,
      scaffolding,
      this.rejectNextCorrection,
      inventsRole,
      this.spokenTurn,
    );
    // A learner-topic chat: the template's steer-toward-the-objective sentences
    // would contradict "follow the learner" (ADR-046) — rewrite them and state
    // that the TOPIC rules win. Every other chat keeps the template as rendered.
    const layer1 = learnerChosenTopic(context.studentProfile)
      ? `${adaptTemplateForLearnerTopic(renderedLayer1)}\n\n${LEARNER_TOPIC_PRECEDENCE_LINE}`
      : renderedLayer1;
```
- Notes:
  - The thrown message still says the prompt_templates row must be loaded at startup (L3).
  - inventsRole is decided once per prompt and passed to Layer 1, so the register rule and the micro-scenario layer always agree.
  - lastPromptInventedRole is what the reply-chip backfill reads (LOM-86).

### X7 · buildPrompt: layer order and the join
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-prompt-builder.ts:460-479, 535-538, 567-568` (Lomem main branch as read on 2026-10-15)
- Implements: C3, C8, F2.6, F2.7
```ts
    // WHO speaks: the tutor, or in a scenario the person of the scene this prompt plays.
    const identityLayer = buildTutorIdentityLayer(context, storyScene?.currentActKey ?? null);

    const layers = [
      layer1,
      ...(identityLayer ? [identityLayer] : []),
      buildTutorModelLayer(this.tutorModel, context),
      buildLayer2StudentState(context),
      buildLayer3OutputFormat(context, storyScene?.goalsMet ?? false),
    ];

    // TOOLS section — tells the model which callable tools it has and when to
    // use them. Without this, the engine hands the model the function-call schema but never
    // instructs it to use tools, so it defaults to narrating (e.g. typing out
    // a conjugation table instead of calling show_conjugation_info). Sourced
    // from the per-session enabled list so disabled tools never appear.
    const toolsLayer = buildToolsPromptSection(this.enabledToolNames);
    if (toolsLayer) {
      layers.push(toolsLayer);
    }
...
    const layer5 = buildLayer5UserMemory(context);
    if (layer5) {
      layers.push(layer5);
    }
...
    return layers.join("\n\n---\n\n");
  }
```
- Notes:
  - Layer 1 (the only admin-editable text) comes first; every later layer is built in code.
  - The TOOLS section comes from the enabled tool list, which admins toggle in the database (X19), so it can change the rendered prompt without a template edit.
  - Many more optional layers are pushed between line 479 and line 567 (settings, objectives, scene, micro-scenario, adaptive, memory, address, continuity, errors, learner intelligence, lexicon, session focus).

### X8 · The identity layer is built in code so admin edits cannot remove it
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-prompt-builder.ts:611-619` (Lomem main branch as read on 2026-10-15)
- Implements: C8
```ts
// ─── Tutor Identity Layer (WHO the tutor is — name + gender) ───

// tutor-model.ts deliberately defines HOW the tutor teaches, never WHO it is,
// so without this the LLM invents a name/gender each session that can clash
// with the selected voice (a female voice self-introducing as "Mateo"). The
// persona is resolved from the Azure voice the learner actually hears — see
// tutor-persona-identity.ts. Built in code (not a DB prompt
// template token) so it always renders regardless of admin template edits.
function buildTutorIdentityLayer(context: AiTutorSessionContext, currentActKey: string | null): string | null {
```
- Notes:
  - Design choice: text that must always be present is kept out of the admin-editable template.

### X9 · Learner-topic chats rewrite two exact sentences of the rendered template
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/learner-topic.ts:119-139` (Lomem main branch as read on 2026-10-15)
- Implements: F2.5, F2.5a
```ts
const LEARNER_TOPIC_TEMPLATE_REWRITES: ReadonlyArray<readonly [string, string]> = [
  [
    "Introduce new phrases, steer toward the learning objective, and keep the lesson moving.",
    "Introduce new phrases and keep the lesson moving inside what the learner is currently talking about.",
  ],
  [
    "Steer conversation toward contexts where the student's struggling words appear naturally.",
    "Bring in the student's struggling words only where they fit what the learner is currently talking about.",
  ],
];

/** A template rendered for a learner-topic chat: its steering sentences rewritten. */
export function adaptTemplateForLearnerTopic(rendered: string): string {
  let out = rendered;
  for (const [from, to] of LEARNER_TOPIC_TEMPLATE_REWRITES) out = out.split(from).join(to);
  return out;
}

/** Appended after the template in a learner-topic chat: the topic rules win. */
export const LEARNER_TOPIC_PRECEDENCE_LINE =
  "THE LEARNER CHOSE THIS CHAT'S TOPIC: wherever these instructions tell you to drive the lesson or lead the conversation somewhere, do it only inside what the learner is currently talking about. Never move the conversation toward a lesson goal — the TOPIC rules below take precedence.";
```
- Notes:
  - The rewrite matches exact strings from DEFAULT_LAYER1_TEMPLATE; if an admin edits those sentences, the rewrite silently does nothing (code reading).
  - This is a second place where code depends on the template's wording, besides the placeholders.

### X10 · Placeholder extraction and the unknown-variable check
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/prompt-templates.ts:5-41` (Lomem main branch as read on 2026-10-15)
- Implements: C23, F3.2a, F3.2b, E3
```ts
// Extract {{varName}} tokens from template content. Used by the upsert
// path to catch typos and stale variable references before they ship
// (Gap 3 in the ADR-029 Amendment 1 inventory). Permissive about
// surrounding whitespace inside the braces — `{{ foo }}` and `{{foo}}`
// both resolve to the same name.
const TEMPLATE_TOKEN_REGEX = /\{\{\s*(\w+)\s*\}\}/g;

function extractTemplateVariables(content: string): Set<string> {
  const names = new Set<string>();
  let match;
  while ((match = TEMPLATE_TOKEN_REGEX.exec(content)) !== null) {
    names.add(match[1]);
  }
  return names;
}

function assertVariablesRegistered(
  key: string,
  content: string,
  registered: PromptTemplateVariable[],
): void {
  const referenced = extractTemplateVariables(content);
  const registeredNames = new Set(registered.map((v) => v.name));
  const unknown: string[] = [];
  for (const name of referenced) {
    if (!registeredNames.has(name)) unknown.push(name);
  }
  if (unknown.length > 0) {
    throw new ValidationError(
      `Template "${key}" references unregistered variable(s): ${unknown
        .map((n) => `{{${n}}}`)
        .join(", ")}. Registered variables for this template: ${
        Array.from(registeredNames).map((n) => `{{${n}}}`).join(", ") || "(none)"
      }.`,
    );
  }
}
```
- Notes:
  - The comment cites ADR-029 Amendment 1, Gap 3.
  - The regex is permissive about whitespace: `{{ foo }}` and `{{foo}}` resolve to the same name here, but not in the render code (X5).
  - The error message lists both the unknown tokens and every registered token.

### X11 · Template registry and the in-memory cache
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/prompt-templates.ts:43-89` (Lomem main branch as read on 2026-10-15)
- Implements: K6, K7, C42, C44, F1.2, F1.2a, F1.2b, F1.3, L2
```ts
// ─── Registry ───

interface TemplateRegistration {
  defaultContent: string;
  variables: PromptTemplateVariable[];
}

const registry = new Map<string, TemplateRegistration>();

export function registerPromptTemplate(
  key: string,
  registration: TemplateRegistration,
): void {
  registry.set(key, registration);
}

export function getTemplateRegistration(
  key: string,
): TemplateRegistration | undefined {
  return registry.get(key);
}

// ─── In-Memory Cache ───

const cache = new Map<string, string>();

export async function loadTemplateCache(key: string): Promise<void> {
  let row = await prisma.promptTemplate.findUnique({ where: { key } });
  if (!row) {
    const registration = registry.get(key);
    if (!registration) {
      throw new Error(`[prompt-templates] No DB row and no registration found for key "${key}"`);
    }
    row = await prisma.promptTemplate.create({
      data: { key, content: registration.defaultContent },
    });
  }
  cache.set(key, row.content);
}

export function getCachedTemplate(key: string): string {
  const value = cache.get(key);
  if (!value) {
    throw new Error(`[prompt-templates] Cache miss for key "${key}" — was loadTemplateCache() called at startup?`);
  }
  return value;
}
```
- Notes:
  - loadTemplateCache is create-when-absent: an existing row always wins over the code default. Before the heal, that was the July bug (F11.2).
  - Both Maps are per process; nothing in this file refreshes another process's cache.

### X12 · Archive and admin save (upsertPromptTemplate)
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/prompt-templates.ts:99-131` (Lomem main branch as read on 2026-10-15)
- Implements: K9, K10, C28, F3.2-F3.5, L1
```ts
async function archiveCurrentContent(key: string, currentContent: string): Promise<void> {
  await prisma.promptTemplateVersion.create({
    data: { templateKey: key, content: currentContent },
  });
}

export async function upsertPromptTemplate(
  key: string,
  content: string,
): Promise<{ key: string; content: string; updatedAt: Date }> {
  // Variable hygiene check (ADR-029 Amendment 1, Gap 3). If the template
  // is registered with a variable list, refuse to save content that
  // references any token outside that list — those would silently fail to
  // resolve at render time and leak `{{garbage}}` straight into the LLM
  // prompt. Unregistered templates (no registry entry) skip the check.
  const registration = registry.get(key);
  if (registration) {
    assertVariablesRegistered(key, content, registration.variables);
  }

  const existing = await prisma.promptTemplate.findUnique({ where: { key } });
  if (existing && existing.content !== content) {
    await archiveCurrentContent(key, existing.content);
  }

  const row = await prisma.promptTemplate.upsert({
    where: { key },
    create: { key, content },
    update: { content },
  });
  cache.set(key, row.content);
  return row;
}
```
- Notes:
  - Archive happens only when the content actually changes; an identical save writes no version row.
  - cache.set updates this process only (L2).

### X13 · resetPromptTemplate and why the heal must not archive
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/prompt-templates.ts:133-165` (Lomem main branch as read on 2026-10-15)
- Implements: K11, F1.8, F4.2-F4.4, C26, E6
```ts
/**
 * Reset a template row to its registered code default.
 *
 * `archive` (default true) controls whether the outgoing content is archived
 * as a `prompt_template_versions` row first. Admin-triggered resets keep the
 * default (an admin may want the old content back). The startup self-heal
 * (`ai-tutor/index.ts` → `healStaleTemplate`) passes `archive: false`: it only
 * ever overwrites machine-authored content (a stale code default), and
 * archiving from the heal path would bump `versionCount` 0→1 and permanently
 * poison the "never admin-edited" signal the heal itself relies on — the
 * exact trap that kept the July-11 layer-1 heal from re-firing (#100).
 */
export async function resetPromptTemplate(
  key: string,
  options: { archive?: boolean } = {},
): Promise<void> {
  const { archive = true } = options;
  const registration = registry.get(key);
  if (!registration) {
    throw new Error(`[prompt-templates] No registration found for key "${key}"`);
  }

  const existing = await prisma.promptTemplate.findUnique({ where: { key } });
  if (archive && existing && existing.content !== registration.defaultContent) {
    await archiveCurrentContent(key, existing.content);
  }

  await prisma.promptTemplate.update({
    where: { key },
    data: { content: registration.defaultContent },
  });
  cache.set(key, registration.defaultContent);
}
```
- Notes:
  - Admin resets archive by default; the startup heal passes archive: false.
  - The comment records the #100 trap: archiving from the heal path bumps versionCount 0 to 1 and poisons the never-edited signal.

### X14 · countTemplateVersions: the never-edited signal
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/prompt-templates.ts:167-177` (Lomem main branch as read on 2026-10-15)
- Implements: C27, F1.7
```ts
/**
 * Count archived versions for a template key (rows in `prompt_template_versions`).
 * A row is only archived by `upsertPromptTemplate`/`resetPromptTemplate` when
 * the content actually changes from what's stored, so `count === 0` means
 * the template has never been edited away from whatever it was created
 * with — used by startup self-heal checks to avoid clobbering a genuine
 * admin edit (see `ai-tutor/index.ts`'s layer-1 self-heal, #33).
 */
export async function countTemplateVersions(key: string): Promise<number> {
  return prisma.promptTemplateVersion.count({ where: { templateKey: key } });
}
```
- Notes:
  - count === 0 means never edited away from the content the row was created with.

### X15 · activatePromptTemplateVersion: rollback through the save path
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/prompt-templates.ts:190-201` (Lomem main branch as read on 2026-10-15)
- Implements: K12, C29, F5.2, F5.3
```ts
export async function activatePromptTemplateVersion(
  key: string,
  versionId: number,
): Promise<{ key: string; content: string; updatedAt: Date }> {
  const version = await prisma.promptTemplateVersion.findFirst({
    where: { id: versionId, templateKey: key },
  });
  if (!version) {
    throw new Error(`[prompt-templates] Version ${versionId} not found for key "${key}"`);
  }
  return upsertPromptTemplate(key, version.content);
}
```
- Notes:
  - Activation calls upsertPromptTemplate, so it runs the variable check and archives the current text first.

### X16 · The one-time md5 shim for the heal-poisoned default
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/index.ts:38-52` (Lomem main branch as read on 2026-10-15)
- Implements: C26, F1.6, E6
```ts
// One-time historical shim for the July-11 layer-1 self-heal's own archive
// (#100 "verifier trap"): that heal used the archiving resetPromptTemplate,
// so every DB it touched now has versionCount === 1 even though no admin ever
// edited the row — the never-edited signal is poisoned for exactly one known
// content: the pre-batch-7 DEFAULT_LAYER1_TEMPLATE (6259 chars) as it stood
// from heal commit 69e2799d through 540a671c^, extractable via
// `git show 69e2799d:apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-prompt-builder.ts`.
// A row whose content md5-matches this string is provably machine-authored
// and safe to heal regardless of its version count. New heals never archive
// (archive: false below), so no future entry is ever needed here.
const HEAL_POISONED_LAYER1_MD5 = "46f3013c294f78b4c49c93a9ca97d180";

function md5(content: string): string {
  return createHash("md5").update(content, "utf8").digest("hex");
}
```
- Notes:
  - The comment names commits 69e2799d and 540a671c, which are not reachable in Lomem's history today (see Open questions).
  - Length 6259 chars and the md5 are pinned again in X26.

### X17 · healStaleTemplate: the startup self-heal
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/index.ts:54-85` (Lomem main branch as read on 2026-10-15)
- Implements: K13, C26, C27, F1.4-F1.9, L1
```ts
/**
 * Idempotent, admin-safe startup self-heal for a registered prompt template
 * (#33 → generalized by #100). If the cached DB content differs from the
 * registered code default AND the row was never admin-edited, reset it to
 * the code default. "Never admin-edited" holds when either:
 *   - the template has zero archived versions (an admin edit always archives
 *     the prior content first, so versionCount ≥ 1 after any real edit), or
 *   - the content byte-matches the one known heal-poisoned historical
 *     default (see HEAL_POISONED_LAYER1_MD5).
 * The reset deliberately does NOT archive (archive: false) — archiving from
 * the heal path would itself bump versionCount and re-poison the signal on
 * the next code-constant change.
 *
 * Exported (in addition to being called from `init()`) so tests can exercise
 * the self-heal decision directly against a mocked template store.
 */
export async function healStaleTemplate(key: string): Promise<void> {
  const registration = getTemplateRegistration(key);
  if (!registration) return;

  const content = getCachedTemplate(key);
  if (content === registration.defaultContent) return;

  const isHealPoisonedHistoricalDefault = md5(content) === HEAL_POISONED_LAYER1_MD5;
  if (!isHealPoisonedHistoricalDefault) {
    const versionCount = await countTemplateVersions(key);
    if (versionCount > 0) return;
  }

  await resetPromptTemplate(key, { archive: false });
  await loadTemplateCache(key);
}
```
- Notes:
  - Order of checks: registered, differs from default, md5 shim, version count, reset without archive, reload cache.
  - It is exported so the tests in X26 can call it directly.

### X18 · init(): register, load and heal each prompt at startup
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/index.ts:115-132` (Lomem main branch as read on 2026-10-15)
- Implements: F1.1, F1.10, F1.11, C42
```ts
    registerPromptTemplate(LAYER1_KEY, {
      defaultContent: DEFAULT_LAYER1_TEMPLATE,
      variables: LAYER1_TEMPLATE_VARIABLES,
    });
    await loadTemplateCache(LAYER1_KEY);
    await healStaleTemplate(LAYER1_KEY);

    registerPromptTemplate(PUBLIC_DEMO_KEY, {
      defaultContent: DEFAULT_PUBLIC_DEMO_TUTOR_TEMPLATE,
      variables: [...PUBLIC_DEMO_TEMPLATE_VARIABLES],
    });
    await loadTemplateCache(PUBLIC_DEMO_KEY);
    await healStaleTemplate(PUBLIC_DEMO_KEY);

    // Pre-warm the tutor-tool-config cache so configureAiTutorEngine can
    // read enabled tools + numeric knobs synchronously when a session opens
    // (ADR-029).
    await loadTutorToolConfigCache();
```
- Notes:
  - Two keys today: ai-tutor-layer1 and public-demo-tutor.
  - Every instance runs this on every startup (S6).

### X19 · configureAiTutorEngine: a session captures its Layer 1 text once
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-engine-setup.ts:1-13, 27-53` (Lomem main branch as read on 2026-10-15)
- Implements: K20, F2.0, F2.0a, L3
```ts
/**
 * configureAiTutorEngine — centralized post-construction setup for a
 * fresh AiTutorConversationEngine instance.
 *
 * Both the fresh-session path (routes/sessions.ts createEngine) and the
 * reopen path (ai-tutor-rehydrate.ts) call this helper so every engine
 * runtime knob is set in one place. Extracted because code review found
 * that the rehydrate path was missing setLayer1Template, which would
 * cause buildPrompt to throw on the next turn after reopen.
 *
 * Any new per-engine setup step (personality, scenario phase, adaptive
 * knobs, etc.) should be added here so both paths inherit it automatically.
 */
...
export function configureAiTutorEngine(
  engine: AiTutorConversationEngine,
  options: ConfigureAiTutorEngineOptions = {},
): void {
  // 1. Load the layer-1 prompt template into the prompt builder. Without
  // this, buildPrompt throws "layer1Template is not set" on the next turn.
  engine.promptBuilderInstance.setLayer1Template(
    getCachedTemplate(options.isDemo ? "public-demo-tutor" : "ai-tutor-layer1"),
  );

  // 2. Declare the tutor's tool catalog. The route connects the tools to the
  //    socket separately when it binds. The enabled tool list is read from
  //    tutor_tool_config (ADR-029) so admins can toggle individual tools
  //    without a deploy. Cache is pre-warmed at startup by the ai-tutor index
  //    init.
  const config = getTutorToolConfigCached();
  engine.setTools(
    config.enabledTools
      .map((name) => TUTOR_TOOLS_BY_NAME[name])
      .filter((t): t is TutorToolSpec => t !== undefined),
  );
  // Render the same enabled list into the prompt's TOOLS section so the
  // model is actually told it has these tools and when to call them.
  // Without this the model receives the function schema but no instruction
  // to use it, and narrates instead of invoking (e.g. show_conjugation_info).
  engine.promptBuilderInstance.setEnabledToolNames(config.enabledTools);
}
```
- Notes:
  - The template is read from the cache when the engine is configured, not on every turn.
  - The header records that the reopen path once forgot setLayer1Template, which made buildPrompt throw.

### X20 · Engine preview renders the prompt skeleton from the cached template
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/engine-preview.ts:15-39` (Lomem main branch as read on 2026-10-15)
- Implements: K30
```ts
// Build the assembled prompt skeleton the ai-tutor engine would produce for a
// given student profile. Lives inside the ai-tutor session type because it
// depends on ai-tutor's prompt builder — core infrastructure (services/) must
// never import a session type, so this preview helper belongs here, alongside
// the builder it exercises. The admin tutor-tools route consumes it.
export function buildEnginePreviewPrompt(studentProfile: PreviewStudentProfile): EnginePreviewPrompt {
  // Minimal session context — enough for the prompt builder to exercise the
  // static skeleton without needing pre-populated user memory / recurring
  // errors / struggling vocab.
  const minimalContext = {
    sessionType: "ai_tutor",
    studentProfile,
    conversationHistory: [],
    turnNumber: 0,
  };

  const builder = new AiTutorPromptBuilder();
  builder.setLayer1Template(getCachedTemplate("ai-tutor-layer1"));
  const templateContents: Record<string, string> = {
    "ai-tutor-layer1": getCachedTemplate("ai-tutor-layer1"),
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- the preview's minimal context is deliberately partial
  const finalPrompt = builder.buildPrompt(minimalContext as any);

  return { finalPrompt, templateContents };
```
- Notes:
  - The admin tutor-tools route uses this to show the assembled prompt for a minimal profile.

### X21 · The seed SQL no longer seeds Layer 1
- File: `~/projects/lomem/apps/tunatutor/backend/prisma/seed/04-app-settings.sql:120-127` (Lomem main branch as read on 2026-10-15)
- Implements: C25, K16, E1
```sql
-- AI Tutor Layer 1 (tutor chat) master prompt: NOT seeded here.
-- It is registered + seeded from the TypeScript constant
-- DEFAULT_LAYER1_TEMPLATE (ai-tutor-prompt-builder.ts) via
-- registerPromptTemplate() / loadTemplateCache() at backend startup, which
-- creates the prompt_templates row when absent. Single source of truth — no
-- SQL duplicate to keep in sync (a prior duplicate here drifted stale and
-- shadowed the code constant — see #33 in the 2026-07-10 linguist review).
-- Admin "Reset to default" pulls from the same constant.
```
- Notes:
  - The comment is the human-readable half of the fix; the drift test (X22) is the enforced half.

### X22 · Drift test 1: the seed must not insert the Layer 1 row
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/__tests__/layer1-template-drift.test.ts:10-21, 37-49` (Lomem main branch as read on 2026-10-15)
- Implements: C22, K17, E1
```ts
// Guards finding #33 (2026-07-10 linguist review): the tutor's Layer-1
// prompt template drifted because a stale seed-SQL row shadowed the code
// constant (loadTemplateCache uses the DB row when present, only falling
// back to the registered default when the row is absent — see
// services/prompt-templates.ts). The fix deletes the seed duplicate so
// DEFAULT_LAYER1_TEMPLATE is the sole source of truth. This test prevents
// both halves of that regression from recurring silently.

const SEED_SQL_PATH = path.resolve(
  fileURLToPath(import.meta.url),
  "../../../../../../prisma/seed/04-app-settings.sql",
);
...
test("seed SQL no longer inserts a stale ai-tutor-layer1 prompt_templates row", () => {
  const seedSql = readFileSync(SEED_SQL_PATH, "utf8");
  // Guard against re-introducing a SQL duplicate of the code constant — any
  // 'ai-tutor-layer1' prompt_templates INSERT here would again shadow
  // DEFAULT_LAYER1_TEMPLATE via loadTemplateCache's DB-row-wins behavior.
  const hasStaleInsert =
    /INSERT INTO\s+"prompt_templates"[\s\S]*?'ai-tutor-layer1'/i.test(seedSql);
  assert.equal(
    hasStaleInsert,
    false,
    "04-app-settings.sql must not INSERT an 'ai-tutor-layer1' prompt_templates row — the row is registered + created-when-absent from DEFAULT_LAYER1_TEMPLATE at startup",
  );
});
```
- Notes:
  - The header dates the review (2026-07-10) and names the bug: a stale seed row shadowed the code constant.
  - It reads the seed SQL as text and matches an INSERT INTO prompt_templates that mentions 'ai-tutor-layer1'.

### X23 · Drift test 2: every template token is a registered variable
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/__tests__/layer1-template-drift.test.ts:51-65` (Lomem main branch as read on 2026-10-15)
- Implements: C22, C23
```ts
test("every {{token}} in DEFAULT_LAYER1_TEMPLATE is a registered Layer1 variable", () => {
  // Mirrors assertVariablesRegistered in services/prompt-templates.ts:21-41 —
  // any token referenced in the template but absent from the registered
  // variable list would silently fail to resolve at render time and leak
  // a literal "{{token}}" into the LLM prompt.
  const referenced = extractTemplateVariables(DEFAULT_LAYER1_TEMPLATE);
  const registeredNames = new Set(LAYER1_TEMPLATE_VARIABLES.map((v) => v.name));
  const unknown = [...referenced].filter((name) => !registeredNames.has(name));

  assert.deepEqual(
    unknown,
    [],
    `DEFAULT_LAYER1_TEMPLATE references unregistered variable(s): ${unknown.join(", ")}`,
  );
});
```
- Notes:
  - Same rule as the admin save check (X10), applied to the code constant in CI.

### X24 · Drift test 3: the tokens that drifted out of the stale row must stay
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/__tests__/layer1-template-drift.test.ts:67-87` (Lomem main branch as read on 2026-10-15)
- Implements: C22, E1
```ts
test("DEFAULT_LAYER1_TEMPLATE contains the render tokens that drifted out of the stale seed row", () => {
  // These specific tokens are the ones #33 found missing from the stale seed
  // content (rule 14 complexity guidance + rule 15 teaching toolkit, plus the
  // other render tokens the stale row also lacked wiring for). Asserting on
  // the literal token strings makes it impossible for the code constant to
  // silently lose one of them again.
  const requiredTokens = [
    "{{complexityGuidance}}",
    "{{registerRule}}",
    "{{vocabularyCompletenessRule}}",
    "{{correctionInstruction}}",
    "{{languageRatio}}",
  ];

  for (const token of requiredTokens) {
    assert.ok(
      DEFAULT_LAYER1_TEMPLATE.includes(token),
      `DEFAULT_LAYER1_TEMPLATE is missing required token ${token}`,
    );
  }
});
```
- Notes:
  - Pins the literal tokens so the constant cannot lose one of them again.

### X25 · Drift test 4: no language names in template defaults
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/__tests__/layer1-template-drift.test.ts:89-98, 109-122` (Lomem main branch as read on 2026-10-15)
- Implements: C43
```ts
test("no ai-tutor template code default hardcodes a language name or language-specific affirmation", () => {
  // Guards findings #37/#100: the Language-Pair Rule (apps/tunatutor/CLAUDE.md)
  // bans concrete language names in prompt builders — templates must be
  // parameterized via {{targetLanguage}}/{{nativeLanguage}}. The stale
  // pre-batch-7 defaults carried a full French worked example and French
  // affirmations; this pins the CODE constants clean so the #100 startup
  // self-heal always propagates a language-neutral template.
  const forbidden = [
    "French", // language-exempt: forbidden-string list for the drift guard itself, never rendered to users
    "Spanish", // language-exempt: forbidden-string list for the drift guard itself, never rendered to users
...
  ];
  const templates: Array<[string, string]> = [
    ["DEFAULT_LAYER1_TEMPLATE", DEFAULT_LAYER1_TEMPLATE],
    ["DEFAULT_PUBLIC_DEMO_TUTOR_TEMPLATE", DEFAULT_PUBLIC_DEMO_TUTOR_TEMPLATE],
  ];

  for (const [name, template] of templates) {
    for (const needle of forbidden) {
      assert.ok(
        !template.includes(needle),
        `${name} hardcodes "${needle}" — templates are sent to every language pair and must stay language-neutral (Language-Pair Rule)`,
      );
    }
  }
```
- Notes:
  - Guards findings #37 and #100 under the Language-Pair Rule; also covers DEFAULT_PUBLIC_DEMO_TUTOR_TEMPLATE.

### X26 · Heal tests: the decision table on a mocked store
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/__tests__/heal-stale-template.test.ts:8-22, 50-64, 81-90, 130-144` (Lomem main branch as read on 2026-10-15)
- Implements: K18, E5, E6
```ts
// Guards finding #100 (tunatutor Experience Review v2, 2026-07-16), generalizing
// the #33 self-heal: `loadTemplateCache` is create-when-absent only, so an
// already-seeded DB (e.g. staging) keeps serving a stale prompt_templates row
// forever, even after the code default changes. `healStaleTemplate(key)`
// (called from `init()` right after each `loadTemplateCache(key)`, for all
// three registered ai-tutor keys) self-heals: it resets a row to the code
// default when the cached content differs from it AND the row was never
// admin-edited — zero archived versions, OR content byte-matching the one
// known heal-poisoned historical default (the July-11 heal archived its own
// write, bumping versionCount 0→1 on rows no admin ever touched).
// Critically, the heal's reset must NOT archive (archive: false): archiving
// would bump versionCount and re-poison the never-edited signal on the very
// next code-constant change. These tests exercise the decision directly
// against a mocked template store — no real DB, no full `init()` side
// effects.
...
const LAYER1_KEY = "ai-tutor-layer1";
const CURRENT_DEFAULT = "You are a tutor. 14. {{complexityGuidance}} 15. {{registerRule}}";
// Stand-in for a pre-batch-7 row that still carries hardcoded French — any
// content that differs from the registered default triggers the same path.
const STALE_FRENCH_CONTENT = "You are a tutor. Say «Très bien!» and «Parfait!»."; // language-exempt: simulated stale prompt content in a test fixture, never rendered to users
const ADMIN_EDITED_CONTENT = "You are a tutor, hand-tuned by an admin.";

// The one heal-poisoned historical default (#100 "verifier trap"): the
// July-11 layer-1 heal archived its own write, so rows carrying exactly this
// content have versionCount === 1 without any admin edit. Byte-exact bytes
// extracted from `git show 69e2799d:…/ai-tutor-prompt-builder.ts`.
const HISTORICAL_LAYER1_FIXTURE = readFileSync(
  path.resolve(fileURLToPath(import.meta.url), "../fixtures/layer1-template-pre-batch7.txt"),
  "utf8",
);
...
test("the fixture is byte-identical to the known heal-poisoned historical default", () => {
  // If the fixture drifts (editor re-encoding, trailing-newline mangling),
  // the poisoned-version-count tests below would silently stop exercising
  // the md5 branch — pin the hash here.
  assert.equal(
    createHash("md5").update(HISTORICAL_LAYER1_FIXTURE, "utf8").digest("hex"),
    "46f3013c294f78b4c49c93a9ca97d180",
  );
  assert.equal(HISTORICAL_LAYER1_FIXTURE.length, 6259);
});
...
test("heal-poisoned historical default + versionCount 1 → heals anyway (md5 branch skips the version check)", async () => {
  // The #100 trap: the July-11 heal's own archive made versionCount === 1 on
  // rows no admin ever edited. The md5 match is proof of machine authorship,
  // so the heal must fire without even consulting the version count.
  mockGetCachedTemplate.mock.mockImplementationOnce(() => HISTORICAL_LAYER1_FIXTURE);
  mockCountTemplateVersions.mock.mockImplementationOnce(async () => 1);

  await healStaleTemplate(LAYER1_KEY);

  assert.equal(mockCountTemplateVersions.mock.callCount(), 0);
  assert.equal(mockResetPromptTemplate.mock.callCount(), 1);
  assert.equal(mockResetPromptTemplate.mock.calls[0].arguments[0], LAYER1_KEY);
  assert.deepEqual(mockResetPromptTemplate.mock.calls[0].arguments[1], { archive: false });
  assert.equal(mockLoadTemplateCache.mock.callCount(), 1);
});
```
- Notes:
  - The header says healStaleTemplate runs 'for all three registered ai-tutor keys'; index.ts registers two (see Open questions).
  - The fixture file layer1-template-pre-batch7.txt holds the historical default byte for byte.

### X27 · Scenario golden test: rendered prompts pinned byte for byte
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/scenario-prompts.golden.test.ts:1-16, 32-44` (Lomem main branch as read on 2026-10-15)
- Implements: C17, K19, F7.1-F7.3b
```ts
/**
 * Byte-identical pin (ADR-032 §4, tunatutor Quest #1): a NON-quest scenario chat — a
 * single-scene scenario and a journey, mid-way and at the wrap-up — renders
 * exactly the tutor prompt, scene-handoff prompt and judge prompt it rendered
 * before quests existed. The golden JSON was rendered from the builder at commit
 * 6f2d612cc with the inputs in fixtures/scenario-prompt-cases.ts. Every quest
 * branch is gated on `isQuest`, so none of these bytes may move.
 * journeyWrapUp@0/@3 were re-rendered when the scene anchor began to hold with no
 * goal left to offer (story-FNQG7JBTS5Y34WVM); the only change is the anchor line.
 * They were re-rendered again when a story with every goal met began to have the
 * tutor wrap up with a goodbye instead of more questions; the only changes are
 * that block, the scene layer's closing line and Layer 3's "end with" rule.
 * Every case moved once more when the correction's "original" / "corrected"
 * fields began asking for just the wrong words, copied exactly (the chat's
 * short fix chip); the only change is those two field descriptions.
 */
...
const golden = JSON.parse(
  readFileSync(fileURLToPath(new URL("./__tests__/fixtures/scenario-prompts.pre-quest.json", import.meta.url)), "utf8"),
) as Record<string, string>;

for (const name of Object.keys(SCENARIO_PROMPT_STORIES)) {
  for (const turn of SCENARIO_PROMPT_TURNS) {
    test(`${name} at turn ${turn}: the tutor prompt is byte-identical to before quests`, () => {
      const builder = new AiTutorPromptBuilder();
      builder.setLayer1Template(DEFAULT_LAYER1_TEMPLATE);
      assert.equal(builder.buildPrompt(scenarioPromptContext(name, turn)), golden[`${name}@${turn}`]);
    });
  }
}
```
- Notes:
  - The header is the change log of intended re-renders.
  - setLayer1Template(DEFAULT_LAYER1_TEMPLATE) means the test never sees the database copy.
  - The JSON also pins the scene-handoff prompt and the judge prompt (lines 46-56).

### X28 · Learner-topic golden test: the file LOM-86 moved
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/learner-topic.golden.test.ts:1-12, 25-36` (Lomem main branch as read on 2026-10-15)
- Implements: C17, C18, E2
```ts
/**
 * Byte-identical pin (ADR-046 "The chat topic"): an agenda-topic or no-topic chat
 * renders exactly the prompt and greeting hint it rendered before
 * learner-chosen topics existed. The golden JSON was rendered from origin/main's
 * builder and engine (04631ade0) with the inputs in fixtures/topic-prompt-cases.ts.
 * noTopic@0/@3 and agendaTopic@0/@3 were re-rendered when the role the tutor
 * invents in a chat's micro-scenario began to decide the address register
 * (LOM-86); the only change is the register rule. Every case moved once more
 * when the correction's "original" / "corrected" fields began asking for just
 * the wrong words, copied exactly (the chat's short fix chip); the only change
 * is those two field descriptions.
 */
...
const golden = JSON.parse(
  readFileSync(fileURLToPath(new URL("./__tests__/fixtures/topic-prompts.pre-learner-topic.json", import.meta.url)), "utf8"),
) as Record<string, string>;

for (const name of Object.keys(TOPIC_PROMPT_CASES)) {
  for (const turn of TOPIC_PROMPT_TURNS) {
    test(`${name} at turn ${turn}: the prompt is byte-identical to before`, () => {
      const builder = new AiTutorPromptBuilder();
      builder.setLayer1Template(DEFAULT_LAYER1_TEMPLATE);
      assert.equal(builder.buildPrompt(topicPromptContext(name, turn)), golden[`${name}@${turn}`]);
    });
  }
```
- Notes:
  - The header records that noTopic@0/@3 and agendaTopic@0/@3 were re-rendered for LOM-86 and that only the register rule changed.

### X29 · The topic golden cases and turns
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/__tests__/fixtures/topic-prompt-cases.ts:29-32, 53-60` (Lomem main branch as read on 2026-10-15)
- Implements: C18, E2
```ts
const BASE: Partial<AiTutorStudentProfile> = {
  nativeLanguage: "english",
  targetLanguage: "french",
  cefrLevel: "A2",
...
/** name → studentProfile overrides. */
export const TOPIC_PROMPT_CASES: Record<string, Partial<AiTutorStudentProfile>> = {
  noTopic: {},
  agendaTopic: { topicPreference: "Work and Study Roles" },
  noObjectivesAgendaTopic: { topicPreference: "Work and Study Roles", curriculumObjectives: undefined },
};

export const TOPIC_PROMPT_TURNS = [0, 3] as const;
```
- Notes:
  - noObjectivesAgendaTopic has no objectives, so no micro-scenario and no invented role; LOM-86 did not move it.

### X30 · Admin routes: activate, save (with length cap) and reset
- File: `~/projects/lomem/apps/tunatutor/backend/src/routes/admin/prompt-templates.ts:78-95, 136-157, 169-181` (Lomem main branch as read on 2026-10-15)
- Implements: K14, F3.1-F3.1c, F4.1, F5.1-F5.2a
```ts
  // POST /:key/versions/:versionId/activate — restore a previous version
  app.post<{ Params: { key: string; versionId: string } }>(
    "/:key/versions/:versionId/activate",
    async (request, reply) => {
      const { key, versionId } = request.params;
      const registration = getTemplateRegistration(key);

      if (!registration) {
        throw new NotFoundError(`No template registered for key "${key}"`);
      }

      const id = parseInt(versionId, 10);
      if (isNaN(id)) {
        throw new ValidationError("versionId must be a number");
      }

      try {
        const row = await activatePromptTemplateVersion(key, id);
...
  // PUT /:key — upsert template content
  app.put<{ Params: { key: string }; Body: { content: string } }>(
    "/:key",
    async (request, reply) => {
      const { key } = request.params;
      const { content } = request.body;

      const registration = getTemplateRegistration(key);
      if (!registration) {
        throw new NotFoundError(`No template registered for key "${key}"`);
      }

      if (!content || typeof content !== "string") {
        throw new ValidationError("content is required");
      }

      const MAX_TEMPLATE_LENGTH = 100_000;
      if (content.length > MAX_TEMPLATE_LENGTH) {
        throw new ValidationError(`content exceeds maximum length of ${MAX_TEMPLATE_LENGTH} characters`);
      }

      const row = await upsertPromptTemplate(key, content);
...
  // DELETE /:key — reset template to factory default
  app.delete<{ Params: { key: string } }>("/:key", async (request, reply) => {
    const { key } = request.params;

    const registration = getTemplateRegistration(key);
    if (!registration) {
      throw new NotFoundError(`No template registered for key "${key}"`);
    }

    await resetPromptTemplate(key);

    return reply.send({ ok: true });
  });
```
- Notes:
  - MAX_TEMPLATE_LENGTH is 100_000 characters.
  - The activate route wraps every error as NotFoundError (lines 103-106, not shown).

### X31 · Admin page: template keys, CUSTOM/DEFAULT pill and Reset
- File: `~/projects/lomem/apps/tunatutor/admin/src/pages/PromptTemplatesPage.tsx:14-17, 76-79, 178-200` (Lomem main branch as read on 2026-10-15)
- Implements: K15, L8, F3.6, F4.5
```tsx
const TEMPLATE_KEYS = [
  { key: "ai-tutor-layer1", label: "Manual Tutor (Layer 1)" },
  { key: "public-demo-tutor", label: "Public Demo Tutor" },
] as const;
...
      const activeContent = data.template?.content ?? data.defaultContent;
      setContent(activeContent);
      setSavedContent(activeContent);
      setIsCustom(data.template !== null);
...
            <StatusPill variant={isCustom ? "active" : "idle"}>
              {isCustom ? "CUSTOM" : "DEFAULT"}
            </StatusPill>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDump}
            >
              <Download className="mr-1.5 h-3.5 w-3.5" />
              <span className="hidden sm:inline">Dump All</span>
              <span className="sm:hidden">Dump</span>
            </Button>
            {isCustom && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleReset}
                disabled={saving}
              >
                <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                Reset
              </Button>
            )}
```
- Notes:
  - isCustom is true whenever the API returns a row; startup always creates the row (X11), so the pill likely shows CUSTOM for unedited templates too (see Open questions).
  - The page subtitle says the prompt is 'sent to the LLM at the start of every AI Tutor session'.

### X32 · Lesson-note writer: the version constant and the stamp
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/tutor-continuity/lesson-note-writer.ts:17-26, 208-234` (Lomem main branch as read on 2026-10-15)
- Implements: C13, C15, K21, F8.2-F8.4, E10
```ts
/** Idempotency-key prefix for the enqueue call site (Task 7) — `${LESSON_NOTE_KEY_PREFIX}${sessionUuid}`. */
export const LESSON_NOTE_KEY_PREFIX = "lesson-note:";
/** Stamped onto every note as `writerPromptVersion` — bump when the prompt shape changes. */
export const LESSON_NOTE_PROMPT_VERSION = "v1";

/** Only the last N transcript messages are fed to the writer — long sessions are token-bounded (design doc §5). */
const TRANSCRIPT_WINDOW = 40;
const NOTE_WRITER_MAX_TOKENS = 800;
const NOTE_WRITER_SYSTEM_PROMPT =
  "You write private, internal lesson notes for a language tutor. Follow the caller's instructions exactly and reply with JSON only, no commentary, no markdown code fences.";
...
    const raw = await deps.generate(
      prompt,
      userUsageContext(payload.userId, "lesson_note_writer", payload.conversationSessionUuid),
    );
    const out = OutputSchema.parse(extractJSON(raw));

    const noteId = await deps.saveNote(
      {
        conversationSessionId: meta.dbId,
        userId: payload.userId,
        language: payload.language,
        workedOn: sanitizeTextArray(out.workedOn),
        wins: sanitizeTextArray(out.wins),
        stumbles: sanitizeTextArray(out.stumbles),
        newItems: sanitizeTextArray(out.newItems),
        tutorRemark: sanitizeRemark(out.tutorRemark ?? null),
        writerModel: deps.model,
        writerPromptVersion: LESSON_NOTE_PROMPT_VERSION,
      },
      out.newPromises.map((p) => ({ text: p.text, saidAloud: p.saidAloud })),
    );

    const toResolve = out.promisesResolved.filter((id) => openPromises.some((p) => p.id === id));
    if (toResolve.length) await deps.resolvePromises(toResolve, noteId, deps.now());
  } catch (err: unknown) {
    logger.warn({ err: getErrorMessage(err), payloadRaw }, "tutor lesson-note write failed (non-fatal)");
  }
```
- Notes:
  - The comment says bump 'when the prompt shape changes'; the store's rule is any change to the rendered text (C40).
  - Failures are logged and swallowed.

### X33 · Lesson-note writer: where writerModel comes from
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/tutor-continuity/lesson-note-writer.ts:273-283, 309-315` (Lomem main branch as read on 2026-10-15)
- Implements: C14, F8.2
```ts
export function defaultNoteWriterDeps(): NoteWriterDeps {
  let model = "unknown";
  try {
    model = getActiveProvider().modelId;
  } catch (err: unknown) {
    // Registry not initialized (e.g. a bare unit-test process that never ran
    // `initLLMRegistry()`). Non-fatal — production always initializes the
    // registry at startup; this only affects the `writerModel` audit field.
    logger.debug({ err: getErrorMessage(err) }, "lesson-note writer: LLM registry unavailable, using placeholder model id");
  }

...
    generate: (prompt, usage) =>
      callLLM(NOTE_WRITER_SYSTEM_PROMPT, [{ role: "user", content: prompt }], NOTE_WRITER_MAX_TOKENS, {
        json: true,
        temperature: 0.3,
        usageContext: usage,
      }),
    model,
```
- Notes:
  - model is the active provider's modelId when the deps are built, or 'unknown'. If the gateway falls back to another model, the stamp may not name the model that answered (see Open questions).

### X34 · Schema: stamp columns and the template tables
- File: `~/projects/lomem/apps/tunatutor/backend/prisma/schema.prisma:1745-1760, 2075-2099` (Lomem main branch as read on 2026-10-15)
- Implements: K8, K9, K22, C14, C28
```prisma
model TutorLessonNote {
  id                    Int    @id @default(autoincrement())
  userId                Int    @map("user_id")
  language              String
  conversationSessionId Int    @unique @map("conversation_session_id")

  workedOn    Json?
  wins        Json?
  stumbles    Json?
  newItems    Json?   @map("new_items")
  tutorRemark String? @map("tutor_remark")
  openerUsed  String? @map("opener_used")

  schemaVersion       Int     @default(1) @map("schema_version")
  writerModel         String? @map("writer_model")
  writerPromptVersion String? @map("writer_prompt_version")
...
model PromptTemplate {
  /// Unique template key used to look the prompt up at runtime.
  key       String                  @id
  /// Current prompt template text.
  content   String
  updatedAt DateTime                @updatedAt @map("updated_at")
  versions  PromptTemplateVersion[]

  @@map("prompt_templates")
}

/// One row per historical revision of a PromptTemplate, preserving prior content for audit/rollback.
model PromptTemplateVersion {
  id          Int      @id @default(autoincrement())
  /// Key of the PromptTemplate this revision belongs to.
  templateKey String   @map("template_key")
  /// Snapshot of the prompt text at this revision.
  content     String
  createdAt   DateTime @default(now()) @map("created_at")

  template PromptTemplate @relation(fields: [templateKey], references: [key])

  @@index([templateKey, createdAt(sort: Desc)], name: "prompt_template_versions_key_created")
  @@map("prompt_template_versions")
}
```
- Notes:
  - writer_model and writer_prompt_version are separate nullable columns.
  - prompt_template_versions has no author column, so an archive row does not say who or what wrote it.

### X35 · First-chat note stamps its own prompt version
- File: `~/projects/lomem/apps/tunatutor/backend/src/use-cases/onboarding/first-chat.ts:1036-1048` (Lomem main branch as read on 2026-10-15)
- Implements: C13
```ts
    await deps
      .writeLessonNote(
        {
          conversationSessionId: chat.id,
          userId: input.userId,
          language: chat.targetLanguage,
          workedOn: [firstChatWorkedOn(input.levelPick)],
          wins: tryNext ? [`ordered in a café: "${tryNext.said}"`] : [],
          newItems: { firstChat: facts },
          tutorRemark: tryNext?.tip ?? null,
          openerUsed: null,
          writerModel: null,
          writerPromptVersion: "first-chat-v1",
```
- Notes:
  - A second stamp in the codebase: writerPromptVersion 'first-chat-v1', writerModel null.

### X36 · Scenario eval: simulated tutor prompt, turn cap and pass rate
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/scenario/run-scenario-eval.ts:99-107, 144-168, 389-396, 413-414` (Lomem main branch as read on 2026-10-15)
- Implements: K24, F12.2-F12.5, E12
```ts
  const seeded = history.length > 0 ? history : [{ role: "user" as const, content: "(You walk up and begin.)" }];
  const raw = await callWithRetry(system, seeded, 150, {
    temperature: 0.7,
    usageContext: systemUsageContext(
      "scenario_eval_student",
      `admin scenario eval (triggered by admin ${userId}) — a simulated learner, not a real one`,
      uuid,
    ),
  });
...
/** Simulated tutor — role-plays the scene and steers toward the objectives. */
async function simTutor(
  language: string,
  sceneText: string,
  objectives: EvalObjective[],
  history: Array<{ role: "user" | "assistant"; content: string }>,
  userId: number,
  uuid: string,
): Promise<string> {
  const system = [
    `You are role-playing this scene with a language learner. Stay fully in character. Speak ONLY ${language} at an A1 level — short, simple, warm.`,
    `SCENE: ${sceneText}`,
    `Steer the conversation naturally so the learner gets openings to: ${objectives.map((o) => o.text).join(", ")}. Never list these aloud, never tell them what to say.`,
    `Keep every turn to ONE short line and hand the conversation back to the learner.`,
  ].join("\n");
  const raw = await callWithRetry(system, history, 150, {
    temperature: 0.6,
    usageContext: systemUsageContext(
      "scenario_eval_tutor",
      `admin scenario eval (triggered by admin ${userId}) — a simulated tutor, not a real learner`,
      uuid,
    ),
  });
  return firstLine(raw);
}
...
    const required =
      resolveRequiredHits(
        null,
        story.completionThreshold,
        story.objectives,
        story.objectives.filter((o) => !o.stretch).length,
      ) ?? 1;
    const maxTurns = Math.max(12, objectives.length * 2 + 4);
...
    const passedCount = convs.filter((c) => c.passed).length;
    const passRate = runs > 0 ? passedCount / runs : 0;
```
- Notes:
  - simTutor has its own short system prompt; the production tutor prompt is never called, so this eval cannot score a Layer 1 change.
  - Temperatures: learner 0.7, adversary 0.8 (lines 133-134), tutor 0.6.

### X37 · A prompt variant kept in code: arc and card
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-translation-prompt.ts:7-12, 54-60` (Lomem main branch as read on 2026-10-15)
- Implements: C38, F10.1
```ts
/**
 * Which judge asks. `arc` is the Translation arc's tutor judge (marks, focus,
 * why). `card` is Drill Me's judge and stays exactly as it was: it shows the
 * judge's `feedback` to the learner.
 */
export type JudgePromptVariant = "arc" | "card";
...
export function buildJudgeTranslationPrompt(
  a: BuildJudgePromptArgs,
  opts: { variant?: JudgePromptVariant } = {},
): string {
  if (opts.variant === "arc") return buildArcPrompt(a);
  return buildCardPrompt(a);
}
```
- Notes:
  - The older card prompt 'stays exactly as it was' so the gate (X38) can compare old and new.

### X38 · Translation judge gate: old versus new prompt with numeric bars
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/translation-judge-gate.ts:1-11, 48-55` (Lomem main branch as read on 2026-10-15)
- Implements: C19, C20, C34, K25, F10, E11
```ts
/**
 * Translation judge GATE (TR4): the frozen pre-TR2 prompt (`card`) against the
 * arc tutor prompt (`arc`), on real AI-judged answers plus a hand-made fixture.
 * Decides whether `TD_JUDGE_MARKS` may be turned on.
 *
 *   1. right/wrong agreement old vs new on the REAL rows (>= 95%), AND the new
 *      prompt vs the fixture's `expected` (>= 95%) with every paraphrase RIGHT.
 *   2. share of marks `placeNamedMarks` could place (>= 95%).
 *   3. share of marked words that are really wrong (>= 90%) - read BY HAND from
 *      the table this script prints (the fixture's `markedWords` give a hint).
 *   4. share of arc replies within 2.5 s (>= 95%).
...
const USAGE: LLMSystemUsageContext = {
  system: true,
  conversationType: "translation_judge_gate",
  reason: "dev gate script: no learner is behind these calls",
};
const LEVEL_BAR = { agree: 0.95, place: 0.95, wrong: 0.9, fast: 0.95 } as const;
const LATENCY_LIMIT_MS = 2500;
const CONCURRENCY = 3;
```
- Notes:
  - A dev harness, not a CI test: it needs the network and a local database filled from staging (lines 13-18).

### X39 · TD_JUDGE_MARKS: the switch the gate unlocks
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-reply.ts:15-20` (Lomem main branch as read on 2026-10-15)
- Implements: L7, F10.3a, F10.3b
```ts
/**
 * The switch for the judge's marks. While false, a parsed reply keeps `focus`
 * and `why` and returns `marks: null` (unknown, so the phone draws nothing).
 * Only TR4's PR may flip it to true.
 */
export const TD_JUDGE_MARKS = false;
```
- Notes:
  - A code constant, not a runtime flag; flipping it is a PR.

### X40 · LOM-86 commit message (part of squash commit 739eb9f7c)
- File: `~/projects/lomem` git commit `739eb9f7c`, message section `fix(ai-tutor): the role the tutor plays decides polite or casual you` (Lomem main branch as read on 2026-10-15)
- Implements: C9, C11, E2
```text
* fix(ai-tutor): the role the tutor plays decides polite or casual you

What was wrong: in a plain chat with a lesson goal, the micro-scenario has
the tutor play a role it invents (a ticket seller, a waiter), but the register
rule stayed level-keyed. At A1/A2 it locked the informal "you" for the whole
session, while the reply-chip rule asked for formal forms to a clerk. So the
seller said "tu" and the chips offered "vous".

The fix: when the prompt carries the curriculum micro-scenario, the register
rule follows the role instead of the level: formal / polite for service roles
and strangers, informal for peers. The prompt builder records this per prompt
(getLastPromptInventedRole), and the reply-suggestion backfill for prose turns
uses the same role rule. Bound scenes keep their own rule. Chats with no
micro-scenario (no objective, a learner-chosen topic, reference text or a
picture) keep the level rule.

Behaviour change, at every level: A1/A2 learners now meet polite forms in
shop, ticket and cafe role-plays of plain chats, and at B1+ a peer role turns
casual. ADR-032 section 9 now says so. Four golden prompts (noTopic and
agendaTopic, turns 0 and 3) change in the register sentence only.

Refs: LOM-86
```
- Notes:
  - Read with `git show 739eb9f7c`; the commit is dated 2026-10-12 (PR #613).
  - It names the reply-chip contradiction, the per-prompt record (getLastPromptInventedRole) and the four golden prompts.

### X41 · Eval runs store no prompt version
- File: `~/projects/lomem/apps/tunatutor/backend/prisma/schema.prisma:1266-1284` (Lomem main branch as read on 2026-10-15)
- Implements: C19
```prisma
model ScenarioEvalRun {
  id              String    @id @default(cuid())
  storyId         String    @map("story_id")
  requestedRuns   Int       @map("requested_runs")
  /// pending | running | done | failed
  status          String    @default("pending")
  passRate        Float?    @map("pass_rate")
  avgTurns        Float?    @map("avg_turns")
  resultJson      Json?     @map("result_json")
  error           String?
  createdByUserId Int       @map("created_by_user_id")
  createdAt       DateTime  @default(now()) @map("created_at")
  completedAt     DateTime? @map("completed_at")

  story Story @relation(fields: [storyId], references: [id], onDelete: Cascade)

  @@index([storyId, createdAt], map: "scenario_eval_runs_story_created_idx")
  @@map("scenario_eval_runs")
}
```
- Notes:
  - ScenarioEvalRun stores storyId, passRate and avgTurns, but no prompt version or model id, so eval scores cannot be grouped by prompt version today.

### X42 · The judge prompt is extracted so a golden test can pin it
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/scenario/judge-prompt.ts:1-2, 19-20` (Lomem main branch as read on 2026-10-15)
- Implements: C17
```ts
// The scenario judge's prompt (ADR-032 §6). PURE, no I/O — extracted verbatim from
// grade-scenario-objectives.ts so its bytes can be pinned by a golden test.
...
export const JUDGE_SYSTEM_PROMPT =
  "You grade which communicative objectives a language learner has demonstrated, from their own utterances only. Credit a function ONLY when the learner actually performs its defining speech-act move — never on topical or lexical overlap with a neighboring objective. Be strict: do not credit echoes of the tutor or vague near-misses. Reply with JSON only.";
```
- Notes:
  - Pure, no I/O: a prompt kept as a constant can be pinned byte for byte.

## Analogy to classic backend

| AI-side item (id) | classic Java/Spring equivalent | holds where | breaks where |
|---|---|---|---|
| Prompt template (C5) | an externalised message in a Spring MessageSource: text with placeholders, kept outside the logic, filled at runtime (S6) | both are text with named slots filled per request, stored outside the code path | your code defines what a message means; the model decides what a prompt means, so the effect of an edit is known only by running many inputs and measuring (S6) |
| Production label (C31) | a feature flag that selects which variant is live (S6) | both switch the live variant without a deployment, and rollback is flipping it back (S6) | a flag toggles code you tested; a label switches text whose effect is measured only by evals (S6) |
| Prompt management (C30) | externalised config with versions and environment labels (S5) | versions, environments, rollback | the same version can give different outputs on two calls (S6) |
| Changing a prompt (C9) | changing timeout=30 to timeout=60 in config (S6) | both are a one-line, deploy-free change | you can reason about a timeout change; you cannot reason about a prompt change without measuring (S6) |
| Stale database row overriding a code default (C24, E1) | a stale config row or seed overriding an application default (S6) | the same bug shape, the same fix (one source of truth, drift tests) | the stale value produces fluent output instead of a failing check, so it hides (S6) |
| Golden test (C17) | snapshot or approval test of generated output | byte-for-byte comparison with a stored file, re-recorded on intended change | it pins the input to the model, not the model's reply; quality needs evals (S6) |
| Eval (C19) | a test suite whose result is a score and a pass rate, not green or red (S5) | fixed inputs run in CI on every change | outputs are non-deterministic, so `assertEquals` does not work and a threshold must be chosen beforehand (S5, S6) |
| Model id (C14) | a library or runtime version pinned in a build | changing it can change behaviour without code changes | a vendor model can change under the same prompt; the prompt version does not move with it (S6) |
| Archive table (C28) | an audit or history table (Envers-style) | every change keeps the previous value | tunatutor's archive has no author column, so it cannot tell an admin edit from a reset (X34) |
| Prisma (C45) | a JPA repository (S6) | typed database access | none for this block |

## Pitfalls

| id | mistake | consequence | what to do instead | source |
|---|---|---|---|---|
| M1 | Keep a prompt in two places (code constant and seed or database row) without deciding which wins | the stale copy silently shadows the code; production lacked rules 14 and 15 in July 2026 | keep one copy; if a database copy exists, decide and test which wins | S6, X22 |
| M2 | Let the database row win whenever it exists | an old seed row overrides every later code improvement | code wins unless an admin edited; heal unedited rows at startup | S6, X17 |
| M3 | Archive from the heal path | the heal's own archive row makes healed rows look admin-edited, so future heals never fire | heal with archive: false | X13, X16 |
| M4 | Bump the version only when the prompt "shape" changes | one-word edits and variable-code changes ship under the old version | change the version on any change to the rendered text | S6, X32 |
| M5 | Version only the template text | a LOM-86-style change to variable code never moves the version | tie the version to the rendered golden output or bump by hand for variable code too | S6, testing |
| M6 | Tie the version to a golden-file hash and assume forgetting is impossible | branches the golden cases do not render never move the hash | choose golden inputs so every branch of every variable renders | testing, S6 |
| M7 | Write golden cases without a role-play case | LOM-86 would not have moved the golden file | cover every variable branch | S6 |
| M8 | Treat the golden test as the guard against a stale database copy | it feeds the code constant, so it cannot see the database | drift tests plus the startup heal | S6, X27 |
| M9 | Rely on golden tests for quality | they say nothing about whether replies got better; LOM-86 was never measured | run an eval on old and new versions | S6 |
| M10 | Choose the blocking threshold after seeing eval results | variance makes any result look acceptable | decide the blocking drop before the run | S6 |
| M11 | Let a misspelled placeholder through | it reaches the model as literal text and nothing fails | reject unknown placeholders in CI and on save | S6, X10, X23 |
| M12 | Use a permissive save-check regex and a strict render regex | `{{ registerRule }}` passes the check and leaks literally | use one shared regex for both, or reject whitespace in tokens | X5, X10, E4 |
| M13 | Stamp only a code version constant on the admin-edit path | results do not say which admin text produced them | stamp a hash of the text actually used | S6 |
| M14 | Fold the model id into the prompt version | a model switch looks like no change, or every model switch bumps the prompt | store model id in its own field | S6, X34 |
| M15 | Forget that an admin-edited row never gets code improvements | the July bug happens in reverse | show CUSTOM or DEFAULT and give a Reset; a person decides when to take the new default | S6, X31 |
| M16 | Assume Reset returns the row to automatic healing | after Reset the archive count is above zero, so later constant changes are not healed | track "follows code default" explicitly, or have Reset clear the protection (code reading) | X13, X17 |
| M17 | Expect an admin edit to reach every instance at once | the cache is per process; other instances keep the old text until restart, and running sessions keep their captured text | reload caches across instances or restart; or use a registry with a short client cache | X11, X12, X19 |
| M18 | Keep code that rewrites exact template sentences while the template is admin-editable | an admin wording change silently disables the rewrite | keep such text out of the editable template, or test the rewrite against the current row | X9 |
| M19 | Use an eval that never calls the production prompt to judge a prompt change | the scenario eval's simulated tutor cannot score Layer 1 changes | run the production prompt in the eval | S6, X36 |
| M20 | Put changing variables at the start of a long system prompt | the provider prompt-cache prefix breaks on every request | put stable content first and variable content last | S5, S13 |

## Misconceptions

| id | what a newcomer believed | correct statement | evidence |
|---|---|---|---|
| Q1 | The golden test guards against the July stale-row incident | golden tests feed the code constant, so they cannot catch a stale database copy | testing, X27 |
| Q2 | "Decide which copy wins" is an open question in tunatutor | tunatutor decided: the code constant wins unless an admin edited the row; a startup heal resets unedited stale rows | testing, X17 |
| Q3 | Bump the version only when the prompt "shape" changes | bump on every change to the rendered text, including one-word edits and variable code | testing, S6 |
| Q4 | The model id is part of the prompt version, or does not matter | a new model can change what an unchanged prompt does; store the model id separately | testing, S6, X34 |
| Q5 | An eval is the same as a golden test | a golden test pins text; an eval scores replies with a rule, a person or a grading model | testing, S6 |
| Q6 | The git path and the database path share one version constant | a code constant cannot know about an admin's edit; on the database path stamp a hash of the text used | testing, S6 |
| Q7 | LOM-86 was an edit to the template wording | it changed only the code that computes {{registerRule}}; the template did not change | testing, X4, X40 |
| Q8 | "Classic backends have no equivalent" of the prompt problem | a stale row overriding a default is a familiar bug; the new part is that a wrong prompt fails silently with plausible output | testing, S6 |
| Q9 | A call sends only the new message | every call sends the system prompt, earlier messages and the new message, because the model keeps no memory | testing, S6 |
| Q10 | Layer 1 is the whole system prompt | Layer 1 is the first block; code adds many more layers | testing, X7 |
| Q11 | A version that is a hash of the template text catches every change | variable-code changes do not change the template text | testing, S6 |
| Q12 | The fix was only a seed test | the fix had three parts: delete the seed duplicate, heal stale rows at startup, add drift tests | testing, X21, X17, X22 |
| Q13 | A golden-file hash makes forgetting a version bump impossible | the hash moves only for golden cases that exercise the changed branch | testing |
| Q14 | "The code constant is the single source" always holds | an admin edit wins until someone resets the row | testing, S6 |
| Q15 | A change of model is a third kind of prompt version | it is a separate field; the prompt version does not change with it | testing, S6 |
| Q16 | Outputs repeat for the same prompt | the model samples each next word, so outputs vary between calls | testing, S6 |
| Q17 | The production tutor is tested by the scenario eval | the scenario eval uses a simulated tutor with its own prompt and tests the judge and the scenes | testing fact-check, X36 |
| Q18 | Every model call is logged with its prompt version in Langfuse automatically | traces "can be linked" to the prompt version; linking is optional | testing fact-check, S3 |
| Q19 | The admin screen shows the current text beside the code default | it shows a CUSTOM/DEFAULT pill and a Reset button | testing fact-check, X31 |
| Q20 | Startup loads every prompt_templates row | startup loads only each registered key's row | testing fact-check, X18 |
| Q21 | Terms readers did not know | eval, eval set, eval run, Layer 1, register, Lomem, Tunatutor, quests, scenario chats, turn, suggested replies, scaffolding, rejectedCorrection, inventedRole, spokenTurn, Langfuse, SDK, traces, promptfoo, prisma, registry, registration, model id, prompt shape, cost of a model call, LOM-86, finding #33, drift test, label, regression, micro-scenario, polite-neutral, template cache, golden file, languageRatio, LLM, Gemini, Claude, prompt_templates key, seed SQL or seed script, scenario or story, SCENARIO_PROMPT_STORIES, SCENARIO_PROMPT_TURNS, "before quests", other layers, Layer1Variables, resolveLayer1Variables, LAYER1_TEMPLATE_VARIABLES, assertVariablesRegistered, getCachedTemplate, loadTemplateCache, gemini-2.5-flash, a correction's original and corrected fields, Lomem repository | testing |
| Q22 | LOM-86 was a small wording fix with no wider effect | one new sentence for role-play changed address at every level, including the B1+ peer case; readers missed this while the before and after wording and the outcome were not shown | testing, X3, X4, X40 |
| Q23 | The four golden prompts LOM-86 moved are in the scenario golden file | they are in topic-prompts.pre-learner-topic.json, pinned by learner-topic.golden.test.ts | testing fact-check, X28 |
| Q24 | A prompt service only stores versions | the client caches prompts briefly, so a label move reaches servers after the cache refreshes, and model calls can be linked to their prompt version | testing, S3, S4 |
| Q25 | The checklist steps "run the eval" and "re-render the golden file" are self-explanatory | readers had no way to build an eval or regenerate the golden file until both were spelled out (C19, F7.3b) | testing |

## Open questions

- Questions readers still had after the final read (testing):
  - If the version constant should equal the golden-file hash, why does the lesson-note writer use "v1", and should it change?
  - Is the "production judge" a model call in the live product, and what does it judge?
  - With several instances, does an admin edit take effect everywhere at once? Code reading says no: the cache is per process (X11, X12) and sessions capture text at configuration (X19); not run.
  - Does the rendered prompt include the chat history and the user message? The golden tests cover only the system prompt (X27, X28).
  - Should the version stamp cover all layers of the system prompt or only Layer 1?
- Unverified claims:
  - "A case nobody had reported" for the B1+ peer change: neither the commit nor the code records it (testing fact-check).
  - Two instances healing at once is harmless: follows from reading the code; no concurrent startup was run (testing fact-check).
  - Teams usually move production only after an eval passes: general practice; the Langfuse pages do not state it (testing fact-check).
  - Running servers pick up a label move within about a minute: inferred from the 60 s default TTL (testing fact-check).
  - LangSmith and Braintrust being hosted products: the catalogue lists them without stating hosting (S5).
- Code that does not match its comments:
  - heal-stale-template.test.ts says the heal runs "for all three registered ai-tutor keys"; index.ts registers two (X26, X18). A third key may have left with the Live tutor removal (commit f95297865, 2026-10-02) (unverified).
  - index.ts and the heal test cite commits 69e2799d and 540a671c, which `git log` cannot resolve in Lomem today (X16, X26).
  - lesson-note-writer.ts says bump "when the prompt shape changes", narrower than the rule this store gives (X32, S6).
  - The admin page sets CUSTOM whenever a row exists, but startup always creates the row, so DEFAULT likely never shows after the first startup (X31, X11; code reading, not run in a browser).
  - The admin page subtitle says the prompt is sent "at the start of every AI Tutor session"; the rendered system prompt is sent on every call, while the template text is captured once per session (X31, X19, X6).
  - The drift-test header says loadTemplateCache "uses the DB row when present"; that is still true, and the heal, not loadTemplateCache, now protects the constant (X22, X11, X17).
- Behaviour found by code reading that the drafts did not cover:
  - Save-check and render regexes disagree on whitespace inside braces (X10, X5; regexes verified in node, app not run).
  - After an admin Reset, later code-constant changes are not healed, because the archive count stays above zero (X13, X17; not run).
  - Activating an archived version that holds a no-longer-registered token fails the variable check, and the route reports it as 404 Not Found (X15, X30; not run).
  - writer_model records the active model when the deps are built; a gateway fallback could answer with a different model (X33; gateway behaviour in gateway block; not run).
  - The learner-topic rewrite depends on exact template sentences, so an admin wording change disables it silently (X9).
  - Admin tool toggles change the TOOLS layer of the rendered prompt with no template edit and no version record (X7, X19).
  - ScenarioEvalRun stores no prompt version or model id (X41).
- Corrections the fact-check made to earlier drafts (testing):
  - Layer 1 excerpt cited ai-tutor-prompt-builder.ts:42, 47, 51; correct lines are 43, 45, 48, 52, with RULES: at 45 (X1).
  - Template substitution excerpt cited 270-274; correct lines are 271-275 (X5).
  - Informal-register sentence cited line 196; correct line is 197 (X4).
  - Invented-role register sentence cited line 110; line 110 is the const declaration and the string is on 111 (X3).
  - "At advanced levels a tutor playing a friend" was corrected to "from B1 up a tutor playing a peer", the commit's wording (X40).
  - "The learner chats with the tutor" in the scenario eval was corrected: a simulated learner faces a simulated tutor, scored by the production judge (X36).
- Disagreements between sources:
  - The catalogue's minimal version logs a version hash on every call (S5); tunatutor logs none for tutor replies and stamps only lesson notes (X32, X35).
  - Research code map cited the layer list at ai-tutor-prompt-builder.ts lines 462-478 and the throw at 387; on 2026-10-15 they are 463-479 and 388 (S14, X6, X7).
- Not covered by the research:
  - How promptfoo, LangSmith or Braintrust version and serve prompts in detail.
  - Spring AI or LangChain4j prompt template APIs for Java teams.
  - Whether scenario-text-eval.mts, which drives the real production tutor path (S14), would have exercised LOM-86; it runs bound scenarios, which keep the scene register rule, so likely not (unverified).

## Sources

| id | title | author or publisher | date | URL | what it supports |
|---|---|---|---|---|---|
| S1 | Lomem monorepo, tunatutor backend and admin source | Lomem (local repository ~/projects/lomem) | main 8e3f5d5db, read 2026-10-15 | ~/projects/lomem | all X excerpts |
| S2 | Prompt management overview | Langfuse | (undated page) | https://langfuse.com/docs/prompt-management/overview | registry concept, Langfuse as open source |
| S3 | Prompt version control | Langfuse | (undated page) | https://langfuse.com/docs/prompt-management/features/prompt-version-control | numbered versions, labels, rollback by moving production, trace linking |
| S4 | Caching | Langfuse | (undated page) | https://langfuse.com/docs/prompt-management/features/caching | 60 s default client cache, stale-while-revalidate |
| S5 | Web research catalogue of building blocks, block 2 and request path | internal research note (sources/research-web.md) | 2026-10-15 | file in this store | backend analogue, new problems, minimal and mature versions, tools list; prompt-related lines of the tools, guardrails, evals, observability, caching, governance and feedback-loop blocks and of the request path |
| S6 | Long fact-checked draft, section 02 | internal draft (sources/sections-long/03-prompts.html) | 2026-10-15 | file in this store | narrative facts, advice, made-up examples, analogy |
| S7 | Short tested section 02 | internal draft (sources/sections-tested/03-prompts.html) | 2026-10-15 | file in this store | tested wording of the same facts |
| S8 | LangSmith docs | LangChain | (undated) | https://docs.smith.langchain.com/ | listed prompt-management tool |
| S9 | Braintrust docs | Braintrust | (undated) | https://www.braintrust.dev/docs | listed prompt-management tool |
| S10 | promptfoo intro | promptfoo | (undated) | https://www.promptfoo.dev/docs/intro/ | testing prompts in the repository |
| S11 | Emerging Patterns in Building GenAI Products | Bharani Subramaniam and Martin Fowler | 28 Jan to 25 Feb 2025 | https://martinfowler.com/articles/gen-ai-patterns/ | Direct Prompting and Evals definitions |
| S12 | AI Evals: Everything You Need to Know | Hamel Husain and Shreya Shankar | updated Sep 2026 | https://hamel.dev/blog/posts/evals-faq/ | evals on every prompt or model change (via S5) |
| S13 | Prompt caching | Anthropic | current at research time | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | exact-prefix matching order, stable content first (via S5) |
| S14 | Lomem code map | internal research note (sources/research-lomem.md) | 2026-10-15 | file in this store | which Lomem files implement this block, judge gate, flags |
| testing | Testing notes for section 02 (three reader rounds, fact-check, final read) | internal (sources/testing-notes/03-prompts-testing.md) | 2026-10-15 | file in this store | misreadings, unknown terms, fact-check fixes, open reader questions |
