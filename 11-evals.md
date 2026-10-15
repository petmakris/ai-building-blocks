---
id: evals
number: 11
title: Evals
summary: An eval runs an LLM feature over a fixed set of real inputs, scores each output pass or fail and compares the pass rate with a bar set before the run, because assertEquals cannot test output that varies and is open-ended.
lomem_status: by hand
depends_on: [prompts, structured]
related: [gateway, prompts, structured, guardrails, hitl, observability, governance]
---

# Evals

## Summary

An eval (short for evaluation) runs an LLM feature over a fixed set of real inputs, scores every output as pass or fail, and compares the pass rate with a bar chosen before the run.
An eval replaces assertEquals for code whose output is never exactly the same twice, and it tells you whether a change to a prompt or a model made the feature better or worse.
An eval has three parts: a dataset of inputs with references, a scorer per check, and a bar per check.
In a classic backend one green unit-test run is proof; an eval score is a statistical sample that moves between runs, and the eval's scorer can itself be wrong.
Lomem runs its evals by hand as dev scripts (the translation judge gate, the scenario judge precision check, the scenario evals), because every run makes paid model calls over the network.

## Problem

- P1 · The output varies between runs of the same code: a model picks each next word with some randomness, so one passing test can fail tomorrow with no code change. [S11, S3, S9]
- P2 · The output is open-ended: a free-text explanation (such as the grader's `why`) has no single correct string to compare with. [S11, S9]
- P3 · One case proves nothing: a new prompt that fixes paraphrases can quietly break negations, which shows only across many cases. [S11]
- P4 · Every prompt or model change can silently regress something that used to work. [S9]
- P5 · A real input has no stored right answer, so a reference must come from somewhere: an old version's output or a person's label. [S11]
- P6 · Some qualities can only be judged by a reader (is this marked word really an error?), so code cannot score them and a person or a second model must. [S11]
- P7 · The scorer itself can be wrong when it is an LLM judge, which never happens with assertEquals. [S11, S12]
- P8 · A pass rate over n cases is an estimate, so a small difference between two prompts may be noise. [S11]
- P9 · Each eval run costs money and needs the network, so it does not fit a free, offline CI step by default. [S11, X1, X13]
- P10 · The system improves only if production failures come back into eval sets and prompts. [S9]

## Concepts

### C1 · Eval
- Definition: An eval runs an LLM feature over a fixed set of real inputs, scores every output pass or fail, and compares the pass rate with a bar chosen before the run.
- Facts:
  - An eval replaces assertEquals for code whose output is never exactly the same twice. [S11]
  - An eval tells you whether a change to a prompt or a model made the feature better or worse. [S11]
  - "Evals" is one of the nine patterns in Subramaniam and Fowler's catalogue, defined there as "Evaluate the responses of an LLM in the context of a specific task". [S6]
  - Eugene Yan's pattern list also starts with Evals. [S7]
  - An eval is "many real cases, a scorer per case and a pass-rate bar per check, written down before the run and never lowered". [S11]
  - The web catalogue's backend analogue: a test suite whose result is a score and a pass rate, not green or red. [S9]
  - Other blocks lean on evals: prompt versions are linked to traces and eval scores, and promotion is gated on an eval run (prompts); RAG adds retrieval-specific evals such as recall@k (rag); a semantic cache's similarity threshold is tuned by evals (caching); documented evals are validation evidence in a regulated setting (governance). [S9]
  - FINMA's assessment areas, as given by secondary sources, include "tests and monitoring". [S9] (unverified: the official PDF did not parse)
- Relations: C1 is made of C7 (dataset), C9 (scorer) and C10 (bar). C1 tests C4 (LLM feature). C1 is split into C26 (regression eval) and C27 (capability eval). C1's result is limited by C30 (standard error).

### C2 · Large language model (LLM), or model
- Definition: A large language model is a hosted service that takes text in and writes text back.
- Facts:
  - Vendors offer several models and replace them with new versions, so "a model change" means switching your code to another one. [S11]
  - Newcomer readers did not know that "model change" or "model version" means switching between several models a vendor offers. [testing]
  - Newcomer readers did not know Anthropic is a model vendor; the text named it only as a documentation source. [testing]
- Relations: C2 is called by C4. A change of C2 is one of the two changes an eval guards (with C3). gateway is the block that sends C2 calls.

### C3 · Prompt
- Definition: The prompt is the text you send a model: your instructions plus the data.
- Facts:
  - In Lomem the old grading prompt is named `card` and the new one is named `arc`. [S11, X1]
  - The `card` prompt has no marks; the `arc` prompt fills marks, focus and why. [S11, X20]
  - The gate's old prompt is a frozen copy of the pre-TR2 `card` prompt, kept in the script with the comment "Do not edit". [X2]
- Relations: C3 is the thing most often changed under an eval. prompts is the block that versions C3.

### C4 · LLM feature
- Definition: An LLM feature is ordinary code that builds a prompt, calls the model and parses its reply.
- Facts:
  - The feature under test in the running example is the translation grader of Lomem's tunatutor app. [S11]
  - Lomem is a private project; its app tunatutor teaches languages. The short tested version calls Lomem "a small codebase of apps". [S11, S12]
  - In the translation drill the learner sees a sentence in her own language (for example English) and types it in the language she practises (for example French). [S11]
  - An earlier draft said she always sees English and types French, Spanish or German; the fact-check fixed it, since the fixture also has Italian and Portuguese rows. [testing, X10]
  - Almost any answer that is not an exact match goes to a model with a prompt that says, in short, "here is the source sentence, the key and the learner's answer; reply with JSON saying whether it is correct". [S11]
- Relations: C4 is what C1 measures. C4 uses C3 and C2. C38 (grader) is one C4.

### C5 · Temperature and non-determinism
- Definition: Temperature is a model setting that controls how much randomness the model uses when it picks each next word.
- Facts:
  - Temperature is usually between 0 and 1; 0 means "always take the likeliest word" and higher means more variety. [S11]
  - Anthropic's Messages API documents a range of 0.0 to 1.0. [S3, testing]
  - An earlier draft linked docs.anthropic.com/en/api/messages, which redirects to a page with no temperature text; the fact-check moved the link to S3. [testing]
  - Anthropic's documentation says: "Note that even with temperature of 0.0, the results will not be fully deterministic". [S3]
  - Lomem calls the translation grader at `temperature: 0.3` in production and in the gate script. [X5, X19]
  - Lomem's fidelity eval calls its own judge at `temperature: 0.2`. [X22]
  - Lomem's simulated learner in the scenario text eval runs at `temperature: 0.7`. [X21]
  - A newcomer reader asked whether setting temperature to 0 would make assertEquals work; the answer is no, because even 0 is not fully deterministic and the output is still open-ended. [testing, S3]
- Relations: C5 causes P1. C5 causes C31 (run-to-run wobble). C5 is the reason for C33 and C34 (k runs).

### C6 · Open-ended output
- Definition: Open-ended output is free text that has no single correct string to compare with.
- Facts:
  - The grader's `why` sentence is open-ended output. [S11]
- Relations: C6 causes P2. C6 is scored by C21 (LLM-as-judge) or a person, not by C19 (exact match).

### C7 · Dataset
- Definition: The dataset is the list of inputs an eval runs, each with a reference: what a good output looks like.
- Facts:
  - The Lomem gate's dataset is up to 200 real learner answers plus the 36 fixture rows. [S11, X1, X9]
  - Only golden rows carry a human reference; real rows use the old prompt's verdict as their reference. [S11, testing]
  - A newcomer reader said the dataset holds "each input with what a good output looks like", which is true only of the golden rows. [testing]
- Relations: C7 is part of C1. C7 is made of C14 (real rows) and C15 (golden rows). C7 carries C8 (reference).

### C8 · Reference
- Definition: A reference is what a good output looks like for one input in the dataset.
- Facts:
  - On golden rows the reference is a person's decided answer (`expected`, `markedWords`). [S11, X9]
  - On real rows the reference is the old prompt's verdict, which stands in because no person has said whether the real answer is right. [S11]
- Relations: C8 belongs to each row of C7. The source of C8 decides whether a check measures change or correctness (C17).

### C9 · Scorer
- Definition: The scorer is the code or the person that turns one output into pass or fail.
- Facts:
  - Choose the cheapest scorer that can decide a case: exact match first, then code assertions, then an LLM-as-judge only for what code cannot check. [S11, S1, S9]
  - Use binary pass/fail scorers; a 1-to-10 score drifts because nobody can say what separates a 6 from a 7. [S11, S1]
  - In the Lomem gate, check 1 uses exact match, checks 2 and 4 use code assertions, and check 3 is scored by a person. [S11, X1]
- Relations: C9 is part of C1. C9 has three kinds: C19, C20, C21. A person scoring is the human fallback (hitl).

### C10 · Bar
- Definition: The bar is the pass rate an eval check must reach, written down before the run.
- Facts:
  - There is one bar per check, for example 95%. [S11]
  - You write the bar down before the run so a disappointing result cannot move it. [S11]
  - When a run misses the bar you read the failing rows, fix the prompt and run again; you do not lower the bar. [S11]
  - Where a bar comes from: the old version's score on the same rows, if there is an old version. [S11]
  - For a brand-new feature: run the cheapest alternative on the same rows and require a clear gain over it, or decide from what an error costs. [S11]
  - "A learner may see at most one wrong grade in 20 answers" is a 95% bar. [S11]
  - A bar must be set anew when the rows or k change; it is not reused. [S11]
  - A pass^3 bar must be set anew from a measured run, not copied from a single-run bar. [S11]
  - The Lomem gate's bars are single-run rates: each row runs once. [S11, X7]
  - Newcomer readers missed that the bar must never be lowered after a miss and how to pick a bar for a brand-new feature. [testing]
- Relations: C10 is part of C1. C10 comes from C11 (baseline) or from the cost of an error. C10's meaning depends on C36 (scoring rule).

### C11 · Baseline (cheapest alternative)
- Definition: A baseline is the cheapest alternative to the feature, run on the same rows to give a brand-new feature a bar to beat.
- Facts:
  - For the grader the baseline is "exact match with the key, everything else wrong". [S11]
- Relations: C11 sets C10 for a new feature.

### C12 · Gate (Lomem term)
- Definition: In Lomem a gate is an eval check that decides whether a change may be switched on for users.
- Facts:
  - `scripts/translation-judge-gate.ts` decides whether the marks may be switched on with the `TD_JUDGE_MARKS` flag. [S11, X1]
  - The gate script's header calls it "A dev harness, not a CI test". [X1]
  - The script's exit code does not depend on the checks; it exits 1 only on a crash. [testing, X8]
  - A person decides after reading the output. [S11]
  - Newcomer readers did not know the word "gate" as a noun. [testing]
  - The short tested version shows four checks (verdict on real rows, verdict on fixture rows, marks land, speed) and leaves out check 1c and check 3; it says a person "decides whether to switch the new prompt on". [S12]
- Relations: C12 is one C1. C12 controls C13 (feature flag). C12 ends in a human decision (hitl).

### C13 · Feature flag
- Definition: A feature flag is a config switch that turns a behaviour on or off without other code changes.
- Facts:
  - `TD_JUDGE_MARKS` is a constant in code, `false` today; "Only TR4's PR may flip it to true." [X16]
  - While `TD_JUDGE_MARKS` is false, a parsed reply returns `marks: null`, so the phone draws nothing. [X16]
  - The `weak` field is held back with the marks because "`weak` was never measured by the judge gate". [X16]
  - Lomem has no feature-flag service; flags are code constants plus database config rows. [S10]
- Relations: C13 is released only through C12. C13 is a rollout control (governance).

### C14 · Real rows
- Definition: Real rows are real learner answers taken from usage data, with no human label.
- Facts:
  - The gate loads real rows from a local copy of the staging database, filled by `tunatutor pull-staging-data`. [X1, S11]
  - The staging database is the pre-production environment, which holds real test usage. [S11]
  - The gate takes drill attempts in translation mode that have a user answer and a score (the "AI-judged answers"). [X3]
  - The gate skips empty answers and answers whose normalised form equals the key or an accepted variant. [X3]
  - The gate keeps up to 200 real rows, spread evenly across languages (round robin by language). [X7, X11]
  - Real rows measure change, not correctness. [S11]
  - Real traffic rarely contains a correct paraphrase, so paraphrase rows had to be written by hand. [S11] (unverified: rests on the fixture header comment, not a count) [testing]
  - The fixture header says the real AI-judged answers "are almost all literal matches or wrong answers". [X9]
- Relations: C14 is part of C7. C14's reference is the old verdict (C17). A disagreement on C14 is a break or a fix (C18).

### C15 · Golden dataset (fixture)
- Definition: A golden dataset is a set of inputs paired with the answer a person who knows the domain decided is correct.
- Facts:
  - Lomem's golden dataset is `judge-gate-fixture.ts`, 36 hand-made rows. [S11, X10]
  - In Java terms "fixture" here means hand-made test data. [S11, testing]
  - Each fixture row carries `language`, optional `source`, `key`, `variants`, `answer`, `expected` ("right" or "wrong"), `markedWords` and `note`. [X9]
  - 15 of the 36 rows have a note starting "paraphrase" and must come out right; 21 rows must come out wrong. [X10]
  - The fixture has 18 French, 7 Spanish, 7 German, 3 Italian and 1 Portuguese row. [X10]
  - Only 4 fixture rows carry a `source` sentence; for the rest the gate passes "(the meaning of) <key>" as the source. [X4, X10]
  - No fixture row is an exact match of its key or variants, because an exact match never reaches the model. [X9]
  - A `markedWords` entry is a word as it stands in `answer`; for a missing word it is the word before the gap. [X9]
  - The best golden rows are real inputs a person has labelled; hand-written rows fill the kinds real traffic lacks. [S11]
  - A purpose-built golden set often grows to 100 rows or more, and grows each time a new kind of failure is found. [S1, S11]
  - An earlier draft called 50 to 200 rows "a normal size"; the cited source does not support it, and the fact-check replaced it with the 100-row figure. [testing]
  - In a mature setup, golden datasets are drawn from production traces. [S9]
- Relations: C15 is part of C7. C15 measures correctness (C17). C15 rows carry C16 (note). C15 grows from C24 (error analysis) and C18 (fixes).

### C16 · Note (kind of case)
- Definition: A note is a short label on a golden row naming the kind of case it tests, such as "negation lost".
- Facts:
  - A failure report counts failures per note, so it says which kind of case broke. [S11]
  - The note column in Lomem's fixture is the result of error analysis. [S11]
  - The gate uses notes starting with "paraphrase" for check 1c. [X7]
- Relations: C16 is the output of C24. C16 groups failures of C15.

### C17 · Change versus correctness
- Definition: Scoring real rows against the old version measures change; scoring golden rows against human labels measures correctness.
- Facts:
  - On real rows, agreement with the old prompt means "nothing changed on everyday traffic" and says nothing about correctness. [S11]
  - A disagreement on a real row may be a fix: the new prompt is right where the old one was wrong. [S11]
  - Correctness comes from the golden rows. [S11, S12]
  - This was the point newcomer readers missed most often across three rounds. [testing]
- Relations: C17 explains why C14 and C15 are kept apart. C17 leads to C18.

### C18 · Break versus fix
- Definition: A real-row disagreement is a break when the new prompt is wrong, and a fix when the new prompt is right where the old one was wrong.
- Facts:
  - A person reads every real-row disagreement and decides whether it is a break or a fix. [S11]
  - A break sends you back to the prompt. [S11]
  - A fix gets a human answer and moves into the fixture, where the new prompt must now match that answer. [S11]
  - Moving a fix into the fixture does not loosen anything: the row is still scored, against a better reference, and the 95% bar stays as written. [S11]
  - The gate script lists only fixture disagreements; real-row verdicts are available only through `GATE_JSON_OUT`. [testing, X7]
  - A newcomer reader read moving rows out of check 1a as a possible way around the bar. [testing]
- Relations: C18 is a step of F2. C18 feeds C15. L4 is the lifecycle of C18.

### C19 · Exact match scorer
- Definition: An exact-match scorer passes an output when it equals the reference; it fits a label, a number or an enum.
- Facts:
  - Check 1 of the Lomem gate is exact match: one verdict against another. [S11]
  - The exact-match scorer is a different idea from the grader's exact-match shortcut, where code accepts an answer equal to the key before any model call. [testing]
  - Exact match cannot be used on live production replies because there is no answer key there. [S11]
- Relations: C19 is the cheapest C9. C19 is not the same as the feature pre-pass (K13).

### C20 · Code assertion
- Definition: A code assertion is a scorer that tests a property code can check, such as valid JSON, a field present, a time limit, or a word that occurs in the input.
- Facts:
  - Checks 2 (marks land) and 4 (speed) of the Lomem gate are code assertions. [S11]
  - Code assertions come first, before an LLM judge. [S9, S1]
- Relations: C20 is a C9. C20 overlaps with structured (validation of a reply's shape).

### C21 · LLM-as-judge
- Definition: An LLM-as-judge is a second, separate model call, made by the eval and not by the feature, that reads the feature's output and grades it against a rubric.
- Facts:
  - Use an LLM judge only for what only a reader can tell, such as whether a marked word is really an error or whether an explanation is accurate. [S11]
  - The Lomem translation gate does not use an LLM judge yet; a person does check 3. [S11]
  - The LLM judge is itself an LLM feature that can be wrong, so you check it before you trust it. [S11]
  - A mature setup uses one judge per failure mode. [S9]
  - Lomem's generator fidelity eval does use an LLM judge, on five dimensions. [X22]
  - Lomem's scenario grader is an LLM judge in the product itself (it grades a learner's conversation), and the precision check tests it. [X13, X27]
  - Newcomer readers were confused that the translation feature is itself a grader while "LLM-as-judge" is a separate scorer; this was the biggest real confusion in round 1. [testing]
- Relations: C21 is the most expensive C9. C21 needs C22 (rubric) and C23 (validation).

### C22 · Rubric
- Definition: A rubric is a short written list of what counts as pass and what counts as fail, given to a judge.
- Facts:
  - Lomem's translation prompts carry a grading rubric that changes with strictness: STRICT, BALANCED, RELAXED. [S10, X20]
  - mytube keeps a canonical scoring rubric in `apps/mytube/web/lib/llm/rubric.ts`, described as "the SINGLE source of truth". [S10]
  - Where a validated judge disagrees with the person, you rewrite the rubric and measure again. [S11, S1]
- Relations: C22 is the input of C21. C22 is revised in F6.

### C23 · Judge validation (true positive and true negative rate)
- Definition: Judge validation compares an LLM judge's grades with a person's labels on the same outputs, separately for the person's fails and the person's passes.
- Facts:
  - Here a "positive" is an error, as in Husain and Shankar's guide. [S1, S11]
  - True positive rate is the share of the person's fails the judge also failed. [S1, S11]
  - True negative rate is the share of the person's passes the judge also passed. [S1, S11]
  - Both rates matter, because a judge that passes everything scores 100% on the true negative rate. [S11]
  - Husain and Shankar suggest at least 50 labelled passes and at least 50 labelled fails. [S1, S11]
  - There is no fixed target; choose it from what a missed failure and a false alarm cost. [S1, testing]
  - Repeat the validation when the judge's model changes. [S11]
  - The hand-read words of check 3 are exactly the labels that would validate a check-3 judge. [S11]
  - An earlier draft had TPR and TNR the wrong way round; the fact-check fixed it. [testing]
  - An earlier draft claimed a rule of thumb of both rates above about 90%; the cited source does not make it and it was removed. [testing]
  - Newcomer readers had judge validation as "compare with 50-100 human labels" and missed that passes and fails are counted separately. [testing]
- Relations: C23 gates trust in C21. C23 is flow F6 and lifecycle L5.

### C24 · Error analysis
- Definition: Error analysis means reading 30 to 100 real outputs by hand, writing a one-line note on each bad one, and grouping the notes into categories.
- Facts:
  - You cannot write good scorers before you know how the feature fails. [S11]
  - Each category became one or more golden rows, and the report counts failures per category. [S11]
  - A category that code can check, such as "marked a word the learner never wrote", also gets a check of its own (check 2). [S11]
  - A category gets a separate check only when code can test it; it does not mean one check per category. [testing]
  - The minimal version reads about 30 to 100 real traces and groups failures into a taxonomy. [S9]
  - The mature version repeats error analysis every 2 to 4 weeks. [S9]
- Relations: C24 comes before C9 and C15. C24 produces C16. C24 is flow F5.

### C25 · Separate checks
- Definition: Separate checks keep each quality (correctness, mark placement, speed) as its own pass/fail with its own bar.
- Facts:
  - Had speed and correctness been one pass/fail, a slow right answer would count as a wrong one. [S11]
  - Newcomer readers copied the Java sketch's single exit condition and lost the per-check diagnosis. [testing]
  - Newcomer readers took check 1's 95% as one bar over real and fixture rows combined; in the code these are three bars: real ≥ 95%, fixture ≥ 95%, paraphrase misses = 0. [testing, X7]
- Relations: C25 shapes C10 (one bar per check).

### C26 · Regression eval and regression set
- Definition: A regression eval reproduces a bug that was fixed and asserts it stays fixed; the cases of fixed bugs together form the regression set.
- Facts:
  - A regression set should pass at or near 100%. [S11, S2, S9]
  - A drop blocks the change: it does not ship until someone has read the failing case and fixed the prompt. [S11]
  - Lomem's example is `scenario-judge-precision-check.mts`, which reproduces the PR #227 false accept. [X13]
  - With two cases a regression check is all-or-nothing. [S11]
  - The regression set belongs in the build pipeline as a required step for every prompt or model change, when the team accepts the cost of model calls on each build. [S11]
  - Lomem does not put it in the pipeline; it runs the scripts by hand because every run calls a paid service over the network. [S11, X13]
  - The precision check's header says "CI never calls the LLM". [X13]
  - An earlier draft said Lomem runs both scripts by hand "before a release"; nothing in the repo ties them to releases, so the fact-check removed it. [testing]
  - As fixed bugs accumulate, their cases form a regression set run together. [S11]
- Relations: C26 is a C1. C26 is the opposite role of C27. C26 pairs C28.

### C27 · Capability eval
- Definition: A capability eval uses the same loop and scorers on cases the feature does not handle well yet, to measure progress.
- Facts:
  - A capability eval may start at 40%. [S11]
  - A capability eval blocks nothing; you watch it climb. [S11]
  - When a case passes reliably, move it into the regression set. [S11, S2]
  - Newcomer readers in rounds 1 and 2 missed that capability cases graduate into the regression set. [testing]
- Relations: C27 feeds C26. C27 is a state in L1.

### C28 · Positive/negative pairing
- Definition: Pairing puts a good case next to each bad case, so a "fix" that rejects everything also fails.
- Facts:
  - The precision check pairs a reschedule-only transcript (must be rejected) with a real shop transaction (must be accepted). [X13]
  - Lomem's scenario eval runs adversarial probes because "pass-rate alone would rubber-stamp an over-latching judge (it only rewards recall)". [X24]
- Relations: C28 protects C26. C28 is the same idea as measuring both C23 rates.

### C29 · True rate and sample
- Definition: The true rate is the pass rate you would get over every input users will ever send; your cases are a sample and the measured rate is an estimate of it.
- Facts:
  - You never see the true rate. [S11]
  - Newcomer readers did not know the term "true rate". [testing]
- Relations: C29 is estimated by C1. C30 measures the distance from C29.

### C30 · Standard error
- Definition: The standard error says how far a measured pass rate typically lies from the true rate: √(p × (1 − p) / n) for a measured rate p over n cases.
- Facts:
  - The estimate falls within two standard errors of the true rate about 95% of the time. [S11]
  - Two standard errors at 200 cases and 95% is about 3 percentage points. [S11]
  - Two standard errors at 40 cases and 95% is about 7 percentage points. [S11]
  - At 40 cases one failure alone moves the rate 2.5 points. [S11]
  - 94% against 96% on 200 cases does not show that one prompt is better for users. [S11]
  - The standard error measures row sampling, not model randomness; an earlier draft blamed model randomness and then gave this formula, which confused readers. [testing]
  - Newcomer readers did not know the term "standard error" or "points" (percentage points). [testing]
- Relations: C30 limits what C1 can show. C30 is separate from C31.

### C31 · Run-to-run wobble
- Definition: Run-to-run wobble is the change in verdicts when the same prompt runs twice on the same rows, caused by the model's randomness.
- Facts:
  - Run-to-run wobble is usually smaller than the sampling error. [S11]
  - A few borderline rows flip between runs. [S11]
  - A row that flips back when re-run was randomness. [S11]
  - A mature eval runs each case several times (k times) to see the randomness. [S11]
- Relations: C31 is caused by C5. C31 is handled by C32 and C33/C34.

### C32 · Paired comparison and flipped rows
- Definition: A paired comparison runs both prompts on the same rows, so the difference cannot come from which rows were drawn, and only the rows whose verdict changed carry information.
- Facts:
  - Read each flipped row: is it a fix or a break? [S11]
  - Re-run a flipped row: a row that flips back was randomness. [S11]
  - That is why the Lomem gate lists every fixture row the new prompt got wrong, and why its JSON file keeps both verdicts for every real row. [S11, X7]
  - Comparing two prompts on different rows is a common mistake. [S11]
- Relations: C32 removes the C30 sampling noise from a comparison. C32 is flow F9.

### C33 · pass@k
- Definition: pass@k is the chance that at least one of k runs of a case passed.
- Facts:
  - pass@k fits when something can check each attempt and keep a good one, for example generated code kept only if its unit tests pass. [S11, S2]
  - With 75% per run and k = 3, pass@3 = 1 − 0.25³ ≈ 98%. [S11] (made up)
- Relations: C33 is one C36 rule. C33 requires C35.

### C34 · pass^k
- Definition: pass^k is the chance that all k runs of a case passed.
- Facts:
  - pass^k fits when every user gets one attempt and each must be right, as with a grader shown to a learner. [S11, S2]
  - With 75% per run and k = 3, pass^3 = 0.75³ ≈ 42%. [S11, S9] (made up)
  - Switching to pass^3 lowers every score: a case that passes 95% of single runs passes all three only 0.95³ ≈ 86% of the time. [S11]
  - Report pass^k for the grader. [S11]
- Relations: C34 is one C36 rule. C34 requires C35. C34 needs its own C10.

### C35 · Independent runs
- Definition: Runs are independent when each call is a fresh request, so one result does not affect the next.
- Facts:
  - The pass@k and pass^k formulas assume independent runs. [S11]
  - Newcomer readers did not know why "independent" mattered in the example. [testing]
- Relations: C35 is an assumption of C33 and C34.

### C36 · Dataset score under a rule
- Definition: The dataset score is the share of cases that passed under the chosen rule (single run, pass@k or pass^k), and the bar is set on that share.
- Facts:
  - Report the rule that matches how users meet the feature. [S11]
  - Newcomer readers asked whether the bar applies to the single-run rate or to pass^k. [testing]
- Relations: C36 connects C33/C34 to C10.

### C37 · Online eval
- Definition: An online eval scores a sample of live production replies, asynchronously, and alerts when their failure rate rises.
- Facts:
  - Online evals use code assertions and the judge, because there is no answer key in production and exact match cannot be used. [S11]
  - Online evals score sampled traces asynchronously, across every step of a request. [S9]
  - The backend analogue of an online eval is synthetic monitoring or canary analysis. [S9]
- Relations: C37 is part of the mature version. C37 depends on observability (traces). C37 feeds C47.

### C38 · Grader versus judge (naming)
- Definition: The grader is the feature under test (the translation drill's model call that grades a learner); a judge is a separate model call an eval uses to score outputs.
- Facts:
  - Lomem's code calls the translation grader "the judge" (`judge-adapter.ts`, `judge-reply.ts`, `translation-judge-gate.ts`). [S11, X1]
  - The section uses "grader" for the feature and keeps "judge" for LLM-as-judge. [S11]
  - The word "judge" naming both the feature and LLM-as-judge confused newcomer readers. [testing]
  - In a checkpoint the grader makes at most one extra call, only when the raw reply contradicts itself; a consistent second reply replaces the first, and a second contradiction makes the item wrong with a score below 50. [X33]
  - A checkpoint answer scored 50 to 85 is logged as `td_checkpoint_borderline` so the owner can hand-check the 50s and decide on a third-call tie-break; the comment says to remove the log two weeks after release. [X33, S10]
- Relations: C38 is a C4. C38 is not a C21, although it is built like one.

### C39 · Verdict and marks
- Definition: The verdict (`correct`) is the grader's right/wrong decision; marks list the words in the learner's answer that are wrong, so the phone can underline them.
- Facts:
  - Each mark has a `word` and a `kind`. [S11, X20]
  - The mark kinds are: wrong (a word that is not right), extra (a word to delete), form (right word, wrong form), accent (right letters, wrong accent), order (a word in the wrong place), missing (a word is absent). [X20]
  - For kind "missing", `word` is the learner's word before the gap, or "" when the gap is at the very start. [X20]
  - A right answer has `"marks": []`. [X20]
  - The arc reply also has `score` (0-100 integer), `matchedVariant`, `focus` (one of sixteen areas or null), `why` (one sentence of 15 words or fewer) and `weak` (at most one word). [X20]
  - The sixteen focus areas are verb-form, verb, tense, time, place, who-does-it, pronoun, article, agreement, preposition, negation, noun, describing-word, order, missing, accents. [X32]
  - `parseJudgeReply` drops a `why` that writes out the key or a variant (`whyGivesAnswer`), and keeps only its first sentence. [X17, X34]
  - In production a wrong verdict whose marks cannot be placed gets typed-word fallback marks; failing that, `null`. [X17]
  - Newcomer readers did not know the reply's `score` field or the `kind` field, and saw only "form" as a mark kind. [testing]
  - Check 2 is deliberately weak: one good mark is enough. Whether each mark is a real error is check 3's job, and the fixture's `markedWords` are printed next to each marked word as a hint for the person. [S11, X7]
- Relations: C39 is the output of C38. C39's placement is check 2; its accuracy is check 3. C39 is shaped by structured.

### C40 · Exact-match pre-pass (in the feature)
- Definition: The pre-pass is code in the grader that accepts an answer equal to the key, an accepted variant, or a forgiven accent slip, before any model call.
- Facts:
  - If the answer equals the key or one of its accepted variants (ignoring case and punctuation), code marks it right and no model is called. [S11]
  - The pre-pass also accepts forgiven accent slips (`accentForgiven`). [testing, X18]
  - A one-letter typo is accepted by the pre-pass only in a checkpoint (`runMode: "test"`); in practice a typo still goes to the model. [X18]
  - An accent slip on the pair list ("il à" for "il a") is never accepted. [X18]
  - The pre-pass only ever accepts; everything else goes to the model. [X18]
  - The phone runs the same function with the same accept list, so the screen and the score agree. [X18]
- Relations: C40 sits before C38. C40 is why the gate excludes exact matches from C14 and C15.

### C41 · Scenario grader, transcript, objective, latch, false accept
- Definition: The scenario grader reads a transcript (the full text of a learner's practice conversation) and decides, for each goal (objective) of the lesson, whether the conversation completed it.
- Facts:
  - The scenario grader's code returns the list of completed (latched) objectives, stored as `UserObjectiveHit` rows; ACCEPTED and REJECTED are the precision check's names for the outcomes. [testing, X15]
  - "Everyday Transactions" (buying something) is one objective. [S11, X14]
  - The grader once accepted a conversation where the learner only rescheduled a meetup, because both talk about times and places: a false accept. [S11, X13, X14]
  - The scenario judge's system prompt says to credit a function "ONLY when the learner actually performs its defining speech-act move — never on topical or lexical overlap with a neighboring objective". [X27]
  - Completion is decided by an async LLM judge, "never in the turn loop". [X28]
  - Every credit must cite a verbatim learner utterance as evidence, and this is code-enforced. [X28]
  - "Every verdict logs `completed` vs `accepted` so judge accuracy is reviewable from logs alone." [X28]
  - The judge sees a candidate window of objectives chosen by `selectRelevantObjectives()` (ADR-032 §5); the precision check grades twice so every objective is inside that window. [S10, X15]
  - Newcomer readers did not know "transcript", "objective", "scenario" or "false accept". [testing]
- Relations: C41 is the feature under test in F4 and F10. C41's precision is C42.

### C42 · Precision and false-accept rate
- Definition: Precision here is how rarely the grader credits a goal the learner did not complete; the false-accept rate is its opposite measure.
- Facts:
  - The scenario eval's adversarial probe counts false accepts over objective opportunities (probes × objectives). [X24]
  - The text eval's adversarial mode reports "Adversarial false positives: <n>/<m> objective-opportunities latched (target: 0)". [X21]
  - Pass rate alone rewards only recall. [X24]
  - Newcomer readers did not know "precision" in the file name `scenario-judge-precision-check`. [testing]
- Relations: C42 is measured by F4, F10, F11. C42 pairs with pass rate as C28.

### C43 · Shadow mode and log mode (measure before enforcing)
- Definition: Shadow mode runs a new judge or guard and stores what it would have done, without changing what the user sees, until its rate is measured.
- Facts:
  - Lomem's overheard guards run in `log` mode until `scripts/overheard-guard-rates.ts` shows the refusal rate is under about 15 percent; then a guard is switched to `enforce` with one line. [X29]
  - Lomem's code map describes a level-chat judge in shadow mode whose opinion is stored but never shown. [S10] (unverified: the file is not on main as read on 2026-10-15; see Open questions)
- Relations: C43 is a form of C37 that feeds a release decision (L6). C43 relates to guardrails.

### C44 · Simulated learner
- Definition: A simulated learner is an LLM that plays the user in a conversation with the real system, so an eval can run whole conversations without a person.
- Facts:
  - `scenario-text-eval.mts` drives the real production tutor path with a simulated A1 learner over the REST API and WebSocket, using text turns, and reports a per-scenario pass rate. [X21]
  - `ADVERSARIAL=1` runs a non-cooperative learner that echoes, gives fragments or goes off-topic, and reports a false-positive rate instead. [X21]
  - `runScenarioEval` runs N simulated conversations plus 2 adversarial probes and writes results to a `ScenarioEvalRun` row. [X24]
- Relations: C44 is the input generator of F10 and F11. C44 relates to agents.

### C45 · Drift report (generator fidelity)
- Definition: A drift report is a per-generator, per-level pass rate per dimension, produced by judging generated items against their spec.
- Facts:
  - `eval-generator-fidelity.ts` judges each generated item on five dimensions: levelFit, verbWhitelist, lexicalTargets, antiExamples, correctness. [X22]
  - A dimension whose spec field is empty is skipped. [X22]
  - "A hard judge-parse failure is an "error" bucket, never a silent pass." [X22]
  - The report is written to stdout and as a timestamped markdown + JSON artifact. [X22]
- Relations: C45 is F12's output. C45 uses C21.

### C46 · Cost of an eval run
- Definition: Every eval case calls a paid model, so an eval run has a money cost that grows with cases, prompts compared and k.
- Facts:
  - The translation gate makes up to about 470 model calls per run, each one paid for. [S11]
  - The fidelity eval makes roughly `cells × samples × 2` calls, possibly more because the generator retries up to 3× on a malformed item. [X22]
  - The fidelity eval offers `DRY_RUN=1` to print the plan and estimate with no model call. [X22]
  - A real-path eval run writes usage events and allowance debits, "exactly as the production path would". [X22]
  - The airport eval has a binding budget: "3 runs for a1/a2, 2 runs for b1/b2 — spanish only". [X26]
  - The gate uses a system usage context with the reason "dev gate script: no learner is behind these calls". [X1]
- Relations: C46 is why C26 is run by hand in Lomem. C46 relates to gateway (usage context, metering) and governance.

### C47 · Stale dataset and feedback loop
- Definition: A dataset goes stale when new production failures do not become new rows.
- Facts:
  - New failures seen in production must become new rows. [S11]
  - Failures flow into offline eval datasets, which gate the next prompt or model change in CI. [S9]
  - User feedback (thumbs up or down, "edit before send") is logged against the trace ID; failures are triaged into eval datasets. [S9, S7]
  - In a mature human-in-the-loop setup, reviewer decisions are captured as eval labels (hitl). [S9]
- Relations: C47 is fed by C37 and user feedback (observability). C47 grows C15.

### C48 · Latency bar
- Definition: A latency bar is a check that a share of replies arrives within a time limit.
- Facts:
  - The gate's check 4 requires 95% of arc replies within 2.5 seconds (`LATENCY_LIMIT_MS = 2500`). [X1, X7]
  - The gate also prints p50 and p95 latency, by nearest rank. [X7, X11]
  - p95 is the time under which 95% of requests finish. [S11]
- Relations: C48 is a C20. C48 is the analogue of a load-test threshold.

### C49 · Pipeline (CI) placement
- Definition: Pipeline placement decides whether an eval runs automatically on every change in the build pipeline or by hand.
- Facts:
  - The minimal version in the web catalogue runs 50 to 200 cases in CI on every prompt or model change. [S9]
  - A regression set as a required pipeline step is part of the mature version. [S11]
  - In Lomem, the eval arithmetic (agreement, placeable share, latency share, percentile, stratify) lives in plain functions with ordinary unit tests. [S11, X11, X12]
  - Lomem's tunatutor backend unit tests run in CI only on manual dispatch, "for cost"; `/ship` runs them locally. [X30]
  - Newcomer readers did not know whether "pipeline" meant CI, and read "pipeline" as contradicting "kept out of CI". [testing]
- Relations: C49 decides how C26 blocks a change. C49 trades against C46.

## Components

| id | name | role | inputs | outputs | where it lives |
|---|---|---|---|---|---|
| K1 | Translation judge gate | runs old and new grading prompts on real and fixture rows and prints four checks | local DB drill attempts, fixture, env keys | PASS/FAIL per check, check-3 table, optional JSON | `apps/tunatutor/backend/scripts/translation-judge-gate.ts` |
| K2 | Golden fixture | 36 hand-made rows with human answers and notes | none | `JUDGE_GATE_FIXTURE` | `apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-gate-fixture.ts` |
| K3 | Gate stats | pure functions for agreement, placeable share, latency share, percentile, stratify | verdict lists, reply summaries, latencies, rows | numbers or null | `.../translation-drill/engine/judge-gate-stats.ts` |
| K4 | Gate stats tests | unit tests for K3 | hand-made values | pass/fail | `.../translation-drill/engine/judge-gate-stats.test.ts` |
| K5 | Frozen old prompt | copy of the pre-TR2 `card` prompt used as the reference version | row fields | prompt text | `translation-judge-gate.ts:71-110` |
| K6 | Arc prompt builder | builds the new prompt (and today's card prompt) | source, key, variants, answer, leniency, meta | prompt text | `.../translation-drill/engine/judge-translation-prompt.ts` |
| K7 | Reply parser | turns the arc raw reply into a validated verdict, marks, focus, why | raw text, answer, key, variants, language | `ParsedJudgeReply` or throws | `.../translation-drill/engine/judge-reply.ts` |
| K8 | `TD_JUDGE_MARKS` flag | switch that releases marks to users | none | boolean constant | `judge-reply.ts:20` |
| K9 | Mark placement | puts named marks on the learner's own words | answer, named marks, language | placed marks with offsets | `@tunatutor/shared` `drill-text/mark-placement.ts` |
| K10 | LLM gateway call | sends every model call with usage context | system prompt, messages, max tokens, temperature, json | reply text | `apps/tunatutor/backend/src/services/llm/index.ts` (gateway block) |
| K11 | Scenario judge precision check | regression for the PR #227 false accept | two hand-written transcripts, three objectives | exit 0 or 1 | `apps/tunatutor/backend/scripts/scenario-judge-precision-check.mts` |
| K12 | Scenario grader | production LLM judge that latches objectives | session transcript, objectives | `UserObjectiveHit` rows | `.../ai-tutor/scenario/grade-scenario-objectives.ts`, `judge-prompt.ts` |
| K13 | Pre-pass | accepts exact, variant and forgiven-accent answers without a model call | answer, key, variants, leniency, language | accept or null | `.../translation-drill/engine/judge-adapter.ts:27-43` |
| K14 | Scenario text eval | simulated learner talks to the running backend; pass rate or false-positive rate | running backend URL, story ids, runs | console report, exit code | `apps/tunatutor/backend/scripts/scenario-text-eval.mts` |
| K15 | Scenario eval runner | runs N simulated conversations plus 2 adversarial probes and stores results | eval run id, story id, runs, user id | `ScenarioEvalRun` row update | `.../ai-tutor/scenario/run-scenario-eval.ts` |
| K16 | Eval repository | creates, reads and lists eval runs | story id, requested runs, user id | `ScenarioEvalRun` rows / DTOs | `apps/tunatutor/backend/src/services/scenarios/eval-repository.ts` |
| K17 | Admin eval route | starts an eval run as a background job and lets admins poll it | `POST /api/admin/scenarios/:id/eval` with `runs` | `evalRunId` | `apps/tunatutor/backend/src/routes/admin/scenarios.ts:194-226` |
| K18 | Eval job handler | runs K15 from the job queue | job payload | none | `.../ai-tutor/jobs/handlers.ts:77-84` |
| K19 | Airport family driver | runs K15 on four airport story variants with a fixed budget | variant names | console report | `apps/tunatutor/backend/scripts/eval-airport-family.ts` |
| K20 | Generator fidelity eval | generates items with real generators and LLM-judges them against their spec | local DB objectives, env knobs | drift report (stdout, md, json) | `apps/tunatutor/backend/scripts/curriculum/eval-generator-fidelity.ts` |
| K21 | Guard rates script | measures how often log-mode guards would refuse | generated items | rates | `apps/tunatutor/backend/scripts/overheard-guard-rates.ts` |
| K22 | Person (reviewer) | scores check 3, reads disagreements, decides the flag | gate output, JSON file | decision, labels | generic (hitl) |
| K23 | Eval dataset store | golden rows plus real rows, versioned with results per prompt and model version | traces, labels | datasets | generic (mature version) |
| K24 | LLM judge | separate model call that grades outputs against a rubric | output, rubric | PASS/FAIL with reason | generic; Lomem uses one in K20 |
| K25 | Eval tools | runners and platforms for datasets, scorers and reports | prompts, datasets | scores, dashboards | promptfoo, Braintrust, LangSmith, Langfuse, Arize Phoenix, Spring AI (see Tools) |
| K26 | Checkpoint judge | rechecks a self-contradicting reply once and logs borderline scores for a hand check | judge input, one-call function | verdict, borderline log line | `.../translation-drill/engine/checkpoint-rules.ts` |

## Flows

### F1 · Translation judge gate run
Purpose: score the new `arc` grading prompt against the frozen `card` prompt on real and golden rows. Trigger: a developer runs `node --env-file=.env --import tsx scripts/translation-judge-gate.ts` from `apps/tunatutor/backend` with the network allowed.

- F1.1 · Developer → local DB: fill the local database with `tunatutor pull-staging-data` | condition: before the run | data: staging usage rows | ref: X1
- F1.2 · Script → LLM registry: `initLLMRegistry()` | condition: always | data: model config | ref: X7 (`translation-judge-gate.ts:267`)
- F1.3 · Script → DB: load drill attempts in translation mode with a user answer and a score, oldest first | condition: always | data: answer, key, variants, source line, languages | ref: X3 (`:115-125`)
- F1.3a · Script: skip an attempt whose trimmed answer is empty | condition: empty answer | data: none | → continues at F1.3 with the next attempt | ref: X3 (`:129`)
- F1.3b · Script: skip an attempt whose normalised answer equals the normalised key or a variant | condition: exact match | data: none | → continues at F1.3 with the next attempt | ref: X3 (`:130-131`)
- F1.4 · Script: `stratify(rows, 200, language)` picks up to 200 real rows, round robin across languages | condition: more than 200 rows | data: real rows | ref: X7 (`:268`), X11
- F1.4a · Script: keep all real rows | condition: 200 rows or fewer | → continues at F1.5 | ref: X11
- F1.5 · Script: load the 36 fixture rows; a row with no `source` gets "(the meaning of) <key>" | condition: always | data: fixture rows | ref: X4
- F1.6 · Script: run all real rows, then all fixture rows, through a pool of 3 workers | condition: always | data: rows | ref: X6 (`CONCURRENCY = 3`)
- F1.7 · Worker → gateway → model: call the frozen old prompt, max 256 tokens, temperature 0.3, JSON, system usage context | condition: per row | data: old prompt, "Judge now." | ref: X5 (`:209`)
- F1.8 · Worker: read the old verdict as `Boolean(parsed.correct)` | condition: the reply parses as JSON | data: oldCorrect | ref: X5 (`:210-211`)
- F1.8a · Worker: set old verdict to true only if the text matches `"correct": true` | condition: the reply is not JSON | → continues at F1.9 | ref: X5 (`:212-214`)
- F1.9 · Worker: build the arc prompt with balanced leniency | condition: always | data: row fields | ref: X5 (`:215-226`)
- F1.10 · Worker → gateway → model: call the arc prompt, max 600 tokens, and time the call | condition: always | data: arc prompt; ms | ref: X5 (`:227-228`)
- F1.11 · Worker → parser: `parseJudgeReply` with `marksEnabled: true` | condition: always | data: newCorrect, why | ref: X5 (`:229-237`), X17
- F1.11a · Parser: throw "could not be read" or "had no verdict" | condition: no clear verdict in the reply | → continues at F1.14a | ref: X17
- F1.12 · Worker: read named marks from the raw reply only when the verdict is wrong; a right verdict gets none | condition: newCorrect false | data: named marks | ref: X5 (`:238-239`)
- F1.13 · Worker → mark placement: place named marks on the learner's words; record each placed word or "(gap)" | condition: always | data: placed words with kinds | ref: X5 (`:240-241`)
- F1.14 · Worker: mark the row ok | condition: no error | → continues at F1.15 | ref: X5 (`:242`)
- F1.14a · Worker: log "call failed for ..." and leave the row not ok | condition: any call or parse error | data: error message | → the row is dropped at F1.15 | ref: X5 (`:243-245`)
- F1.15 · Script: drop rows that are not ok | condition: always | data: judged rows | ref: X7 (`:272-273`)
- F1.16 · Script: check 1a, agreement of old and new verdicts on real rows, bar 95% | condition: always | data: agreement share | ref: X7 (`:276-279, 286`)
- F1.17 · Script: check 1b, agreement of new verdict and fixture `expected`, bar 95% | condition: always | data: agreement share | ref: X7 (`:280-283, 287`)
- F1.18 · Script: check 1c, count fixture paraphrase rows graded wrong, must be 0; list each | condition: always | data: misses | ref: X7 (`:284, 288-289`)
- F1.19 · Script: print every fixture row whose new verdict differs from `expected`, with its note | condition: always | data: disagreements | ref: X7 (`:290-292`)
- F1.20 · Script: check 2, share of all replies whose marks are placeable, bar 95% | condition: always | data: placeable share | ref: X7 (`:295-299`), X11
- F1.21 · Script: check 4, share of arc latencies at or under 2500 ms, bar 95%; print p50 and p95 | condition: always | data: share, percentiles | ref: X7 (`:302-305`)
- F1.22 · Script: print the check-3 table, one line per placed word of each wrong reply, with the fixture hint "expected" or "not in expected set" | condition: always | data: table rows | ref: X7 (`:308-327`)
- F1.23 · Script: print the count of fixture marked words inside the expected set ("a hint, not the check") and the number of real rows judged ("need >= 20 hand-checked to turn marks on") | condition: always | ref: X7 (`:328-329`)
- F1.24 · Script → file: write every reply as JSON | condition: `GATE_JSON_OUT` is set | data: all judged rows with old and new verdicts | ref: X7 (`:331-333`)
- F1.25 · Script: disconnect and exit normally, whatever the checks say | condition: no crash | ref: X7 (`:334`)
- F1.25a · Script: print the error and exit 1 | condition: uncaught error | ref: X8
- F1.26 · Script: each check prints "NOT CHECKED" instead of PASS/FAIL | condition: its denominator is empty | ref: X7 (`:263-264`), X11

### F2 · Release decision for the marks flag
Purpose: decide whether `TD_JUDGE_MARKS` may be turned on. Trigger: a person has the output of F1. (The process is the team's; no code enforces it. Unverified per testing.)

- F2.1 · Person: read PASS/FAIL for checks 1a, 1b, 1c, 2 and 4 | condition: after F1 | ref: S11
- F2.2 · Person: read each line of the check-3 table and count marked words that are really wrong | condition: always | data: hand count | ref: X1, S11
- F2.3 · Person: check that the count covers at least 20 real rows and reaches 90% | condition: always | ref: X1, X7 (`:329`), S11
- F2.4 · Person: read every real-row disagreement from the JSON file | condition: `GATE_JSON_OUT` was set | ref: S11
- F2.4a · Person: classify a disagreement as a break | condition: the new prompt is wrong | → continues at F2.7 | ref: S11
- F2.4b · Person: classify a disagreement as a fix, write the human answer and move the row into the fixture | condition: the new prompt is right where the old was wrong | → continues at F1 (re-run) | ref: S11
- F2.5 · Person: flip `TD_JUDGE_MARKS` to true in TR4's PR | condition: checks 1, 2 and 4 print PASS and the person's count for check 3 reaches its bar | ref: X16, S11 (unverified)
- F2.6 · Person: keep the flag false | condition: any check misses its bar | → continues at F2.7 | ref: S11
- F2.7 · Person: fix the prompt, never the bar, and run F1 again | condition: a miss or a break | ref: S11

### F3 · Production translation grading (the feature under test)
Purpose: grade one learner answer in the translation drill. Trigger: the learner submits an answer.

- F3.1 · Grader → pre-pass: `judgeTypedAnswer` with the translation settings | condition: always | data: answer, key, variants, leniency, language | ref: X18 (`judge-adapter.ts:27-37`)
- F3.2 · Pre-pass: accept with score 100 and no model call | condition: verdict is exact, variant or accentForgiven, or a typo in a checkpoint | data: matched candidate | ref: X18 (`:38-42, 68-77`)
- F3.3 · Grader → gateway → model: call the arc prompt, temperature 0.3, JSON, max 600 tokens | condition: pre-pass returned null | ref: X18 (`:78-81`), X19
- F3.3a · Grader: in a checkpoint, call through `judgeCheckpointItem`, which makes one extra recheck call only when the raw reply contradicts itself; feedback is empty | condition: `runMode === "test"` | ref: X18 (`:80`), X33
- F3.3b · Checkpoint: mark the item wrong with a score below 50 | condition: the recheck reply also contradicts itself | ref: X33 (`checkpoint-rules.ts:55-56`)
- F3.3c · Checkpoint: log `td_checkpoint_borderline` for a later hand check | condition: the final score is 50 to 85 | ref: X33 (`checkpoint-rules.ts:59, 63-76`)
- F3.4 · Parser: validate the reply; place marks or fall back; drop a `why` that gives the answer | condition: always | ref: X17
- F3.4a · Parser: throw `ServiceUnavailableError`, so /answer fails, nothing is saved and she can retry | condition: no clear verdict | ref: X17
- F3.5 · Parser: return `marks: null` | condition: `TD_JUDGE_MARKS` is false | ref: X16

### F4 · Scenario judge precision check (regression eval)
Purpose: prove the PR #227 false accept stays fixed. Trigger: a developer runs `node --env-file=.env --import tsx scripts/scenario-judge-precision-check.mts` with the sandbox off.

- F4.1 · Script → DB: create an ephemeral story "Precision check — A2-U02 bundle" with three objectives (invite, Everyday Transactions, service complaint) and bare success hints | condition: always | ref: X14
- F4.2 · Script → DB: create a session and write the reschedule-only transcript | condition: negative case | ref: X15
- F4.3 · Script → scenario grader: `gradeScenarioObjectives` twice ("idempotent — so every objective is inside the candidate window") | condition: always | ref: X15
- F4.4 · Script → DB: read latched objectives (`UserObjectiveHit`) for the session | ref: X15
- F4.5 · Script → DB: delete the session | condition: always (finally) | ref: X15
- F4.6 · Script: repeat F4.2-F4.5 with the shop transaction transcript | condition: positive case | ref: X15
- F4.7 · Script: print "Everyday Transactions REJECTED (must reject)" for the negative case | ref: X15
- F4.7a · Script: print a warning, not a failure, if the service complaint was latched on the negative case | condition: complaint latched | ref: X15
- F4.8 · Script: print "Everyday Transactions ACCEPTED (must accept)" for the positive case | ref: X15
- F4.9 · Script: clean up the story and exit 0 | condition: negative rejected and positive accepted | ref: X15
- F4.9a · Script: exit 1 | condition: either required outcome fails | ref: X15
- F4.9b · Script: clean up and rethrow, then exit 1 | condition: an error | ref: X15

### F5 · Error analysis
Purpose: find out how the feature fails before writing scorers. Trigger: before building an eval, and again every 2 to 4 weeks in a mature setup.

- F5.1 · Person: read 30 to 100 real outputs by hand | ref: S11, S1, S9
- F5.2 · Person: write a one-line note on each bad output | ref: S11
- F5.3 · Person: group the notes into categories | ref: S11
- F5.4 · Person: turn each category into one or more golden rows with that note | ref: S11
- F5.5 · Person: add a code check for a category code can test (for example "marked a word the learner never wrote" became check 2) | condition: code can test it | ref: S11
- F5.6 · Eval: report failures per category, which says where to work next | ref: S11

### F6 · Validating an LLM judge
Purpose: decide whether an LLM judge can be trusted as a scorer. Trigger: before using a judge, and again when the judge's model changes.

- F6.1 · Person: label outputs pass or fail, with both kinds well represented (at least 50 of each) | ref: S1, S11
- F6.2 · Judge: grade the same outputs against the rubric | ref: S11
- F6.3 · Eval: compute the true positive rate (share of the person's fails the judge failed) | ref: S1, S11
- F6.4 · Eval: compute the true negative rate (share of the person's passes the judge passed) | ref: S1, S11
- F6.5 · Person: compare both with targets chosen from what a missed failure and a false alarm cost | ref: S1, testing
- F6.5a · Person: rewrite the rubric and go back to F6.2 | condition: the judge disagrees with the person | ref: S11
- F6.6 · Team: use the judge as a scorer | condition: both rates reach their targets | ref: S11
- F6.7 · Team: repeat F6.1-F6.5 | condition: the judge's model changes | ref: S11

### F7 · Minimal CSV eval loop (Java sketch)
Purpose: the smallest working eval. Trigger: before every prompt or model change.

- F7.1 · Person: read 30 to 50 real inputs and write the expected verdict and a note next to each in `golden.csv` (answer,key,expectedRight,note) | ref: S11
- F7.1a · Person: leave out answers equal to the key | condition: your code never sends those to the model | ref: S11
- F7.2 · Loop: load the cases | ref: E10
- F7.3 · Loop → grader: grade each case with the real prompt and model, timing the call | ref: E10
- F7.4 · Loop: count the case as fast when it took 2500 ms or less | ref: E10
- F7.5 · Loop: count the case as right when the verdict equals `expectedRight` | ref: E10
- F7.5a · Loop: add one to the note's failure count and print "FAIL [note] answer" | condition: the verdict differs | → continues at F7.3 | ref: E10
- F7.6 · Loop: print both rates with their bars and the failures by note | ref: E10
- F7.7 · Loop: exit 0 when both rates are at least 0.95, otherwise 1 | ref: E10
- F7.8 · Person: read every printed failure instead of trusting a one-point change, because with 40 cases the rate is coarse | ref: S11

### F8 · Regression and capability cycle
Purpose: keep what works working and measure what does not work yet. Trigger: a bug is fixed, or a new capability is targeted.

- F8.1 · Team: write a case that reproduces a fixed bug, paired with a good case | condition: a bug was fixed | ref: S11, X13
- F8.2 · Team: add the pair to the regression set | ref: S11
- F8.3 · Pipeline or person: run the regression set on every prompt or model change | ref: S11
- F8.3a · Team: block the change until someone has read the failing case and fixed the prompt | condition: the set drops below near 100% | ref: S11
- F8.4 · Team: write capability cases for behaviour that does not work yet; run them with the same loop and scorers | ref: S11
- F8.5 · Team: watch the capability score climb; it blocks nothing | ref: S11
- F8.6 · Team: move a capability case into the regression set | condition: the case passes reliably | → continues at F8.2 | ref: S11, S2

### F9 · Comparing two prompts
Purpose: decide whether a new prompt is better. Trigger: a prompt or model change.

- F9.1 · Eval: run both prompts on the same rows | ref: S11
- F9.2 · Eval: list the rows whose verdict changed | ref: S11
- F9.3 · Person: read each changed row: fix or break? | ref: S11
- F9.4 · Eval: run each changed row again | ref: S11
- F9.4a · Person: treat the row as randomness | condition: the row flips back | ref: S11
- F9.5 · Person: do not call a difference within about two standard errors an improvement | ref: S11

### F10 · Admin scenario eval run (stored)
Purpose: measure a scenario with simulated conversations and store the result. Trigger: `POST /api/admin/scenarios/:id/eval`, or `scripts/eval-airport-family.ts`.

- F10.1 · Admin route: look up the scenario | ref: X25
- F10.1a · Admin route: throw `NotFoundError("Scenario not found")` | condition: no scenario | ref: X25
- F10.2 · Admin route: clamp runs to 1-10, default 5 | ref: X25
- F10.3 · Repository → DB: create a `ScenarioEvalRun` with status "pending" | ref: X23
- F10.4 · Admin route → job queue: enqueue `ScenarioEvalRun` job; return `evalRunId` | ref: X25
- F10.5 · Job handler: validate the payload; log "invalid payload" and stop if a field is missing | ref: X25
- F10.6 · Runner → DB: set status "running" | ref: X24
- F10.7 · Runner: load the story and its objectives; throw if none | condition: missing story or no objectives | → continues at F10.13a | ref: X24
- F10.8 · Runner: compute the required hits from the completion threshold (stretch objectives excluded), or 1 | ref: X24
- F10.9 · Runner: run N simulated conversations with max turns `max(12, objectives × 2 + 4)` | ref: X24
- F10.9a · Runner: count a failed conversation as an incomplete run | condition: a conversation throws | ref: X24
- F10.10 · Runner: compute pass rate (passed / runs), average turns, per-objective reach, per-leg reach for journeys | ref: X24
- F10.11 · Runner: run 2 adversarial probes; a failed probe counts as 0 false accepts | ref: X24
- F10.12 · Runner: compute the false-accept rate as false accepts / (2 × objectives) and stamp `probeMaxTurns` | ref: X24
- F10.13 · Runner → DB: set status "done" with pass rate, average turns and result JSON (per objective, two sample transcripts, false-accept numbers, per leg) | ref: X24
- F10.13a · Runner → DB: set status "failed" with the error | condition: any error | ref: X24
- F10.14 · Admin: poll `GET /api/admin/scenarios/eval/:evalRunId` or list the last 20 runs | ref: X25, X23

### F11 · Scenario text eval (simulated learner against a running backend)
Purpose: check the real tutor path end to end without speech. Trigger: `BACKEND_URL=... node --env-file=.env --import tsx scripts/scenario-text-eval.mts`.

- F11.1 · Script → backend: start a session for each story (default all seeded A1 stories), `RUNS` times (default 1) | ref: X21
- F11.2 · Simulated learner (LLM, temperature 0.7) → tutor: text turns over REST and WebSocket | ref: X21
- F11.2a · Script: retry the simulated learner call up to 4 times | condition: a transient fetch failure | ref: X21
- F11.3 · Production judge (job queue): mark objectives | ref: X21
- F11.4 · Script: a run passes when all its objectives are done | ref: X21
- F11.5 · Script: print "Pass-rate: <passes>/<results>" and exit 0 only when all pass | condition: cooperative mode | ref: X21
- F11.5a · Script: print adversarial false positives and exit 0 only when there are none | condition: `ADVERSARIAL=1` | ref: X21

### F12 · Generator fidelity eval
Purpose: check that the generators follow the objective spec. Trigger: a developer runs `scripts/curriculum/eval-generator-fidelity.ts`, after `DRY_RUN=1` first.

- F12.1 · Script: print the plan and estimated call count and exit | condition: `DRY_RUN=1` or `--plan` | ref: X22
- F12.2 · Script → local DB: sample objectives with a meaningful spec, per CEFR level × generator | ref: X22
- F12.3 · Script → real generator → model: produce an item through the real `callLLM` | ref: X22
- F12.4 · Script → LLM judge: judge the item on up to five dimensions (temperature 0.2, max 800 tokens) | ref: X22
- F12.4a · Script: call the judge a second time | condition: the reply does not parse | ref: X22
- F12.4b · Script: throw "judge produced unparseable output after 2 attempts"; the sample goes to the "error" bucket, never a silent pass | condition: second parse fails | ref: X22
- F12.5 · Script: aggregate the drift report per generator and level and write md + JSON | ref: X22

### F13 · Online eval (mature)
Purpose: watch quality on live traffic. Trigger: sampled production requests.

- F13.1 · System: sample live production replies | ref: S11, S9
- F13.2 · Scorers: score them asynchronously with code assertions and a validated judge (no answer key, so no exact match) | ref: S11, S9
- F13.3 · System: alert when the failure rate rises | ref: S11
- F13.4 · Team: triage failures into the offline eval datasets | → continues at F8.2 | ref: S9

### F14 · Evals in one request's path
Purpose: where evals sit around a user request. Trigger: any request.

- F14.1 · Request: passes through guardrails, cache, router, context assembly, gateway, agent loop and output handling | ref: S9
- F14.2 · Across every step: tracing records tokens, cost, prompt version and model version | ref: S9
- F14.3 · Online evals: score sampled traces asynchronously | ref: S9
- F14.4 · User feedback: attaches to the trace ID | ref: S9
- F14.5 · Failures: flow into offline eval datasets, which gate the next prompt or model change in CI | ref: S9

## States

### L1 · Eval case
- States:
  - candidate: a failure seen in error analysis or production, not yet a row.
  - capability: a row for behaviour that does not work reliably yet; it blocks nothing.
  - regression: a row that must keep passing; a failure blocks the change.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| candidate | person writes the row with a reference and a note | none | capability | the case is measured | S11 |
| candidate | a bug is fixed | paired with a good case | regression | the fix is guarded | S11, X13 |
| capability | repeated runs | the case passes reliably | regression | the case now blocks changes | S11, S2 |
| regression | a change makes it fail | none | regression | the change is blocked until the prompt is fixed | S11 |

### L2 · Scenario eval run (`ScenarioEvalRun.status`)
- States:
  - pending: the row exists and the job is queued.
  - running: the runner has started.
  - done: results are stored (pass rate, average turns, result JSON, completed time).
  - failed: an error is stored with the completed time.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| (none) | admin POST or airport driver calls `createEvalRun` | scenario exists | pending | row created with requested runs | X23, X25 |
| pending | job handler calls `runScenarioEval` | valid payload | running | status updated | X24 |
| running | all conversations and probes finish | no thrown error | done | pass rate, avgTurns, resultJson, completedAt written | X24 |
| running | error (no story, no objectives, DB error) | none | failed | error and completedAt written | X24 |
| pending | job payload invalid | none | pending | handler logs and returns; the row stays pending | X25 (code observation) |

### L3 · Marks flag (`TD_JUDGE_MARKS`)
- States:
  - off: marks are parsed in the gate only; users get `marks: null` and no `weak`.
  - on: users get placed marks and `weak`.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| off | TR4's PR flips the constant | checks 1, 2, 4 PASS and hand count for check 3 ≥ 90% from ≥ 20 real rows | on | phone draws marks | X16, X1, S11 (unverified process) |
| off | gate run misses a bar | none | off | prompt is fixed and the gate re-run | S11 |

### L4 · Real-row disagreement
- States:
  - disagreement: old and new verdicts differ on a real row.
  - break: the new verdict is wrong.
  - fix: the new verdict is right where the old was wrong.
  - golden row: the fix with a human answer, in the fixture.
  - randomness: the row flipped back on a re-run.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| disagreement | re-run | verdict flips back | randomness | no action | S11 |
| disagreement | person reads it | new prompt wrong | break | back to the prompt | S11 |
| disagreement | person reads it | new prompt right | fix | needs a human answer | S11 |
| fix | person labels and moves it | none | golden row | scored against the human answer under check 1b; bar unchanged | S11 |

### L5 · LLM judge trust
- States:
  - unvalidated: the judge exists but has not been compared with human labels.
  - measured: TPR and TNR are known.
  - trusted: both rates reach targets chosen from error costs.
  - stale: the judge's model changed since validation.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| unvalidated | person labels ≥ 50 passes and ≥ 50 fails; judge grades them | none | measured | TPR and TNR computed | S1, S11 |
| measured | review | rates below target | unvalidated | rubric rewritten | S11 |
| measured | review | rates at target | trusted | judge used as a scorer | S11 |
| trusted | judge model change | none | stale | must be re-measured | S11 |
| stale | re-validation | none | measured | new rates | S11 |

### L6 · Guard mode (measure before enforcing)
- States:
  - log: the guard writes the refusal it would have made and lets the item through.
  - enforce: the guard refuses the item.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| log | one-line change in `GUARD_MODES` | `overheard-guard-rates.ts` shows the rate under about 15 percent | enforce | items are refused | X29 |

### L7 · Gate check result
- States:
  - NOT CHECKED: the check had no rows to measure.
  - PASS: the rate is at or above the bar.
  - FAIL: the rate is below the bar.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| (computed) | rate is null | empty denominator | NOT CHECKED | printed | X7 |
| (computed) | rate ≥ bar | none | PASS | printed | X7 |
| (computed) | rate < bar | none | FAIL | printed; exit code unchanged | X7 |

## Worked examples

### E1 · One grader reply (made up)
- Values: made up.
- Input: learner answer "Je mange un pomme." for key "Je mange une pomme.".
- Reply: `{ "correct": false, "marks": [ { "word": "un", "kind": "form" } ], "why": "Pomme is a feminine noun." }` [S11]
- `correct` is the verdict; `marks` lists the wrong word; `kind: "form"` means right word, wrong form. [S11]
- The real reply has a few more fields, which no check uses. [S11]

### E2 · Three fixture rows (real)
- Values: real, `judge-gate-fixture.ts:28, 42, 51` (X10).
- Row 28: key "J'ai très faim.", answer "J'ai vraiment faim.", expected right, no marked words, note "paraphrase: synonym adverb". Check 1b passes if the new verdict is right; check 1c fails if it is wrong.
- Row 42: key "Je mange une pomme.", answer "Je mange un pomme.", expected wrong, marked "un", note "article error".
- Row 51: key "Je ne veux pas de café.", answer "Je veux du café.", expected wrong, marked "veux" and "du", note "negation lost".
- A JUnit `assertTrue(reply.correct)` on row 28 might pass today and fail tomorrow with the same code (P1, P2, P3). [S11]
- The short tested version quotes only rows 28 and 51. [S12]
- An earlier draft reformatted these rows and dropped `variants: []` and `markedWords: []`; the fact-check made it quote the lines exactly. [testing]

### E3 · An LLM judge for check 3 (made up)
- Values: made up. [S11]
- Rubric: "You get a learner's sentence, the answer key and one marked word. PASS if the marked word is itself wrong (wrong form, wrong word, wrong place). FAIL if the word is correct and the error is elsewhere, or there is no error. Reply with JSON: {"verdict": "PASS" | "FAIL", "reason": "..."}"
- Input: "Je mange un pomme.", marked word "mange".
- Judge reply: `{"verdict": "FAIL", "reason": "mange is correct; the error is the article un."}`
- This judge would need F6 before use.

### E4 · Standard error at 200 and 40 cases
- Values: computed from the formula in S11.
- 200 cases at p = 0.95: SE = √(0.95 × 0.05 / 200) ≈ 0.0154; 2 × SE ≈ 0.031, about 3 points. [S11]
- 40 cases at p = 0.95: SE = √(0.95 × 0.05 / 40) ≈ 0.0345; 2 × SE ≈ 0.069, about 7 points. [S11]
- At 40 cases one failure moves the rate 1/40 = 2.5 points. [S11]
- Outcome: 94% against 96% on 200 cases does not show that one prompt is better. [S11]

### E5 · pass@3 and pass^3 at 75% (made up)
- Values: made up; runs assumed independent. [S11]
- Single-run pass rate 0.75, k = 3.
- pass@3 = 1 − 0.25³ = 1 − 0.015625 = 0.984 ≈ 98%.
- pass^3 = 0.75³ = 0.421875 ≈ 42%. (The web catalogue gives the same 42% example.) [S9]
- Outcome: report pass^3 for the grader, because each learner gets one attempt. [S11]

### E6 · Why a single-run bar cannot be reused for pass^3
- Values: computed. [S11]
- A case that passes 95% of single runs passes all three runs 0.95³ ≈ 0.857, about 86% of the time.
- Outcome: a pass^3 bar must be set anew from a measured run.

### E7 · A bar from the cost of an error
- Values: made-up policy. [S11]
- "A learner may see at most one wrong grade in 20 answers" → 19/20 = 95% bar.

### E8 · Gate call count
- Values: real limits from X1, X7, X10; arithmetic from S11.
- Up to 200 real rows + 36 fixture rows = 236 rows.
- 2 calls per row (old and new prompt) = up to 472 calls, "about 470" per run, each paid. [S11]
- Max tokens: 256 for the old prompt, 600 for the arc prompt. [X5]

### E9 · Precision check transcripts (real)
- Values: real, `scenario-judge-precision-check.mts:51-69` (X14).
- Negative: "Hi! Are you free this weekend?" … "Can we move our meetup from Friday to Saturday instead?" … "Let's meet at the park at three o'clock, is that okay?" … "Great, see you on Saturday!" → Everyday Transactions must be REJECTED.
- Positive: "Hello, how much is this bottle of water?" … "I would like to buy two of them, please." … "Here is a ten euro note. Can I have the receipt, please?" → Everyday Transactions must be ACCEPTED.
- The reschedule transcript topically overlaps Everyday Transactions because both settle a place/time and a quantity. [X14]
- Outcome: exit 0 only when both outcomes hold (F4.9).

### E10 · Minimal Java eval (sketch, not Lomem code)
- Values: the code is a sketch; `grader` is your existing service that calls the model and parses the JSON reply into a `Verdict` record; `loadCsv` is any CSV reader. [S11]
- CSV columns: `answer,key,expectedRight,note`. [S11]
```java
record Case(String answer, String key, boolean expectedRight, String note) {}
List<Case> cases = loadCsv("golden.csv");
int right = 0, fast = 0;
Map<String, Integer> failsByNote = new TreeMap<>();
for (Case c : cases) {
    long start = System.currentTimeMillis();
    Verdict v = grader.grade(c.key(), c.answer());      // real prompt, real model
    if (System.currentTimeMillis() - start <= 2500) fast++;
    if (v.correct() == c.expectedRight()) right++;
    else {
        failsByNote.merge(c.note(), 1, Integer::sum);
        System.out.println("FAIL [" + c.note() + "] " + c.answer());
    }
}
double rightRate = (double) right / cases.size(), fastRate = (double) fast / cases.size();
System.out.printf("verdict %.1f%% (bar 95%%), speed %.1f%% (bar 95%%), fails %s%n",
        rightRate * 100, fastRate * 100, failsByNote);
System.exit(rightRate >= 0.95 && fastRate >= 0.95 ? 0 : 1);
```
- The short tested version prints only `failsByNote` and has no per-failure line. [S12]
- The sketch keeps speed and correctness as two rates with two bars, but its exit code combines them; readers copied that and lost the per-check diagnosis. [testing]
- The sketch's `grade(key, answer)` passes no source sentence; a reader asked whether the CSV needs it. [testing] (The Lomem gate passes a source or "(the meaning of) key", X4.)

### E11 · Gate stats unit tests (real)
- Values: real, `judge-gate-stats.test.ts` (X12).
- agreement([T,T,F,F,T,F], [T,F,F,T,T,F]) = 4/6; agreement of a list with itself = 1; of two empty lists = null.
- placeableShare of {named 0}, {named 2, placed 1}, {named 1, placed 0}, {named 3, placed 3} = 3/4.
- withinMs(100..2000 in steps of 100, 2500) = 1; adding 4000 gives 20/21.
- percentile(100..2000, 95) = 1900; percentile(…, 100) = 2000.
- stratify(["a1","a2","a3","b1","c1","c2"], 4, first letter) = ["a1","b1","c1","a2"].

### E12 · Scenario eval budgets (real)
- Admin eval: runs default 5, clamped 1 to 10 (X25).
- Adversarial probes: 2 per run, opportunities = 2 × objectives (X24).
- Probe max turns: `min(maxTurns, SCENARIO_EVAL_PROBE_MAX_TURNS ?? 10)` (X24).
- Conversation max turns: `max(12, objectives × 2 + 4)` (X24); for 3 objectives that is max(12, 10) = 12 (computed).
- Airport family: a1 and a2 get 3 runs, b1 and b2 get 2 runs, Spanish only (X26).

### E13 · Check 2 denominator
- Values: from the code (X7, X11).
- A right reply has no named marks and passes check 2.
- A wrong reply with 2 named marks of which 1 lands passes.
- A wrong reply with 1 named mark that does not land fails.
- The bar is 95% of all replies (real and fixture), not of marks. [testing]

## Variants and options

- Minimal version:
  - Read 30 to 50 real inputs yourself and write the expected verdict and a note next to each, in a CSV. [S11]
  - Leave out answers that equal the key if your code never sends those to the model. [S11]
  - Loop them through your real prompt and model, keep speed apart from correctness, count failures per note and set an exit code. [S11]
  - Run it before every prompt or model change, and read every printed failure. [S11]
  - The web catalogue's minimal version: read about 30 to 100 real traces, build a failure taxonomy, write binary checks (code assertions first, LLM-as-judge only for subjective criteria), run 50 to 200 cases in CI on every prompt or model change. [S9]
- Mature version:
  - More labelled real rows; golden datasets drawn from production traces. [S11, S9]
  - LLM judges validated against human labels (TPR and TNR), one judge per failure mode. [S11, S9]
  - Each case run k times, reported as pass@k or pass^k. [S11, S9]
  - Results stored per prompt and model version. [S11]
  - The regression set as a required pipeline step; capability evals tracked apart. [S11, S9]
  - Online evals on sampled production replies with an alert when failures rise. [S11, S9]
  - Error analysis repeated every 2 to 4 weeks. [S9]
- Options and trade-offs:

| id | option | when to choose | cost / risk |
|---|---|---|---|
| V1 | Exact-match scorer | output is a label, number or enum | none beyond the call; useless for free text |
| V2 | Code-assertion scorer | a property code can test (JSON valid, word present, time limit) | can pass wrong content that has the right shape |
| V3 | LLM-as-judge scorer | only a reader can tell | extra paid calls; the judge can be wrong and must be validated |
| V4 | Person as scorer | judging is subtle and a judge is not validated yet | slow; does not scale; Lomem's check 3 |
| V5 | Real rows scored against the old version | measure change on everyday traffic | says nothing about correctness; a fix counts as a disagreement |
| V6 | Golden rows with human labels | measure correctness | labelling effort; may miss kinds real traffic has |
| V7 | Single run per case | cheap, first version | hides run-to-run randomness |
| V8 | pass@k | something checks each attempt and keeps a good one | overstates quality when users get one attempt |
| V9 | pass^k | every user gets one attempt | k times the cost; lower scores; bar must be set anew |
| V10 | Regression set in CI on every change | team accepts model-call cost per build | money and network per build; flaky at small n |
| V11 | Eval scripts run by hand (Lomem) | runs cost money and need the network | relies on people remembering to run them |
| V12 | Gate decided by a person (Lomem) | some checks are scored by hand | no exit code enforces the bar |
| V13 | Simulated learner (LLM) | whole conversations must be tested | the simulator's behaviour adds its own variance |
| V14 | Adversarial probes paired with pass rate | the grader could over-accept | extra calls per run |
| V15 | Shadow or log mode before enforcing | a new judge or guard affects users | delays the benefit until measured |
| V16 | Binary pass/fail | almost always | loses nuance that a scale pretends to have |
| V17 | 1-to-10 score | rarely | nobody can say what separates a 6 from a 7; numbers drift |

- Tools and products:

| name | open source or hosted | what it does here | link |
|---|---|---|---|
| promptfoo | open source, CI-friendly | runs prompts over test cases with assertions | https://github.com/promptfoo/promptfoo |
| Braintrust | hosted | eval datasets, scorers and experiment comparison | https://www.braintrust.dev/docs |
| LangSmith | hosted | tracing, datasets and evaluations | https://docs.smith.langchain.com/ |
| Langfuse | open source | tracing, datasets and evaluations | https://github.com/langfuse/langfuse |
| Arize Phoenix | open source | tracing and evaluations | https://github.com/Arize-ai/phoenix |
| Spring AI evaluation | open source | evaluation support for Spring Boot apps | https://docs.spring.io/spring-ai/reference/api/testing.html |

(The catalogue lists these tools for evals; the "what it does here" column is a one-line summary, unverified per tool. Newcomer readers did not know promptfoo or Spring AI evaluation support. [S9, testing])

## Facts and numbers

| id | fact | value | source id | verified |
|---|---|---|---|---|
| N1 | Temperature range in Anthropic's Messages API | 0.0 to 1.0 | S3 | yes |
| N2 | Temperature that is still "not fully deterministic" | 0.0 | S3 | yes |
| N3 | Translation grader temperature (production and gate) | 0.3 | X5, X19 | yes |
| N4 | Max tokens, old `card` prompt | 256 | X5, X19 | yes |
| N5 | Max tokens, `arc` prompt | 600 | X5, X19 | yes |
| N6 | Real rows in the gate | up to 200 | X7 | yes |
| N7 | Fixture rows | 36 | X10 | yes |
| N8 | Fixture paraphrase rows (must be right) | 15 of 36 | X10 | yes |
| N9 | Fixture rows expected wrong | 21 of 36 | X10 | yes |
| N10 | Fixture rows by language | fr 18, es 7, de 7, it 3, pt 1 | X10 | yes |
| N11 | Fixture rows with a source sentence | 4 | X10 | yes |
| N12 | Model calls per gate run | up to about 470 | S11 | yes (236 × 2 = 472) |
| N13 | Check 1a bar (real rows, old vs new) | 95% | X1, X7 | yes |
| N14 | Check 1b bar (fixture rows) | 95% | X1, X7 | yes |
| N15 | Check 1c bar (paraphrase misses) | 0 allowed | X1, X7 | yes |
| N16 | Check 2 bar (marks land) | 95% of all replies | X7, X11 | yes |
| N17 | Check 3 bar (marks are right, by hand) | 90% of marked words | X1 | yes |
| N18 | Check 3 minimum | at least 20 real rows hand-checked | X7, S11 | yes (printed text only) |
| N19 | Check 4 bar (speed) | 95% of arc replies within 2500 ms | X1 | yes |
| N20 | Gate worker pool | 3 | X1 | yes |
| N21 | Fidelity eval concurrency | default 4, clamped 1 to 8 | X22 | yes |
| N22 | Fidelity eval samples per cell | default 5, clamped 1 to 20 | X22 | yes |
| N23 | Fidelity eval calls | about cells × samples × 2, more with up to 3 generator retries | X22 | yes |
| N24 | Fidelity judge attempts per item | 2 | X22 | yes |
| N25 | Fidelity judge temperature and max tokens | 0.2, 800 | X22 | yes |
| N26 | Fidelity dimensions | 5 | X22 | yes |
| N27 | Simulated learner temperature | 0.7 | X21 | yes |
| N28 | Simulated learner retries | up to 4 attempts | X21 | yes |
| N29 | Admin eval runs | default 5, clamped 1 to 10 | X25 | yes |
| N30 | Adversarial probes per scenario eval | 2 | X24 | yes |
| N31 | Probe max turns default | 10 | X24 | yes |
| N32 | Scenario eval max turns | max(12, objectives × 2 + 4) | X24 | yes |
| N33 | Eval runs listed per scenario | last 20 | X23 | yes |
| N34 | Airport eval budget | 3 runs a1/a2, 2 runs b1/b2, Spanish only | X26 | yes |
| N35 | Guard switch-on threshold | refusal rate under about 15 percent | X29 | yes |
| N36 | Share of objectives that are spec-null (precision-check comment) | 60% | X14 | unverified |
| N37 | Error analysis sample | 30 to 100 real outputs | S11, S1, S9 | yes |
| N38 | Minimal CSV size | 30 to 50 real inputs | S11 | yes |
| N39 | Catalogue minimal CI run | 50 to 200 cases | S9 | unverified (Hamel's CI part unread) |
| N40 | Purpose-built golden set size | often 100 rows or more | S1 | yes |
| N41 | Judge validation labels | at least 50 passes and 50 fails | S1 | yes |
| N42 | Error analysis repeat interval (mature) | every 2 to 4 weeks | S9 | unverified |
| N43 | Regression set pass rate | at or near 100% | S11, S2 | yes |
| N44 | Capability eval starting rate (example) | 40% | S11 | made up example |
| N45 | Two standard errors at 200 cases, 95% | about 3 points | S11 | yes (computed) |
| N46 | Two standard errors at 40 cases, 95% | about 7 points | S11 | yes (computed) |
| N47 | Coverage of two standard errors | about 95% of the time | S11 | yes |
| N48 | One failure at 40 cases | 2.5 points | S11 | yes |
| N49 | pass@3 at 75% per run | ≈ 98% | S11 | made up example |
| N50 | pass^3 at 75% per run | ≈ 42% | S11, S9 | made up example |
| N51 | pass^3 at 95% per run | ≈ 86% | S11 | yes (computed) |
| N52 | Example bar from error cost | 1 wrong in 20 = 95% | S11 | made up example |
| N53 | Load-test analogy threshold | p95 latency under 300 ms | S11 | made up example |
| N54 | Mark kinds | 6 (wrong, extra, form, accent, order, missing) | X20 | yes |
| N55 | Focus areas | 16 | X32 | yes |
| N56 | `why` length | one sentence of 15 words or fewer | X20 | yes |
| N57 | `whyGivesAnswer` minimum key length | 3 key words | X34 | yes |
| N58 | `TD_JUDGE_MARKS` today | false | X16 | yes |
| N59 | Fowler catalogue patterns | 9, Evals is the third | S6 | yes |
| N60 | Fowler catalogue dates | 28 Jan to 25 Feb 2025 | S6 | yes |
| N61 | Anthropic "Demystifying evals for AI agents" date | 9 Jan 2026 | S2 | yes |
| N62 | Husain and Shankar FAQ last update | Sep 2026 | S1 | yes |
| N63 | Scenario judge "Judge-call ceiling" | 2 per run goal + 8 (quest: 4 per goal + 8), never below the per-session cap setting | X28 | yes |
| N64 | Production `why`/score band, balanced rubric | correct 95-100, near-miss 60-85, incorrect 0-50 | X20 | yes |
| N65 | Lomem code read on | 2026-10-15, main at 8e3f5d5db | X1 | yes |
| N66 | Checkpoint borderline log band | score 50 to 85 | X33 | yes |
| N67 | Checkpoint extra calls on a self-contradicting reply | at most 1 | X33 | yes |
| N68 | Newcomer reader scores, round 1 (clarity, self-contained, examples) | senior 7, 6, 7; skimmer 6, 5, 7; both failed | testing | yes |
| N69 | Newcomer reader scores, round 2 | senior 8, 7, 9; skimmer 7, 7, 8; both failed | testing | yes |
| N70 | Newcomer reader scores, round 3 | senior 8, 7, 9; skimmer 7, 7, 8; both failed | testing | yes |


## Code in Lomem

### X1 · Gate header, usage context and bars
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/translation-judge-gate.ts:1-21,48-55` (Lomem main branch as read on 2026-10-15)
- Implements: C12, C10, C14, C46, C48, K1, F1.1, N13-N20
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
 *
 * Uses the real LLM gateway under a system usage context; keys come from the
 * environment. A dev harness, not a CI test (needs the network, so the Bash
 * sandbox must be off). Run from apps/tunatutor/backend, with the local database
 * filled by `tunatutor pull-staging-data`:
 *
 *   node --env-file=.env --import tsx scripts/translation-judge-gate.ts
 *
 * Optional env: GATE_JSON_OUT=<file> writes every reply as JSON.
 */
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
  - The header lists the four checks and their bars; check 3 is read by hand.
  - `LEVEL_BAR.wrong` (0.9) is declared but no code reads it, because check 3 is a person's count.
  - The system usage context names who pays for the calls: no learner (gateway block).
  - "A dev harness, not a CI test": it needs the network and staging data.

### X2 · Frozen copy of the old (card) prompt
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/translation-judge-gate.ts:71-77,85-89,102-110` (Lomem main branch as read on 2026-10-15)
- Implements: C3, K5, F1.7
```ts
/** FROZEN copy of the pre-TR2 `buildJudgeTranslationPrompt` (Drill Me's `card` judge). Do not edit. */
function oldPrompt(a: { nativeName: string; targetName: string; source: string; key: string; variants: string[]; answer: string }): string {
  const variantBlock = a.variants.length
    ? `Also acceptable (equally-valid phrasings):\n${a.variants.map((v, i) => `  variant ${i + 1}: "${v}"`).join("\n")}`
    : "";
  const varietyClause = varietyPromptClause(a.targetName);
  return `You grade a translation from ${a.nativeName} to ${a.targetName}.${varietyClause ? `\n${varietyClause}` : ""}
...
Grading rules (BALANCED):
- A learner answer that matches the canonical OR any variant in meaning (allowing minor punctuation, capitalization, and missing/wrong accents) is correct. Score 95-100. When the only differences are capitalization or accents, still acknowledge the slip in the "feedback" field so the learner knows — just don't lower the score.
- A near-miss with one small error (tense, article, single-letter typo) is partially correct. Score 60-85.
- A wrong meaning, missing key words, or broken grammar is incorrect. Score 0-50.

...
Return JSON — no prose, no markdown fences:

{
  "score": 0-100 integer,
  "correct": boolean,
  "matchedVariant": "canonical" | "variant_1" | "variant_2" | "variant_3" | null,
  "feedback": "1-2 sentences in ${a.nativeName}"
}`;
}
```
- Notes:
  - The reference version is frozen inside the script so later edits to the live `card` prompt cannot move the baseline.
  - Today's live `card` prompt (X20's file) also carries the 'you' rule; the frozen copy does not, so the gate compares against the pre-TR2 card, not today's card.
  - The old reply has only score, correct, matchedVariant and feedback: no marks.

### X3 · Loading real rows from the local copy of staging
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/translation-judge-gate.ts:114-147` (Lomem main branch as read on 2026-10-15)
- Implements: C14, F1.3, F1.3a, F1.3b
```ts
async function realRows(): Promise<GateRow[]> {
  const attempts = await prisma.drillAttempt.findMany({
    where: { arc: { mode: "translation" }, userAnswer: { not: null }, score: { not: null } },
    select: {
      userAnswer: true,
      expectedTranslation: true,
      acceptedVariants: true,
      targetLine: true,
      arc: { select: { nativeLanguage: true, targetLanguage: true } },
    },
    orderBy: { createdAt: "asc" },
  });
  const rows: GateRow[] = [];
  for (const a of attempts) {
    const answer = (a.userAnswer ?? "").trim();
    if (answer === "") continue;
    const n = normalizeTypedAnswer(answer);
    if ([a.expectedTranslation, ...a.acceptedVariants].some((k) => normalizeTypedAnswer(k) === n)) continue;
    rows.push({
      origin: "real",
      language: languageNameToShortCode(a.arc.targetLanguage) ?? a.arc.targetLanguage,
      nativeName: a.arc.nativeLanguage,
      targetName: a.arc.targetLanguage,
      source: a.targetLine,
      key: a.expectedTranslation,
      variants: a.acceptedVariants,
      answer,
      expected: null,
      markedWords: [],
      note: "",
    });
  }
  return rows;
}
```
- Notes:
  - `score: { not: null }` selects answers that were already judged (the "AI-judged answers").
  - Exact matches are removed by normalised comparison with the key and every variant, because those never reach the model.
  - Real rows get `expected: null`: no human answer, so the old verdict is the reference.

### X4 · Loading fixture rows
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/translation-judge-gate.ts:149-164` (Lomem main branch as read on 2026-10-15)
- Implements: C15, F1.5
```ts
function fixtureRows(): GateRow[] {
  return JUDGE_GATE_FIXTURE.map((f) => ({
    origin: "fixture",
    language: f.language,
    nativeName: "English",
    targetName: LANGUAGE_NAMES[f.language]!,
    // Most fixture rows have no source sentence; the key's meaning stands in for it.
    source: f.source ?? `(the meaning of) ${f.key}`,
    key: f.key,
    variants: f.variants,
    answer: f.answer,
    expected: f.expected,
    markedWords: f.markedWords,
    note: f.note,
  }));
}
```
- Notes:
  - Fixture rows always use English as the native language.
  - A row without `source` sends "(the meaning of) <key>" as the source sentence.

### X5 · One row: old call, new call, parse, marks
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/translation-judge-gate.ts:196-247` (Lomem main branch as read on 2026-10-15)
- Implements: F1.7-F1.14a, C5, C39, N3-N5
```ts
async function ask(system: string, maxTokens: number): Promise<{ text: string; ms: number }> {
  const t0 = Date.now();
  const text = await callLLM(system, [{ role: "user", content: "Judge now." }], maxTokens, {
    temperature: 0.3,
    json: true,
    usageContext: USAGE,
  });
  return { text, ms: Date.now() - t0 };
}

async function judge(row: GateRow): Promise<Judged> {
  const out: Judged = { row, oldCorrect: null, newCorrect: null, ms: null, named: [], placedWords: [], why: "", ok: false };
  try {
    const oldReply = await ask(oldPrompt(row), 256);
    try {
      out.oldCorrect = Boolean((JSON.parse(oldReply.text) as { correct?: unknown }).correct);
    } catch {
      out.oldCorrect = /"correct"\s*:\s*true/.test(oldReply.text);
    }
    const prompt = buildJudgeTranslationPrompt(
      {
        nativeLanguage: row.nativeName,
        targetLanguage: row.targetName,
        sourceSentence: row.source,
        expectedTranslation: row.key,
        acceptedVariants: row.variants,
        userAnswer: row.answer,
        gradingLeniency: "balanced",
      },
      { variant: "arc" },
    );
    const r = await ask(prompt, 600);
    out.ms = r.ms;
    const parsed = parseJudgeReply(r.text, {
      userAnswer: row.answer,
      expected: row.key,
      variants: row.variants,
      language: row.language,
      marksEnabled: true,
    });
    out.newCorrect = parsed.correct;
    out.why = parsed.why;
    // A right verdict ships with no marks (parseJudgeReply drops them), so only a wrong reply is checked.
    out.named = parsed.correct ? [] : readNamed(r.text);
    const placed = placeNamedMarks(row.answer, out.named, row.language);
    out.placedWords = placed.map((m) => ({ word: row.answer.slice(m.start, m.end) || "(gap)", kind: m.kind }));
    out.ok = true;
  } catch (err) {
    console.error(`  call failed for "${row.answer}":`, err instanceof Error ? err.message : err);
  }
  return out;
}
```
- Notes:
  - Both calls use temperature 0.3 and JSON mode, as production does (X19).
  - Only the arc call is timed; check 4 measures the new prompt's latency.
  - Named marks are read from the raw reply only for a wrong verdict, and placed before any production fallback.
  - Any thrown error leaves `ok: false`; the row is then dropped from every check (see Open questions).

### X6 · Worker pool
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/translation-judge-gate.ts:249-261` (Lomem main branch as read on 2026-10-15)
- Implements: F1.6, N20
```ts
async function runAll(rows: GateRow[]): Promise<Judged[]> {
  const results: Judged[] = new Array<Judged>(rows.length);
  let next = 0;
  const worker = async (): Promise<void> => {
    for (;;) {
      const i = next++;
      if (i >= rows.length) return;
      results[i] = await judge(rows[i]!);
    }
  };
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));
  return results;
}
```
- Notes:
  - Three workers pull the next index from a shared counter; results keep row order.

### X7 · The four checks and the printed report
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/translation-judge-gate.ts:263-335` (Lomem main branch as read on 2026-10-15)
- Implements: F1.15-F1.26, C25, C32, L7
```ts
const pct = (x: number | null): string => (x === null ? "Not checked" : `${(x * 100).toFixed(1)}%`);
const mark = (x: number | null, bar: number): string => (x === null ? "NOT CHECKED" : x >= bar ? "PASS" : "FAIL");

async function main(): Promise<void> {
  await initLLMRegistry();
  const real = stratify(await realRows(), 200, (r) => r.language);
  const fixture = fixtureRows();
  console.log(`\nTranslation judge gate. Real non-exact rows: ${real.length}. Fixture rows: ${fixture.length}.\n`);

  const realJ = (await runAll(real)).filter((j) => j.ok);
  const fixJ = (await runAll(fixture)).filter((j) => j.ok);

  // Check 1
  const agreeReal = agreement(
    realJ.map((j) => j.oldCorrect === true),
    realJ.map((j) => j.newCorrect === true),
  );
  const agreeFix = agreement(
    fixJ.map((j) => j.row.expected === "right"),
    fixJ.map((j) => j.newCorrect === true),
  );
  const paraphraseMisses = fixJ.filter((j) => j.row.note.startsWith("paraphrase") && j.newCorrect !== true);
  console.log("CHECK 1  verdict agreement");
  console.log(`  old vs new on REAL rows (n=${realJ.length}): ${pct(agreeReal)} (bar 95%) ${mark(agreeReal, LEVEL_BAR.agree)}`);
  console.log(`  new vs fixture expected (n=${fixJ.length}): ${pct(agreeFix)} (bar 95%) ${mark(agreeFix, LEVEL_BAR.agree)}`);
  console.log(`  fixture paraphrases wrongly marked wrong: ${paraphraseMisses.length} (must be 0) ${paraphraseMisses.length === 0 ? "PASS" : "FAIL"}`);
  for (const j of paraphraseMisses) console.log(`    - "${j.row.answer}" for "${j.row.key}"`);
  for (const j of fixJ.filter((x) => (x.row.expected === "right") !== (x.newCorrect === true))) {
    console.log(`    fixture disagreement: "${j.row.answer}" (expected ${j.row.expected}, got ${j.newCorrect ? "right" : "wrong"}; ${j.row.note})`);
  }

  // Check 2
  const all = [...realJ, ...fixJ];
  const replies: PlaceableReply[] = all.map((j) => ({ correct: j.newCorrect === true, named: j.named.length, placed: j.placedWords.length }));
  const place = placeableShare(replies);
  console.log("\nCHECK 2  marks placeable on her words");
  console.log(`  (n=${replies.length}): ${pct(place)} (bar 95%) ${mark(place, LEVEL_BAR.place)}`);

  // Check 4
  const lat = all.map((j) => j.ms).filter((m): m is number => m !== null);
  const fast = withinMs(lat, LATENCY_LIMIT_MS);
  console.log("\nCHECK 4  latency of the arc reply");
  console.log(`  within ${LATENCY_LIMIT_MS} ms (n=${lat.length}): ${pct(fast)} (bar 95%) ${mark(fast, LEVEL_BAR.fast)}; p50 ${percentile(lat, 50)} ms, p95 ${percentile(lat, 95)} ms`);

  // Check 3: the hand-check table
  console.log("\nCHECK 3  marked words, to be read BY HAND (bar 90% really wrong)");
  console.log("| # | origin | her sentence | the key | marked word (kind) | the judge's why | fixture hint |");
  console.log("|---|---|---|---|---|---|---|");
  let n = 0;
  let hintHit = 0;
  let hintTotal = 0;
  for (const j of all) {
    if (j.newCorrect === true) continue;
    for (const p of j.placedWords) {
      n++;
      let hint = "";
      if (j.row.origin === "fixture") {
        const inSet = j.row.markedWords.some((w) => normalizeTypedAnswer(w) === normalizeTypedAnswer(p.word));
        hint = inSet ? "expected" : "not in expected set";
        hintTotal++;
        if (inSet) hintHit++;
      }
      console.log(`| ${n} | ${j.row.origin} | ${j.row.answer} | ${j.row.key} | ${p.word} (${p.kind}) | ${j.why.replace(/\|/g, "/")} | ${hint} |`);
    }
  }
  console.log(`\n  fixture marked words inside the expected set: ${hintHit}/${hintTotal} (a hint, not the check)`);
  console.log(`  real non-exact rows judged: ${realJ.length} (need >= 20 hand-checked to turn marks on)`);

  if (process.env.GATE_JSON_OUT) {
    writeFileSync(process.env.GATE_JSON_OUT, JSON.stringify(all.map((j) => ({ ...j, row: { ...j.row } })), null, 2));
  }
  await prisma.$disconnect();
}
```
- Notes:
  - Check 1 prints three separate verdicts: real agreement, fixture agreement, paraphrase misses.
  - Only fixture disagreements are listed; real-row disagreements need `GATE_JSON_OUT`.
  - Check 2 and check 4 run over all replies, real and fixture together.
  - PASS/FAIL is printed only; nothing sets the exit code from the checks.
  - The "need >= 20 hand-checked" line prints the number of real rows judged, not a hand count.

### X8 · Crash exit
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/translation-judge-gate.ts:337-341` (Lomem main branch as read on 2026-10-15)
- Implements: F1.25a
```ts
main().catch(async (err) => {
  console.error(err);
  await prisma.$disconnect().catch(() => undefined);
  process.exit(1);
});
```
- Notes:
  - The only non-zero exit is a crash.

### X9 · Fixture header and row type
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-gate-fixture.ts:1-23` (Lomem main branch as read on 2026-10-15)
- Implements: C15, C16, K2
```ts
/**
 * Hand-made rows for the translation judge gate (TR4). The real AI-judged
 * answers are almost all literal matches or wrong answers, so they cannot
 * carry the gate alone: these rows test paraphrases that must be RIGHT and the
 * error kinds that must be WRONG with the right word marked.
 *
 * No row is an exact match of its key or variants (an exact match never
 * reaches the judge). A `markedWords` entry is a word as it stands in `answer`;
 * for a missing word it is the word before the gap.
 */
export interface JudgeGateFixtureRow {
  /** The practice language's short code. */
  language: "fr" | "es" | "de" | "it" | "pt";
  /** The sentence in her own language; absent = the judge gets the key's meaning described. */
  source?: string;
  key: string;
  variants: string[];
  answer: string;
  expected: "right" | "wrong";
  markedWords: string[];
  /** A note starting "paraphrase" marks a row that must come out right. */
  note: string;
}
```
- Notes:
  - The header gives the reason for hand-made rows: real answers are almost all literal matches or wrong answers.
  - `markedWords` uses the word before the gap for a missing word, matching the arc prompt's rule.

### X10 · All 36 golden rows
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-gate-fixture.ts:25-62` (Lomem main branch as read on 2026-10-15)
- Implements: C15, C16, E2, N7-N11
```ts
export const JUDGE_GATE_FIXTURE: readonly JudgeGateFixtureRow[] = [
  { language: "pt", source: "I am a barista.", key: "Eu sou barista.", variants: [], answer: "Eu sou um barista.", expected: "right", markedWords: [], note: "paraphrase: an article the language allows either way" },
  { language: "fr", key: "Je vais réserver une table.", variants: [], answer: "Je compte réserver une table.", expected: "right", markedWords: [], note: "paraphrase: compter + infinitive for aller + infinitive" },
  { language: "fr", key: "J'ai très faim.", variants: [], answer: "J'ai vraiment faim.", expected: "right", markedWords: [], note: "paraphrase: synonym adverb" },
  { language: "fr", source: "To your boss: Can you help me?", key: "Vous pouvez m'aider ?", variants: [], answer: "Tu peux m'aider ?", expected: "right", markedWords: [], note: "paraphrase: the other 'you' form, whole sentence agrees (any address form counts)" },
  { language: "es", source: "To a friend: Can you help me?", key: "¿Puedes ayudarme?", variants: [], answer: "¿Puede usted ayudarme?", expected: "right", markedWords: [], note: "paraphrase: the other 'you' form, usted with its third-person verb" },
  { language: "de", source: "To your boss: Do you have time?", key: "Haben Sie Zeit?", variants: [], answer: "Hast du Zeit?", expected: "right", markedWords: [], note: "paraphrase: the other 'you' form (du for Sie)" },
  { language: "es", key: "Yo quiero un café.", variants: [], answer: "Quiero un café.", expected: "right", markedWords: [], note: "paraphrase: dropped optional subject pronoun" },
  { language: "es", key: "Nosotros vivimos en Madrid.", variants: [], answer: "Vivimos en Madrid.", expected: "right", markedWords: [], note: "paraphrase: dropped optional subject pronoun" },
  { language: "de", key: "Ich möchte einen Kaffee.", variants: [], answer: "Ich hätte gern einen Kaffee.", expected: "right", markedWords: [], note: "paraphrase: another polite request form" },
  { language: "it", key: "Dov'è la stazione?", variants: [], answer: "Dove si trova la stazione?", expected: "right", markedWords: [], note: "paraphrase: other construction, same meaning" },
  { language: "fr", key: "Où est la gare ?", variants: [], answer: "Où se trouve la gare ?", expected: "right", markedWords: [], note: "paraphrase: other construction, same meaning" },
  { language: "fr", key: "Je suis fatigué.", variants: [], answer: "Je suis fatiguée.", expected: "right", markedWords: [], note: "paraphrase: gender of the speaker is not fixed by the source" },
  { language: "de", key: "Wir fahren morgen nach Berlin.", variants: [], answer: "Morgen fahren wir nach Berlin.", expected: "right", markedWords: [], note: "paraphrase: another word order, same meaning" },
  { language: "es", key: "Compré un coche nuevo.", variants: [], answer: "Compré un auto nuevo.", expected: "right", markedWords: [], note: "paraphrase: regional synonym" },
  { language: "fr", key: "Il fait très chaud.", variants: [], answer: "Il fait vraiment chaud.", expected: "right", markedWords: [], note: "paraphrase: synonym adverb" },
  { language: "fr", key: "Je voulais prendre un rendez-vous.", variants: [], answer: "Je veux prendre un rendez-vous.", expected: "wrong", markedWords: ["veux"], note: "tense slip" },
  { language: "fr", key: "Je mange une pomme.", variants: [], answer: "Je mange un pomme.", expected: "wrong", markedWords: ["un"], note: "article error" },
  { language: "fr", key: "Elle est contente.", variants: [], answer: "Elle est content.", expected: "wrong", markedWords: ["content"], note: "agreement error" },
  { language: "fr", key: "Nous allons au marché.", variants: [], answer: "Ils vont au marché.", expected: "wrong", markedWords: ["Ils", "vont"], note: "person error" },
  { language: "fr", key: "Je ne parle pas français.", variants: [], answer: "Je parle ne pas français.", expected: "wrong", markedWords: ["parle", "ne"], note: "swapped order" },
  { language: "fr", key: "Je vais au cinéma ce soir.", variants: [], answer: "Je vais cinéma ce soir.", expected: "wrong", markedWords: ["vais"], note: "missing word (marked word is the one before the gap)" },
  { language: "fr", key: "Nous habitons à Paris.", variants: [], answer: "Nous habitons à très Paris.", expected: "wrong", markedWords: ["très"], note: "extra word" },
  { language: "fr", key: "Je vais à Paris.", variants: [], answer: "Je vais a Paris.", expected: "wrong", markedWords: ["a"], note: "accent minimal pair (à and a are two words)" },
  { language: "fr", key: "Vous pouvez m'aider ?", variants: [], answer: "Tu pouvez m'aider ?", expected: "wrong", markedWords: ["Tu"], note: "pronoun and verb disagree (tu with the vous verb)" },
  { language: "fr", key: "Je voudrais une table.", variants: [], answer: "Je voudrais une tabel.", expected: "wrong", markedWords: ["tabel"], note: "one-letter typo" },
  { language: "fr", key: "Je ne veux pas de café.", variants: [], answer: "Je veux du café.", expected: "wrong", markedWords: ["veux", "du"], note: "negation lost" },
  { language: "fr", key: "Les enfants jouent dehors.", variants: [], answer: "L'enfant joue dehors.", expected: "wrong", markedWords: ["L'enfant", "joue"], note: "number changed" },
  { language: "es", key: "Ayer comimos pizza.", variants: [], answer: "Hoy comemos pizza.", expected: "wrong", markedWords: ["Hoy", "comemos"], note: "tense and time changed" },
  { language: "es", key: "Las casas son bonitas.", variants: [], answer: "Las casas son bonito.", expected: "wrong", markedWords: ["bonito"], note: "agreement error" },
  { language: "es", key: "Quiero un vaso de agua.", variants: [], answer: "Quiero un vaso de leche.", expected: "wrong", markedWords: ["leche"], note: "wrong word" },
  { language: "de", key: "Ich sehe den Hund.", variants: [], answer: "Ich sehe der Hund.", expected: "wrong", markedWords: ["der"], note: "article (case) error" },
  { language: "de", key: "Er kommt aus Spanien.", variants: [], answer: "Ich komme aus Spanien.", expected: "wrong", markedWords: ["Ich", "komme"], note: "person error" },
  { language: "de", key: "Das Buch liegt auf dem Tisch.", variants: [], answer: "Das Buch liegt auf der Tisch.", expected: "wrong", markedWords: ["der"], note: "article (case) error" },
  { language: "de", key: "Ich habe einen Hund.", variants: [], answer: "Ich habe Hund.", expected: "wrong", markedWords: ["habe"], note: "missing word (marked word is the one before the gap)" },
  { language: "it", key: "Ieri ho mangiato la pizza.", variants: [], answer: "Ieri mangio la pizza.", expected: "wrong", markedWords: ["mangio"], note: "tense slip" },
  { language: "it", key: "Io bevo un caffè al bar.", variants: [], answer: "Io bevo un caffè bar.", expected: "wrong", markedWords: ["caffè"], note: "missing word (marked word is the one before the gap)" },
];
```
- Notes:
  - Lines 26-40 are the 15 paraphrases that must be right; lines 41-61 are the 21 errors that must be wrong.
  - Each note names a kind of case from error analysis (C24).

### X11 · Gate arithmetic as pure functions
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-gate-stats.ts:1-78` (Lomem main branch as read on 2026-10-15)
- Implements: K3, C25, C48, F1.4, F1.20, F1.21
```ts
/**
 * Pure maths for the translation judge gate (`scripts/translation-judge-gate.ts`).
 * The script needs the network; these helpers do not, so they are unit-tested.
 */

/** Share of positions where two verdict lists agree. `null` when there is nothing to compare. */
export function agreement(a: readonly boolean[], b: readonly boolean[]): number | null {
  const n = Math.min(a.length, b.length);
  if (n === 0) return null;
  let same = 0;
  for (let i = 0; i < n; i++) if (a[i] === b[i]) same++;
  return same / n;
}

/** One judge reply, reduced to what mark placement needs. */
export interface PlaceableReply {
  /** The verdict of the reply. */
  correct: boolean;
  /** How many marks the reply named. */
  named: number;
  /** How many of them `placeNamedMarks` put on the learner's own words. */
  placed: number;
}

/**
 * Share of replies whose marks could be placed. A reply that named no mark is
 * placeable (a right answer has none). A reply that named marks is placeable
 * only when at least one landed on her words. `null` for no replies.
 */
export function placeableShare(replies: readonly PlaceableReply[]): number | null {
  if (replies.length === 0) return null;
  const ok = replies.filter((r) => r.named === 0 || r.placed > 0).length;
  return ok / replies.length;
}

/** Share of latencies at or under `limitMs`. `null` for none. */
export function withinMs(latencies: readonly number[], limitMs: number): number | null {
  if (latencies.length === 0) return null;
  return latencies.filter((l) => l <= limitMs).length / latencies.length;
}

/** The p-th percentile (nearest rank, 0 to 100) of the latencies. `null` for none. */
export function percentile(latencies: readonly number[], p: number): number | null {
  if (latencies.length === 0) return null;
  const sorted = [...latencies].sort((x, y) => x - y);
  const rank = Math.max(1, Math.ceil((p / 100) * sorted.length));
  return sorted[Math.min(sorted.length, rank) - 1]!;
}

/**
 * Pick up to `n` rows, spread evenly over the groups `keyOf` gives (round
 * robin, groups in first-seen order, each group in its own order). Fewer rows
 * than asked returns them all.
 */
export function stratify<T>(rows: readonly T[], n: number, keyOf: (row: T) => string): T[] {
  if (n <= 0) return [];
  if (rows.length <= n) return [...rows];
  const groups = new Map<string, T[]>();
  for (const r of rows) {
    const k = keyOf(r);
    const g = groups.get(k);
    if (g) g.push(r);
    else groups.set(k, [r]);
  }
  const lists = [...groups.values()];
  const out: T[] = [];
  for (let i = 0; out.length < n; i++) {
    let took = false;
    for (const l of lists) {
      if (i < l.length && out.length < n) {
        out.push(l[i]!);
        took = true;
      }
    }
    if (!took) break;
  }
  return out;
}
```
- Notes:
  - `placeableShare` passes a reply with no named marks and a reply with at least one placed mark.
  - Every function returns `null` for no data, which the script prints as NOT CHECKED.
  - `percentile` uses nearest rank.
  - `stratify` is round robin over groups in first-seen order.

### X12 · Unit tests for the gate arithmetic
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-gate-stats.test.ts:1-40` (Lomem main branch as read on 2026-10-15)
- Implements: K4, E11, C49
```ts
import test from "node:test";
import assert from "node:assert/strict";
import { agreement, percentile, placeableShare, stratify, withinMs } from "./judge-gate-stats.js";

test("agreement on a hand-made 6-row set", () => {
  const a = [true, true, false, false, true, false];
  const b = [true, false, false, true, true, false];
  assert.equal(agreement(a, b), 4 / 6);
  assert.equal(agreement(a, a), 1);
  assert.equal(agreement([], []), null);
});

test("a zero-mark reply counts as placeable; a reply whose marks all missed does not", () => {
  const share = placeableShare([
    { correct: true, named: 0, placed: 0 },
    { correct: false, named: 2, placed: 1 },
    { correct: false, named: 1, placed: 0 },
    { correct: false, named: 3, placed: 3 },
  ]);
  assert.equal(share, 3 / 4);
  assert.equal(placeableShare([]), null);
});

test("withinMs and the p95 latency", () => {
  const l = Array.from({ length: 20 }, (_, i) => (i + 1) * 100); // 100..2000
  assert.equal(withinMs(l, 2500), 1);
  assert.equal(withinMs([...l, 4000], 2500), 20 / 21);
  assert.equal(percentile(l, 95), 1900);
  assert.equal(percentile(l, 100), 2000);
  assert.equal(percentile([], 95), null);
  assert.equal(withinMs([], 2500), null);
});

test("stratify spreads over groups and returns all when there are fewer rows than asked", () => {
  const rows = ["a1", "a2", "a3", "b1", "c1", "c2"];
  const key = (s: string): string => s[0]!;
  assert.deepEqual(stratify(rows, 4, key), ["a1", "b1", "c1", "a2"]);
  assert.deepEqual(stratify(rows, 10, key), rows);
  assert.deepEqual(stratify(rows, 0, key), []);
});
```
- Notes:
  - These tests need no network and no model; they pin exact values.
  - They run with the backend unit suite, which CI runs only on manual dispatch (X30).

### X13 · Precision check header (regression eval)
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/scenario-judge-precision-check.mts:1-32` (Lomem main branch as read on 2026-10-15)
- Implements: C26, C28, C41, F4, K11
```ts
/**
 * Scenario judge PRECISION check (PR1 — situational-coherence judge fix).
 *
 * A hand-authored, LLM-calling regression that reproduces the PR #227 false-accept
 * and asserts it is now REJECTED. It stages an A2-U02-style objective set (peer
 * invite / everyday transaction / service complaint — the three functions the buggy
 * micro-scene bundled) as an ephemeral Story, feeds two hand-authored transcripts,
 * and runs the REAL production judge (`gradeScenarioObjectives`) against them:
 *
 *   • NEGATIVE — a reschedule-only transcript (a learner rescheduling a meetup, NO
 *     transaction): the "Everyday Transactions" objective MUST be REJECTED.
 *   • POSITIVE — a real shop transaction: "Everyday Transactions" MUST be ACCEPTED.
 *
 * The objectives are UNBOUND (no functionKey / sourceObjectiveId), so the judge's
 * latch decision is exercised in isolation — no XP / curriculum writes, nothing to
 * clean up beyond the ephemeral session + story.
 *
 * This is a DEV-time, LLM-calling harness — NOT a CI unit test (CI never calls the
 * LLM). Needs the Bash sandbox DISABLED for LLM egress. Run from apps/tunatutor/backend:
 *
 *   node --env-file=.env --import tsx scripts/scenario-judge-precision-check.mts
 *
 * Optional env:
 *   PROBE_LANGUAGE=english   the practice language the transcripts are authored in
 *                            (default english — the judge is language-agnostic; the
 *                            reschedule-vs-transaction distinction is semantic, so an
 *                            English harness tests the move-vs-overlap logic cleanly
 *                            without hand-authoring foreign text).
 *   PROBE_USER_ID=1          user the ephemeral session belongs to (default 1 = admin).
 *
 * Exit 0 only when the negative case is REJECTED and the positive case is ACCEPTED.
 */
```
- Notes:
  - "A hand-authored, LLM-calling regression that reproduces the PR #227 false-accept".
  - "CI never calls the LLM" explains why it is run by hand.
  - Exit 0 only when the negative case is rejected and the positive case is accepted.

### X14 · Precision check transcripts and objectives
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/scenario-judge-precision-check.mts:50-69,85-112` (Lomem main branch as read on 2026-10-15)
- Implements: E9, F4.1, F4.2, C28
```ts
/** A learner rescheduling a social meetup — NO transaction, NO complaint. */
const RESCHEDULE_TRANSCRIPT: Turn[] = [
  { role: "user", content: "Hi! Are you free this weekend?" },
  { role: "assistant", content: "Hey! Yes, I think so. What did you have in mind?" },
  { role: "user", content: "Can we move our meetup from Friday to Saturday instead?" },
  { role: "assistant", content: "Saturday works great for me." },
  { role: "user", content: "Let's meet at the park at three o'clock, is that okay?" },
  { role: "assistant", content: "Perfect, the park at three. See you then!" },
  { role: "user", content: "Great, see you on Saturday!" },
];

/** A learner carrying out a real shop transaction — asks price, buys, pays. */
const TRANSACTION_TRANSCRIPT: Turn[] = [
  { role: "user", content: "Hello, how much is this bottle of water?" },
  { role: "assistant", content: "It is two euros." },
  { role: "user", content: "I would like to buy two of them, please." },
  { role: "assistant", content: "Of course, here you go. That's four euros." },
  { role: "user", content: "Here is a ten euro note. Can I have the receipt, please?" },
  { role: "assistant", content: "Certainly, here is your change and your receipt." },
];
...
  // BARE successHints — no "Does NOT count" anti-examples, i.e. the description-only
  // successHint a NULL-spec micro-scene goal produces (ADR-020 → buildMicroSceneGoal
  // folds anti-examples in ONLY when the spec has them; 60% of objectives are
  // spec-null). Each names its defining ACT but carries no explicit exclusions —
  // the faithful shape of a decent-but-unspecced objective. The reschedule
  // transcript topically overlaps "Everyday Transactions" (both settle a place/time
  // and a quantity), which is exactly the overlap PR #227 credited; a move-focused
  // judge must instead require the buy/pay act.
  const objectives: Array<{ id: string; order: number; text: string; successHint: string }> = [
    {
      id: OBJ.invite,
      order: 0,
      text: "Invite a friend to meet up",
      successHint: "The learner arranges to meet a friend socially — settling when and where to get together.",
    },
    {
      id: OBJ.transaction,
      order: 1,
      text: "Everyday Transactions",
      successHint: "The learner buys a product or pays for a service — asking for an item, asking its price, or paying for it.",
    },
    {
      id: OBJ.complaint,
      order: 2,
      text: "Make a service complaint",
      successHint: "The learner tells staff about a problem with a product or service and asks them to put it right.",
    },
  ];
```
- Notes:
  - Bare success hints with no anti-examples reproduce the shape that caused the false accept.
  - The comment's "60% of objectives are spec-null" is a claim in a comment (unverified).

### X15 · Precision check run and verdict
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/scenario-judge-precision-check.mts:121-148,161-180` (Lomem main branch as read on 2026-10-15)
- Implements: F4.2-F4.9a, C41
```ts
async function runCase(storyId: string, transcript: Turn[]): Promise<Set<string>> {
  const uuid = randomUUID();
  const session = await prisma.conversationSession.create({
    data: {
      uuid, userId: USER_ID, storyId, sessionType: "ai_tutor",
      status: "active", targetLanguage: LANGUAGE, nativeLanguage: "english",
      topic: "", startedAt: new Date(), storyObjectiveTarget: 0,
    },
    select: { id: true },
  });
  try {
    for (const turn of transcript) {
      await prisma.conversationMessage.create({ data: { sessionId: session.id, role: turn.role, content: turn.content } });
    }
    // Grade twice — idempotent — so every objective is inside the candidate window.
    await gradeScenarioObjectives({ conversationSessionId: session.id, userId: USER_ID });
    await gradeScenarioObjectives({ conversationSessionId: session.id, userId: USER_ID });
    const runs = await prisma.userStoryRun.findMany({ where: { sessionId: session.id }, select: { id: true } });
    const hits = await prisma.userObjectiveHit.findMany({
      where: { runId: { in: runs.map((r) => r.id) } },
      select: { objectiveId: true },
    });
    // Strip the storyId prefix back to the short objective key.
    return new Set(hits.map((h) => h.objectiveId.replace(`${storyId}:`, "")));
  } finally {
    await prisma.conversationSession.delete({ where: { id: session.id } }).catch(() => undefined);
  }
}
...
    const negative = await runCase(storyId, RESCHEDULE_TRANSCRIPT);
    const positive = await runCase(storyId, TRANSACTION_TRANSCRIPT);

    const negTxnRejected = !negative.has("obj-transaction");
    const negComplaintRejected = !negative.has("obj-complaint");
    const posTxnAccepted = positive.has("obj-transaction");

    console.log("── NEGATIVE (reschedule-only transcript) ──");
    console.log(`  latched: [${[...negative].join(", ") || "none"}]`);
    console.log(`  ${negTxnRejected ? "✅" : "❌"} Everyday Transactions REJECTED (must reject)`);
    console.log(`  ${negComplaintRejected ? "✅" : "⚠️ "} Service complaint rejected (should reject)`);
    console.log("\n── POSITIVE (real shop transaction) ──");
    console.log(`  latched: [${[...positive].join(", ") || "none"}]`);
    console.log(`  ${posTxnAccepted ? "✅" : "❌"} Everyday Transactions ACCEPTED (must accept)`);

    const ok = negTxnRejected && posTxnAccepted;
    console.log(`\n${ok ? "✅ PRECISION CHECK PASSED" : "❌ PRECISION CHECK FAILED"}\n`);
    await cleanup(storyId);
    await prisma.$disconnect();
    process.exit(ok ? 0 : 1);
```
- Notes:
  - The judge runs twice per transcript; it is idempotent.
  - A latched service complaint on the negative case is only a warning.
  - Each case runs once; there is no k-run repetition.

### X16 · The marks flag
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-reply.ts:15-20,107-108,172-174` (Lomem main branch as read on 2026-10-15)
- Implements: C13, K8, L3, F3.5
```ts
/**
 * The switch for the judge's marks. While false, a parsed reply keeps `focus`
 * and `why` and returns `marks: null` (unknown, so the phone draws nothing).
 * Only TR4's PR may flip it to true.
 */
export const TD_JUDGE_MARKS = false;
...
export function parseJudgeReply(raw: string, opts: ParseJudgeReplyOptions): ParsedJudgeReply {
  const marksEnabled = opts.marksEnabled ?? TD_JUDGE_MARKS;
...
  const weakRaw = Array.isArray(parsed.weak) ? parsed.weak : [];
  // `weak` was never measured by the judge gate, so it is held back with the marks.
  const weak = !marksEnabled ? [] : weakRaw.filter((w): w is string => typeof w === "string" && w.trim() !== "").slice(0, 1);
```
- Notes:
  - The flag is a code constant; flipping it is a code change in a reviewed PR.
  - `weak` is held back with the marks because the gate never measured it.
  - Only line 108 reads `TD_JUDGE_MARKS` directly; later lines use `marksEnabled`.

### X17 · Reply parsing: verdict, marks, fallback, why guard
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-reply.ts:87-98,121-170` (Lomem main branch as read on 2026-10-15)
- Implements: C39, F1.11, F1.11a, F3.4, F3.4a
```ts
/**
 * Reads a verdict out of cut-off JSON, but only when `"correct": true|false` is
 * clearly there. Anything else is not a verdict: null.
 */
function salvageBroken(raw: string): { score: number; correct: boolean } | null {
  const c = /"correct"\s*:\s*(true|false)/.exec(raw);
  if (!c) return null;
  const correct = c[1] === "true";
  const m = /"score"\s*:\s*(\d+(?:\.\d+)?)/.exec(raw);
  const score = m ? Math.max(0, Math.min(100, Number(m[1]))) : correct ? 100 : 0;
  return { score, correct };
}
...
  let parsed: Record<string, unknown> | null = null;
  try {
    const p: unknown = JSON.parse(raw);
    if (typeof p === "object" && p !== null && !Array.isArray(p)) parsed = p as Record<string, unknown>;
  } catch {
    parsed = null;
  }

  if (parsed === null) {
    const salvaged = salvageBroken(raw);
    // No clear verdict: throw, so /answer fails, nothing is saved and she can retry.
    if (salvaged === null) throw new ServiceUnavailableError("The judge's reply could not be read");
    const { score, correct } = salvaged;
    return {
      score,
      correct,
      matchedVariant: null,
      marks: !marksEnabled ? null : correct ? [] : fallback(),
      focus: null,
      why: "",
      weak: [],
      contradictory: false,
    };
  }

  // An object with no boolean `correct` is no verdict either.
  if (typeof parsed.correct !== "boolean") throw new ServiceUnavailableError("The judge's reply had no verdict");
  const correct = parsed.correct;
  const named = readNamed(parsed.marks);
  const contradictory = correct
    ? named.some((n) => n.kind === "wrong" || n.kind === "form" || n.kind === "extra")
    : named.length === 0; // a `missing` entry is a mark too

  let marks: AnswerMark[] | null;
  if (!marksEnabled) marks = null;
  else if (correct) marks = [];
  else {
    const placed = placeNamedMarks(opts.userAnswer, named, opts.language);
    marks = placed.length > 0 ? placed : fallback();
  }

  const focusRaw = parsed.focus;
  const focus =
    typeof focusRaw === "string" && (JUDGE_FOCUS_AREAS as readonly string[]).includes(focusRaw)
      ? (focusRaw as JudgeFocus)
      : null;

  let why = typeof parsed.why === "string" ? parsed.why.trim() : "";
  if (why !== "" && whyGivesAnswer(why, opts.expected, opts.variants)) why = "";
  if (why !== "") why = firstSentence(why);
```
- Notes:
  - No clear verdict throws `ServiceUnavailableError`; the gate catches it and drops the row.
  - In production, unplaced marks on a wrong verdict fall back to typed-word marks; the gate's check 2 measures before this fallback.
  - `contradictory` drives the checkpoint recheck call.

### X18 · Pre-pass and the translation grader
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-adapter.ts:11-43,55-84` (Lomem main branch as read on 2026-10-15)
- Implements: C40, K13, F3.1-F3.3a
```ts
/** Verdicts the pre-pass accepts at once in practice. */
const PRACTICE_ACCEPTS: ReadonlySet<TypedVerdict> = new Set(["exact", "variant", "accentForgiven"]);

/**
 * The shared typed judge as a pre-pass (the Translation row of
 * `TYPED_JUDGE_SETTINGS`: `typoRule: "5plus"`, `accentRule: "pairList"`). The
 * phone runs the same function with the same accept list, so the screen and the
 * score agree. It only ever ACCEPTS; everything else goes to the LLM judge.
 *
 * A one-letter typo is accepted here only in a checkpoint (`runMode: "test"`),
 * so the fixed rule "a typo in a long word is right" does not depend on the
 * model's mood. The shared judge's own guards (a base letter, 5+ letters, never
 * word-final, one typo per answer, the different-word pair list) are the
 * safety against a minimal pair. In practice a typo still goes to the LLM.
 * An accent slip on the pair list ("il à" for "il a") is never accepted.
 */
function prePass(input: DrillJudgeInput): { verdict: TypedVerdict; matched: string } | null {
  const language = languageNameToShortCode(input.targetLanguage) ?? input.targetLanguage;
  const result = judgeTypedAnswer({
    typed: input.userAnswer,
    expected: input.expectedTranslation,
    variants: input.acceptedVariants,
    traps: [],
    settings: TYPED_JUDGE_SETTINGS.translation,
    leniency: input.gradingLeniency,
    language,
  });
  const accepts =
    PRACTICE_ACCEPTS.has(result.verdict) ||
    (result.verdict === "typo" && input.runMode === "test" && CHECKPOINT_PREPASS_ACCEPTS_TYPO);
  if (!result.correct || !accepts) return null;
  return { verdict: result.verdict, matched: matchedCandidate(input, result.verdict) };
}
...
/**
 * Wraps the TD LLM adapter's `judgeTranslation` as a `DrillJudge`: the shared
 * typed judge as a pre-pass, then the meaning-aware LLM judge. In a checkpoint
 * the prompt carries the fixed rules and one extra call is made only when the
 * raw reply contradicts itself (`judgeCheckpointItem`).
 *
 * A checkpoint's `feedback` is empty: the arc judge's feedback is its `why`
 * ("With nous, use allons."), which names the key, and a checkpoint never shows
 * it. `why` itself is stored and withheld by the mask like the other judge keys.
 */
export function createTranslationDrillJudge(adapter: DrillLLMAdapter): DrillJudge {
  return {
    async judge(input: DrillJudgeInput): Promise<DrillJudgeResult> {
      const pre = prePass(input);
      if (pre !== null) {
        return {
          correct: true,
          score: 100,
          matchedVariant: pre.matched,
          feedback: "",
          typedVerdict: pre.verdict,
        };
      }
      const call = async (recheck: boolean): Promise<DrillJudgeResult> =>
        adapter.judgeTranslation({ ...input, recheck }, { variant: "arc" });
      if (input.runMode === "test") return { ...(await judgeCheckpointItem(input, { call })), feedback: "" };
      return call(false);
    },
  };
}
```
- Notes:
  - The pre-pass only accepts; it never rejects.
  - Exact, variant and accent-forgiven answers get score 100 with no model call.
  - Production always asks the `arc` variant here.

### X19 · Production call settings for the grader
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/llm-adapter.ts:134,246-269` (Lomem main branch as read on 2026-10-15)
- Implements: C5, N3-N5, F3.3
```ts
const JUDGE_MAX_TOKENS: Record<JudgePromptVariant, number> = { card: 256, arc: 600 };
...
    async judgeTranslation(args: {
      usage: LLMUserUsageContext;
      nativeLanguage: string;
      targetLanguage: string;
      sourceSentence: string;
      expectedTranslation: string;
      acceptedVariants: readonly string[];
      userAnswer: string;
      gradingLeniency: GradingLeniency;
      generationMeta?: DrillGenerationMeta | null;
      runMode?: RunMode;
      recheck?: boolean;
    }, opts: { variant?: JudgePromptVariant } = {}): Promise<JudgedTranslation> {
      // `card` (Drill Me) is the default and is today's judge, unchanged.
      const variant: JudgePromptVariant = opts.variant ?? "card";
      const system = buildJudgeTranslationPrompt(args, { variant });
      const r = await llm.callLLM({
        system,
        messages: [{ role: "user", content: "Judge now." }],
        temperature: 0.3,
        json: true,
        maxTokens: JUDGE_MAX_TOKENS[variant],
        usage: args.usage,
      });
```
- Notes:
  - Same temperature (0.3), JSON mode and token budgets as the gate's `ask` (X5).
  - Production passes a user usage context; the gate passes a system usage context.

### X20 · Arc prompt variants and the marks contract
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-translation-prompt.ts:7-12,30-41,119-139` (Lomem main branch as read on 2026-10-15)
- Implements: C3, C22, C39, K6
```ts
/**
 * Which judge asks. `arc` is the Translation arc's tutor judge (marks, focus,
 * why). `card` is Drill Me's judge and stays exactly as it was: it shows the
 * judge's `feedback` to the learner.
 */
export type JudgePromptVariant = "arc" | "card";
...
function buildRubricBlock(leniency: GradingLeniency): string {
  switch (leniency) {
    case "strict":
      return `Grading rules (STRICT):
- A learner answer that matches the canonical OR any variant in meaning (allowing minor punctuation / capitalization differences) is correct. Score 95-100.
- A near-miss with one small error (tense, article, accent, typo) is partially correct. Score 60-85 with a clear "correct" field.
- A wrong meaning, missing key words, or broken grammar is incorrect. Score 0-50.`;
    case "balanced":
      return `Grading rules (BALANCED):
- A learner answer that matches the canonical OR any variant in meaning (allowing minor punctuation, capitalization, and missing/wrong accents) is correct. Score 95-100. When the only differences are capitalization or accents, still acknowledge the slip in the "feedback" field so the learner knows — just don't lower the score.
- A near-miss with one small error (tense, article, single-letter typo) is partially correct. Score 60-85.
- A wrong meaning, missing key words, or broken grammar is incorrect. Score 0-50.`;
...
Tutor fields. You mark the learner's own words. You never write the answer for her.
- "marks": one entry per ERROR THAT COSTS, as { "word": ..., "kind": ... }. Judge the learner against the SOURCE sentence, not the canonical's exact words. Before you mark a word as extra or missing, ask whether the source asks for it and a native speaker would find the answer wrong. If the source says "I am a barista" and ${a.targetLanguage} allows the article either way, an answer with the article is correct: set "correct" to true and "marks" to [].
  - "word" is the word EXACTLY as the learner wrote it (one word, same spelling). For kind "missing", "word" is the learner's word BEFORE the gap, or "" when the gap is at the very start.
  - "kind" is one of: wrong (a word that is not right), extra (a word to delete), form (right word, wrong form), accent (right letters, wrong accent), order (a word in the wrong place), missing (a word is absent).
  - Leave these UNMARKED because they cost nothing: punctuation, capital letters, hyphen or apostrophe spacing, a style choice, and an accent slip when the grading is balanced or relaxed (unless two different words differ only by that accent, like "a" and "à").
  - A right answer has "marks": [].
- "focus": one of ${areas}. Pick the area of the error that changes the sentence most; the topic of the lesson only breaks a tie. Use null when the answer is right.
- "why": ONE sentence of 15 words or fewer, in ${a.nativeLanguage}. Name the rule. You may name one or two words. NEVER write the whole answer, and never write "the correct answer is". When the answer is right, "why" is a register or style note, or "".
- "weak": at most one ${a.targetLanguage} word (its dictionary form) that the learner replaced or put in the wrong form. [] when none.

Return JSON — no prose, no markdown fences:

{
  "score": 0-100 integer,
  "correct": boolean,
  "matchedVariant": "canonical" | "variant_1" | "variant_2" | "variant_3" | null,
  "marks": [ { "word": string, "kind": "wrong" | "extra" | "form" | "accent" | "order" | "missing" } ],
  "focus": ${areas.split(" | ").map((x) => `"${x}"`).join(" | ")} | null,
  "why": "one sentence in ${a.nativeLanguage}",
  "weak": [ string ]
}`;
```
- Notes:
  - The rubric block changes with strictness; the gate always uses balanced.
  - The six mark kinds and the `why` limit are defined in the prompt text.

### X21 · Scenario text eval: simulated learner and report
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/scenario-text-eval.mts:1-36,228-236,255-271,486-497` (Lomem main branch as read on 2026-10-15)
- Implements: C44, C42, F11, K14
```ts
/**
 * Scenario text-eval harness — Tutor Scenarios (tutor-stories) Step 4.5.
 *
 * Drives the REAL production tutor path with NO speech engine: a simulated
 * A1 learner (LLM) converses with the tutor over the session REST API + the
 * audio-stream WebSocket using TEXT turns (`ai_tutor_text_input`), and the
 * production out-of-band judge (on the job queue) marks objectives. It reports a
 * per-scenario pass-rate.
 *
 * This is the cheap, audio-free validation the spec defers to Phase 2 (§8),
 * pulled forward because the objective loop (student utterance → judge →
 * UserObjectiveHit) is independent of TTS/STT. It exercises the real route +
 * persistence + job-queue enqueue, so a green run means the judge, the seeded
 * content, and the tutor's steering all work end-to-end.
 *
 * Requires a running backend (`tunatutor up`). Run from apps/tunatutor/backend:
 *
 *   BACKEND_URL=http://localhost:<backend-port> \
 *     node --env-file=.env --import tsx scripts/scenario-text-eval.mts
 *
 * Optional env:
 *   STORY_IDS=story-train-a1,story-supermarket-a1   (default: all seeded A1 stories)
 *   RUNS=2                                           (runs per scenario; default 1)
 *   MAX_TURNS=16                                     (override per-scenario turn cap)
 *   ADVERSARIAL=1                                    (run a non-cooperative learner; reports a false-positive rate instead of pass-rate)
 *
 * Get the backend port for this worktree with `lomem ports`.
 *
 * Quests (`story-quest-*`, isQuest) run with four differences, all gated on
 * isQuest so every other story's run is unchanged: the bot account gets the
 * `tester` role (quests are hidden from everyone else), the learner plays at the
 * story's own CEFR level, it works only on the CURRENT place's goals (the same
 * leg scoping the admin eval uses, eval-leg-scope.ts) and hears each new
 * villager's opening line, and the report adds the places reached and the
 * clues found.
 */
...
  const system = ADVERSARIAL
    ? [
        `You are STRESS-TESTING a language tutor's objective judge. You are the human side of this scene:`,
        `"${sceneText}". Speak only ${language}.`,
        `Your job is to NEVER actually complete the listed goals, while still talking. Each turn do ONE of:`,
        `  (a) repeat/echo the tutor's last line almost verbatim,`,
        `  (b) say a 1-2 word fragment ("euh… fromage ?"),`,
        `  (c) say something off-topic or unrelated to the goals.`,
        `Do NOT produce a clean, correct request that satisfies a goal. Reply as JSON: {"utterance":"<one short ${language} line>"}.`,
...
  // The student runs in THIS process and occasionally hits a transient Gemini
  // "fetch failed" on both providers — retry a few times so a blip doesn't abort
  // the whole scenario and discard progress.
  let raw = "";
  for (let attempt = 1; attempt <= 4; attempt++) {
    try {
      raw = await callLLM(system, seeded, 200, {
        json: true,
        temperature: 0.7,
        // The simulated learner is not a real user: the gateway refuses userId 0.
        usageContext: systemUsageContext(
          "scenario_eval_student",
          "dev eval harness: the simulated learner has no user account",
          "scenario-eval-student",
        ),
      });
      break;
...
  console.log(`Pass-rate: ${passes}/${results.length}\n`);

  if (ADVERSARIAL) {
    const falsePositives = results.reduce((n, r) => n + r.done, 0);
    const opportunities = results.reduce((n, r) => n + r.total, 0);
    console.log(`Adversarial false positives: ${falsePositives}/${opportunities} objective-opportunities latched (target: 0)`);
    await prisma.$disconnect();
    process.exit(falsePositives === 0 ? 0 : 1);
  }

  await prisma.$disconnect();
  process.exit(passes === results.length ? 0 : 1);
```
- Notes:
  - The adversarial learner must never complete a goal; any latch is a false positive.
  - The exit code enforces the result: all pass, or zero false positives.
  - The learner retries a transient failure up to 4 times.

### X22 · Generator fidelity eval
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/curriculum/eval-generator-fidelity.ts:1-66,611-627` (Lomem main branch as read on 2026-10-15)
- Implements: C45, C46, C21, F12, K20
```ts
/**
 * Offline generator-fidelity eval — Curriculum → 10, Phase 4 (Workstream F).
 *
 * A DEVELOPER-RUN DIAGNOSTIC you run and read. It proves that the Phase-1/2
 * authoring on curriculum objectives (the objective `spec`: `verbConcepts`,
 * `tenseForm`, `sceneTypes`, `antiExamples`, `assessmentFocus`, and especially
 * the new Phase-2 `lexicalTargets`) actually REACHES the items the six drill
 * generators + the two Phase-3 recognition generators produce — and surfaces
 * where a generator drifts.
 *
 * What it does, per CEFR level × per generator:
 *   1. Samples objectives that carry a meaningful `spec` from the LOCAL DB
 *      (reading-lane objectives → reading-recognition; listening-lane →
 *      Overheard pinned mode; productive-lane → the five production drills).
 *   2. Calls the REAL in-process generator to produce an item (real `callLLM`,
 *      a NO-OP/empty seed-pool + empty vocab caller so the LLM path is
 *      exercised, NOT the seed/fallback path).
 *   3. LLM-JUDGES that item against its spec on five dimensions — levelFit,
 *      verbWhitelist, lexicalTargets, antiExamples, correctness — skipping a
 *      dimension whose spec field is empty. A hard judge-parse failure is an
 *      "error" bucket, never a silent pass.
 * Then it aggregates a per-generator, per-level DRIFT REPORT (pass-rate per
 * dimension + overall + failure reasons) to stdout, and writes the same report
 * as a timestamped markdown + JSON artifact.
 *
 * READ-ONLY on curriculum data. No CI wiring, no runtime gate, no live
 * regeneration. The ONLY LLM calls are (a) inside the real generator and (b)
 * this judge. It is NOT write-free at the metering layer: calling the real
 * generator means the real `callLLM`, which attributes every call — so a run
 * appends `provider_usage_events` rows (and allowance debits) for the admin
 * user, exactly as the production path would. That is the price of measuring
 * the real path; keep runs on a LOCAL database.
 *
 * ── Conjugation scope decision ──────────────────────────────────────────────
 * The conjugation drill is DELIBERATELY OUT OF SCOPE. It is DETERMINISTIC
 * (word_cache tables, no `spec-to-prompt`), so there is no LLM-fidelity signal
 * to measure — it is skipped with a printed note in the report rather than
 * checked. (The other five drills + the two recognition generators are the
 * spec-consuming LLM surfaces this eval targets.)
 *
 * ── Cost / scope ────────────────────────────────────────────────────────────
 * REAL PAID Gemini/Anthropic calls. Roughly `cells × samples × 2` calls (1
 * generation + 1 judge per sample); the generator may internally retry up to 3×
 * on a malformed item, so the true generation count can be higher. Keep
 * SAMPLES_PER_CELL modest. Always DRY_RUN first to read the estimate.
 *
 * ── Run (from apps/tunatutor/backend) ───────────────────────────────────────────
 *   # Plan + estimated call count, NO LLM calls:
 *   DRY_RUN=1 node --env-file=.env --import tsx scripts/curriculum/eval-generator-fidelity.ts
 *
 *   # Tiny smoke run (one cell, one sample):
 *   SAMPLES_PER_CELL=1 LEVELS=A1 GENERATORS=translation-drill \
 *     node --env-file=.env --import tsx scripts/curriculum/eval-generator-fidelity.ts
 *
 *   # Full run (all present levels × all generators, 5 samples/cell):
 *   node --env-file=.env --import tsx scripts/curriculum/eval-generator-fidelity.ts
 *
 * ── Env knobs ───────────────────────────────────────────────────────────────
 *   SAMPLES_PER_CELL  samples per (generator,level) cell. Default 5, clamped 1..20.
 *   LEVELS            csv of CEFR levels (e.g. A1,A2). Default = all present in DB.
 *   GENERATORS        csv of generator names. Default = all (see GENERATOR list).
 *   NATIVE_LANGUAGE   learner's NATIVE language. Default "english".
 *   TARGET_LANGUAGE   learner's PRACTICE language. Default "spanish".
 *   CONCURRENCY       max parallel (generate+judge) tasks. Default 4, clamped 1..8.
 *   DRY_RUN=1         (or pass --plan) print the plan + estimate and EXIT — no LLM.
 *   REPORT_DIR        directory for the md+json artifact. Default a temp dir.
...
async function judgeItem(
  obj: SampledObjective,
  item: NormalizedItem,
  dims: Dimension[],
): Promise<Partial<Record<Dimension, Verdict>>> {
  const system = buildJudgePrompt(obj, item, dims);
  for (let attempt = 0; attempt < 2; attempt++) {
    const raw = await callLLM(system, [{ role: "user", content: "Judge now." }], 800, {
      temperature: 0.2,
      json: true,
      usageContext: JUDGE_USAGE,
    });
    const parsed = parseJudgeResponse(raw, dims);
    if (parsed) return parsed;
  }
  throw new Error("judge produced unparseable output after 2 attempts");
}
```
- Notes:
  - `DRY_RUN=1` prints the plan and estimate before any spend.
  - A judge that cannot be parsed twice throws; the header says that goes to an "error" bucket, never a silent pass.
  - Real-path calls are metered like production, so runs belong on a local database.
  - The header says "Gemini/Anthropic calls"; the code map found only Gemini and Cerebras providers (Open questions).

### X23 · Eval run repository
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/scenarios/eval-repository.ts:4-15,32-60` (Lomem main branch as read on 2026-10-15)
- Implements: L2, K16, F10.3, F10.14
```ts
type Row = {
  id: string;
  storyId: string;
  status: string;
  requestedRuns: number;
  passRate: number | null;
  avgTurns: number | null;
  resultJson: unknown;
  error: string | null;
  createdAt: Date;
  completedAt: Date | null;
};
...
export async function createEvalRun(
  prisma: PrismaClient,
  params: { storyId: string; requestedRuns: number; createdByUserId: number },
): Promise<string> {
  const r = await prisma.scenarioEvalRun.create({
    data: {
      storyId: params.storyId,
      requestedRuns: params.requestedRuns,
      createdByUserId: params.createdByUserId,
      status: "pending",
    },
    select: { id: true },
  });
  return r.id;
}

export async function getEvalRun(prisma: PrismaClient, id: string): Promise<ScenarioEvalRunDTO | null> {
  const row = await prisma.scenarioEvalRun.findUnique({ where: { id } });
  return row ? toDTO(row as Row) : null;
}

export async function listEvalRuns(prisma: PrismaClient, storyId: string): Promise<ScenarioEvalRunDTO[]> {
  const rows = await prisma.scenarioEvalRun.findMany({
    where: { storyId },
    orderBy: { createdAt: "desc" },
    take: 20,
  });
  return rows.map((r) => toDTO(r as Row));
}
```
- Notes:
  - Each run row stores status, requested runs, pass rate, average turns, result JSON, error and timestamps.
  - A new run starts as "pending"; listing returns the last 20 runs.

### X24 · Scenario eval runner
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/scenario/run-scenario-eval.ts:111-117,276,362-486` (Lomem main branch as read on 2026-10-15)
- Implements: L2, C28, C42, C44, F10.6-F10.13a, K15
```ts
/**
 * Adversarial learner (precision probe): talks in-scene but NEVER cleanly
 * performs any listed move — echoes the tutor, drops 1-2 word fragments, or goes
 * off-topic. Any objective the judge latches from this learner is a FALSE ACCEPT.
 * This is the negative complement of the cooperative sim-learner: pass-rate alone
 * would rubber-stamp an over-latching judge (it only rewards recall).
 */
...
const PROBE_MAX_TURNS = Number(process.env.SCENARIO_EVAL_PROBE_MAX_TURNS ?? 10);
...
/** Run N simulated conversations and write aggregate results to the ScenarioEvalRun row. */
export async function runScenarioEval(params: {
  evalRunId: string;
  storyId: string;
  runs: number;
  userId: number;
}): Promise<void> {
  const { evalRunId, storyId, runs, userId } = params;
  try {
    await prisma.scenarioEvalRun.update({ where: { id: evalRunId }, data: { status: "running" } });

    const story = await prisma.story.findUnique({
      where: { id: storyId },
      include: { objectives: { orderBy: { order: "asc" } } },
    });
    if (!story) throw new Error("Scenario not found");
    const objectives: EvalObjective[] = story.objectives.map((o) => ({
      id: o.id, text: o.text, exampleUtterance: typeof o.exampleUtterance === "string" ? o.exampleUtterance : null,
    }));
    if (objectives.length === 0) throw new Error("Scenario has no objectives to evaluate");

    // Measure against the real completion bar (threshold), not the whole pool —
    // otherwise the eval gate demands every objective when the learner only ever
    // needs `completionThreshold`, inflating avgTurns and under-reporting pass-rate (H5).
    // Shared resolver so stretch objectives are excluded exactly like the
    // runtime (the eval runs the whole pool as its "subset"). Null only when
    // the pool is all-stretch — degrade to a 1-hit bar, not an unpassable one.
    const required =
      resolveRequiredHits(
        null,
        story.completionThreshold,
        story.objectives,
        story.objectives.filter((o) => !o.stretch).length,
      ) ?? 1;
    const maxTurns = Math.max(12, objectives.length * 2 + 4);
    const convs: ConversationResult[] = [];
    for (let i = 0; i < runs; i++) {
      try {
        convs.push(await runOneConversation(story, objectives, userId, maxTurns, required));
        logger.info({ evalRunId, run: i + 1, runs }, "scenario eval: conversation complete");
      } catch (err: unknown) {
        // A single conversation that fails (e.g. LLM outage after retries) counts
        // as an incomplete run rather than aborting the whole eval.
        logger.warn({ err: getErrorMessage(err), evalRunId, run: i + 1 }, "scenario eval: conversation failed");
        convs.push({
          completedIds: new Set(), turns: 0, passed: false, transcript: [],
          legsEntered: new Set(), legsExited: new Set(),
        });
      }
    }

    const passedCount = convs.filter((c) => c.passed).length;
    const passRate = runs > 0 ? passedCount / runs : 0;
    const avgTurns = convs.length > 0 ? convs.reduce((n, c) => n + c.turns, 0) / convs.length : 0;
    const perObjective: ScenarioEvalObjectiveResult[] = objectives.map((o) => ({
      objectiveId: o.id,
      text: o.text,
      reached: convs.filter((c) => c.completedIds.has(o.id)).length,
    }));

    // Per-leg reachability (journeys only) — built from the story's act spine
    // plus each conversation's leg cursor. placeLabel resolves through the same
    // pure helper the progress DTO uses, never the raw authoring `scene.place`.
    const acts = parseActs(story.acts);
    const perLeg: ScenarioEvalLegResult[] | undefined = isJourney(acts)
      ? acts.map((act, index) => ({
          key: act.key,
          index: index + 1,
          placeLabel: resolveSceneLabels(act, SIM_LOCALE).placeLabel,
          entered: convs.filter((c) => c.legsEntered.has(act.key)).length,
          exited: convs.filter((c) => c.legsExited.has(act.key)).length,
        }))
      : undefined;

    // Adversarial precision probe (PR1): an off-target learner must latch NOTHING.
    // Runs a small fixed number of probes regardless of `runs` so the false-accept
    // rate is always measured; a probe failure degrades to "0 false accepts this
    // probe" rather than aborting the eval. Kept small — it is a precision floor,
    // not a full sweep.
    const probeCount = 2;
    let falseAccepts = 0;
    for (let i = 0; i < probeCount; i++) {
      try {
        falseAccepts += await runOneAdversarialProbe(story, objectives, userId, maxTurns);
      } catch (err: unknown) {
        logger.warn({ err: getErrorMessage(err), evalRunId, probe: i + 1 }, "scenario eval: adversarial probe failed");
      }
    }
    const falseAcceptOpportunities = probeCount * objectives.length;
    const falseAcceptRate = falseAcceptOpportunities > 0 ? falseAccepts / falseAcceptOpportunities : 0;
    // The effective probe budget, stamped on the run so a reader can tell WHICH
    // regime a stored number belongs to. Probe scores are not comparable across a
    // change to this value (run-021 R5) — an unstamped historical run predates
    // the cap and ran the full `maxTurns` with no early exit.
    const probeMaxTurns = Math.min(maxTurns, PROBE_MAX_TURNS);
    logger.info(
      { evalRunId, passRate, falseAccepts, falseAcceptOpportunities, falseAcceptRate, probeMaxTurns },
      "scenario eval: precision probe complete",
    );

    await prisma.scenarioEvalRun.update({
      where: { id: evalRunId },
      data: {
        status: "done",
        passRate,
        avgTurns,
        resultJson: toInputJson({
          perObjective,
          transcripts: pickSamples(convs),
          falseAcceptRate,
          falseAccepts,
          falseAcceptOpportunities,
          probeMaxTurns,
          ...(perLeg ? { perLeg } : {}),
        }),
        completedAt: new Date(),
      },
    });
  } catch (err: unknown) {
    logger.error({ err: getErrorMessage(err), evalRunId }, "scenario eval run failed");
    await prisma.scenarioEvalRun
      .update({ where: { id: evalRunId }, data: { status: "failed", error: getErrorMessage(err), completedAt: new Date() } })
      .catch(() => undefined);
  }
}
```
- Notes:
  - Pass rate is measured against the real completion threshold, not the whole objective pool.
  - A failed conversation counts as incomplete; a failed probe counts as zero false accepts.
  - `probeMaxTurns` is stamped on the run because probe scores are not comparable across a change to it.

### X25 · Admin route and job handler that start an eval run
- File: `~/projects/lomem/apps/tunatutor/backend/src/routes/admin/scenarios.ts:194-226` (Lomem main branch as read on 2026-10-15)
- Implements: K17, K18, F10.1-F10.5, F10.14
```ts
  // POST /api/admin/scenarios/:id/eval — start an empirical eval run (background job).
  app.post<{ Params: { id: string }; Body: { runs?: number } }>(
    "/:id/eval",
    { schema: ScenarioEvalSchema },
    async (req, reply) => {
      const userId = Number(req.user.sub);
      const scenario = await repo.getAdminScenario(db, req.params.id);
      if (!scenario) throw new NotFoundError("Scenario not found");
      const runs = Math.min(10, Math.max(1, req.body?.runs ?? 5));
      const evalRunId = await createEvalRun(db, {
        storyId: req.params.id,
        requestedRuns: runs,
        createdByUserId: userId,
      });
      await enqueueJob({
        type: JobType.ScenarioEvalRun,
        payload: { evalRunId, storyId: req.params.id, runs, userId },
      });
      return reply.send({ evalRunId });
    },
  );

  // GET /api/admin/scenarios/eval/:evalRunId — poll an eval run's status + results.
  app.get<{ Params: { evalRunId: string } }>("/eval/:evalRunId", async (req, reply) => {
    const run = await getEvalRun(db, req.params.evalRunId);
    if (!run) throw new NotFoundError("Eval run not found");
    return reply.send(run);
  });

  // GET /api/admin/scenarios/:id/eval — past eval runs for a scenario.
  app.get<{ Params: { id: string } }>("/:id/eval", async (req, reply) => {
    return reply.send({ runs: await listEvalRuns(db, req.params.id) });
  });
```
- Notes:
  - Runs are clamped to 1-10, default 5.
  - The eval runs on the background job queue, not in the request.
  - The job handler is quoted below.

Job handler, `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/jobs/handlers.ts:77-84`:
```ts
export async function processScenarioEvalRunJob(payloadRaw: unknown): Promise<void> {
  const p = payloadRaw as { evalRunId?: string; storyId?: string; runs?: number; userId?: number };
  if (!p?.evalRunId || !p.storyId || typeof p.runs !== "number" || typeof p.userId !== "number") {
    logger.warn({ payloadRaw }, "scenario eval job: invalid payload");
    return;
  }
  await runScenarioEval({ evalRunId: p.evalRunId, storyId: p.storyId, runs: p.runs, userId: p.userId });
}
```

### X26 · Airport family eval driver
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/eval-airport-family.ts:11-38` (Lomem main branch as read on 2026-10-15)
- Implements: E12, N34, K19, C46
```ts
// Scenario Legs — Wave 4, Task 9 driver: run the eval harness against each airport-family
// variant's SPANISH realization (the QA-relevant language, per the task brief) and print a
// report readable enough to judge against the content draft's own per-variant expectations
// (draft §1.6 / §2.5 / §3.5 / §4.5). Dynamic admin
// user resolution, per-item try/catch so one failure never aborts the batch, loud console
// output as the primary artifact (no DB dependency for the caller to re-derive the numbers).
//
// Budget (binding, brief): 3 runs for a1/a2, 2 runs for b1/b2 — spanish only. Real, paid LLM
// calls — run with the sandbox off and a generous timeout.
//
//   pnpm --filter @tunatutor/backend exec tsx scripts/eval-airport-family.ts [variant ...]
//   e.g. tsx scripts/eval-airport-family.ts a1        (just one variant, e.g. re-running after a fix)
//        tsx scripts/eval-airport-family.ts           (all four, default budget)

const db = prisma as unknown as PrismaClient;

interface VariantSpec {
  variant: "a1" | "a2" | "b1" | "b2";
  storyId: string;
  runs: number;
}

const ALL_VARIANTS: VariantSpec[] = [
  { variant: "a1", storyId: "story-airport-a1-spanish", runs: 3 },
  { variant: "a2", storyId: "story-airport-a2-spanish", runs: 3 },
  { variant: "b1", storyId: "story-airport-b1-spanish", runs: 2 },
  { variant: "b2", storyId: "story-airport-b2-spanish", runs: 2 },
];
```
- Notes:
  - The budget is written into the script as binding: real, paid calls.

### X27 · Scenario judge system prompt (the grader the precision check tests)
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/scenario/judge-prompt.ts:19-20` (Lomem main branch as read on 2026-10-15)
- Implements: C41, K12
```ts
export const JUDGE_SYSTEM_PROMPT =
  "You grade which communicative objectives a language learner has demonstrated, from their own utterances only. Credit a function ONLY when the learner actually performs its defining speech-act move — never on topical or lexical overlap with a neighboring objective. Be strict: do not credit echoes of the tutor or vague near-misses. Reply with JSON only.";
```
- Notes:
  - The rule "never on topical or lexical overlap" is the fix the precision check guards.

### X28 · ADR-032 on the scenario judge
- File: `~/projects/lomem/docs/adr/032-tutor-scenarios.md:113,125` (Lomem main branch as read on 2026-10-15)
- Implements: C41, N63
```md
Completion is decided by an async LLM judge, **never in the turn loop**:
...
- **Judge-call ceiling.** One grade job per learner turn is capped per session by `judgeCallCeilingFor` (`services/cost-guardrails`): 2 per run goal + 8, never below the `guardrails.judge_calls.per_session_cap` setting. A quest gets 4 per goal + 8, enough for a thorough route with revisits. **A quest keeps grading after it is solved**, at whatever place the learner is in, so a secret or a missed clue can still be found; every other story keeps judging its open goals after completion (extras and bonus goals, §7) and harvests no more coverage fillers. A quest's judge is scoped per visit (§17): its goals are those of the place where the line was said plus the cross-cutting goals, its transcript is that visit's lines only (`questJudgeScope`, `questJudgeWindow`, `quest/quest-place.ts`), and it never moves a quest. A quest's judge prompt also opens with the cast ("Elio is the postman", `questCastLines`), so a DONE WHEN that refuses "the postman" refuses "Elio" too, and carries four quest-only lines (`QUEST_JUDGE_LINES`, `judge-prompt.ts`): saying a villager's value back is the "check it back" move, not an echo (a bare repeat without a question mark counts when the villager takes it up as a check); any everyday reading of the same clock time counts; a move whose DONE WHEN has two parts (a question then the value said back, a name then the reason) may come in two learner turns in a row; and a check-back goal is met only by a learner line that itself contains the value — asking for it is the first half, and the villager's answer is never read as the learner's uptake. That last rule is also enforced after the judge (`quest/quest-checkback-guard.ts`), because the prompt alone did not hold: a credit for a goal tagged `checkback` is dropped unless its evidence repeats a two-word run (with a real word in it) of one of the villager's last two lines before it. A realized hint shortens each DONE WHEN to one line, so these clauses live in the judge prompt rather than in every hint. A goal at a place is a move made to that villager, so a line said to Rosa never meets a goal at Elio's.
```
- Notes:
  - Line 117 (long; not quoted) adds that every credit must cite a verbatim learner utterance, code-enforced by `selectFreshHits`, and that "Every verdict logs `completed` vs `accepted` so judge accuracy is reviewable from logs alone."

### X29 · Guards in log mode until measured
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/overheard/engine/guards.ts:181-209` (Lomem main branch as read on 2026-10-15)
- Implements: C43, L6, K21, N35
```ts
/**
 * 'enforce' refuses the item. 'log' writes the refusal it WOULD have made and
 * lets the item through, until `scripts/overheard-guard-rates.ts` shows the rate
 * is under about 15 percent. Switching a guard on is one line here.
 *
 * Mutable on purpose: tests and the rates script set it. Production code never writes it.
 */
export const GUARD_MODES: Record<GuardName, GuardMode> = {
  structure: "enforce",
  "choice substring": "enforce",
  span: "enforce",
  "why line": "enforce",
  "span repeat": "enforce",
  "where opener": "enforce",
  "unnatural line": "enforce",
  "question rules out a choice": "enforce",
  "line repeated in this run": "enforce",
  "opening repeated in this run": "enforce",
  "question repeated in this run": "enforce",
  // Measured 0 percent in every language and band (overheard-guard-rates, 2026-10-07).
  "end punctuation": "enforce",
  // Fairness guards: measured first, switched on one by one under about 15 percent.
  cognate: "log",
  "scene word": "log",
  "question names its type": "log",
  "question shares a word": "log",
  "longest choice": "log",
  "intent topic word": "log",
};
```
- Notes:
  - The same measure-then-enforce pattern as the gate, applied to guardrails.

### X30 · CI runs the backend unit tests only on manual dispatch
- File: `~/projects/lomem/.github/workflows/tunatutor-ci.yml:685-692,753-756` (Lomem main branch as read on 2026-10-15)
- Implements: C49
```yaml
  # ── Unit tests: tunatutor backend (manual dispatch only) ──────────────────────
  # Many backend use-case tests hit a real Postgres (curriculum seed, level-test,
  # drills). Boot a Postgres service, write dev .env files from Railway, migrate + seed, then
  # run the non-integration suite. Dispatch-only for cost (~10 minutes); /ship
  # runs it locally whenever the backend or a package it consumes changed.
  unit-tests:
    if: github.event_name == 'workflow_dispatch'
    runs-on: ${{ vars.CI_RUNS_ON || 'petros-main' }}
...
      - name: tunatutor backend unit tests
        id: backend
        if: ${{ !cancelled() && steps.db_setup.outcome == 'success' }}
        run: pnpm --filter @tunatutor/backend test
```
- Notes:
  - Dispatch-only "for cost (~10 minutes)"; `/ship` runs the suite locally.
  - The gate-stats unit tests (X12) are part of this suite.

### X31 · Backend unit test command
- File: `~/projects/lomem/apps/tunatutor/backend/package.json:13` (Lomem main branch as read on 2026-10-15)
- Implements: C49, X12
```json
    "test": "node --import tsx --experimental-test-module-mocks --env-file=.env --test --test-timeout=30000 --test-concurrency=1 $(find src -name '*.test.ts' ! -name '*.integration.test.ts')",
```
- Notes:
  - Every `*.test.ts` under `src` except integration tests runs; that includes `judge-gate-stats.test.ts`.

### X32 · The sixteen focus areas
- File: `~/projects/lomem/packages/tunatutor-shared/src/drill-text/judge-focus.ts:1-23` (Lomem main branch as read on 2026-10-15)
- Implements: C39, N55
```ts
/**
 * The areas Translation's judge can name as what a miss was about (one word
 * each, shown as "Focus: ..."). Sixteen, fixed.
 */
export const JUDGE_FOCUS_AREAS = [
  "verb-form",
  "verb",
  "tense",
  "time",
  "place",
  "who-does-it",
  "pronoun",
  "article",
  "agreement",
  "preposition",
  "negation",
  "noun",
  "describing-word",
  "order",
  "missing",
  "accents",
] as const;
export type JudgeFocus = (typeof JUDGE_FOCUS_AREAS)[number];
```
- Notes:
  - The arc reply's `focus` must be one of these or null; the parser drops anything else.


### X33 · Checkpoint recheck and borderline log
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/checkpoint-rules.ts:19-21,42-76` (Lomem main branch as read on 2026-10-15)
- Implements: C38, F3.3a, F3.3b, F3.3c, N66, N67, K26
```ts
/** A checkpoint answer scored in this band is logged for the two-week review. */
export const BORDERLINE_MIN = 50;
export const BORDERLINE_MAX = 85;
...
/**
 * Grades a checkpoint item with the LLM. At most ONE extra call, and only when
 * the raw reply contradicted itself. A consistent second reply replaces the
 * first; if it also contradicts itself the item is WRONG (a checkpoint never
 * passes on a self-contradiction). No "either call says right".
 */
export async function judgeCheckpointItem(
  input: DrillJudgeInput,
  deps: CheckpointJudgeDeps,
): Promise<DrillJudgeResult> {
  let result = await deps.call(false);
  if (result.contradictory) {
    const second = await deps.call(true);
    result = second.contradictory
      ? { ...second, correct: false, score: Math.min(second.score, BORDERLINE_MIN - 1) }
      : second;
  }
  logBorderline(input, result);
  return result;
}

function logBorderline(input: DrillJudgeInput, r: DrillJudgeResult): void {
  if (r.score < BORDERLINE_MIN || r.score > BORDERLINE_MAX) return;
  // Remove two weeks after release, once the owner has hand-checked the 50s
  // and decided on a third-call tie-break (see translation-drill docs).
  logger.info(
    {
      attemptId: input.attemptId ?? null,
      userAnswer: input.userAnswer,
      score: r.score,
      correct: r.correct,
    },
    "td_checkpoint_borderline",
  );
}
```
- Notes:
  - Only a self-contradicting reply triggers the second call, and a right verdict never comes from either call alone (the comment: No 'either call says right').
  - The borderline log gathers the cases a person will hand-check before deciding on a third call, the same human-labelling step an eval needs.

### X34 · The `why` guard
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-reply.ts:22-23,54-63` (Lomem main branch as read on 2026-10-15)
- Implements: C39, N57
```ts
/** A `why` shorter than this many key words is never checked for the key. */
const MIN_KEY_WORDS_TO_GUARD = 3;
...
/** True when `why` writes out the key or one of the variants. */
export function whyGivesAnswer(why: string, expected: string, variants: readonly string[]): boolean {
  const w = ` ${normalizeTypedAnswer(why)} `;
  for (const key of [expected, ...variants]) {
    const k = normalizeTypedAnswer(key);
    if (k === "" || k.split(" ").length < MIN_KEY_WORDS_TO_GUARD) continue;
    if (w.includes(` ${k} `)) return true;
  }
  return false;
}
```
- Notes:
  - A key or variant of fewer than 3 words is never checked, so a `why` that writes out a one- or two-word key is kept.

## Analogy to classic backend

| AI-side item (id) | classic Java/Spring equivalent | holds where | breaks where |
|---|---|---|---|
| Eval (C1) | parameterised test suite with a load-test threshold | both run many inputs and report a result per check [S11] | one green unit-test run is proof; an eval score is a statistical sample that moves between runs [S11] |
| Golden dataset (C15) | the data table of a JUnit `@ParameterizedTest` | rows of input plus expected value [S11] | golden rows need a domain expert's judgment, and real rows have no expected value at all [S11] |
| Bar (C10) | "p95 latency under 300 ms" in a load test, which passes even though some requests are slow | a threshold on a share, not on every case [S11] | the threshold moves with sample size (C30) and model randomness (C31) [S11] |
| Scorer (C9) | assertEquals / AssertJ assertion | turns one output into pass or fail [S11] | an LLM judge scorer can itself be wrong, which never happens with assertEquals [S11] |
| Regression set (C26) | regression test suite in CI | guards fixed bugs and blocks a change [S9, S11] | every run costs money and needs the network; Lomem runs it by hand [S11] |
| Capability eval (C27) | a backlog of failing acceptance tests marked as known failures | measures what does not work yet, blocks nothing [S11] | graduation is by "passes reliably", a statistical call, not one green run [S11] |
| Online eval (C37) | synthetic monitoring or canary analysis | samples live traffic and alerts on a rising failure rate [S9] | there is no expected answer in production, so only assertions and a judge can score [S11] |
| Feedback into datasets (C47) | product analytics plus a dead-letter queue that becomes test fixtures | failures become new test inputs [S9] | (the source does not say) |
| Gate plus flag (C12, C13) | release toggle flipped after a QA sign-off | a person decides from a test report [S11] | part of the report is scored by hand, and no exit code enforces the bar [X7] |
| Shadow or log mode (C43) | dark launch: run new code, log the result, keep serving the old one | measures before affecting users [X29] | (the source does not say) |
| Pass rate under k runs (C33, C34) | flaky-test rerun policy | reruns reveal non-determinism | in an eval, flakiness is the property being measured, not a defect to retry away [S11] |

(The catalogue's backend analogues are the researcher's own, not from a fetched source. [S9])

## Pitfalls

| id | mistake | consequence | what to do instead | source |
|---|---|---|---|---|
| M1 | Writing the dataset before reading real outputs | the rows test only what the author already knew | do error analysis first (F5) | S11, S1 |
| M2 | Using a 1-to-10 score where pass or fail would do | nobody can say what separates a 6 from a 7, so the numbers drift | binary pass/fail per check | S11, S1 |
| M3 | Comparing two prompts on different rows | the difference may come from which rows were drawn | run both on the same rows; read the flipped rows (F9) | S11 |
| M4 | Reusing a bar after changing the rows or k | the bar no longer means what it did | set the bar anew from a measured run | S11 |
| M5 | Letting the set go stale | new production failures are not guarded | turn new production failures into new rows | S11, S9 |
| M6 | Lowering the bar after a miss | the check stops measuring anything | read the failing rows, fix the prompt, run again | S11 |
| M7 | Treating agreement with the old version as correctness | a real fix counts as a failure; a shared error counts as a pass | score correctness on human-labelled golden rows; move real fixes into them | S11, testing |
| M8 | Folding speed and correctness into one pass/fail | a slow right answer counts as a wrong one; the per-check diagnosis is lost | one check and one bar per quality | S11, testing |
| M9 | Trusting an LLM judge without validation | the scorer's own errors look like feature errors | measure TPR and TNR against human labels on both passes and fails (F6) | S11, S1 |
| M10 | Validating a judge on passes only | a judge that passes everything scores 100% on the TNR | label at least 50 of each and measure both rates | S11, S1 |
| M11 | A regression case with only the bad example | a "fix" that rejects everything passes | pair each negative with a positive | S11, X13 |
| M12 | Reading a one- or two-point change as an improvement | noise is about ±3 points at 200 cases and ±7 at 40 | compare on the same rows and read every flipped row | S11 |
| M13 | Reporting pass@k for a feature users meet once | quality looks far higher than users see | report pass^k for one-attempt features | S11 |
| M14 | Copying a single-run bar to pass^k | every case scores lower, so the bar fails for no reason | set the pass^k bar from a measured run | S11 |
| M15 | Testing at temperature 0 and expecting assertEquals to work | even 0 is not fully deterministic, and the output is still open-ended | use an eval | S3, testing |
| M16 | Running costly evals with no cost estimate | surprise spend; real-path runs also write usage rows | dry-run the plan first and keep runs on a local database | X22 |
| M17 | Dropping failed calls from the denominator | a prompt whose replies cannot be parsed looks no worse | count call and parse failures as failures, or report them | X5, X7 (code observation) |
| M18 | Letting a judge parse failure pass silently | broken judging looks like success | put parse failures in an "error" bucket | X22 |
| M19 | Treating the Java sketch's 40-case 95% bar as precise | one failure moves the rate 2.5 points | read every printed failure | S11, testing |

## Misconceptions

| id | what a newcomer believed | correct statement | evidence |
|---|---|---|---|
| Q1 | The translation grader is the same thing as LLM-as-judge | the grader is the feature under test; an LLM judge is a separate model call the eval makes to score outputs | testing (round 1), S11 |
| Q2 | The gate is an LLM-as-judge | the gate uses exact match, code assertions and a person; no LLM judge yet | testing (round 1), S11 |
| Q3 | Agreement with the old prompt on real rows means the new prompt is correct | it means nothing changed; the old verdict is only a stand-in reference, and a disagreement may be a fix | testing (rounds 1-3), S11 |
| Q4 | Every row in the dataset has a known good output | only golden rows do; real rows use the old verdict | testing (round 2) |
| Q5 | Moving a real fix into the fixture is a way around the bar | the row is still scored, against a human answer, and the bar stays as written | testing (round 3), S11 |
| Q6 | Temperature 0 would make assertEquals work | even at 0.0 results "will not be fully deterministic", and free text has no single correct string | testing (round 1), S3 |
| Q7 | The ±3 points at 200 cases is run-to-run model wobble | it is row-sampling error; model randomness is a second, usually smaller wobble | testing (round 3), S11 |
| Q8 | Check 1's 95% is one bar over real and fixture rows combined, and includes paraphrases | three separate bars: real ≥ 95%, fixture ≥ 95%, paraphrase misses = 0 | testing (round 2), X7 |
| Q9 | Check 3's 90% counts rows | it counts marked words | testing (round 2), X1 |
| Q10 | Check 2 asks that each mark be placeable | the bar is 95% of all replies; a reply with no marks passes; one placed mark is enough | testing (round 3), X11 |
| Q11 | The Lomem gate exits non-zero below 95% | the gate's exit code does not depend on the checks; a person decides | testing (round 3), X7 |
| Q12 | The gate lists every real-row disagreement | it lists only fixture misses; real-row verdicts come only from `GATE_JSON_OUT` | testing (round 3), X7 |
| Q13 | Each error category gets its own check | each category gets golden rows and a failure count; a separate check only when code can test it | testing (round 2), S11 |
| Q14 | Judge validation is "compare with 50-100 human labels" | it compares on the person's passes and the person's fails separately (TNR and TPR), at least 50 of each | testing (round 1), S1 |
| Q15 | pass@k and pass^k are just definitions | the choice changes the score a lot (98% vs 42% in the example) and must match how users meet the feature; pass^k for the grader | testing (rounds 1, 3), S11 |
| Q16 | The 95% bars could be pass^k | the gate's bars are single-run rates | testing (round 2), S11 |
| Q17 | The analogy to a JUnit suite holds fully | an eval is a statistical sample, and its scorer can be wrong | testing (rounds 1, 2) |
| Q18 | Capability cases stay capability cases | a case that passes reliably moves into the regression set | testing (rounds 1, 2), S11 |
| Q19 | The smallest eval is the two-case precision check | the smallest eval is 30-50 labelled cases; the two-case check is a regression check and all-or-nothing | testing (round 1) |
| Q20 | "Exact match" means one thing | it names both the feature's pre-pass (answer equals key, no model call) and a scorer type | testing (round 1) |
| Q21 | "Pipeline" contradicts "kept out of CI" | the regression set belongs in the pipeline when the team accepts the cost; Lomem does not and runs it by hand | testing (round 3), S11 |
| Q22 | The minimal version can use a 95% bar at 30-50 cases like a large set | at that size one failure is 2.5 points; read every failure | testing (round 2), S11 |
| Q23 | The bar can be lowered after a miss | the bar is fixed before the run; the prompt is fixed, not the bar | testing (round 3), S11 |
| Q24 | Terms readers did not know | Lomem, tunatutor, TR2/TR4, arc/card, AI-judged answers, "literal matches", temperature scale, marks, placeNamedMarks, model gateway, TD_JUDGE_MARKS, frozen prompt, transcript, objective (and objective versus goal), scenario judge, false accept, promptfoo, Spring AI, fixture, gate, staging database, CI, p95, PR #227, precision, regional synonym, "the other you form", standard error, score field, kind field, Anthropic, model connection, runner, true rate, percentage points, model version, settings, Verdict, independent, pipeline, feature flag, markedWords, loadCsv | testing (rounds 1-3) |

## Open questions

- Is the release process for `TD_JUDGE_MARKS` (checks 1, 2, 4 PASS and a hand count for check 3) followed? The script header supports it, but no code enforces it. [testing]
- Does the gate use the same model as production? Both paths use the same `callLLM` gateway with temperature 0.3, JSON and the same token budgets; the provider registry was not traced far enough to rule out model routing by usage context. [testing]
- Does the staging database hold real test usage? This rests only on the script's mention of `tunatutor pull-staging-data`; the data was not inspected. [testing]
- "Real traffic rarely contains a correct paraphrase" rests on the fixture's header comment, not on a count. [testing]
- Code versus comment: the gate header says check 2 is the "share of marks `placeNamedMarks` could place", but the code measures the share of replies that have no named marks or at least one placed mark. [X1, X11]
- Code versus comment: the gate prints "need >= 20 hand-checked to turn marks on" next to the number of real rows judged, not the number hand-checked. [X7]
- Code versus comment: `LEVEL_BAR.wrong` (0.9) is declared and never read. [X1]
- The gate drops rows whose call or parse failed (`ok: false`) from every denominator, so an unreadable reply is not counted as a failure and is not in check 4's latencies. Is that intended? [X5, X7]
- The gate's check 2 measures mark placement before production's typed-word fallback, so production may show marks on replies that fail check 2. [X5, X17]
- Real rows are filtered by normalised equality with the key and variants only; answers the production pre-pass accepts as `accentForgiven` may still be in the real rows although production never sends them to the model. (unverified) [X3, X18]
- Fixture rows without a `source` give the model "(the meaning of) <key>", which production never sends. Does that change verdicts? A reader also asked whether a CSV needs the source sentence. [X4, testing]
- The gate's "old" prompt is the frozen pre-TR2 `card`, which differs from today's live `card` prompt (today's adds the 'you' rule). [X2, X20]
- The research map says `TD_JUDGE_MARKS` "is used at lines 108, 138, 155 and 174"; only line 108 reads it directly. [S10, X16]
- The research map quotes a level-chat judge in shadow mode at `apps/tunatutor/backend/src/use-cases/level-chat/judge.ts` and `JUDGE_CALL` at `level-chat/prompts.ts` line 36; neither exists on main as read on 2026-10-15. [S10]
- The fidelity eval header says "REAL PAID Gemini/Anthropic calls"; the code map found only Gemini and Cerebras providers in the shared package. [X22, S10]
- The precision check comment claims "60% of objectives are spec-null"; not verified. [X14]
- The long draft says the eval arithmetic has "ordinary unit tests in CI"; in Lomem CI those backend unit tests run only on manual dispatch, and `/ship` runs them locally. [S11, X30]
- An invalid scenario-eval job payload is logged and dropped, which leaves the run row "pending" forever. [X25, X23] (code observation)
- The web catalogue's minimal version runs 50 to 200 cases in CI on every change; the long draft's minimal version is 30 to 50 cases, and Lomem runs evals by hand. Sources differ on where the minimum sits. [S9, S11]
- Hamel Husain's CI/CD guidance was not read, because the page was truncated. [S9]
- The tool descriptions in the Tools table are not verified per tool. [S9]
- Questions newcomer readers left open: if the new prompt fixes 10% of real rows, check 1a fails at 90%; do you relabel all of them before re-running, and do they stop being real rows? Does the CSV need the source sentence? How many times should a flipped row be re-run before calling it randomness? Should the two-case regression check also be run k times? Where are pass^k results stored, and how is k picked? [testing]
- The research did not cover: how to pick k, how to version eval results per prompt and model in Lomem, online evals in Lomem (none found), and judge validation numbers for any Lomem judge.

## Sources

| id | title | author or publisher | date | URL | what it supports |
|---|---|---|---|---|---|
| S1 | AI Evals: Everything You Need to Know | Hamel Husain and Shreya Shankar | updated Sep 2026 | https://hamel.dev/blog/posts/evals-faq/ | error analysis, binary scorers, validating judges with TPR/TNR, at least 50 of each label, golden set size; ranked 4th of five newcomer sources in the catalogue, "how to actually test these systems" (S9) |
| S2 | Demystifying evals for AI agents | Anthropic | 9 Jan 2026 | https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents | capability versus regression evals, pass@k and pass^k |
| S3 | Messages API reference, Create a Message | Anthropic | n.d. | https://platform.claude.com/docs/en/api/messages/create | temperature range 0.0-1.0 and "will not be fully deterministic" |
| S4 | Evaluation best practices | OpenAI | n.d. | https://developers.openai.com/api/docs/guides/evaluation-best-practices | listed as a source for evals in the catalogue (content not summarised) |
| S5 | LLM evaluators | Eugene Yan | n.d. | https://eugeneyan.com/writing/llm-evaluators/ | listed as a source for evals in the catalogue (content not summarised) |
| S6 | Emerging Patterns in Building GenAI Products | Bharani Subramaniam and Martin Fowler | 28 Jan - 25 Feb 2025 | https://martinfowler.com/articles/gen-ai-patterns/ | Evals as a named pattern and its definition; ranked 3rd of five newcomer sources in the catalogue, "the clearest pattern-language treatment of evals" (S9) |
| S7 | Patterns for Building LLM-based Systems & Products | Eugene Yan | about Aug 2023 | https://eugeneyan.com/writing/llm-patterns/ | Evals and Collect user feedback patterns |
| S8 | Building A Generative AI Platform | Chip Huyen | 25 Jul 2024 | https://huyenchip.com/2024/07/25/genai-platform.html | the request ordering the catalogue uses for where evals sit |
| S9 | Web research catalogue, block 11 and "How they fit together in one request" | this store's research | 2026 | `sources/research-web.md` | minimal and mature versions, tools, analogues, online evals, feedback loop |
| S10 | Lomem code map, sections 6, 7, 11e, 13 | this store's research | 2026 | `sources/research-lomem.md` | which Lomem files implement evals and judges |
| S11 | Evals, long fact-checked draft | this store | 2026 | `sources/sections-long/11-evals.html` | running example, gate walk-through, statistics, Java sketch, mistakes |
| S12 | Evals, short version tested on newcomer readers | this store | 2026 | `sources/sections-tested/11-evals.html` | the condensed wording that readers saw |
| S13 | Evals testing notes ("testing") | this store | 2026 | `sources/testing-notes/11-evals-testing.md` | what readers misread, unknown terms, fact-check fixes, unverified claims |
