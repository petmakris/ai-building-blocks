---
id: rollout
number: 17
title: Shadow mode, flags and the feedback loop
summary: New AI behaviour reaches users in stages (shadow mode, log mode, an eval-gated flag, a canary) and confirmed production failures become new eval cases, because a wrong model answer looks exactly like a right one to ordinary monitoring.
lomem_status: partly
depends_on: [evals, prompts, observability]
related: [gateway, structured, guardrails, hitl, governance, caching]
---

# Shadow mode, flags and the feedback loop

## Story

### Hook
- Headline: A new prompt ships, every dashboard stays green, and ==its answers are wrong.==
- Setup: A prompt is the instruction text the app sends to the model. A model that gives a wrong answer still returns HTTP 200 with well-formed JSON, in normal time. Error rates, exceptions and latency stay flat. The feature passed every test before release. Real users send inputs no test set covered, so the first one to see the failure is a user.
- Teaser: Your eval, a scripted run over fixed cases with the real model, passed. How does the new behaviour meet real users without betting them on it?

### Panel
- Title: A second model could grade the chat for 15 seconds because the learner never waited for it
- Row: Language-tutor reply | 4 s | gemini-2.5-flash, the learner waits for it | 
- Row: Judge: the same model grading the chat | 15 s | runs in the background, its answer never shown | accent
- Row: Learner's wait for the judge | 0 s | the reply returns without waiting for the judge | big
- Source: Real time limits from Lomem's code at commit 8fa41788f.
- Refs: N1, N3, N5, C12, X2, X5

### Idea
- Sentence: New AI behaviour ==earns its way to users in stages==: it first runs unseen on real traffic (shadow mode), a flag turns it on only when measured numbers clear a bar written down beforehand, and every confirmed failure becomes a new test case.
- Analogy: In a classic backend, shadow mode is a dark launch, or GitHub's Scientist library. Scientist runs new code next to the current code, returns the current result and logs mismatches. The analogy breaks on mismatches: two different model answers can both be right. So a mismatch needs a rule in code and a person to judge it.

### Walkthrough
- Title: A judge model disagrees with the rules. Here is every step before anyone trusts it.
- Lead: In Lomem's language app, a tutor chats with a learner. Rules in code place the learner at a level from A1 (beginner) to B2, and the learner sees that level. The judge grades the same chat in shadow mode, so the learner still sees the rules' level. The chat below is real test data from the code. The readout numbers in step 6 are made up.
- Lanes: Learner, Server, Judge, DB, Team
- Step 1 · Start the judge once, then answer without waiting | refs: F1.4, F1.5, F1.6, F1.8, C10, C12
  - Arrow: Learner → Server: the answer that reaches the wind-down
  - Self: Server: claim the judge for this chat ✓
  - Arrow: Server → Learner: tutor reply, no wait for the judge
  - Text: When the chat reaches its wind-down, or is force-closed, the server claims the judge: it writes a start time in the database. The claim succeeds only once, so the judge runs at most once per chat. The server starts the judge in the background. It returns the tutor's reply without waiting.
- Step 2 · The judge reads the answers, never the rules' level | refs: F2.1, F2.2, F2.3, C10, C41, X5, M18, E1
  - Arrow: Server → Judge: answered turns + their facts
  - Reply: Judge → Server: B2 · cited turns 5 and 7
  - Text: A turn is one tutor question plus the learner's answer. Each answer already carries facts: fields such as its text type and whether its meaning was clear. The judge gets the answered turns and their facts. It never gets the rules' level, so it cannot copy it. It replies in JSON with a level and its cited turns, the turns it relied on.
- Step 3 · Check in code whether the judge's level is backed by evidence | refs: F3.1, F3.4, F3.5, F3.6, F3.7, E1, C11, C40
  - Self: Server: rules say B1 · judge says B2, one level up
  - Self: Server: 2 cited turns pass the B2 check · no B2 question failed
  - Tag: Server: accepted · would change the level
  - Text: A judge two or more levels away from the rules is rejected. A judge one level up needs two things. First, at least two cited turns whose facts pass the code's check for that level. Second, no question at that level that the learner failed.
  - Fact: Real test case. Had the judge cited only turn 5, the verdict would be rejected.
- Step 4 · Store the comparison next to the answer | refs: F2.7b, C13, M3, K6
  - Event: Server → DB: judge_level B2 · judge_would_change true
  - Text: The server stores the judge's level and whether it would change the rules' level. It writes only the judge's own columns. Later, someone can count disagreements without re-running anything.
- Step 5 · The learner still sees the rules' level | refs: F2.8, F2.9, F2.10, F4.5, C9, C14, Q1
  - Arrow: Server → Learner: your level: B1
  - Self: Server: judge error → log it, keep the rules' level
  - Text: Nothing the judge says reaches the learner yet. If the judge fails, the server logs it, stores nothing and keeps the rules' level.
- Step 6 · A person reads the disagreements against a bar written first | refs: F4.1, F4.2, F4.3, F4.4, F4.4a, F4.5, E2, E3
  - Tag: Team: bar written first: right in ≥ 30 of 38
  - Arrow: Team → DB: count judge_would_change
  - Reply: DB → Team: 38 of 412 chats
  - Text: Once enough chats have run, the team counts the stored disagreements. A person reads each one and notes whether the judge or the rules placed the learner right. If the judge clears the bar, a flag shows learners the judge's accepted level. If not, the judge is dropped.
  - Fact: 412, 38 and the bar of 30 are made up. Lomem dropped its real judge the same day it was added. Because it only ran in shadow, no learner saw a change.

### Takeaways
1. Wrong answers look like right ones | A wrong answer is a fast HTTP 200 with valid JSON, so error rates and latency miss it. Measure what users do with the answer instead: edit it, discard it, retry it. | P1, C25, M6
2. Shadow first, off the request path | Run the new behaviour in the background, with no side effects. Store the comparison while users see the old result. | C9, C12, C13, M3
3. Write the bar before the numbers | A flag flips only when an eval clears bars fixed in advance. | C5, C6, C7, C22, M7
4. Failures become eval cases | A confirmed failure, stored with the turn it is about, becomes a new eval case. | C31, C33, C34, C35

### Trap
- Title: Counting every mismatch as an improvement
- Assume: "The new model answered differently, so it caught what the old behaviour missed." | So the team counts mismatches, as GitHub Scientist does for code, and ships when the count looks high.
- Actually: Two model answers can both be right, so a mismatch is not a bug in the old answer. | Count a difference only when a rule in code finds evidence for it. Have a person read the disagreements against a bar written before reading.
- Refs: M5, M7, C11, C39, P4

### Build
- Title: The smallest shadow mode is one async method and one flag
- Lead: Compute the current result, grade it again in the background, compare in code, store the new result and the comparison, and flip a flag only after the readout. This Java sketch is for teaching. Lomem's real code is TypeScript.
- Refs: F13, K22, C9, C12, F1.5, F2.10
- Code:
```java
public Level placement(Chat chat) {
  Level current = rules.level(chat);                         // the rules' level, which the user sees
  if (NEW_GRADER_ON) return candidateOrCurrent(chat, current); // [6] flipped only after the readout
  shadow.shadowGrade(chat, current);                         // [1] start, don't wait
  return current;                                            // [5] the user still sees the rules' level
}

@Async   // a separate thread pool, never the request thread
public void shadowGrade(Chat chat, Level current) {
  try {
    Level candidate = grader.grade(chat);                    // [2] gets the chat, never `current`
    boolean candidateWins = comparisonRule.candidateWins(current, candidate); // [3] evidence check in code
    chatRepository.saveShadow(chat.id(), candidate, candidateWins);           // [4] level and comparison
  } catch (Exception e) {
    log.warn("shadow grader failed, current level stands", e); // [5] failure keeps the rules' level
  }
}
```
- Note: Each [n] marks the code for walkthrough step n. The sketch skips step 1's claim, so the same chat can be graded twice. Lomem claims the chat first: it sets `judge_started_at` only where it is still empty.

## Summary

Rollout of AI behaviour is the set of steps that move a new model-driven behaviour from "built" to "seen by every user" while measuring its quality on real traffic at each step.
The steps are shadow mode (run on real traffic, store the answer and the comparison, show the old result), log mode for new checks (record the refusal a check would have made, let the item through), a flag flipped only when an eval clears bars fixed in advance, and a canary that widens the share of users only while quality signals stay no worse.
After release, explicit and implicit user feedback is stored with the exact turn it refers to, triaged by a person, and every confirmed failure becomes a new eval case (the data flywheel); the eval is rerun on a schedule because the provider can change the model with no deploy of yours.
In a classic backend a broken release shows up as exceptions, HTTP 500s or failing tests; a model that gives a wrong answer returns HTTP 200 with well-formed JSON in normal time, so only quality measured on real traffic shows how it performs.
Lomem does shadow mode (one judge, removed the same day), log-mode guards, an eval-gated constant flag and a feedback table with triage status; it has no canary, no flag service, and no scheduled eval rerun.

## Problem

- P1 · A wrong model answer is invisible to ordinary monitoring: it comes back as HTTP 200 with valid JSON, in normal time, so error rates, exceptions and latency do not reveal it. (S9, testing)
- P2 · An LLM feature can pass every test before release and still fail on real users, because real inputs are more varied than any test set. (S9)
- P3 · Nobody knows in advance whether a new model-driven behaviour (for example a second-opinion judge) is better than the current behaviour; this has to be measured on real traffic before anyone depends on it. (S9)
- P4 · Two different model answers can both be right, so "the new behaviour said something different" is not "the old behaviour was wrong"; a plain mismatch count (as GitHub Scientist does) overstates bugs. (S9, S2)
- P5 · A new check that refuses generated content too often makes generation slow, expensive or broken, because every refusal triggers another paid model call and repeated refusals can end in an HTTP 503. (S9, X12)
- P6 · Product traffic may be too small to measure a check's refusal rate per language and level from production logs, so the rate must be measured offline with real paid calls. (S9, unverified)
- P7 · A flag flip that changes AI behaviour cannot be judged by "the code compiles and tests pass"; it needs numeric bars on model output, fixed before the run so nobody can move them after seeing the numbers. (S9)
- P8 · Feedback that is not tied to the exact turn, input and output cannot be reproduced and cannot become a test case. (S9, S1)
- P9 · Explicit feedback (thumbs-down, report button) is rare; most signal has to be read from what users do with an answer. (S1, S9)
- P10 · The provider can update the model behind the same name, often without notice, so quality can drift with no deploy of yours; a test suite run only on your own changes never sees it. (S9, S4)
- P11 · The system improves only if production failures come back into eval sets and prompts. (S4)
- P12 · A shadow feature can cost money forever with no benefit if it never leaves shadow mode ("Judge never leaves shadow mode", impact "Judge spend with no benefit"). (X8)

## Concepts

### C1 · Large language model (LLM), or model
- Definition: A hosted service, rented from a provider such as OpenAI or Anthropic, that takes text in and writes text back.
- Facts:
  - A model is called over HTTP by a name such as gpt-4o. (S9)
  - The provider can change what stands behind a model name without telling you. (S9)
  - Each model call costs money. (S9)
  - The same prompt can get a different answer on two calls, because the model picks each next word partly at random. (S9)
  - Newcomer readers did not know "gateway" in round 1. (testing)
- Relations: C1 is the thing whose behaviour C8 (staged release) controls; C1 causes C34 (drift); same concept as gateway.C1; every C1 call goes through gateway.C15 (model gateway).

### C2 · Prompt and prompt version
- Definition: The prompt is the text sent to the model (instructions plus data); a prompt version is a label such as draft-reply@8 that says which prompt produced which answer.
- Facts:
  - Teams give each prompt a version so they can tell which prompt produced which answer. (S9)
  - The canary example moves from prompt version 7 ("draft-reply@7") to version 8 ("draft-reply@8"). (S9, made up)
  - A model version is distinct from a prompt version: the prompt version is yours, the model version is the provider's; readers asked about the difference. (testing)
  - A mature prompt registry gates promotion of a prompt version on an eval run, and rollback means moving a label. (S6)
- Relations: C2 is what C24 (canary) switches between; C2 is part of C4 (trace); see prompts.C13 (prompt version) and prompts.C30 (prompt registry).

### C3 · Turn and session
- Definition: In a chat, a turn is one user message plus the reply to it, and a session is one sitting of turns.
- Facts:
  - Newcomer readers did not know "turn" in round 1; the term was later defined in the text. (testing)
  - Lomem's feedback table stores the turn as `turn_index` and the session as `session_id`. (X19)
  - In Lomem's placement chat each turn has an index `idx`; the judge numbers turns `n = idx + 1`. (X1)
- Relations: C3 is the unit C31 (feedback with context) points at; C3 is what C10 (judge) cites.

### C4 · Trace and trace ID
- Definition: A trace is the stored record of one model call (prompt version, input, output), and its trace ID is the key you log to find it again.
- Facts:
  - The minimal feedback version logs thumbs up/down and "edit before send" against the trace ID. (S4)
  - In the mature request path, user feedback attaches to the trace ID. (S4)
  - Where a system does not store turns, the feedback row needs the trace ID instead of session plus turn. (S9)
  - Lomem's feedback table has no trace ID column; it uses session plus turn index. (X19, testing)
- Relations: C4 is the key C29 and C30 (feedback) attach to; C4 is the same concept as observability.C12; feedback on traces is observability.C40.

### C5 · Eval and eval case
- Definition: An eval is a script that runs a feature over a fixed list of eval cases (an input plus the expected answer), scores each output and reports pass rates.
- Facts:
  - An eval plays the role of a test suite, except that it calls the real model and passes on a rate, not on every case. (S9)
  - An eval case is an input plus the expected answer. (S9)
  - When two answers could both be right, the eval case lists all accepted answers (in Lomem's fixture: `key` plus `variants`). (S9, X18)
  - Fixture row fields: `key` is the reference translation, `variants` other accepted translations, `answer` what the learner typed. (S9, X18)
  - Newcomer readers did not know "fixture" (round 1) or the `key` and `variants` fields (round 2). (testing)
- Relations: C5 decides C7 (flag) through C19 (gate); C33 (flywheel) adds cases to C5; see evals.C1 and evals.C15 (golden dataset).

### C6 · Bar
- Definition: A bar is the threshold a measured rate must clear, such as "at least 95% of cases pass", written down before the measurement.
- Facts:
  - The bar is written before the measurement so nobody can move it after seeing the numbers. (S9)
  - A usual starting point for a bar is the current behaviour's own measured rate, so a change may not make things worse. (S9)
  - Lomem's translation gate has four bars fixed in the script header (95%, 95%, 90%, 95%). (X17)
  - Lomem's guard bar is about 15 percent, written in the guard comment and the rates script. (X9, X11)
  - A newcomer reader saw "bar" used in the lede before it was explained. (testing)
  - A skimmer reader kept "the eval reports a pass rate" but lost that the bars must be fixed before the run. (testing)
- Relations: C6 limits C7 (flag flip), C17 (guard switch), C24 (canary widening) and C15 (shadow readout).

### C7 · Feature flag (feature toggle)
- Definition: A switch in code or config that turns a behaviour on or off without a code change elsewhere.
- Facts:
  - Lomem's marks flag `TD_JUDGE_MARKS` is an ordinary boolean constant in code. (X15)
  - What is new for AI behaviour is the rule that the flag changes only when the eval's numbers clear bars written before the run. (S9)
  - Lomem has no feature-flag service; its flags are code constants plus database config rows. (S5 §13, X15)
  - Other Lomem runtime switches: tutor tool allow-list toggled by admins without a deploy, model on/off and priority via `updateModelConfig`, Billpod's `HouseholdMember.assistantEnabled` column. (S5 §13, unverified: not opened for this file)
  - A newcomer reader noted "flag / feature flag" was never defined explicitly in an earlier draft. (testing)
- Relations: C7 is gated by C19 (gate); C7 is protected by C22 (flag test); C7 depends on C23 (old behaviour kept); C36 (flag service) is the mature form of C7.

### C8 · Staged release (rollout)
- Definition: Releasing AI behaviour in steps: shadow mode, then a flag once measured numbers clear a bar, often for a small share of users first (canary), with production failures fed back as test cases.
- Facts:
  - Order of stages in the inputs: shadow mode → flag flipped after an eval clears bars → canary widening → feedback → flywheel → scheduled rerun. (S9)
  - Lomem goes from off to on for everyone; it has no canary step. (S9)
- Relations: C8 is made of C9, C17, C7, C24, C33, C35.

### C9 · Shadow mode
- Definition: The new behaviour is called on real traffic and its answer is stored, while the user is still shown the old result.
- Facts:
  - Shadow mode measures quality on real traffic before anyone depends on the result. (S9)
  - Three properties make it safe: it runs off the request path, it cannot break the request, and it stores the comparison, not only the answer. (S9)
  - A shadow call must have no side effects: if it sends an email or writes business data, it is not shadow mode. (S9)
  - Because a shadow feature never reached users, removing it changes nothing any user sees. (S9, testing)
  - Lomem ran a shadow placement judge, added in #622 (commit 8fa41788f) and removed with its columns in #624 (commit bdd9ab7b8) on the same day, 2026-10-13. (X1, X7)
  - The Java analogy is a dark launch: new code deployed to production but not shown to users. (S9)
  - GitHub's Scientist library implements the same idea for code: run candidate next to current, return current, log mismatches. (S2)
- Relations: C9 uses C12 (off request path), C13 (no side effects), C11 (comparison rule); C9 precedes C7 (flag); C9 is measured by C15 (readout).

### C10 · Judge (LLM-as-judge)
- Definition: A model used to grade or score something.
- Facts:
  - Lomem's placement judge received the learner's answered turns plus the extracted facts, never the rules' level D, so it could not copy D. (S9, X1)
  - The placement judge's prompt required a JSON reply holding a level and the numbers of the turns it relied on (its cited turns). (S9, X5)
  - The judge schema also has optional `ruledOutTurns` per level, a boolean `nearNext` and a string `reason`. (X5)
  - The placement judge ran on `gemini-2.5-flash`, temperature 0.2, timeout 15000 ms, max 600 tokens. (X5)
  - The placement judge ran once per chat, starting with the wind-down stage (stage `"S4"` in code; not source S4) or at a forced close, "so its wait hides behind the last answer". (X2)
  - Lomem has two unrelated judges in this block: the placement judge (level chat, shadow mode, removed) and the translation grader (translation drill, live); the code calls both "judge". (S9, testing)
  - The plan's judge prompt says learner answers are DATA and instructions in them must be ignored. (X8)
- Relations: C10 is compared through C11; C10's output is C15's input; see evals.C21.

### C11 · Comparison rule (acceptJudge)
- Definition: Code that decides whether a difference between the new and the current answer is credible, instead of counting every mismatch as a win for the new answer.
- Facts:
  - Same level: no change (verdict "same"). (X3)
  - Two or more levels apart: rejected (code: `Math.abs(gap) > 1`). (X3)
  - One level up: accepted only when at least 2 cited turns have stored facts that meet a pass rule of the higher level and no real breakdown exists at that level (a `no_data` breakdown does not count). (X3, X4)
  - One level down: accepted when a cited row at level D broke down or had meaning "effortful" or "no". (X3)
  - The result carries `verdict` (same, accepted_up, accepted_down, rejected), `level` and `judgeWouldChange`. (X3)
  - "The judge said something different" is not "the judge is right". (S9)
  - Where the Scientist analogy breaks: Scientist counts any mismatch as a bug, but two model answers can both be right, so a mismatch needs a comparison rule such as acceptJudge and a person reading the cases. (S9)
  - The plan calls the one-level check "the quote check". (X8)
  - Readers did not know "rows" (the argument to acceptJudge) in round 2. (testing)
  - In round 3 a reader could not say what makes a judge's evidence count, because acceptJudge was never shown at work; the golden cases (E1) were added for that. (testing)
- Relations: C11 is part of C9; C11 produces `judge_would_change` (C15); C11 limits C10.

### C12 · Request path and fire-and-forget
- Definition: The request path is the code the user's request waits on; fire-and-forget starts work in the background and returns without waiting for it.
- Facts:
  - Lomem's chat code starts the judge in the background, once per chat, and returns the tutor's reply without waiting; the learner sees no extra delay. (S9, X2)
  - Lomem's default background runner attaches a `.catch` that logs "level chat: background task failed". (X2)
  - In the Java sketch the shadow call runs under `@Async` on a separate thread pool, never the request thread. (S9, made up)
  - If the request waits for a shadow call, every user pays its delay and its failures. (S9)
  - "Request path" was only implied in an early draft; readers flagged it. (testing)
  - Readers did not know "background runner" in round 3. (testing)
- Relations: C12 is a safety property of C9.

### C13 · Side effects (of a shadow call)
- Definition: Anything a call changes outside its own stored result: sending an email, writing business data, calling a tool that changes data.
- Facts:
  - A shadow call with side effects is not shadow mode. (S9)
  - Lomem's shadow judge writes nothing except its own columns. (S9, X1, X2)
  - The shadow judge columns were `judge_level`, `judge_would_change` and `judge_started_at` (three, not two). (X7, X23, testing)
  - A round-1 draft listed "writes memory" and "calls a tool that changes data" as side effects; readers did not know "memory" or "tool" in that sense. (testing)
- Relations: C13 must be absent for C9.

### C14 · Undegradable errors (rethrowIfUndegradable)
- Definition: The two Lomem error codes that a degrade or retry chain must never swallow: a missing usage context and the daily spending cap.
- Facts:
  - Codes: `FST_MISSING_USAGE_CONTEXT` (a programming error) and `FST_DAILY_SPEND_CAP` (an admission decision already made at the door). (X6)
  - `rethrowIfUndegradable` is called first inside any catch that would otherwise degrade. (X6)
  - In the shadow judge these two errors are rethrown out of `runLevelChatJudge`, then caught and only logged by the background runner, so they still cannot reach the learner. (S9, X1, X2, testing)
  - The Overheard generator also rethrows them instead of serving a fallback. (X12)
  - The daily spend cap is checked once, when an activity starts ("a DOOR, not a tripwire"); everything downstream of a door, judges included, "runs uncapped by design". (S5 §14, `~/projects/lomem/apps/tunatutor/backend/src/services/cost-guardrails/activity-entry.ts:3-17`, main)
  - Readers did not know "undegradable" in round 2. (testing)
- Relations: C14 is an exception to C9's "cannot break the request" only inside the judge function, not at the request.

### C15 · Shadow readout and human reading
- Definition: After enough shadow runs, counting how often the new behaviour would have changed the result and having a person read those cases against a bar written beforehand.
- Facts:
  - Made-up readout: 412 chats, `judge_would_change` in 38 (9%). (S9, made up)
  - A person reads the 38 chats and notes chat by chat whether the judge or the rules placed the learner right. (S9, made up)
  - Bar written before reading, for example "the judge is right in at least 30 of the 38". (S9, made up)
  - If the bar clears, a flag makes the accepted judge level the one learners see; if not, the judge is dropped. (S9)
  - Lomem's plan: the judge moves to live only after the real check shows judge-adjusted levels agree with a teacher more often than D alone. (X8)
  - Lomem's plan real check: 10 to 20 tester chats placed blind by a teacher; target at least 70% exact and at least 95% within one level; these chats also decide whether the judge goes live. (X8)
  - Storing the comparison (not only the answer) lets disagreements be counted later without re-running everything. (S9)
- Relations: C15 uses C11 output; C15 is limited by C6; C15 decides C7.

### C16 · Guard (Overheard)
- Definition: A plain code check that refuses a bad generated exercise.
- Facts:
  - Lomem's Overheard drill has a model write listening exercises: the learner hears a spoken line, then picks its meaning from several choices. (S9)
  - Every generated exercise passes through named guards. (S9, X9)
  - Enforced guards (main): structure, choice substring, span, why line, span repeat, where opener, unnatural line, question rules out a choice, line repeated in this run, opening repeated in this run, question repeated in this run, end punctuation. (X9)
  - Log-mode guards (main): cognate, scene word, question names its type, question shares a word, longest choice, intent topic word. (X9)
  - "Fairness guards" refuse exercises a learner could answer without understanding the line. (S9)
  - Cognate guard: a content token of the line (4+ letters, similarity at least 0.8) matches a content word of the correct choice and of no distractor. (X22, X12 `COGNATE_SIMILARITY = 0.8`)
  - Scene word guard: the scene chip shares a word of 4+ letters with a choice (not on a `where` item). (X22)
  - Structure guard: exactly 4 non-empty, mutually distinct choices and a valid `correctIndex`. (X22)
  - Longest choice guard: the right choice is the longest and at least 20 percent longer than the second-longest ("a starting value"). (X22)
  - A cognate is a word that looks alike in two languages, such as French "restaurant" and English "restaurant". (S9)
  - "Band" in the guard code means level (A1 to B2). (S9)
  - Readers did not know "band", "fairness guards", "cognate guard", "scene word guard" or "structure guard" (rounds 1-3); in round 3 "cognate" was explained only by the guard's behaviour, never as a word. (testing)
- Relations: C16 runs in C17 modes; C16's refusals are counted as C18.

### C17 · Log mode versus enforce mode
- Definition: In enforce mode a check refuses the item; in log mode it writes the refusal it would have made and lets the item through.
- Facts:
  - A new guard starts in log mode. (S9, X9)
  - Switching a guard on is one line in `GUARD_MODES`. (X9)
  - `GUARD_MODES` is mutable on purpose: tests and the rates script set it; production code never writes it. (X9)
  - Only enforced hits refuse an item (`enforcedHits` filters on `"enforce"`). (X12)
  - The guard log keeps would-be refusals apart as `wouldReject` in the per-call summary. (X10)
  - A test pins every fairness guard to log mode and the cheap structural guards to enforce, so switching a guard also changes that test. (X14)
  - The Java analogy: a new validation rule deployed in report-only mode. (S9)
- Relations: C17 is gated by C18 against C6; C17 is the check-level form of C9.

### C18 · Refusal rate (would-reject rate)
- Definition: The share of exercises a guard would refuse, per language and level.
- Facts:
  - A large product reads the rate straight from the guard log of real traffic. (S9)
  - Lomem measures it with `scripts/overheard-guard-rates.ts`, which generates exercises in bulk with real paid calls and prints each guard's rate. (S9, X11)
  - The script's rate is the share of ITEMS where the guard fired on any try. (X11)
  - The script switches every guard to enforce for the measurement, so tries behave as they would once everything is on. (X11)
  - The script refuses to run with `NODE_ENV=production`. (X11)
  - Bar: `ENFORCE_BELOW = 0.15`; a log guard is switched on only when its rate is under 15% in every cell (worst cell). (X11)
  - Defaults: 50 items per band for French, 25 for the other languages; languages french, spanish, german, greek, korean; bands A1, A2, B1, B2; concurrency 2. (X11, X22)
  - The header says "Run it only when the owner says go." (X11)
  - A guard above the bar is not switched on; a person reads a sample of what it refused: if those exercises are fine, the guard is too strict and is loosened or dropped; if they are really bad, the fix belongs in the prompt that writes them. (S9)
- Relations: C18 is measured against C6; C18 decides C17.

### C19 · Gate
- Definition: Lomem's word for an eval that decides a flag.
- Facts:
  - `scripts/translation-judge-gate.ts` decides whether `TD_JUDGE_MARKS` may be turned on. (X17)
  - The gate is a dev harness, not a CI test; it needs the network. (X17)
  - The gate runs under a system usage context with reason "dev gate script: no learner is behind these calls". (X17)
  - The gate reads real rows from the local database filled by `tunatutor pull-staging-data`. (X17)
  - TR4 is the task in the translation drill's plan that built the gate script. (S9)
  - Readers did not link "gate" to "eval" in round 2, and read "TR4" as an unexplained ID (rounds 2-3). (testing)
- Relations: C19 is a C5 that decides C7; see evals.C12.

### C20 · Translation grader: verdict, focus, why, marks
- Definition: The model that grades a learner's translated sentence in Lomem's translation drill; its reply holds a right/wrong verdict, a focus, a why and optional marks.
- Facts:
  - Focus is which area the mistake is in, such as word order; why is one line of explanation. (S9)
  - Marks are the learner's wrong words, to be underlined on the phone. (S9)
  - Verdict, focus and why went live with the drill; only the marks are held back by the flag. (S9, X15, testing)
  - While `TD_JUDGE_MARKS` is false, a parsed reply keeps focus and why and returns `marks: null` ("unknown, so the phone draws nothing"). (X15)
  - The `weak` field is held back with the marks because the gate never measured it. (X15)
  - The new grading prompt is called `arc`; the frozen old prompt is called `card` (pre-TR2, Drill Me's judge). (X17)
  - Cheap exact matches never reach the model: an exact-match pre-pass runs first and returns correct with score 100. (X18, S5 §6a, `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-adapter.ts:65-77`, main)
  - Readers did not know the focus, why and marks fields (rounds 1 and 3). (testing)
- Relations: C20's marks are controlled by C7; C20 is measured by C19.

### C21 · No-regression bar versus hand-written cases
- Definition: Bar 1 has two halves: agreement with the old prompt on real answers (no worse than before) and agreement with expected answers on hand-written cases (catches where the old prompt was itself wrong).
- Facts:
  - The new verdicts reached learners before any gate measured them, so bar 1 checks afterwards that they did not get worse. (S9, unverified)
  - The hand-written cases cover places where the old prompt was itself wrong. (S9)
  - Real AI-judged answers are almost all literal matches or wrong answers, so they cannot carry the gate alone. (X18)
  - Readers did not know "literal matches" in round 1. (testing)
  - Every fixture paraphrase must come out right (must be 0 misses). (X17)
  - Readers saw bar 1 as contradicting the goal of improvement. (testing)
- Relations: C21 is part of C19.

### C22 · Flag guard test
- Definition: A test that asserts the flag's current value, so flipping it by accident fails the build.
- Facts:
  - `judge-reply.test.ts` asserts `TD_JUDGE_MARKS` is false. (X16)
  - The PR that flips the flag on purpose also changes that test. (S9)
  - `judge-reply.ts` says "Only TR4's PR may flip it to true." (X15)
- Relations: C22 protects C7.

### C23 · Keeping the old behaviour (rollback path)
- Definition: The code for the old behaviour stays after the flag flips, so turning the flag off restores it.
- Facts:
  - The old code stays until the new one has passed several later reruns. (S9)
  - Deleting the old behaviour when the flag flips leaves nothing to switch back to after a failed rerun. (S9)
  - In the canary, rollback is `rolloutPercent` back to 0. (S9, made up)
- Relations: C23 is required by C7 and C35.

### C24 · Canary
- Definition: Showing the new behaviour to a small share of users, comparing their outcomes with everyone else's, and widening the share only if nothing got worse.
- Facts:
  - The comparison uses quality signals because only those reveal a wrong answer. (S9)
  - Made-up steps: 5%, then 25%, then 100%. (S9, made up)
  - Hodgson's Feature Toggles article on martinfowler.com covers canary releasing. (S3, testing fact-check)
  - Lomem has no canary. (S9)
  - A mature version compares canary groups automatically. (S9)
- Relations: C24 uses C25, C26, C27; C24 follows C7.

### C25 · Quality signals
- Definition: Measures of what users did with an answer (sent, edited, discarded, retried, thumbs-down).
- Facts:
  - Error rates and latency are not quality signals, because a bad draft is still a fast 200. (S9)
  - Readers found "quality signals" only illustrated by example in an earlier draft. (testing)
  - The canary's bar uses one quality signal, the discard rate. (S9, made up)
  - How implicit signals such as edit distance turn into a pass/fail bar is not covered by the inputs. (testing)
- Relations: C25 is measured from C29 and C30; C25 decides C24.

### C26 · Sticky bucketing (hash of a stable ID)
- Definition: Assigning each user to the canary or control group by hashing a stable ID, so the same user always lands in the same group.
- Facts:
  - Example: `Math.floorMod(customerId.hashCode(), 100) < rolloutPercent`. (S9, made up)
  - Hashing the customer ID keeps each customer in the same group, so one person does not see the two versions alternate. (S9)
- Relations: C26 is part of C24.

### C27 · Sample size and difference threshold
- Definition: The number of observations to wait for, and the gap that counts as "worse", both set before a canary starts.
- Facts:
  - Made-up bar: v8 is worse if its discard rate is more than 3 points above v7's (v7 at 20%). (S9, made up)
  - With a 20% rate, two groups of 1,500 drafts differ by up to about 3 points from chance alone, so the team waits for 1,500 drafts in the v8 group. (S9)
  - Arithmetic check: standard error of the difference = sqrt(2 × 0.2 × 0.8 / 1500) ≈ 0.0146; 1.96 × 0.0146 ≈ 0.029, about 3 points at 95% confidence. (computed here from S9's numbers)
  - How many eval cases are enough before 95% bars mean anything is not answered by the inputs. (testing)
- Relations: C27 limits C24.

### C28 · Edit distance
- Definition: The number of characters a person changed in a draft before sending it.
- Facts:
  - In the canary example `editDistance(draft.text(), sentText)` is logged when the agent acts on the draft. (S9, made up)
  - Newcomer readers did not know "edit distance". (testing)
  - Lomem has an `editDistance` function in `core-drill/text-match.js`, imported by the Overheard generator. (X12)
- Relations: C28 is an implicit C30 signal.

### C29 · Explicit feedback
- Definition: What users give when asked: a thumbs-down, a "report a problem" button, a flag with a reason.
- Facts:
  - Few users ever press it. (S9, S1)
  - Lomem's feedback table holds a rating (satisfaction with sentiment positive, neutral or negative) or a flag with a reason. (X19)
  - Lomem flag reasons: bad_response, wrong_correction, wrong_language, wrong_mastery, ui_bug, other. (X19)
  - Eugene Yan's "Collect user feedback" pattern covers explicit and implicit feedback ("To build our data flywheel"). (S1, testing fact-check)
  - In round 3 the canary example used "thumbs-down" before explicit feedback was defined, and readers flagged it. (testing)
- Relations: C29 is less voluminous than C30; C29 feeds C32 (triage).

### C30 · Implicit feedback
- Definition: Feedback read from what users do (send, edit, discard, retry, accept).
- Facts:
  - Implicit feedback arrives for almost every response, so it carries far more volume than explicit feedback. (S9, S1)
  - Mature feedback collection uses implicit signals (accepted, edited or retried). (S4)
  - Readers listed explicit and implicit as equal; the point that explicit is rare did not land. (testing)
- Relations: C30 feeds C25.

### C31 · Feedback stored with context
- Definition: A feedback row is useful only if it carries the key to the exact exchange it is about and a snapshot of state at the moment of the click.
- Facts:
  - `session_id` and `turn_index` say which session and which turn the complaint is about. (S9, X19)
  - `session_id` is a free-form string, not a foreign key. (X19, testing)
  - Session plus turn finds the exact exchange only where the session's turns are stored; there is no evidence Lomem stores every turn. (S9, testing)
  - `server_context` is a JSON snapshot of the session's state taken by the server at the moment of the click, so the row keeps it after the session moves on. (S9, X19)
  - Only the AI tutor session type registers a context resolver; it stores the turn number and the learner's level and languages; other session types store null. (X20, X21, testing)
  - The AI tutor resolver reads the live in-memory session and returns null when the session is not found or belongs to another user. (X21)
  - A resolver error is swallowed and stored as null. (X20)
  - `client_context` is a JSON snapshot of client-side context. (X19)
  - `status` says where the report stands in triage. (S9, X19)
  - `idempotency_key` is unique and prevents duplicate submissions. (X19)
  - A thumbs-down without these cannot be reproduced and cannot become a test case. (S9)
- Relations: C31 is what C32 (triage) reads; C31 uses C3 or C4 as key.

### C32 · Triage
- Definition: A person checks a flagged or failed answer to decide whether the model was really wrong.
- Facts:
  - If the model was not wrong, the report is closed as won't-fix. (S9)
  - When two answers could both be right, the person decides which ones the eval accepts, and the case lists all of them. (S9)
  - Lomem triage statuses: open, acknowledged, investigating, resolved, wont_fix. (X19)
  - Lomem's admin feedback detail shows the row plus up to 50 analytics events of the same user and session and up to 20 objective-progress rows. (X20)
  - Readers did not know "triage" or "triage queue". (testing)
- Relations: C32 feeds C33.

### C33 · Data flywheel
- Definition: The loop in which each round of real use produces cases that make the next change safer.
- Facts:
  - A confirmed failure is written down as a new eval case with its real input and the correct answer, and the next prompt or model change must pass it. (S9)
  - In Lomem this is done by hand, and the cases live in a file next to the gate script (`judge-gate-fixture.ts`). (S9, X18)
  - Lomem's level-chat plan: every misplacement found becomes a regression case in `policy.test.ts`. (X8)
  - Mature: failures triaged into eval datasets. (S4)
  - In the full request path, failures flow into offline eval datasets, which gate the next prompt or model change in CI. (S4)
  - The Java analogy: a dead-letter queue whose parked messages become test fixtures; a dead-letter queue is where messages that failed processing are parked. (S9, S4)
  - The research analogue is product analytics plus a dead-letter queue that becomes test fixtures. (S4)
  - Readers did not know "dead-letter queue" in round 2. (testing)
  - Lomem's `scenario-judge-precision-check.mts` is a hand-written, LLM-calling regression that reproduces the PR #227 false-accept and asserts it is now rejected (a production failure kept as a test, for the scenario judge, not this block's features). (S5 §7c, `~/projects/lomem/apps/tunatutor/backend/scripts/scenario-judge-precision-check.mts:1-12`, main)
- Relations: C33 adds to C5; C33 is fed by C32.

### C34 · Drift
- Definition: Quality getting worse with no deploy of yours.
- Facts:
  - The provider can update the model behind the same name, often without notice. (S9)
  - Quality drifts as provider models update, user inputs change or the corpus goes stale. (S4)
  - Only a scheduled rerun catches a silent change. (S9)
  - Mature observability adds drift alerts on score distributions. (S4)
  - Lomem's generator-fidelity eval writes a per-generator, per-level "DRIFT REPORT". (S5 §7e)
  - Neither round-1 reader mentioned rerunning the eval when the provider silently changes the model. (testing)
- Relations: C34 is caught by C35; C34 is why the checks never finish.

### C35 · Scheduled rerun
- Definition: Running the eval on a schedule even when nothing in your code changed.
- Facts:
  - Lomem's gate is run by hand today. (S9)
  - No Lomem CI workflow references the gate script or the guard-rates script (checked: the only references are the scripts themselves, the code and ADR-049). (X17, X11)
  - The smallest scheduled version is a weekly CI job that runs the eval and alerts the feature's owner when a bar is missed. (S9)
  - Cost of a run is cases times price per call; made up: 300 cases at $0.002 a call is $0.60 a run. (S9, made up)
  - If a rerun misses a bar, the flag goes back off, users get the old behaviour, and the failing cases stay in the eval. (S9)
  - Readers did not learn what to do when a scheduled rerun fails in an earlier draft. (testing)
- Relations: C35 detects C34; C35 can turn C7 off; C35 depends on C23.

### C36 · Flag service
- Definition: A server that changes flags at runtime, per share of users, without a deploy.
- Facts:
  - Example named: Unleash. (S9)
  - A mature version keeps flags in a flag service and compares canary groups automatically. (S9)
  - Lomem has no LaunchDarkly-style flag service. (S5 §13)
  - Readers did not know "flag service". (testing)
- Relations: C36 is the mature form of C7 and the runtime home of C24's `rolloutPercent`.

### C37 · Defensive UX
- Definition: UX that sets expectations about an AI answer: citations, confidence, an easy undo.
- Facts:
  - Listed as mature practice for the feedback block. (S4, S1)
  - Eugene Yan's catalogue names "Defensive UX" as a pattern. (S1)
- Relations: C37 sits next to C29 in Yan's catalogue; the inputs give no Lomem example.

### C38 · Dark launch
- Definition: New code deployed to production but not shown to users.
- Facts:
  - Used as the Java analogy for shadow mode. (S9)
  - The Fowler Feature Toggles article does not use the term "dark launch"; the guide does not attribute it to that article. (testing)
  - Readers found it explained only by pointing at Scientist. (testing)
  - In rounds 2 and 3 no reader repeated the Java analogy or where it breaks (two right answers need a comparison rule; quality drifts with no deploy). (testing)
- Relations: C38 is the classic name for C9.

### C39 · Scientist (GitHub library)
- Definition: A library that runs candidate code next to current code, returns the current result and logs mismatches.
- Facts:
  - The Scientist README says it returns the control (use) result, compares it with the try block and publishes the results. (S2, testing)
- Relations: C39 implements C9 for deterministic code; C39 lacks C11.

### C40 · Placement chat and level D
- Definition: Lomem's chat in which a tutor model asks the learner a few questions, each aimed at one level, and rules in code turn extracted facts into a level called D that the learner sees.
- Facts:
  - Levels run from A1 (beginner) through A2 and B1 to B2 (upper intermediate). (S9)
  - After each answer, code extracts facts (was the meaning clear, did it use a paragraph, did it speculate) and records whether the learner handled the question. (S9)
  - D comes from `decideLevel(state).level`. (X1)
  - Each question is a probe with a level and a pass rule; `probesAt(level)` gives the probes of a level. (X3)
  - Turn outcomes include handled, partial, breakdown; a breakdown can have cause `no_data`. (X3, X4)
  - The plan estimates one assessment at about $0.023 in model calls, of which the judge (Flash, once, 5k in, 0.5k out) is $0.003. (X8)
  - Readers asked about A2 and B1 when only A1 and B2 were glossed (round 2), and did not know `decideLevel(state)` or "state" (rounds 2-3). (testing)
- Relations: C40 is the domain of C10 and C11; C40 is part of C45 (Lomem).

### C41 · Extracted facts and pass rule
- Definition: Facts are fields a rater model fills in about an answer (text type, features, lexical range, meaning clear); a pass rule is code that says whether facts meet a level.
- Facts:
  - B2 facts in the golden cases: textType "paragraph", features "speculation" and "consequence", lexicalRange "adequate". (X4)
  - `meaningClear` values used by acceptJudge: "effortful", "no". (X3)
  - Readers did not know "fact rows", "probe-tagged transcript", "spec §6.2". (testing)
- Relations: C41 is the evidence C11 checks.

### C42 · Usage context (cost-accounting context)
- Definition: The record of who pays for a model call that Lomem requires on every call.
- Facts:
  - The gate script uses `LLMSystemUsageContext` with `system: true`, `conversationType: "translation_judge_gate"` and a reason. (X17)
  - A missing usage context is one of the two undegradable errors. (X6)
  - Readers did not know "cost-accounting context". (testing)
- Relations: same concept as gateway.C16; the gate's form is gateway.C18 (system usage context); C42 relates to C14 (see gateway.C37, gateway.C39).

### C43 · Staging database
- Definition: The non-production database the gate pulls real learner answers from.
- Facts:
  - The gate takes real learner answers that the old prompt graded, pulled from the staging database via `tunatutor pull-staging-data`. (S9, X17)
  - Whether the staging database holds real learner data was not stated; a reader asked. (testing)
- Relations: C43 feeds C19.

### C44 · Overheard degrade chain
- Definition: What Lomem's listening-exercise generator does when guards refuse its tries.
- Facts:
  - A refused exercise is generated again, which is another paid model call. (S9)
  - Up to 3 tries (`MAX_GENERATION_ATTEMPTS = 3`); a checkpoint gets up to 2 extra tries (five in all) while every try so far was a give-away. (X12)
  - A refusal's reason goes into the next try's prompt. (X12)
  - After the tries run out, the best refused try that may still ship is served: clean, else QUALITY, else REPEAT, never GIVEAWAY. (X12, X13)
  - If none may ship, the request fails with a 503 ("a clean 503, which the client retries"). (X12)
  - An earlier draft wrongly said a 503 always follows three failed tries. (testing)
- Relations: C44 is why C17 matters: an enforced guard that fires often lengthens C44.

### C45 · Lomem and tunatutor
- Definition: Lomem is the author's own project, the repo at `~/projects/lomem`; tunatutor is its language-learning app, under `apps/tunatutor/`, from which every real code example in this block comes.
- Facts:
  - The examples come from a language-learning app; the long draft names it as "the author's own project, used for the real code below". (S9)
  - Lomem session types named in this block are values of the `SessionType` enum: `ai_tutor`, `translation_drill`, `overheard`; the level chat lives under `use-cases/level-chat/`, not `session-types/`. (X21, K2, K7, K12; `~/projects/lomem/apps/tunatutor/backend/prisma/schema.prisma:39-49`, main)
  - Readers did not know "Lomem" or "tunatutor": the product was never introduced and tunatutor appeared only in paths (round 1); "session-types" was unknown in round 3. (testing)
- Relations: C45 holds C40, C16, C20 and C31.

## Components

| id | name | role | inputs | outputs | where it lives |
|---|---|---|---|---|---|
| K1 | Placement rules (`decideLevel`) | Turns stored facts into level D, the level the learner sees | chat state | level D, nearNext | `apps/tunatutor/backend/src/use-cases/level-chat/policy.ts` |
| K2 | Shadow judge (`runLevelChatJudge`) | Calls the judge model once per chat, compares, stores; never shows its result | chat id, state, turns | `judgeLevel`, `judgeWouldChange` or null | `level-chat/judge.ts` at 8fa41788f (removed in bdd9ab7b8) |
| K3 | Background runner (`defaultBackground` / `runInBackground`) | Runs the judge off the request path and logs its failures | a promise | nothing (log line on failure) | `level-chat/level-chat-turn.ts` at 8fa41788f |
| K4 | Judge claim (`claimLevelChatJudge`) | Atomic compare-and-set so the judge starts at most once per chat | chat id, time | true if claimed | `repositories/level-chat.repository.ts` at 8fa41788f |
| K5 | Comparison rule (`acceptJudge`) | Decides whether the judge's different level is credible | D, judge opinion, rows, ctx | verdict, level, judgeWouldChange | `level-chat/policy.ts` at 8fa41788f |
| K6 | Judge columns | Store the shadow result and the comparison | judge result | `judge_level`, `judge_would_change`, `judge_started_at` | `level_chats` table; added in migration `20261013140000_level_chat`, dropped in `20261013160000_level_chat_drop_judge` |
| K7 | Overheard content generator | Generates an exercise with up to 3 tries against guards, serves best fallback or 503 | generation input | exercise or `ServiceUnavailableError` | `session-types/overheard/engine/content-generator.ts` |
| K8 | Guards and `GUARD_MODES` | Code checks with a per-guard mode, enforce or log | parsed item | guard hits | `session-types/overheard/engine/guards.ts` |
| K9 | Guard log and tally | Logs every refusal and would-be refusal; per-call summary with `rejections` and `wouldReject` | guard name, mode | log lines | `session-types/overheard/engine/guard-log.ts` |
| K10 | Fallback ranker | Ranks refused tries: clean, quality, repeat, giveaway, unusable | guards failed | rank, chosen fallback | `session-types/overheard/engine/fallback-rank.ts` |
| K11 | Guard-rates script | Measures each guard's would-reject rate with real paid calls | languages, bands, counts | table per guard per cell, verdict per log guard | `apps/tunatutor/backend/scripts/overheard-guard-rates.ts` |
| K12 | Translation grader reply parser (`parseJudgeReply`) | Validates the grader reply; drops marks while the flag is off | raw reply, options | verdict, score, focus, why, marks or null, weak | `session-types/translation-drill/engine/judge-reply.ts` |
| K13 | Marks flag `TD_JUDGE_MARKS` and its test | Holds the marks back; test fails if flipped by accident | none | boolean false | `judge-reply.ts:20`, `judge-reply.test.ts:13-15` |
| K14 | Translation judge gate | Eval with four bars that decides the marks flag | staging rows, fixture | PASS/FAIL per check, hand-check table | `apps/tunatutor/backend/scripts/translation-judge-gate.ts` |
| K15 | Gate fixture | Hand-written eval cases with known right answers (36 rows) | none | fixture rows | `session-types/translation-drill/engine/judge-gate-fixture.ts` |
| K16 | Feedback table | Stores explicit feedback with session, turn, contexts and triage status | submission | `feedback` row | `apps/tunatutor/backend/prisma/schema.prisma:2027-2070` |
| K17 | Feedback service | Submits feedback, captures server context, admin list, detail, update | request, user id | feedback rows, DTOs | `apps/tunatutor/backend/src/services/feedback.ts` |
| K18 | AI tutor context resolver | Supplies `server_context` for ai_tutor sessions | session id, user id | turn number, level, languages | `apps/tunatutor/backend/src/session-types/ai-tutor/index.ts:134-148` |
| K19 | Level-chat plan | Design: judge in shadow at launch, real check, risks, costs | none | spec text | `docs/plans/2026-10-13-level-chat-assessment.md` |
| K20 | Canary router (made up) | Picks prompt version per customer by hash and rollout percent | customer id, rolloutPercent | prompt version | generic (S9 Java sketch) |
| K21 | Trace log (made up) | Records trace, version, customer, outcome, edit distance, thumbs-down | trace id, events | rows | generic (S9 Java sketch) |
| K22 | Shadow service (made up) | `@Async` shadow grade, compare, save | chat, current level | shadow row | generic (S9 Java sketch) |
| K23 | Flag service | Runtime flags per share of users | flag config | flag value per user | product, for example Unleash (S9) |
| K24 | Scheduled eval job | Weekly rerun of the eval, alert on missed bar | eval cases | pass/fail, alert | generic, proposed; not in Lomem (S9) |
| K25 | Scientist | Runs candidate next to control, returns control, publishes mismatches | control and candidate blocks | control result, mismatch events | library (S2) |

## Flows

### F1 · Shadow judge in the placement chat (Lomem, commit 8fa41788f, removed in bdd9ab7b8)
Purpose: get a second-opinion level from a judge model on every real placement chat without changing what the learner sees. Trigger: a chat turn that reaches the wind-down stage (`state.stage === "S4"`), or a forced close (`done`), while `judge_started_at` is null.

- F1.1 · Learner → chat route: sends an answer | condition: any turn | data: learner text, chip | ref: X2
- F1.2 · Chat code → rules: compute the next move and the reply; D stays the level shown | condition: always | data: state | ref: X2, K1
- F1.3 · Chat code: build `thisTurn` (idx, tutor line, learner text, chip, probe id, merged facts, outcome, outcome cause) | condition: always | data: one JudgeSourceTurn | ref: X2 (`level-chat-turn.ts:350-359`)
- F1.4 · Chat code: check the start condition | condition: `state.stage === "S4" || done`, and `!chat.judgeStartedAt` | data: none | ref: X2 (`:406`)
- F1.4a · Chat code: skip the judge | condition: not at stage `"S4"` and not done, or the judge already started | → continues at F1.8 | ref: X2
- F1.5 · Chat code → DB: `claimLevelChatJudge` sets `judge_started_at` only where it is null | condition: always | data: chat id, now | ref: X2 (`:407`), X24
- F1.5a · Chat code: do not start the judge | condition: claim returned false (another request claimed it) | → continues at F1.8 | ref: X2 (`:408`), X24
- F1.6 · Chat code → background runner: `run(runLevelChatJudge(...))` without awaiting | condition: claim succeeded | data: chat id, state, all turns plus this turn; deps `json`, `saveLevelChatJudge` | ref: X2 (`:409-415`)
- F1.7 · Background runner: (background) → continues at F2.1 | ref: X1
- F1.8 · Chat code → learner: return the tutor's reply without waiting for the judge | condition: always | data: reply | ref: X2 (`:418`), S9

### F2 · One shadow judge run (`runLevelChatJudge`)
Purpose: call the judge, compare its level with D through the comparison rule, store both. Trigger: F1.6.

- F2.1 · Judge: keep only turns where the learner gave text (taps and silences carry no answer) | condition: always | data: answered turns | ref: X1 (`judge.ts:49-50`)
- F2.1a · Judge: return null, store nothing, log nothing | condition: no answered turns | ref: X1 (`:51`)
- F2.2 · Judge: map answered turns to JudgeTurn (n = idx + 1, tutor line, probe task, learner answer, chip, facts) | condition: always | data: judge input; never D | ref: X1 (`:52-59`)
- F2.3 · Judge → gateway → model: JSON call kind "judge", model `gemini-2.5-flash`, temperature 0.2, max tokens 600, timeout 15000 ms, schema `judgeSchema` | condition: always | data: system prompt, user message | ref: X1 (`:61-75`), X5
- F2.3a · Judge: call throws (timeout, provider error, schema mismatch) | condition: error | → continues at F2.8 | ref: X1 (`:98`)
- F2.4 · Judge: validate the level | condition: `isLevelChatLevel(answer.level)` false | → return null, nothing stored, nothing logged | ref: X1 (`:76`)
- F2.5 · Judge: build rows for acceptJudge from ALL turns that have a known probe (n, probe level, outcome or "no_data", facts, cause) | condition: always | data: JudgeRow[] | ref: X1 (`:77-89`)
- F2.6 · Judge → rules: `decided = decideLevel(state).level` (D) | condition: always | data: D | ref: X1 (`:90`)
- F2.7 · Judge → acceptJudge: compare (continues at F3.1, returns at F3.end) | condition: always | data: D, {level, citedTurns}, rows, {inputMode, language} | ref: X1 (`:91-94`)
- F2.7b · Judge → DB: `saveJudge(levelChatId, {judgeLevel, judgeWouldChange})` and return the result | condition: compare returned | data: two columns | ref: X1 (`:95-97`)
- F2.7c · Judge: save throws | condition: DB error | → continues at F2.8 | ref: X1
- F2.8 · Judge: `rethrowIfUndegradable(err)` | condition: any caught error | ref: X1 (`:99`), X6
- F2.8a · Judge: rethrow | condition: code `FST_MISSING_USAGE_CONTEXT` or `FST_DAILY_SPEND_CAP` | → background runner logs "level chat: background task failed"; the learner is unaffected | ref: X6, X2 (`:150-152`)
- F2.9 · Judge: log warn "level chat: the shadow judge failed — D stands, nothing is stored", return null | condition: any other error | ref: X1 (`:100-104`)
- F2.10 · DB: `judge_started_at` stays set after any failure, so the judge is never retried for that chat | condition: F2.1a, F2.4, F2.8a, F2.9 | ref: X24 (inferred from code)

### F3 · Comparison rule (`acceptJudge`)
Purpose: decide whether the judge's level would credibly replace D. Trigger: F2.7.

- F3.1 · Rule: `gap = levelIndex(judge.level) - levelIndex(decided)` | ref: X3 (`policy.ts:1263`)
- F3.2 · Rule: return verdict "same", level D, `judgeWouldChange: false` | condition: gap = 0 | ref: X3 (`:1264`)
- F3.3 · Rule: return "rejected", level D, false | condition: |gap| > 1 | ref: X3 (`:1265`)
- F3.4 · Rule: `cited` = rows whose n is in `citedTurns` | condition: |gap| = 1 | ref: X3 (`:1266`)
- F3.5 · Rule (up): `meeting` = cited rows with facts that meet a pass rule of some probe at the judge's level | condition: gap = 1 | ref: X3 (`:1268-1270`)
- F3.6 · Rule (up): `realBreakdown` = any row (cited or not) at the judge's level with outcome "breakdown" and cause not "no_data" | condition: gap = 1 | ref: X3 (`:1271-1273`)
- F3.7 · Rule (up): return "accepted_up", judge level, true | condition: `meeting.length >= 2 && !realBreakdown` | ref: X3 (`:1274-1275`)
- F3.7a · Rule (up): return "rejected", D, false | condition: otherwise | ref: X3 (`:1277`)
- F3.8 · Rule (down): `down` = some cited row at level D with outcome "breakdown" or `meaningClear` "effortful" or "no" | condition: gap = -1 | ref: X3 (`:1279-1283`)
- F3.9 · Rule (down): return "accepted_down", judge level, true if `down`; else "rejected", D, false | ref: X3 (`:1284`)
- F3.end · back to F2.7b | ref: X1 (`judge.ts:91-95`)

### F4 · Shadow readout and go/no-go decision
Purpose: decide whether a shadow behaviour goes live or is dropped. Trigger: enough shadow runs have accumulated (made up: a few hundred chats).

- F4.1 · Team: write the bar before reading | condition: before F4.3 | data: e.g. "the judge is right in at least 30 of the 38" | ref: S9 (made up)
- F4.2 · Analyst → DB: count rows with `judge_would_change = true` | data: 38 of 412 (made up) | ref: S9
- F4.3 · Person: read each disagreeing chat and note whether the judge or the rules placed the learner right | ref: S9
- F4.3b · Lomem plan alternative: 10 to 20 tester chats placed blind by a teacher; go live only if judge-adjusted levels agree with the teacher more often than D alone | ref: X8
- F4.4 · Team: flip a flag so learners see the accepted judge level | condition: bar cleared | → L2 live | ref: S9
- F4.4a · Team: drop the judge | condition: bar missed, or plan risk "Judge never leaves shadow mode" | ref: S9, X8
- F4.4b · Team: drop the judge before any numbers | condition: other decision (Lomem #624, reason not recorded) | data: migration drops three columns | ref: X7
- F4.5 · Users: see no change from the removal, because the judge only ran in shadow mode | ref: S9

### F5 · Overheard exercise generation with guard modes
Purpose: serve a listening exercise that passes the enforced guards, while log-mode guards only record. Trigger: a drill run requests an item.

- F5.1 · Generator: try n = 0 | ref: X12 (`content-generator.ts:527`)
- F5.2 · Generator → model: generate one item, with the previous refusal reason in the prompt | condition: n < 3, or checkpoint and n < 5 and every banked try so far is a giveaway | data: input, previous refusal | ref: X12 (`:528-545`)
- F5.2a · Generator: loop ends | condition: neither regular nor extra try allowed | → continues at F5.9 | ref: X12 (`:533`)
- F5.3 · Guards: compute hits for every guard; each hit is tallied with its mode | data: guard hits | ref: X12 (`:541-543`), X10
- F5.3a · Guard in log mode: write "overheard: guard rejection" with `mode: "log"`, count in `wouldReject`, do NOT refuse | condition: `GUARD_MODES[g] === "log"` | → item continues as if the guard passed | ref: X10, X12 (`enforcedHits`, `:250-253`)
- F5.3b · Guard in enforce mode: count in `rejections`, item is refused | condition: `GUARD_MODES[g] === "enforce"` | ref: X10, X12
- F5.4 · Generator: no parsed item | condition: unparsable or cut-off reply | → next try at F5.2 | ref: X12 (`:548`)
- F5.5 · Generator: add repeat hits (line, opening, question repeated in this run) | ref: X12 (`:554-573`)
- F5.6 · Generator: return the clean item, outcome "clean" | condition: no enforced or repeat failures | ref: X12 (`:574-577`)
- F5.7 · Generator: rank the refused try (quality, repeat, giveaway, unusable) and bank it unless unusable | ref: X12 (`:582-583`), X13
- F5.8 · Generator: next try → continues at F5.2 | ref: X12 (`:527`, loop)
- F5.8a · Generator: model call throws | condition: error | → rethrow if undegradable (spend cap, missing usage context); else serve best banked try (F5.9) or throw 503 "Overheard generation failed" | ref: X12 (`:585-591`)
- F5.9 · Generator: serve the best banked try that may ship: quality before repeat, never giveaway | condition: one exists | ref: X12 (`:594-595`), X13
- F5.10 · Generator: throw `ServiceUnavailableError` (503) "only give-away items after retries" or "no usable item after retries"; the client retries | condition: nothing may ship | ref: X12 (`:596-599`)
- F5.11 · Generator: log the per-call summary with `rejections`, `wouldReject`, total and outcome | condition: always (finally) | ref: X12 (`:600-603`), X10

### F6 · Guard measurement and switch decision
Purpose: decide whether a log-mode guard may enforce. Trigger: the owner says go (header: "Run it only when the owner says go.").

- F6.1 · Developer: run `pnpm --filter @tunatutor/backend exec tsx scripts/overheard-guard-rates.ts` | ref: X11 (`:20-22`)
- F6.1a · Script: refuse and exit 1 | condition: `NODE_ENV=production` | ref: X11 (`:107-111`)
- F6.1b · Script: exit 1 "no founder account found" | condition: no founder user | ref: X11 (`:113-117`)
- F6.2 · Script: save `GUARD_MODES`, set every guard to enforce | ref: X11 (`:125-127`)
- F6.3 · Script → generator → model: per language and band, generate N items with real paid calls (French 50, others 25 by default) | data: items, guard hits per item | ref: X11 (`:131-137`)
- F6.4 · Script: restore `GUARD_MODES` (finally) | ref: X11 (`:139-141`)
- F6.5 · Script: print per cell the share of items not clean, 503 share and no-reveal share | ref: X11 (`:143-146`)
- F6.6 · Script: print per guard the would-reject rate per cell (share of items where the guard fired on any try) | ref: X11 (`:148-154`)
- F6.7 · Script: for each log guard print the worst cell and "-> ready to enforce" if under 15%, else "-> loosen or drop first" | ref: X11 (`:156-161`)
- F6.8 · Developer: switch the guard to enforce, one line in `GUARD_MODES`, plus the mode test | condition: worst cell under 15% | ref: X9, X14
- F6.8a · Person: read a sample of what the guard refused | condition: rate at or above the bar | ref: S9
- F6.8b · Team: loosen or drop the guard | condition: the refused exercises are fine (guard too strict) | ref: S9, X11
- F6.8c · Team: fix the generation prompt | condition: the refused exercises are really bad | ref: S9
- F6.9 · Real record: "end punctuation" measured 0 percent in every language and band on 2026-10-07 and is enforced | ref: X9

### F7 · Translation grading in production, with the marks flag off
Purpose: grade a learner's translated sentence; keep marks hidden until the gate passes. Trigger: the learner submits an answer.

- F7.1 · Drill → pre-pass: accept an exact match of key or variants without a model call | condition: exact match | → graded right (score 100) | ref: `judge-adapter.ts:65-77` (main), S5 §6a, X18 (`:7-8`)
- F7.2 · Drill → gateway → model: grade with the `arc` prompt | condition: no exact match | ref: X17, X15
- F7.3 · Parser: `marksEnabled = opts.marksEnabled ?? TD_JUDGE_MARKS` (false) | ref: X15 (`judge-reply.ts:108`)
- F7.3a · Parser: throw 503 "could not be read"; nothing is saved and the learner can retry | condition: unparsable and not salvageable | ref: X15 (`:129-132`)
- F7.3b · Parser: throw 503 "had no verdict" | condition: no boolean `correct` | ref: X15 (`:147`)
- F7.4 · Parser: `marks = null` | condition: flag false | ref: X15 (`:155`)
- F7.4a · Parser: marks `[]` if right, else placed marks or typed-word fallback | condition: flag true (gate passed) | ref: X15 (`:156-160`)
- F7.5 · Parser: keep focus (one of sixteen areas or null) and why (one sentence, never giving the answer) | ref: X15 (`:162-170`)
- F7.6 · Parser: `weak = []` | condition: flag false | ref: X15 (`:172-174`)
- F7.7 · Phone: draws nothing for `marks: null` | ref: X15 (`:16-17`)

### F8 · Releasing the marks flag through the gate (TR4)
Purpose: flip `TD_JUDGE_MARKS` only when the eval clears its four bars. Trigger: the TR4 task.

- F8.1 · Developer: `tunatutor pull-staging-data` fills the local DB | ref: X17 (`:15-16`)
- F8.2 · Developer: `node --env-file=.env --import tsx scripts/translation-judge-gate.ts` | ref: X17 (`:18`)
- F8.3 · Gate: load real non-exact rows, stratified to at most 200 across languages, plus the 36 fixture rows | ref: X17 (`:268-270`), X18
- F8.4 · Gate → model: run old (`card`) and new (`arc`) prompts on every row; 3 workers | ref: X17 (`CONCURRENCY = 3`)
- F8.5 · Gate: check 1, old vs new agreement on real rows ≥ 95% AND new vs fixture expected ≥ 95% AND 0 paraphrases marked wrong | ref: X17 (`:276-288`)
- F8.6 · Gate: check 2, marks placeable on the learner's words ≥ 95% | ref: X17 (`:295-299`)
- F8.7 · Gate: check 4, replies within 2500 ms ≥ 95%; also prints p50 and p95 latency | ref: X17 (`:53-54`; check 4 at `translation-judge-gate.ts:301-305`, not in the excerpt)
- F8.8 · Gate: check 3, print every marked word in a hand-check table | ref: X17 (`:307-325`)
- F8.9 · Person: count the really wrong marked words; bar ≥ 90%; the script says "need >= 20 hand-checked to turn marks on" | ref: X17 (`:329`)
- F8.10 · Person: write the count into the pull request beside the output | ref: S9 (unverified)
- F8.11 · Developer: flip `TD_JUDGE_MARKS` to true and change the flag test in the same PR | condition: all four bars pass | ref: X15, X16, S9
- F8.11a · Developer: flag stays false | condition: any bar fails | ref: S9
- F8.12 · Codebase: old behaviour code stays until the new one has passed several later reruns | ref: S9

### F9 · Canary rollout of a new prompt version (made up, Spring)
Purpose: widen prompt v8 from 5% to 100% only while quality is no worse. Trigger: v8 cleared its eval.

- F9.1 · Team: write the bar and sample size first: v8 worse if discard rate > v7's + 3 points; wait for 1,500 v8 drafts | ref: S9 (made up)
- F9.2 · Service: `useV8 = floorMod(customerId.hashCode(), 100) < rolloutPercent` (5) | ref: S9 (made up)
- F9.3 · Service → model: draft with "draft-reply@8" or "draft-reply@7" | ref: S9
- F9.4 · Service → trace log: record trace ID, prompt version, customer ID | ref: S9
- F9.5 · Support agent → service: sends, edits or discards the draft; outcome and edit distance logged by trace ID | ref: S9
- F9.5b · Support agent → service: thumbs-down logged by trace ID | condition: agent clicks thumbs-down | ref: S9
- F9.6 · Team: compare discard rates of v8 and v7 groups | condition: 1,500 v8 drafts reached | ref: S9
- F9.7 · Team: widen to 25, then 100 | condition: v8 not worse | ref: S9
- F9.7a · Team: `rolloutPercent` back to 0, read the bad drafts to find out why | condition: v8 worse | ref: S9
- F9.8 · Team: does not use error rates or latency as the decision signal | ref: S9

### F10 · Feedback capture in Lomem
Purpose: store a rating or flag tied to its session and turn. Trigger: a user submits feedback.

- F10.1 · Client → API: submit feedback (session id, session type, language, type, sentiment or flag reason, turn index, note, client context) | ref: X20, X19
- F10.2 · Service: build idempotency key from user and input | ref: X20 (`feedback.ts:59`)
- F10.3 · Service → resolver: capture server context for the session type | ref: X20 (`:61-65`)
- F10.3a · Service: server context null | condition: no resolver registered for the type (every type except ai_tutor) | ref: X20 (`:44-45`)
- F10.3b · Service: server context null | condition: resolver throws | ref: X20 (`:48-50`)
- F10.3c · AI tutor resolver: null | condition: session not in memory or belongs to another user | ref: X21
- F10.4 · Service: resolve conversation session id from analytics events | ref: X20 (`:67-71`)
- F10.5 · Service → DB: create row with status "open" | ref: X20 (`:73-94`)
- F10.6 · Service: write an analytics event, fire-and-forget | ref: X20 (`:96`)

### F11 · Triage to eval case (the flywheel)
Purpose: turn a confirmed production failure into a permanent eval case. Trigger: a flagged or failed answer.

- F11.1 · Admin: open the feedback row; detail shows the row plus up to 50 analytics events for user and session | ref: X20
- F11.2 · Admin: find the turn through `turn_index` (or the trace ID in a system without stored turns) | ref: S9
- F11.3 · Admin: decide whether the model was really wrong | ref: S9
- F11.3a · Admin: set status won't-fix | condition: model not wrong | ref: S9, X19
- F11.4 · Admin: decide which answers the eval accepts when two could be right | ref: S9
- F11.5 · Admin: set status resolved, add an eval case with the real input and the correct answer(s) | condition: confirmed failure | ref: S9
- F11.6 · Eval: every later eval run checks the case; the next prompt or model change must pass it | ref: S9

### F12 · Scheduled rerun and drift response (proposed; not in Lomem)
Purpose: catch silent model changes. Trigger: a schedule (smallest version: weekly CI job).

- F12.1 · CI → eval: run all cases with real calls | data: cost = cases × price per call | ref: S9
- F12.2 · CI → owner: alert | condition: a bar is missed | ref: S9
- F12.3 · Owner: turn the flag back off; users get the old behaviour | condition: bar missed | ref: S9
- F12.4 · Eval: failing cases stay in the eval | ref: S9
- F12.5 · Owner: no action | condition: all bars pass | ref: S9

### F13 · Smallest version in one Spring service (made up)
Purpose: shadow, flag and feedback in one service. Trigger: a placement request.

- F13.1 · Controller → rules: `current = rules.level(chat)` | ref: S9 (made up)
- F13.2 · Service: `return candidateOrCurrent(chat, current)` | condition: `NEW_GRADER_ON` true (after the eval) | ref: S9 (made up)
- F13.3 · Service → shadow: `shadow.shadowGrade(chat, current)` fire and forget | condition: flag false | ref: S9 (made up)
- F13.4 · Service → user: return current | ref: S9 (made up)
- F13.5 · Shadow (`@Async`, separate pool) → model: `grader.grade(chat)` read-only | ref: S9 (made up)
- F13.6 · Shadow: `comparisonRule.candidateWins(current, candidate)` | ref: S9 (made up)
- F13.7 · Shadow → DB: `saveShadow(chat.id(), candidate, candidateWins)` | ref: S9 (made up)
- F13.7a · Shadow: log warn "shadow grader failed, current level stands" | condition: any exception | ref: S9 (made up)
- F13.8 · Plus: a thumbs-down endpoint storing trace ID (or session and turn) with a snapshot of input and output; an eval file confirmed failures are appended to by hand; a scheduled job that reruns the eval | ref: S9

### F14 · Scientist experiment (classic analogue)
Purpose: compare candidate code with current code in production. Trigger: a call to the instrumented method.

- F14.1 · App: run the control ("use") block and the candidate ("try") block | ref: S2
- F14.2 · Scientist: compare results | ref: S2
- F14.3 · Scientist: publish the results (mismatches) | ref: S2
- F14.4 · App: return the control result | ref: S2
- F14.5 · Breaks for models: every mismatch counts as a bug, though two model answers can both be right | ref: S9

## States

### L1 · Shadow judge run, per chat (Lomem level_chats row)
- States:
  - not started: `judge_started_at` null.
  - claimed: running; `judge_started_at` set, judge columns null.
  - stored: `judge_level` and `judge_would_change` set.
  - ended without result: `judge_started_at` set, judge columns stay null (failure, invalid level, no answered turns).
  - columns gone: migration `20261013160000_level_chat_drop_judge` removed the judge; no state is kept.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| not started | turn reaches stage `"S4"` or done | claim succeeds | claimed | background run starts | F1.4-F1.6, X2, X24 |
| not started | turn reaches stage `"S4"` or done | claim fails | not started (for this request) | nothing | F1.5a |
| claimed | judge returns valid level, save succeeds | none | stored | two columns written | F2.7b |
| claimed | error, invalid level or no answered turns | none | ended without result | warn log (errors only) | F2.1a, F2.4, F2.9 |
| any | migration `20261013160000_level_chat_drop_judge` | none | columns gone | judge removed | X7 |

### L2 · Shadow feature lifecycle
- States:
  - shadow: runs on real traffic, result stored, not shown.
  - live: flag on, users see the accepted new result.
  - dropped: code and columns removed.
  - off: rerun missed the bar, flag off; users get the old behaviour.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| shadow | readout | bar written beforehand cleared | live | flag shows the accepted judge level | F4.4, S9 |
| shadow | readout | bar missed | dropped | spend stops | F4.4a, S9, X8 |
| shadow | decision before numbers | none | dropped | no user sees a change | F4.4b, X7 |
| live | rerun misses bar | old code kept | shadow or off | flag off | F12.3, S9 |

### L3 · Guard mode (Overheard)
- States:
  - log: writes the refusal it would have made, lets the item through.
  - enforce: refuses the item.
  - loosened: rule changed.
  - dropped: rule removed.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| (new guard) | added | none | log | would-reject counts in logs | X9, S9 |
| log | rates script | worst cell < 15% | enforce | one-line change plus test change | F6.8, X9, X11, X14 |
| log | rates script | rate ≥ 15%, sample fine | loosened or dropped | none | F6.8b |
| log | rates script | rate ≥ 15%, sample really bad | log (prompt fixed) | prompt change, re-measure | F6.8c |

### L4 · Marks flag `TD_JUDGE_MARKS`
- States:
  - false: marks null, weak empty, verdict, focus and why live.
  - true: marks placed and shown.
  - build fails: an accidental edit to true while the test still asserts false.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| false | TR4's PR | gate bars 1-4 pass; test changed in same PR | true | phone underlines wrong words | F8.11, X15, X16 |
| false | accidental edit | test still asserts false | build fails | none | X16 |
| true | scheduled rerun misses a bar | old behaviour kept | false | users get the old behaviour | F12.3, S9 |

### L5 · Canary stage (made up)
- States:
  - 0%: no customer sees v8; the start, and the rollback when v8 is worse.
  - 5%: hashed 5% of customers see v8.
  - 25%: widened to 25% of customers.
  - 100%: every customer sees v8.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| 0% | eval passed | none | 5% | hashed 5% of customers see v8 | F9.2 |
| 5% | 1,500 v8 drafts | discard rate ≤ v7 + 3 points | 25% | widen | F9.7 |
| 25% | readout | not worse | 100% | widen | F9.7 |
| any | readout | worse | 0% | read the bad drafts | F9.7a |

### L6 · Feedback row status (Lomem)
- States:
  - open: row created on submit.
  - acknowledged: triage status set by an admin.
  - investigating: triage status set by an admin; triage moves it on.
  - resolved: confirmed failure, eval case added.
  - wont_fix: model not wrong.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| (none) | submit | none | open | row created | F10.5, X20 |
| any | admin update | none: the code checks no transition, any of the five statuses may follow any other | any (the given status) | `updateFeedback` sets status and, if given, `adminNote` | `services/feedback.ts:254-265` (main) |
| open or investigating | triage | model not wrong | wont_fix | none | F11.3a |
| open or investigating | triage | confirmed failure | resolved | eval case added | F11.5 |

### L7 · Overheard item request
- States:
  - trying: n of 3, or of 5 at a checkpoint.
  - served clean: a try passed all enforced guards.
  - served fallback: quality or repeat try served.
  - unavailable: 503.
  - error rethrown: model call threw an undegradable error.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| trying | try passes all enforced guards | none | served clean | outcome "clean" | F5.6 |
| trying | try refused | tries left | trying | rank banked, refusal to next prompt | F5.7 |
| trying | tries exhausted | a quality or repeat try banked | served fallback | outcome = rank | F5.9 |
| trying | tries exhausted | only giveaways or nothing | unavailable | 503, client retries | F5.10 |
| trying | model call throws | undegradable | error rethrown | none | F5.8a |

### L8 · Eval case from production
- States:
  - flagged: a flagged or failed answer.
  - triaged: an admin has read it.
  - case added: new fixture row.
  - checked: checked on every run.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| flagged | admin reads | none | triaged | status change | F11 |
| triaged | confirmed failure | none | case added | new fixture row | F11.5 |
| case added | each eval run | none | checked | change must pass it | F11.6 |

## Worked examples

### E1 · acceptJudge golden cases (real, from `policy.test.ts:748-791` at 8fa41788f)
- Values: real test data. Rules level D = B1 in every case except the last.
- Rows: turn 1 = A1 probe, handled; turn 5 = B2 probe, partial, B2 facts (paragraph, speculation, consequence, adequate range); turn 7 = B2 probe, partial, same B2 facts; turn 8 = B1 probe, breakdown, meaning clear "no". (X4)
- Case a (F3.2): judge says B1, cites 5 → verdict "same", level B1, `judgeWouldChange` false.
- Case b (F3.5-F3.7): judge says B2, cites 5 and 7 → both meet a B2 pass rule, no real B2 breakdown → "accepted_up", level B2, `judgeWouldChange` true.
- Case c (F3.7a): judge says B2, cites only 5 → one meeting row < 2 → "rejected".
- Case d (F3.6, F3.7a): judge says B2, cites 5 and 7, but a turn 9 B2 breakdown with cause "facts" exists → "rejected".
- Case e (F3.6, F3.7): same as d but turn 9's cause is "no_data" → does not count → "accepted_up".
- Case f (F3.8-F3.9): judge says A2, cites 8 (B1 probe, meaning not clear) → "accepted_down".
- Case g (F3.9): judge says A2, cites 1 (A1 probe, handled) → "rejected": that turn says nothing against B1.
- Case h (F3.3): D = A2, judge says B2, cites 5 and 7 → two levels apart → "rejected".
- Outcome: only b, e and f would change the shown level; in shadow mode none of them did.

### E2 · Shadow readout (made up)
- Inputs: 412 chats with stored judge results. (S9, made up)
- F4.2: `judge_would_change` true in 38 chats (38 / 412 ≈ 9%).
- F4.1: bar written before reading: judge right in at least 30 of the 38.
- F4.3: a person reads the 38 chats.
- Outcome: if at least 30 → flag on (F4.4); else judge dropped (F4.4a).

### E3 · The real fate of Lomem's shadow judge
- Values: real (git). (X7, testing)
- Added: commit 8fa41788f, PR #622, 2026-10-13 07:25 (+0300).
- Removed: commit bdd9ab7b8, PR #624, 2026-10-13 20:18 (+0300), "The blind shadow judge and its columns are removed (follow-up migration)."
- Migration drops `judge_level`, `judge_started_at`, `judge_would_change`, with the marker "shadow-judge columns were only written by the removed shadow judge; no reader remains".
- Removed before any numbers came in (unverified: whether it ever ran in production or stored rows cannot be shown from the repo).
- Plan risk: "Judge never leaves shadow mode" → "Judge spend with no benefit" → mitigation "Drop the judge if the real check shows no gain". (X8)
- Outcome: no learner saw any change (F4.5).

### E4 · Cognate guard (made up)
- Inputs: line "Le restaurant ferme à dix heures"; right choice "The restaurant closes at ten"; no wrong choice mentions a restaurant. (S9, made up)
- F5.3: the cognate guard fires: "restaurant" in the line matches a content word of the right choice and of no distractor.
- F5.3a: in log mode the item is served and a would-reject is logged.
- F5.3b: in enforce mode the item is refused, ranked GIVEAWAY, never shipped.
- Outcome: the learner could pick the answer by matching one word without understanding the line.

### E5 · What a 15 percent guard bar costs
- Values: derived from the bar. (S9)
- At 15%, about one exercise in seven (1 / 0.15 ≈ 6.7) needs a second paid call.
- Three refusals in a row: 0.15³ = 0.003375, about 3 in 1,000.
- Assumes refusals on successive tries are independent (the inputs do not state this; the next try's prompt carries the refusal reason, so they are likely not independent).

### E6 · End punctuation guard (real)
- Measured 0 percent in every language and band (overheard-guard-rates, 2026-10-07), so it is enforced. (X9, X22)

### E7 · Fallback ranking (real comment)
- Inputs: three tries: one with a mismatched full stop (QUALITY), one opening like an earlier line (REPEAT), one with the answer in the question (GIVEAWAY). (X13)
- F5.9: the QUALITY try ships.
- Variant: if only the GIVEAWAY try exists → F5.10, the app gets a clean 503 and retries.

### E8 · Canary from prompt v7 to v8 (made up)
- Inputs: a Spring service drafts replies to customer emails; a support agent sends, edits or discards each draft. (S9, made up)
- F9.1: bar: v8 worse if discard rate > v7 (20%) + 3 points, i.e. above 23%; wait for 1,500 v8 drafts.
- F9.2: `rolloutPercent` = 5; customer hash mod 100 < 5 → v8.
- F9.5: outcome "sent" or "discarded" and edit distance per trace ID.
- F9.6: compare at 1,500 v8 drafts.
- Outcome: v8 ≤ 23% → 25%, then 100%; v8 > 23% → 0 and read the bad drafts.
- Noise check: two groups of 1,500 at 20% differ by up to about 3 points by chance (1.96 × sqrt(2 × 0.2 × 0.8 / 1500) ≈ 2.9 points).

### E9 · Fixture row from a production failure (real row, made-up story)
- Row (real, `judge-gate-fixture.ts:28`): language "fr", key "J'ai très faim.", variants [], answer "J'ai vraiment faim.", expected "right", markedWords [], note "paraphrase: synonym adverb". (X18)
- Story (made up): a learner types "J'ai vraiment faim" for "I am very hungry" (F7.2); the grader marks it wrong; the learner flags the turn as wrong_correction (F10.1); the developer opens the row, finds the turn through `turn_index` (F11.2), agrees "vraiment" is a fine synonym for "très" (F11.3), sets status resolved and adds the row (F11.5).
- Outcome: every later gate run checks that the grader accepts this answer; because the note starts with "paraphrase", a wrong verdict on it fails check 1c (F8.5).

### E10 · Cost of a scheduled rerun (made up)
- Inputs: 300 cases, $0.002 per call. (S9, made up)
- F12.1: 300 × $0.002 = $0.60 per run.

### E11 · Translation gate bars (real)
- Check 1: old vs new agreement on real rows ≥ 95%; new vs fixture expected ≥ 95%; paraphrase misses = 0. (X17)
- Check 2: marks placeable ≥ 95%. (X17)
- Check 3: marked words really wrong ≥ 90%, by hand; at least 20 hand-checked real rows. (X17)
- Check 4: replies within 2,500 ms ≥ 95%. (X17)
- Sample: up to 200 real non-exact rows, plus 36 fixture rows. (X17, X18)

### E12 · Placement judge cost (real estimate)
- Judge, Flash, once per chat, about 5k tokens in and 0.5k out: $0.003; level chat LLM total about $0.023; voice chat total about $0.10, typed about $0.04. (X8; token counts estimated)

## Variants and options

- Minimal version:
  - A constant flag in code, flipped only by the PR that shows the eval results, with a test that asserts its value. (S9, X15, X16)
  - A shadow call under `@Async` on a separate pool, read-only, with a try/catch that logs and keeps the current result; store the candidate and the comparison. (S9)
  - New checks in log mode until a measured refusal rate is under a bar. (S9)
  - A thumbs-down endpoint that stores the trace ID (or session and turn) with a snapshot of input and output. (S9)
  - Thumbs up or down plus "edit before send", logged against the trace ID. (S4)
  - An eval file that confirmed failures are appended to by hand. (S9)
  - A scheduled job (weekly CI) that reruns the eval and alerts the owner. (S9)
- Mature version:
  - Flags in a flag service (for example Unleash) that changes flags at runtime, per share of users. (S9)
  - Canary groups compared automatically on quality signals. (S9)
  - Implicit signals (accepted, edited, retried) collected for almost every response. (S4)
  - Failures triaged into eval datasets. (S4)
  - UX that sets expectations: citations, confidence, an easy undo. (S4)
  - User feedback attached to traces; drift alerts on score distributions; online eval scores on traces. (S4)
  - Prompt promotion gated on an eval run; rollback moves a label. (S6)
  - Online evals on sampled production traffic; error analysis repeated every 2 to 4 weeks. (S7, via S4)

| id | option | when to choose | cost / risk |
|---|---|---|---|
| V1 | Shadow mode before release | nobody knows whether the new behaviour beats the current one | pays for every shadow call; risk it never leaves shadow (X8) |
| V2 | Ship directly behind a flag after an offline eval | the eval set covers real inputs well | real inputs are more varied than any test set (S9) |
| V3 | Log mode for a new check | refusals cost extra paid calls or can end in a 503 | bad items reach users while in log mode (S9, X9) |
| V4 | Enforce a check immediately | a cheap structural check measured at or near 0% | slow, expensive or broken generation if it refuses often (S9, X12; Lomem enforces cheap structural guards from the start, X22) |
| V5 | Measure refusal rate from production logs | enough traffic per language and level | too sparse at low traffic (S9, unverified for Lomem) |
| V6 | Measure refusal rate with an offline bulk script | low traffic | real paid calls; must be run by hand (X11) |
| V7 | Constant flag in code | small team, few flags, release by PR | each change is a deploy; no per-user share (X15; testing final read on `rolloutPercent`) |
| V8 | Flag service with per-share rollout | canary needed; non-deploy toggling | another service to run (S9 names Unleash); flag clean-up is not from the inputs |
| V9 | Canary on quality signals | enough users for a sample of about 1,500 per group | waiting time; needs implicit signals logged by trace (S9) |
| V10 | Off → on for everyone | too few users for a canary (Lomem) | no live comparison (S9) |
| V11 | Comparison rule in code (acceptJudge) | two different answers can both be right | needs stored facts to check (X3); whether it is too strict or too loose is not measured in the inputs |
| V12 | Human reading of disagreements | judge or candidate is new and untrusted | person time per disagreement (S9) |
| V13 | Key feedback by trace ID | turns are not stored | needs tracing (S9, S4) |
| V14 | Key feedback by session plus turn | turns are stored with the session | breaks if turns are not stored (S9) |
| V15 | Scheduled eval rerun | provider can change the model under the name | cost per run = cases × price per call (S9) |
| V16 | Hand-run eval only (Lomem today) | early, cheap | silent model changes go unseen (S9) |

| name | open source or hosted | what it does here | link |
|---|---|---|---|
| Unleash | open source (unverified: hosting model not in inputs) | flag service that changes flags at runtime per share of users | not given in inputs |
| LaunchDarkly | hosted (unverified) | named only as the kind of flag service Lomem does not have | not given in inputs |
| GitHub Scientist | open source | runs candidate next to control, returns control, publishes mismatches | https://github.com/github/scientist |
| Langfuse | open source | prompt versions and labels, promotion gated on eval, traces with user feedback | https://langfuse.com/docs/prompt-management/overview |
| promptfoo | open source | CI-friendly eval runner for a scheduled rerun | https://github.com/promptfoo/promptfoo |
| Braintrust | hosted | evals and prompt versions | https://www.braintrust.dev/docs |
| LangSmith | hosted | evals, traces, prompt versions | https://docs.smith.langchain.com/ |
| Arize Phoenix | open source | evals and traces | https://github.com/Arize-ai/phoenix |
| Datadog LLM Observability | hosted | traces, drift monitoring | https://docs.datadoghq.com/llm_observability/ |
| Spring AI evaluation | open source | evaluation in a Spring Boot app | https://docs.spring.io/spring-ai/reference/api/testing.html |

## Facts and numbers

| id | fact | value | source id | verified |
|---|---|---|---|---|
| N1 | Placement judge model | gemini-2.5-flash | X5 | yes |
| N2 | Placement judge temperature | 0.2 | X5 | yes |
| N3 | Placement judge timeout | 15000 ms | X5 | yes |
| N4 | Placement judge max tokens | 600 | X5 | yes |
| N5 | Judge runs per chat | once | X2, X24 | yes |
| N6 | Judge start | wind-down stage (`"S4"`) or forced close | X2 | yes |
| N7 | Judge added | 2026-10-13 07:25 +0300, commit 8fa41788f, PR #622 | X1 | yes |
| N8 | Judge removed | 2026-10-13 20:18 +0300, commit bdd9ab7b8, PR #624 | X7 | yes |
| N9 | Judge columns dropped | 3 (judge_level, judge_started_at, judge_would_change) | X7 | yes |
| N10 | acceptJudge up-move: cited turns meeting the higher level's pass rule | at least 2 | X3 | yes |
| N11 | acceptJudge rejection gap | more than 1 level | X3 | yes |
| N12 | Shadow readout chats | 412 | S9 | made up |
| N13 | Shadow readout disagreements | 38 (9%) | S9 | made up |
| N14 | Shadow readout bar | judge right in at least 30 of 38 | S9 | made up |
| N15 | Plan real check size | 10 to 20 tester chats, placed blind by a teacher | X8 | yes |
| N16 | Plan real check target | ≥ 70% exact, ≥ 95% within one level | X8 | yes |
| N17 | Plan simulation gate | ≥ 80% exact, 100% within one level | X8 | yes |
| N18 | Judge cost per chat | $0.003 (Flash, 5k in, 0.5k out, estimated) | X8 | yes (estimate) |
| N19 | Level chat LLM cost | ≈ $0.023 per assessment | X8 | yes (estimate) |
| N20 | Guard enforce bar | under 15% (`ENFORCE_BELOW = 0.15`), in every cell | X11 | yes |
| N21 | Guard rates sample | 50 items per band for French, 25 for other languages | X11, X22 | yes |
| N22 | Guard rates languages | french, spanish, german, greek, korean | X11 | yes |
| N23 | Guard rates concurrency | 2 | X11 | yes |
| N24 | End punctuation guard rate | 0% in every language and band, 2026-10-07 | X9 | yes |
| N25 | Overheard tries | 3; checkpoint up to 5 while only giveaways | X12 | yes |
| N26 | Cognate similarity threshold | 0.8, tokens of 4+ letters | X12, X22 | yes |
| N27 | Longest choice threshold | at least 20% longer than second-longest ("a starting value") | X22 | yes |
| N28 | Second paid call share at 15% | about 1 in 7 | S9 | yes (arithmetic) |
| N29 | Three refusals in a row at 15% | about 3 in 1,000 (0.15³) | S9 | yes (arithmetic, assumes independence) |
| N30 | Enforced guards on main | 12 | X9 | yes |
| N31 | Log-mode guards on main | 6 | X9 | yes |
| N32 | Gate bar 1 | ≥ 95% agreement (real rows old vs new; fixture expected) | X17 | yes |
| N33 | Gate bar 2 | ≥ 95% marks placeable | X17 | yes |
| N34 | Gate bar 3 | ≥ 90% marked words really wrong, by hand | X17 | yes |
| N35 | Gate bar 4 | ≥ 95% replies within 2.5 s | X17 | yes |
| N36 | Gate hand-check minimum | ≥ 20 real non-exact rows | X17 | yes |
| N37 | Gate real-row sample | up to 200, stratified by language | X17 | yes |
| N38 | Gate fixture size | 36 rows | X18 | yes |
| N39 | Gate concurrency | 3 | X17 | yes |
| N40 | Fixture paraphrase misses allowed | 0 | X17 | yes |
| N41 | Translation grader focus areas | sixteen | X15 | yes |
| N42 | Canary steps | 5%, 25%, 100% | S9 | made up |
| N43 | Canary bar | discard rate more than 3 points above v7's | S9 | made up |
| N44 | Canary baseline discard rate | 20% | S9 | made up |
| N45 | Canary sample | 1,500 drafts in the v8 group | S9 | yes (arithmetic checked) |
| N46 | Scheduled rerun cost | 300 cases × $0.002 = $0.60 | S9 | made up |
| N47 | Smallest schedule | weekly CI job | S9 | proposal |
| N48 | Feedback statuses | 5 (open, acknowledged, investigating, resolved, wont_fix) | X19 | yes |
| N49 | Feedback flag reasons | 6 | X19 | yes |
| N50 | Admin detail evidence | up to 50 analytics events, 20 objective-progress rows | X20 | yes |
| N51 | Eugene Yan catalogue date | about Aug 2023 | S1 | yes (approximate) |
| N52 | Error analysis cadence (mature evals) | every 2 to 4 weeks | S4 | yes |
| N53 | Eval cases in CI (minimal evals) | 50 to 200 | S4 | yes |
| N54 | Testing rounds on newcomer readers | 3 rounds, 2 readers each, plus a final read | testing | yes |
| N55 | Reader scores, round 3 | senior clarity 7, self-contained 7, examples 8; skimmer 6, 6, 7 | testing | yes |

## Code in Lomem

Paths are relative to `~/projects/lomem`. "main" means the Lomem main branch as read on 2026-10-15 (HEAD 8e3f5d5db). Excerpts marked "at commit" come from a commit whose file or lines are not on main. "..." marks elided lines.

### X1 · Shadow judge run: call, compare, store, never break the chat
- File: `~/projects/lomem/apps/tunatutor/backend/src/use-cases/level-chat/judge.ts:1-4, 40-106` at commit 8fa41788f (file removed in bdd9ab7b8; not on main)
- Implements: C9, C10, C11, C13, C14; F2.1-F2.9; L1
```ts
// The blind judge (spec §6.2), in shadow mode. It reads the probe-tagged
// transcript and the fact rows — never the rule level D — and places the
// learner. Code compares (`acceptJudge`): at launch D is always shown, and the
// judge's level and `judgeWouldChange` are only stored for the real check.
...
/**
 * Run the judge once and store its opinion. Never throws: a failed judge is
 * logged and the chat goes on with D (it is shadow mode).
 */
export async function runLevelChatJudge(
  input: { levelChatId: string; state: LevelChatState; turns: readonly JudgeSourceTurn[] },
  deps: RunLevelChatJudgeDeps,
): Promise<{ judgeLevel: Level; judgeWouldChange: boolean } | null> {
  const { state } = input;
  // Only answers the learner gave count; taps and silences carry no answer.
  const answered = input.turns.filter((t) => t.learnerText.trim().length > 0);
  if (answered.length === 0) return null;
  const turns: JudgeTurn[] = answered.map((t) => ({
    n: t.idx + 1,
    tutorLine: t.tutorLine,
    probe: probeTask(t.probeId),
    learnerAnswer: t.learnerText,
    chip: t.chip,
    facts: (t.factsMerged as RaterFacts | null) ?? null,
  }));
  try {
    const answer = await deps.json({
      kind: "judge",
      levelChatId: input.levelChatId,
      systemPrompt: buildJudgeSystemPrompt({ targetLanguage: state.language }),
      userMessage: buildJudgeUserMessage({
        turns,
        inputMode: state.inputMode as LevelChatInputMode,
        targetLanguage: state.language,
      }),
      schema: judgeSchema,
      model: LEVEL_CHAT_JUDGE_MODEL,
      temperature: JUDGE_CALL.temperature,
      maxTokens: JUDGE_CALL.maxTokens,
      timeoutMs: JUDGE_CALL.timeoutMs,
    });
    if (!isLevelChatLevel(answer.level)) return null;
    const rows: JudgeRow[] = input.turns.flatMap((t) => {
      const probe = t.probeId ? findProbe(t.probeId) : undefined;
      if (!probe) return [];
      return [
        {
          n: t.idx + 1,
          probeLevel: probe.level,
          outcome: (t.outcome ?? "no_data") as Outcome,
          facts: (t.factsMerged as RaterFacts | null) ?? null,
          ...(t.outcomeCause ? { cause: t.outcomeCause as BreakdownCause } : {}),
        },
      ];
    });
    const decided = decideLevel(state).level;
    const comparison = acceptJudge(decided, { level: answer.level, citedTurns: answer.citedTurns }, rows, {
      inputMode: state.inputMode,
      language: state.language,
    });
    const result = { judgeLevel: answer.level, judgeWouldChange: comparison.judgeWouldChange };
    await deps.saveJudge(input.levelChatId, result);
    return result;
  } catch (err: unknown) {
    rethrowIfUndegradable(err);
    logger.warn(
      { err: getErrorMessage(err), levelChatId: input.levelChatId },
      "level chat: the shadow judge failed — D stands, nothing is stored",
    );
    return null;
  }
}
```
- Notes:
  - The judge prompt gets only answered turns (line 50), but `rows` for acceptJudge are built from all turns with a known probe (lines 77-89).
  - D is computed inside the judge (line 90) and passed only to acceptJudge, never to the model.
  - An invalid level returns null with no log and nothing stored (line 76).
  - The catch rethrows only the two undegradable codes (line 99); everything else is logged as "D stands, nothing is stored".
  - The comment "Never throws" (lines 41-42) is not literally true: see Open questions.

### X2 · Starting the judge off the request path, once per chat
- File: `~/projects/lomem/apps/tunatutor/backend/src/use-cases/level-chat/level-chat-turn.ts:136-137, 150-152, 350-359, 405-419` at commit 8fa41788f (judge parts removed in bdd9ab7b8)
- Implements: C12, C14; F1.3-F1.8; L1
```ts
  /** Runs the shadow judge off the request path. Default: fire and forget, failures logged. */
  runInBackground?: (task: Promise<unknown>) => void;
...
function defaultBackground(task: Promise<unknown>): void {
  task.catch((err: unknown) => logger.warn({ err: getErrorMessage(err) }, "level chat: background task failed"));
}
...
  const thisTurn: JudgeSourceTurn = {
    idx: turns.length,
    tutorLine: last.tutorLine,
    learnerText: text,
    chip: req.chip ?? null,
    probeId: inPlay?.id ?? null,
    factsMerged: step.merged,
    outcome: step.outcome?.outcome ?? null,
    outcomeCause: step.row?.cause ?? step.outcome?.cause ?? null,
  };
...
  // The judge starts with the wind-down (or at a forced close), so its wait hides behind the last answer.
  if ((state.stage === "S4" || done) && !chat.judgeStartedAt) {
    const claimed = await deps.repo.claimLevelChatJudge(chat.id, new Date(nowMs()));
    if (claimed) {
      const run = deps.runInBackground ?? defaultBackground;
      run(
        runLevelChatJudge(
          { levelChatId: chat.id, state, turns: [...turns, thisTurn] },
          { json: deps.json, saveJudge: deps.repo.saveLevelChatJudge },
        ),
      );
    }
  }
  return reply;
}
```
- Notes:
  - `run(...)` is not awaited: the reply returns at line 418 whatever the judge does.
  - `defaultBackground` catches whatever the judge rethrows (the two undegradable errors) and only logs it.
  - `runInBackground` is injectable, so tests can supply their own runner.

### X3 · Comparison rule acceptJudge
- File: `~/projects/lomem/apps/tunatutor/backend/src/use-cases/level-chat/policy.ts:1226-1285` at commit 8fa41788f (removed from main in bdd9ab7b8)
- Implements: C11; F3.1-F3.9
```ts
// ─── The blind judge, compared in code (§6.2) ───

export interface JudgeOpinion {
  level: Level;
  citedTurns: readonly number[];
}

export interface JudgeRow {
  /** The turn number the judge cites. */
  n: number;
  probeLevel: Level;
  outcome: Outcome;
  facts: RaterFacts | null;
  cause?: BreakdownCause;
}

export type JudgeVerdict = "same" | "accepted_up" | "accepted_down" | "rejected";

export interface JudgeComparison {
  verdict: JudgeVerdict;
  /** The level the judge would make it (D unless accepted). */
  level: Level;
  judgeWouldChange: boolean;
}

/**
 * Compare the blind judge with D. Same: logged. One level apart: accepted only
 * when the quote check passes. Two apart: rejected. At launch D is shown and
 * this result is only logged as `judgeWouldChange`.
 */
export function acceptJudge(
  decided: Level,
  judge: JudgeOpinion,
  rows: readonly JudgeRow[],
  ctx: { inputMode: LevelChatInputMode; language: PracticeLanguage },
): JudgeComparison {
  const keep = (verdict: JudgeVerdict): JudgeComparison => ({ verdict, level: decided, judgeWouldChange: false });
  const gap = levelIndex(judge.level) - levelIndex(decided);
  if (gap === 0) return keep("same");
  if (Math.abs(gap) > 1) return keep("rejected");
  const cited = rows.filter((r) => judge.citedTurns.includes(r.n));
  if (gap === 1) {
    const meeting = cited.filter(
      (r) => r.facts && probesAt(judge.level).some((p) => p.passRule(r.facts as RaterFacts, ctx).ok),
    );
    const realBreakdown = rows.some(
      (r) => r.probeLevel === judge.level && r.outcome === "breakdown" && r.cause !== "no_data",
    );
    if (meeting.length >= 2 && !realBreakdown) {
      return { verdict: "accepted_up", level: judge.level, judgeWouldChange: true };
    }
    return keep("rejected");
  }
  const down = cited.some(
    (r) =>
      r.probeLevel === decided &&
      (r.outcome === "breakdown" || r.facts?.meaningClear === "effortful" || r.facts?.meaningClear === "no"),
  );
  return down ? { verdict: "accepted_down", level: judge.level, judgeWouldChange: true } : keep("rejected");
}
```
- Notes:
  - Up-moves also require no real breakdown at the judge level anywhere in the chat, cited or not (lines 1271-1273); the drafts leave this out.
  - Down-moves need only one cited row at D.
  - `keep` always returns level D with `judgeWouldChange: false`.

### X4 · acceptJudge golden cases
- File: `~/projects/lomem/apps/tunatutor/backend/src/use-cases/level-chat/__tests__/policy.test.ts:748-791` at commit 8fa41788f (the file is on main; these cases were removed in bdd9ab7b8)
- Implements: E1; F3
```ts
describe("acceptJudge golden cases (§6.2)", () => {
  const b2Facts = facts({
    textType: "paragraph",
    features: ["speculation", "consequence"],
    lexicalRange: "adequate",
  });
  const judgeRows: JudgeRow[] = [
    { n: 1, probeLevel: "A1", outcome: "handled", facts: facts() },
    { n: 5, probeLevel: "B2", outcome: "partial", facts: b2Facts },
    { n: 7, probeLevel: "B2", outcome: "partial", facts: b2Facts },
    { n: 8, probeLevel: "B1", outcome: "breakdown", facts: facts({ meaningClear: "no" }) },
  ];

  it("same level: logged, nothing changes", () => {
    assert.deepEqual(acceptJudge("B1", { level: "B1", citedTurns: [5] }, judgeRows, ctx), {
      verdict: "same",
      level: "B1",
      judgeWouldChange: false,
    });
  });

  it("one up: accepted with 2 cited turns meeting a B2 pass rule and no real B2 breakdown", () => {
    const r = acceptJudge("B1", { level: "B2", citedTurns: [5, 7] }, judgeRows, ctx);
    assert.equal(r.verdict, "accepted_up");
    assert.equal(r.level, "B2");
    assert.equal(r.judgeWouldChange, true);
  });

  it("one up: rejected with only 1 cited turn, or with a B2 breakdown (a no_data breakdown does not count)", () => {
    assert.equal(acceptJudge("B1", { level: "B2", citedTurns: [5] }, judgeRows, ctx).verdict, "rejected");
    const withBreakdown: JudgeRow[] = [...judgeRows, { n: 9, probeLevel: "B2", outcome: "breakdown", facts: null, cause: "facts" }];
    assert.equal(acceptJudge("B1", { level: "B2", citedTurns: [5, 7] }, withBreakdown, ctx).verdict, "rejected");
    const noData: JudgeRow[] = [...judgeRows, { n: 9, probeLevel: "B2", outcome: "breakdown", facts: null, cause: "no_data" }];
    assert.equal(acceptJudge("B1", { level: "B2", citedTurns: [5, 7] }, noData, ctx).verdict, "accepted_up");
  });

  it("one down: accepted when a cited row at D broke down or was unclear", () => {
    assert.equal(acceptJudge("B1", { level: "A2", citedTurns: [8] }, judgeRows, ctx).verdict, "accepted_down");
    assert.equal(acceptJudge("B1", { level: "A2", citedTurns: [1] }, judgeRows, ctx).verdict, "rejected");
  });

  it("two levels apart: rejected", () => {
    assert.equal(acceptJudge("A2", { level: "B2", citedTurns: [5, 7] }, judgeRows, ctx).verdict, "rejected");
  });
```
- Notes:
  - Turns 5 and 7 are B2 probes with outcome "partial", yet their facts meet a B2 pass rule.
  - The suite name calls these "golden cases (§6.2)", pointing at the plan section (X8).

### X5 · Judge call settings and reply schema
- File: `~/projects/lomem/apps/tunatutor/backend/src/use-cases/level-chat/prompts.ts:28-36, 285-303` at commit 8fa41788f (the file is on main; the judge model, `JUDGE_CALL` and `judgeSchema` were removed in bdd9ab7b8)
- Implements: C10; F2.3; N1-N4
```ts
// ─── Models and budgets (§5.1, §6.2) ───

export const LEVEL_CHAT_RATER_MODEL = "gemini-2.5-flash-lite";
export const LEVEL_CHAT_TUTOR_MODEL = "gemini-2.5-flash";
export const LEVEL_CHAT_JUDGE_MODEL = "gemini-2.5-flash";

export const RATER_CALL = { temperature: 0.1, timeoutMs: 2000, maxTokens: 500 } as const;
export const TUTOR_CALL = { temperature: 0.6, timeoutMs: 4000, maxTokens: 700 } as const;
export const JUDGE_CALL = { temperature: 0.2, timeoutMs: 15000, maxTokens: 600 } as const;
...
// ─── Judge (§6.2, §7.3) ───

const levelEnum = z.enum(LEVEL_CHAT_LEVELS);

export const judgeSchema = z.object({
  level: levelEnum,
  citedTurns: z.array(z.number()),
  ruledOutTurns: z
    .object({
      A1: z.array(z.number()).optional(),
      A2: z.array(z.number()).optional(),
      B1: z.array(z.number()).optional(),
      B2: z.array(z.number()).optional(),
    })
    .optional(),
  nearNext: z.boolean(),
  reason: z.string(),
});
export type JudgeAnswer = z.output<typeof judgeSchema>;
```
- Notes:
  - The judge used the same model as the tutor (Flash) with a much longer timeout (15 s against 4 s); it could afford that because it ran off the request path.

### X6 · The two errors no degrade path may swallow
- File: `~/projects/lomem/apps/tunatutor/backend/src/errors/index.ts:171-196` (main)
- Implements: C14; F2.8, F2.8a, F5.8a
```ts
/**
 * Errors a degrade / retry chain must NEVER swallow.
 *
 * Drill generation is deliberately forgiving: a bare `catch { continue }`
 * around an LLM call turns malformed JSON or a provider blip into "try again,
 * then fall back". That is right for content failures and WRONG for these two,
 * which are not content failures at all:
 *
 *  - `FST_MISSING_USAGE_CONTEXT` is a programming error. Swallowed, a
 *    mis-threaded attribution shows up as a slightly worse drill instead of a
 *    loud failure, and the metering hole this whole layer exists to close
 *    silently reopens.
 *  - `FST_DAILY_SPEND_CAP` is an admission decision that was already made at
 *    the door. Retrying past it would burn the very budget it just refused.
 *
 * Call this FIRST inside any `catch` that would otherwise degrade.
 */
const UNDEGRADABLE_ERROR_CODES = new Set([
  "FST_MISSING_USAGE_CONTEXT",
  "FST_DAILY_SPEND_CAP",
]);

export function rethrowIfUndegradable(err: unknown): void {
  const code = getErrorCode(err);
  if (code !== undefined && UNDEGRADABLE_ERROR_CODES.has(code)) throw err;
}
```

### X7 · Removing the shadow judge columns
- File: `~/projects/lomem/apps/tunatutor/backend/prisma/migrations/20261013160000_level_chat_drop_judge/migration.sql:1-5` (main; added in bdd9ab7b8)
- Implements: L1 last row, L2 shadow → dropped; F4.4b; E3
```sql
-- @destructive-ok: shadow-judge columns were only written by the removed shadow judge; no reader remains
-- AlterTable
ALTER TABLE "level_chats" DROP COLUMN "judge_level",
DROP COLUMN "judge_started_at",
DROP COLUMN "judge_would_change";
```
- Notes:
  - The commit message of bdd9ab7b8 says: "The blind shadow judge and its columns are removed (follow-up migration)." It gives no reason.

### X8 · Level-chat plan: judge in shadow at launch, real check, regression rule, cost, risk
- File: `~/projects/lomem/docs/plans/2026-10-13-level-chat-assessment.md:447-458, 850-853, 855-862, 892` (main)
- Implements: C11, C15, C33; F4.3b, F4.4a; L2; N15-N19; P12
```markdown
### 6.2 Step 2: blind LLM judge (shadow mode at launch)

- **Model and timing.** `gemini-2.5-flash`, temperature 0.2. It starts when S4 begins, so its latency hides behind the wind-down answer.
- **Input.** The probe-tagged transcript and the fact rows. It does **not** get D.
- **Output.** `{level, citedTurns, reason, nearNext}`.
- **Comparison, done in code (`acceptJudge`):**
  - Same level: logged.
  - One level apart: accepted only if the quote check passes.
    - *Up:* at least 2 cited learner turns whose stored facts meet a pass rule of the higher level, and no breakdown at that level other than a no_data.
    - *Down:* a cited row with a breakdown, or with `effortful`/`no` meaning, at D.
  - Two levels apart: rejected.
- **At launch,** `acceptJudge` runs and its result is logged as `judgeWouldChange`, but **D is shown**. The judge moves to live only after the real check (§9.9) shows judge-adjusted levels agree with a teacher more often than D alone.
...
   - It writes a table: exact, within one, answers, learner time, no_data rate, fallback-line rate, and p50/p95 latency.
   - **Gate:** ≥ 80% exact and 100% within one level.
5. **Real check:** 10–20 tester chats, placed blind by a teacher. Target ≥ 70% exact and ≥ 95% within one level. These chats also decide whether the judge goes live.
6. Every misplacement found becomes a regression case in `policy.test.ts`.
...
### 9.10 Cost per assessment (from `dev/provider-prices.ts`; token counts estimated)

| Item | Estimate | Cost |
|---|---|---|
| Rater, Flash-Lite, 10 calls × (1.8k in, 0.35k out) | 18k in / 3.5k out | $0.003 |
| Tutor, Flash, 10 calls × (1.8k in, 0.45k out) | 18k in / 4.5k out | $0.017 |
| Judge, Flash, once (5k in, 0.5k out) | | $0.003 |
| **LLM total** | | **≈ $0.023** |
...
| Judge never leaves shadow mode | Judge spend with no benefit | Drop the judge if the real check shows no gain |
```
- Notes:
  - Line 853 is a Lomem flywheel rule: every misplacement found becomes a regression case.
  - Line 892 is the risk the drafts quote.

### X9 · Guard modes: enforce or log
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/overheard/engine/guards.ts:176, 181-209` (main)
- Implements: C16, C17; L3; F6.8, F6.9
```ts
export type GuardMode = "enforce" | "log";
...
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
  - The comment says "under about 15 percent"; the rates script requires under 15% in every cell (X11).

### X10 · Guard log: would-reject kept apart
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/overheard/engine/guard-log.ts:1-48` (main)
- Implements: C17, C18; F5.3a, F5.3b, F5.11
```ts
/**
 * Guard rejection log (OH2, OH3b). Every rejection is another AI call, so the rate of
 * each guard has to be readable from the log: one line per rejection, plus one
 * summary per `generate()` call with the count per guard.
 *
 * A guard in 'log' mode writes the rejection it WOULD have made (`mode: "log"`) and
 * lets the item through; the summary keeps those apart as `wouldReject`.
 */
import { logger } from "../../../logger.js";
import type { GuardMode } from "./guards.js";

export function logGuardRejection(input: {
  guard: string;
  arcId?: string | null;
  slotType?: string | null;
  mode?: GuardMode;
}): void {
  logger.info(
    { guard: input.guard, mode: input.mode ?? "enforce", arcId: input.arcId ?? null, slotType: input.slotType ?? null },
    "overheard: guard rejection",
  );
}

/** A per-`generate()` tally: `add` on each rejection, `summary` once at the end. */
export function createGuardTally(ctx: { arcId?: string | null; slotType?: string | null }) {
  const counts: Record<string, number> = {};
  const wouldReject: Record<string, number> = {};
  return {
    add(guard: string, mode: GuardMode = "enforce"): void {
      const bucket = mode === "log" ? wouldReject : counts;
      bucket[guard] = (bucket[guard] ?? 0) + 1;
      logGuardRejection({ guard, mode, ...ctx });
    },
    summary(outcome?: string): void {
      logger.info(
        {
          arcId: ctx.arcId ?? null,
          slotType: ctx.slotType ?? null,
          rejections: { ...counts },
          wouldReject: { ...wouldReject },
          total: Object.values(counts).reduce((a, b) => a + b, 0),
          outcome: outcome ?? null,
        },
        "overheard: guard summary",
      );
    },
  };
}
```

### X11 · Guard-rates script: measure with every guard enforced, decide per guard
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/overheard-guard-rates.ts:11-29, 106-161` (main)
- Implements: C18; F6.1-F6.7; N20-N23
```ts
// Overheard guard measurement (OH3b). Generates items with REAL, paid LLM calls and prints,
// per language and band, how often each guard would have refused an attempt, plus the
// share of items where every try failed. The fairness guards ship in 'log' mode; a guard
// whose rate here is under about 15 percent is switched to 'enforce' in GUARD_MODES, a
// higher one is loosened or dropped first. Run it only when the owner says go.
//
// Every guard is switched to 'enforce' for the measurement, so the tries behave as they
// would once everything is on: an item that a log-mode guard would refuse is retried here.
//
//   pnpm --filter @tunatutor/backend exec tsx scripts/overheard-guard-rates.ts
//   options: --fr 50  --other 25  --languages french,spanish,german,greek,korean  --bands A1,A2,B1,B2  --concurrency 2
//   a quick look: --fr 4 --other 0 --languages french --bands A2

const db = prisma as unknown as PrismaClient;

const BANDS = ["A1", "A2", "B1", "B2"] as const;
const DEFAULT_LANGUAGES = ["french", "spanish", "german", "greek", "korean"];
/** The rate under which a log-mode guard may be switched on. */
const ENFORCE_BELOW = 0.15;
...
async function main(): Promise<void> {
  if (process.env.NODE_ENV === "production") {
    console.error("[overheard-guard-rates] refusing to run with NODE_ENV=production");
    process.exitCode = 1;
    return;
  }
  await initLLMRegistry();
  const userId = await findFounderId(db.user);
  if (userId === null) {
    console.error("[overheard-guard-rates] no founder account found. Start the backend once (`tunatutor up b`).");
    process.exitCode = 1;
    return;
  }
  const concurrency = Math.max(1, Number(arg("concurrency", "2")));
  const french = Number(arg("fr", "50"));
  const other = Number(arg("other", "25"));
  const languages = arg("languages", DEFAULT_LANGUAGES.join(",")).split(",").map((s) => s.trim().toLowerCase());
  const bands = arg("bands", BANDS.join(",")).split(",").map((s) => s.trim().toUpperCase());

  // Measure every guard as if it were enforced.
  const before = { ...GUARD_MODES };
  for (const g of guardNames()) GUARD_MODES[g] = "enforce";

  const table: { language: string; band: string; cell: Cell }[] = [];
  try {
    for (const language of languages) {
      const count = language === "french" ? french : other;
      if (count <= 0) continue;
      for (const band of bands) {
        console.log(`[overheard-guard-rates] ${language} ${band}: ${count} items`);
        table.push({ language, band, cell: await measure(language, band, count, userId, concurrency) });
      }
    }
  } finally {
    Object.assign(GUARD_MODES, before);
  }

  console.log("\nShare of items where every try failed (no clean item in three tries), and the 503 share");
  for (const { language, band, cell } of table) {
    console.log(`  ${language.padEnd(8)} ${band}  items=${cell.items}  not clean=${pct(cell.notClean, cell.items)}  503=${pct(cell.unavailable, cell.items)}  no reveal=${pct(cell.noReveal, cell.items)}`);
  }

  console.log("\nPer-guard would-reject rate (share of ITEMS where the guard fired on any try)");
  const names = guardNames();
  console.log(`  ${"guard".padEnd(30)} mode   ${table.map((t) => `${t.language.slice(0, 3)}-${t.band}`.padEnd(7)).join("")}`);
  for (const g of names) {
    const row = table.map((t) => pct(t.cell.hits.get(g) ?? 0, t.cell.items).padEnd(7)).join("");
    console.log(`  ${g.padEnd(30)} ${before[g].padEnd(7)}${row}`);
  }

  console.log(`\nSwitch a 'log' guard to 'enforce' only when its rate is under ${(ENFORCE_BELOW * 100).toFixed(0)}% in every cell; loosen or drop a higher one first.`);
  for (const g of names) {
    if (before[g] !== "log") continue;
    const worst = Math.max(0, ...table.map((t) => (t.cell.items === 0 ? 0 : (t.cell.hits.get(g) ?? 0) / t.cell.items)));
    console.log(`  ${g.padEnd(30)} worst cell ${(worst * 100).toFixed(0)}%  ${worst < ENFORCE_BELOW ? "-> ready to enforce" : "-> loosen or drop first"}`);
  }
```

### X12 · Overheard generation loop: only enforced hits refuse; best fallback or 503
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/overheard/engine/content-generator.ts:43-48, 250-253, 501-606` (main)
- Implements: C44, C17; F5.1-F5.11; L7
```ts
const MAX_GENERATION_ATTEMPTS = 3;
/** A checkpoint may not dead-end on bad luck: two more tries when every try so far was a give-away. */
const CHECKPOINT_EXTRA_ATTEMPTS = 2;
const VOCAB_CANDIDATE_LIMIT = 8;
/** Cognate/loanword near-identity threshold (normalized similarity). */
const COGNATE_SIMILARITY = 0.8;
...
/** The hits that refuse the item (guards in 'enforce' mode). */
export function enforcedHits(hits: readonly GuardHit[]): GuardHit[] {
  return hits.filter((h) => GUARD_MODES[h.guard] === "enforce");
}
...
      // Every try that parsed but was refused is ranked (`fallback-rank.ts`). After the
      // tries run out the best one that may ship is served: a clean item, else the best
      // QUALITY one, else a REPEAT one, NEVER a GIVEAWAY. There is no seed-pool fallback:
      // a DrillSeed carries no authored distractors, so it cannot yield an MC item.
      const banked: Banked[] = [];
      const questionType = pickOverheardQuestionType(input);
      const earlierLines = input.arcPrompts ?? [];
      const earlierQuestions = input.runHistory?.questions ?? [];
      const tally = createGuardTally({ arcId: input.arcId ?? null, slotType: input.slotType ?? null });
      let previousRefusal: string | null = null;
      const languages: OverheardLanguages = {
        nativeLanguage: input.nativeLanguage,
        targetLanguage: input.targetLanguage,
      };
      const isCheckpoint = input.runMode === "test";
      /** The best banked try that may ship, built; null when none may. Sets `outcome`. */
      const serveBest = (): DrillContent | null => {
        const best = pickFallback(banked);
        if (!best) return null;
        outcome = best.rank;
        return buildContent(best.parsed, languages, random);
      };
      const onlyGiveaways = (): boolean => banked.length > 0 && banked.every((b) => b.rank === "giveaway");
      let outcome: CandidateRank | "unavailable" = "unavailable";
      try {
        try {
          for (let attempt = 0; ; attempt++) {
            const regular = attempt < MAX_GENERATION_ATTEMPTS;
            // A checkpoint pass gate must not dead-end on bad luck: while every try so far
            // was a give-away, it makes two more (five in all) before the 503.
            const extra =
              isCheckpoint && attempt < MAX_GENERATION_ATTEMPTS + CHECKPOINT_EXTRA_ATTEMPTS && onlyGiveaways();
            if (!regular && !extra) break;

            const { parsed, failed } = await generateOnce(
              input,
              languages,
              candidates,
              questionType,
              previousRefusal,
              (hits) => {
                for (const h of hits) tally.add(h.guard, GUARD_MODES[h.guard]);
                deps.observer?.({ hits });
              },
            );
            // A refusal goes to the NEXT try's prompt.
            previousRefusal = failed[0]?.reason ?? null;
            if (!parsed) continue;

            const guardsFailed: GuardName[] = failed.map((f) => f.guard);
            // An exact repeat of THIS run's line is retried, and banked as a REPEAT: it ships
            // only when every try failed and nothing better was banked. A repeated line beats
            // a 503 that stalls the run on a narrow A1 lesson (QA drills-smoke 2026-10-08).
            const exact = earlierLines.find((l) => normalizeForCompare(l) === normalizeForCompare(parsed.snippet));
            const repeats: GuardHit[] = [];
            if (exact !== undefined) {
              repeats.push({ guard: "line repeated in this run", reason: `the line repeats an earlier one of this run ("${exact}")` });
            }
            // A line that opens like an earlier one, or a question asked again, ranks the
            // try as a REPEAT whatever else it failed (a rough repeat never beats a rough fair item).
            // An exact repeat fails this too, so a merely close line ships before it.
            const opening = repeatedOpeningOf(parsed.snippet, earlierLines);
            const near = opening ?? earlierLines.find((l) => isNearDuplicate(parsed.snippet, [l])) ?? null;
            if (near !== null) {
              repeats.push({ guard: "opening repeated in this run", reason: `the line opens like an earlier one of this run ("${near}")` });
            }
            if (repeatsQuestion(parsed.question, earlierQuestions)) {
              repeats.push({ guard: "question repeated in this run", reason: "the question repeats one this run already asked" });
            }
            for (const r of repeats) {
              tally.add(r.guard, "enforce");
              guardsFailed.push(r.guard);
            }
            if (guardsFailed.length === 0) {
              outcome = "clean";
              return buildContent(parsed, languages, random);
            }
            // A repeat names itself to the next try first: it is the refusal the model must fix.
            if (exact !== undefined) previousRefusal = repeats[0]!.reason;
            previousRefusal ??= repeats[0]?.reason ?? null;
            // A structurally broken item is not a candidate at all.
            const rank = rankCandidate(guardsFailed);
            if (rank !== "unusable") banked.push({ parsed, rank, guardsFailed });
          }
        } catch (err: unknown) {
          // The spend cap and a missing usage context are never degraded past.
          rethrowIfUndegradable(err);
          // The LLM call threw — serve the best item so far, if any may ship.
          const best = serveBest();
          if (best) return best;
          throw new ServiceUnavailableError(`Overheard generation failed: ${getErrorMessage(err)}`);
        }

        const best = serveBest();
        if (best) return best;
        // Nothing may ship: a lone give-away is never served. A clean 503, which the client retries.
        throw new ServiceUnavailableError(
          onlyGiveaways() ? "Overheard: only give-away items after retries" : "Overheard: no usable item after retries",
        );
      } finally {
        tally.summary(outcome);
        deps.observer?.({ outcome });
      }
    },
  };
}
```

### X13 · Fallback ranking of refused tries
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/overheard/engine/fallback-rank.ts:1-34` (main)
- Implements: C44; F5.7, F5.9; E7
```ts
/**
 * What may ship when three tries found no clean item (OH3b). Pure.
 *
 * Every refused try is ranked by the guards it failed:
 * - GIVEAWAY: the answer can be had without listening (a cognate, a scene word in a
 *   choice, the answer in the question, a question that rules out a choice). Never shipped.
 * - REPEAT: the item repeats this run (a span, an opening, or the whole line). Shipped only when nothing better exists.
 * - QUALITY: the item is fair but rough (an unnatural line, odd punctuation, the longest
 *   choice, a topic word, a choice inside another). Shipped before a REPEAT.
 *
 * Example: three tries, one with a mismatched full stop (QUALITY), one that opens like an
 * earlier line (REPEAT), one with the answer in the question (GIVEAWAY). The first ships.
 * If only the third exists, the learner's app gets a clean 503 and retries.
 */
import type { GuardName } from "./guards.js";

export type CandidateRank = "clean" | "quality" | "repeat" | "giveaway" | "unusable";

const GIVEAWAY: ReadonlySet<GuardName> = new Set<GuardName>([
  "cognate",
  "scene word",
  "question shares a word",
  "question rules out a choice",
]);

const REPEAT: ReadonlySet<GuardName> = new Set<GuardName>([
  "span repeat",
  "line repeated in this run",
  "opening repeated in this run",
  "question repeated in this run",
]);

/** Best to worst: a lower number ships first. `giveaway` and `unusable` never ship. */
const ORDER: Record<CandidateRank, number> = { clean: 0, quality: 1, repeat: 2, giveaway: 3, unusable: 4 };
```

### X14 · Test that pins each guard mode
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/overheard/engine/guards.test.ts:223-243` (main)
- Implements: C17, the C22 pattern applied to guards; L3
```ts
describe("every guard has a mode", () => {
  it("the cheap structural guards enforce; the fairness guards start in log mode", () => {
    // "end punctuation" was measured at 0 percent in every cell and is already enforced.
    for (const g of ["structure", "choice substring", "span", "why line", "span repeat", "where opener", "end punctuation"] as const) {
      assert.equal(GUARD_MODES[g], "enforce", g);
    }
    for (const g of [
      "question names its type",
      "question shares a word",
      "longest choice",
      "intent topic word",
      "scene word",
      "cognate",
    ] as const) {
      assert.equal(GUARD_MODES[g], "log", g);
    }
  });
  it("GUARD_MODES names every guard once", () => {
    assert.deepEqual(Object.keys(GUARD_MODES).sort(), guardNames().sort());
  });
});
```

### X15 · The marks flag and where the parser reads it
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-reply.ts:15-20, 107-108, 129-160, 172-174` (main)
- Implements: C7, C20; F7.3-F7.7; L4
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
...
  const weakRaw = Array.isArray(parsed.weak) ? parsed.weak : [];
  // `weak` was never measured by the judge gate, so it is held back with the marks.
  const weak = !marksEnabled ? [] : weakRaw.filter((w): w is string => typeof w === "string" && w.trim() !== "").slice(0, 1);
```
- Notes:
  - Only line 108 reads `TD_JUDGE_MARKS`; the other places read the local `marksEnabled`, which a caller can override with `opts.marksEnabled`.

### X16 · Test that fails the build if the flag is flipped by accident
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-reply.test.ts:13-15` (main)
- Implements: C22; L4
```ts
test("TD_JUDGE_MARKS defaults to false", () => {
  assert.equal(TD_JUDGE_MARKS, false);
});
```

### X17 · Translation judge gate: four bars fixed in the header
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/translation-judge-gate.ts:1-21, 48-55, 127-131, 263-299, 307-310, 328-329` (main)
- Implements: C19, C21; F8.1-F8.9; N32-N40; E11
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
...
  for (const a of attempts) {
    const answer = (a.userAnswer ?? "").trim();
    if (answer === "") continue;
    const n = normalizeTypedAnswer(answer);
    if ([a.expectedTranslation, ...a.acceptedVariants].some((k) => normalizeTypedAnswer(k) === n)) continue;
...
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
...
  // Check 3: the hand-check table
  console.log("\nCHECK 3  marked words, to be read BY HAND (bar 90% really wrong)");
  console.log("| # | origin | her sentence | the key | marked word (kind) | the judge's why | fixture hint |");
  console.log("|---|---|---|---|---|---|---|");
...
  console.log(`\n  fixture marked words inside the expected set: ${hintHit}/${hintTotal} (a hint, not the check)`);
  console.log(`  real non-exact rows judged: ${realJ.length} (need >= 20 hand-checked to turn marks on)`);
```
- Notes:
  - The script prints PASS/FAIL but does not set a failing exit code when a bar fails; it is a dev harness, not a CI gate.
  - Real rows exclude exact matches of key or variants (lines 130-131), because an exact match never reaches the grader.

### X18 · Gate fixture: hand-written cases, including the running example
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-gate-fixture.ts:1-10, 25-28` (main)
- Implements: C5, C21, C33; E9
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
...
export const JUDGE_GATE_FIXTURE: readonly JudgeGateFixtureRow[] = [
  { language: "pt", source: "I am a barista.", key: "Eu sou barista.", variants: [], answer: "Eu sou um barista.", expected: "right", markedWords: [], note: "paraphrase: an article the language allows either way" },
  { language: "fr", key: "Je vais réserver une table.", variants: [], answer: "Je compte réserver une table.", expected: "right", markedWords: [], note: "paraphrase: compter + infinitive for aller + infinitive" },
  { language: "fr", key: "J'ai très faim.", variants: [], answer: "J'ai vraiment faim.", expected: "right", markedWords: [], note: "paraphrase: synonym adverb" },
```

### X19 · Feedback table
- File: `~/projects/lomem/apps/tunatutor/backend/prisma/schema.prisma:2027-2070` (main)
- Implements: C29, C31, C32; L6
```prisma
/// One row per user-submitted feedback item (satisfaction rating or content flag) with triage status.
model Feedback {
  id                    Int                 @id @default(autoincrement())
  userId                Int                 @map("user_id")
  /// Free-form external/string session id the feedback targets; not an FK.
  sessionId             String              @map("session_id")
  /// Conversation session id when applicable; not an FK (denormalized).
  conversationSessionId Int?                @map("conversation_session_id")
  /// Session-type discriminator the feedback came from.
  sessionType           SessionType         @map("session_type")
  /// App-level language key the feedback pertains to.
  language              String
  /// Kind of feedback: satisfaction | flag.
  feedbackType          FeedbackType        @map("feedback_type")
  /// Sentiment for satisfaction feedback: positive | neutral | negative.
  sentiment             FeedbackSentiment?
  /// Reason for a flag: bad_response | wrong_correction | wrong_language | wrong_mastery | ui_bug | other.
  flagReason            FeedbackFlagReason? @map("flag_reason")
  /// Turn ordinal the feedback targets, when turn-scoped.
  turnIndex             Int?                @map("turn_index")
  /// Optional free-text note from the user.
  note                  String?
  /// Triage status: open | acknowledged | investigating | resolved | wont_fix.
  status                FeedbackStatus      @default(open)
  /// Internal note added by an admin during triage.
  adminNote             String?             @map("admin_note")
  /// JSON snapshot of client-side context captured at submission.
  clientContext         Json?               @map("client_context")
  /// JSON snapshot of server-side context captured at submission.
  serverContext         Json?               @map("server_context")
  /// Unique dedup key preventing duplicate submissions.
  idempotencyKey        String              @unique @map("idempotency_key")
  createdAt             DateTime            @default(now()) @map("created_at")
  updatedAt             DateTime            @updatedAt @map("updated_at")

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId, createdAt(sort: Desc)])
  @@index([sessionId])
  @@index([feedbackType, createdAt(sort: Desc)])
  @@index([status])
  @@index([flagReason])
  @@map("feedback")
}
```
- Notes:
  - No trace ID column; the key to the exchange is `sessionId` (free-form, not a foreign key) plus `turnIndex`.
  - Prisma is a TypeScript ORM; `schema.prisma` plays the role a JPA entity plus Flyway script plays in Spring (not from the inputs).

### X20 · Feedback service: server context capture, create, admin detail
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/feedback.ts:23-94, 187-213` (main)
- Implements: C31, C32; F10.2-F10.5; F11.1
```ts
// ─── Context Resolver Pattern ────────────────────────────

type ContextResolver = (
  sessionId: string,
  userId: number,
) => Promise<Record<string, unknown> | null>;

const contextResolvers = new Map<string, ContextResolver>();

export function registerFeedbackContextResolver(
  sessionType: string,
  resolver: ContextResolver,
): void {
  contextResolvers.set(sessionType, resolver);
}

async function captureServerContext(
  sessionType: string,
  sessionId: string,
  userId: number,
): Promise<Record<string, unknown> | null> {
  const resolver = contextResolvers.get(sessionType);
  if (!resolver) return null;
  try {
    return await resolver(sessionId, userId);
  } catch {
    return null;
  }
}

// ─── Submit Feedback ─────────────────────────────────────

export async function submitFeedback(
  userId: number,
  input: SubmitFeedbackRequest,
): Promise<SubmitFeedbackResponse> {
  const idempotencyKey = buildFeedbackIdempotencyKey(userId, input);

  const serverContext = await captureServerContext(
    input.sessionType,
    input.sessionId,
    userId,
  );

  // Look up conversationSessionId from analytics events
  const conversationSessionId = await resolveConversationSessionId(
    input.sessionId,
    userId,
  );

  const feedback = await prisma.feedback.create({
    data: {
      userId,
      sessionId: input.sessionId,
      conversationSessionId,
      sessionType: input.sessionType,
      language: input.language,
      feedbackType: input.feedbackType,
      sentiment: input.sentiment ?? null,
      flagReason: input.flagReason ?? null,
      turnIndex: input.turnIndex ?? null,
      note: input.note ?? null,
      status: "open",
      clientContext: input.clientContext
        ? toInputJson(input.clientContext)
        : Prisma.JsonNull,
      serverContext: serverContext
        ? toInputJson(serverContext)
        : Prisma.JsonNull,
      idempotencyKey,
    },
  });
...
export async function getFeedbackDetail(
  feedbackId: number,
): Promise<FeedbackDetailDTO | null> {
  const feedback = await prisma.feedback.findUnique({
    where: { id: feedbackId },
    include: { user: { select: { username: true } } },
  });
  if (!feedback) return null;

  const { userId, sessionId } = feedback;

  // Query related evidence data in parallel
  const [analyticsEvents, objectiveProgress] = await Promise.all([
    prisma.analyticsEvent.findMany({
      where: { userId, sessionId },
      orderBy: { occurredAt: "desc" },
      take: 50,
    }),
    prisma.userObjectiveProgress.findMany({
      where: { userId, language: feedback.language },
      include: {
        objective: { select: { code: true, title: true } },
      },
      orderBy: { lastAttemptedAt: "desc" },
      take: 20,
    }),
  ]);
```

### X21 · The only server-context resolver: AI tutor
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/index.ts:134-148` (main)
- Implements: C31; F10.3c
```ts
    // Register feedback context resolver for ai_tutor sessions
    registerFeedbackContextResolver("ai_tutor", async (sessionId, userId) => {
      const session = getAiTutorSession(sessionId);
      if (!session || String(session.userId) !== String(userId)) return null;
      const ctx = session.engine.getContext();
      return {
        sessionType: "ai_tutor",
        turnNumber: ctx.turnNumber,
        studentProfile: {
          cefrLevel: ctx.studentProfile.cefrLevel,
          targetLanguage: ctx.studentProfile.targetLanguage,
          nativeLanguage: ctx.studentProfile.nativeLanguage,
        },
      };
    });
```

### X22 · ADR-049: guard modes, fairness guards and the rates script
- File: `~/projects/lomem/docs/adr/049-overheard-listening-drill.md:55-73` (main)
- Implements: C16, C17, C18; N21, N26, N27
```markdown
The prompt states the applicable distractor rule per type (e.g. `who` → other plausible roles in the *same* setting; `where` → other settings sharing surface cues, disconfirmed only by the keyword; `intent`/`attitude`/`outcome`/`register` → same topic, different stance), and a "fair question and choices" block with the rules below. Because an LLM cannot be trusted to honor a prose rule 100% of the time, deterministic guards run in code against every parsed item (`engine/guards.ts`, assembled by `guardHits` in `engine/content-generator.ts`; `rejectReason` returns the first enforced reason). Each guard has a name and a **mode** in `GUARD_MODES`: `enforce` refuses the item; `log` writes the refusal it WOULD have made (`overheard: guard rejection`, `mode: "log"`, summed per call as `wouldReject`) and lets the item through.

Enforced from the start:
- **Structure** — exactly 4 non-empty, mutually-distinct choices and a valid `correctIndex`.
- **Choice substring** — no choice is a normalized substring of another choice or of the native gloss.
- **Span and why lines** — the deciding span is in the line (`locateSpan`) and is not a frame verb; each why is one short sentence with no grammar terms and quotes only words of the line.
- **End punctuation** — the four choices all end alike (all with a full stop, or none). Measured at 0 percent in every language and band.
- **Run shape** — no deciding span twice in a run (a tripped word may return once), and `where` only at a stretch opener.
- **The grammar check** — one short model call after the guards pass: the line is natural spoken language, and the question rules out every wrong choice (`engine/item-check.ts`; it fails open, except on the daily spend cap and a missing usage context, which it throws on).

Fairness guards, which start in `log` mode until the guard-rates script shows a rate under about 15 percent:
- **Cognate** — a content token of the line (4+ letters, similarity ≥ 0.8) matches a content word of the correct choice and of no distractor, so cognate-spotting wins without listening.
- **Scene word** — the scene chip shares a word of 4+ letters with a choice (not on a `where` item, whose chip is hidden until the answer).
- **Question names its type** — a stance question (intent, register, attitude, outcome) holds "intent", "register", "attitude", "outcome" or its translation in the learner's language. Where, who and what questions are not checked.
- **Question shares a word** — the question and the right choice share a content word of 4+ letters.
- **Longest choice** — the right choice is the longest and at least 20 percent longer than the second-longest (a starting value).
- **Intent topic word** — on intent, register, attitude and outcome items, no content word of the right choice (other than the word carrying the span's gloss, which the word-level tag needs in the right choice only) is in at least two wrong choices. `what`, `who` and `where` items are exempt.

`apps/tunatutor/backend/scripts/overheard-guard-rates.ts` makes real calls (about 50 items per band for French, about 25 for the other languages), with every guard enforced, and prints each guard's would-reject rate per band and language plus the share of items where all three tries fail. A guard under about 15 percent is switched to `enforce` (one line); a higher one is loosened or dropped first.
```

### X23 · The judge columns as added
- File: `~/projects/lomem/apps/tunatutor/backend/prisma/migrations/20261013140000_level_chat/migration.sql:18-22` at commit 8fa41788f (unchanged on main; the columns are dropped by the later migration in X7)
- Implements: C13, C15; K6
```sql
    "proposed_level" TEXT,
    "accepted_level" TEXT,
    "judge_level" TEXT,
    "judge_would_change" BOOLEAN,
    "judge_started_at" TIMESTAMP(3),
```

### X24 · Claim and save of the judge result
- File: `~/projects/lomem/apps/tunatutor/backend/src/repositories/level-chat.repository.ts:236-249` at commit 8fa41788f (the file is on main; both functions were removed in bdd9ab7b8)
- Implements: L1; F1.5, F2.7b, F2.10
```ts
export async function claimLevelChatJudge(id: string, at: Date): Promise<boolean> {
  const { count } = await prisma.levelChat.updateMany({
    where: { id, judgeStartedAt: null },
    data: { judgeStartedAt: at },
  });
  return count > 0;
}

export async function saveLevelChatJudge(
  id: string,
  judge: { judgeLevel: string; judgeWouldChange: boolean },
): Promise<void> {
  await prisma.levelChat.update({ where: { id }, data: judge });
}
```
- Notes:
  - `updateMany ... where judgeStartedAt: null` is an atomic compare-and-set: two concurrent turns cannot both start the judge.

## Analogy to classic backend

| AI-side item (id) | classic Java/Spring equivalent | holds where | breaks where |
|---|---|---|---|
| Shadow mode (C9) | Dark launch; GitHub Scientist experiment (C38, C39; S9, S2) | new code runs in production, its result is not shown, the current result is returned | Scientist counts any mismatch as a bug; two model answers can both be right, so a mismatch needs a comparison rule and a person reading cases (S9) |
| Comparison rule (C11) | Scientist's custom compare block (S2) | code decides what counts as a match | the rule has to weigh evidence (cited turns, facts), not equality |
| Shadow call off request path (C12) | `@Async` method on a separate thread pool, fire and forget (S9) | the request does not wait; failures are caught and logged | a model call is slow and paid, so even off-path it costs money per request |
| Log-mode guard (C17) | Validation rule deployed in report-only mode (S9) | logs what it would reject, lets data through | each enforced refusal triggers another paid model call, not just a 400 to the client |
| Eval-gated flag (C7, C19) | Feature toggle released after the test suite passes (S9: "Flags and canaries work as for any service") | ordinary boolean; flip by PR | the gate passes on rates over bars fixed in advance, with real model calls, not on every assertion |
| Flag guard test (C22) | Unit test pinning a config constant (this file's analogy, not from the inputs) | flipping by accident fails the build | none found in inputs |
| Canary (C24) | Canary release judged on error rate and latency (S9) | small share first, widen if nothing got worse | the signal must be quality (discard, edit, thumbs-down); a bad answer is still a fast 200 (S9) |
| Sticky bucketing (C26) | Hash-based user bucketing in a flag service (this file's analogy, not from the inputs) | same as classic | none found in inputs |
| Feedback with context (C31) | Error report with correlation ID and request snapshot (this file's analogy, not from the inputs) | key plus snapshot make it reproducible | the model may answer differently on replay, so the stored output matters, not only the input |
| Data flywheel (C33) | Product analytics plus a dead-letter queue whose parked messages become test fixtures (S9, S4) | failures are parked and replayed as tests | a person must decide whether the model was really wrong and which answers are acceptable |
| Scheduled rerun (C35) | Nightly regression build (this file's analogy); synthetic monitoring (S4, for online evals) | runs on a schedule, alerts on failure | it must run with no code change, because the provider can change the model under the same name (C34) |
| Drift (C34) | Dependency upgrade that changes behaviour (this file's analogy, not from the inputs) | behaviour changes under you | there is no version bump of yours to blame; no deploy happened |
| Evals (C5) | Regression suite; online evals as synthetic monitoring or canary analysis (S4) | fixed cases, run before release | result is a pass rate against a bar, not green or red |

## Pitfalls

| id | mistake | consequence | what to do instead | source |
|---|---|---|---|---|
| M1 | A shadow call with side effects (sends an email, writes business data) | it is not shadow mode; users are affected | keep the shadow call read-only; write only its own result columns | S9 |
| M2 | A shadow call on the request path | every user pays its delay and its failures | run it in the background, fire and forget, errors caught | S9, X2 |
| M3 | Storing the shadow output but not the comparison | nobody can count disagreements later without re-running everything | store the comparison (e.g. `judge_would_change`) next to the answer | S9 |
| M4 | Deleting the old behaviour when the flag flips | a failed rerun leaves nothing to switch back to | keep the old code until the new one has passed several later reruns | S9 |
| M5 | Counting every mismatch as a win for the new behaviour | false "improvements" from answers that are only different | a comparison rule plus a person reading the disagreements against a bar | S9 |
| M6 | Judging a canary on error rates and latency | wrong answers stay invisible | quality signals: discarded, edited, thumbs-down | S9 |
| M7 | Writing the bar after seeing the numbers | the bar moves to fit the result | write it down before the measurement | S9 |
| M8 | Deciding a canary before the sample is large enough | chance differences of about 3 points look like regressions or wins | set sample size and difference threshold first; wait for them | S9 |
| M9 | Feedback stored without trace ID or session plus turn | cannot be reproduced, cannot become a test case | store the key and a snapshot of input and output | S9, S1 |
| M10 | Treating explicit feedback as the main signal | too few events to act on | collect implicit signals for almost every response | S9, S1 |
| M11 | Running the eval only when your code changes | silent provider changes go unseen | rerun on a schedule; turn the flag off on a missed bar | S9 |
| M12 | Enforcing a new content check at once | generation becomes slow, expensive or broken (503s) | start in log mode; enforce under a measured bar | S9, X12 |
| M13 | Loosening a guard because its rate is high, without reading what it refused | real bad items ship | read a sample: guard too strict → loosen or drop; items bad → fix the prompt | S9 |
| M14 | Flipping a flag by accident | unmeasured behaviour reaches users | a test asserting the flag value; the intended PR changes the test | S9, X16 |
| M15 | Random per-request canary assignment | one user sees two versions alternate | hash a stable ID | S9 |
| M16 | A degrade path that swallows the spend cap or a missing usage context | spend past the cap; silent metering holes | rethrow the undegradable codes first in every degrading catch | X6 |
| M17 | A shadow feature that never leaves shadow mode | spend with no benefit | set the go/no-go check in the plan; drop the feature if it shows no gain | X8 |
| M18 | Giving the second-opinion model the current answer | it can copy instead of judging | keep it blind to the current result (the judge never sees D) | S9, X1 |
| M19 | A scheduled rerun that only detects | users keep getting the worse behaviour | turn the flag off and keep the failing cases in the eval | S9, testing |
| M20 | Letting new AI behaviour (verdicts) go live before any gate measured it | regressions are found only afterwards | gate before release; Lomem's bar 1 checks afterwards | S9 (unverified that this happened) |

## Misconceptions

| id | what a newcomer believed | correct statement | evidence |
|---|---|---|---|
| Q1 | "It cannot break the chat" is contradicted by `rethrowIfUndegradable` | only two error codes are rethrown out of the judge function, and the background runner catches and logs them, so a shadow failure cannot reach the learner | X1, X2, X6; testing round 2 |
| Q2 | Shadow mode showed the placement judge was bad, so it was removed | it was removed the same day it was added, before any numbers came in; no reason is recorded | X7, E3; testing rounds 2-3 |
| Q3 | The removal story teaches nothing | the payoff is that removing a shadow feature changes nothing any user sees | S9; testing round 3 |
| Q4 | Bar 1 (agree with the old prompt) contradicts the goal of improving | bar 1 is a no-regression check on verdicts that were already live; the hand-written cases catch where the old prompt was wrong | C21; testing rounds 2-3 |
| Q5 | "Judge" names one thing | Lomem has two unrelated judges here: the placement judge (shadow, removed) and the translation grader (live) | C10; testing round 2 |
| Q6 | The new translation prompt is in shadow mode | its verdict, focus and why are live; only the marks are held back by the flag | X15; testing round 2 |
| Q7 | The translation prompt being live while its verdicts are gated is a contradiction | the verdicts went live before any gate; the gate protects only the marks, and checks the verdicts afterwards | S9 (unverified); testing round 3 |
| Q8 | The 15% guard bar is arbitrary or specific to the example | it is Lomem's chosen bar, written in the guard comment and the script; at 15% about 1 in 7 items needs a second paid call and 3 refusals in a row are about 3 in 1,000; when it was written relative to measuring cannot be shown | X9, X11, E5; testing round 1, fact-check |
| Q9 | A high guard rate means the guard is bad | it can also mean the generator writes bad items; a person reads a sample to tell which | S9; testing round 3 |
| Q10 | Lomem reads its log-mode records to get the rate | Lomem measures offline with the rates script because its traffic is too small for a rate per language and level (unverified claim about traffic) | S9, X11; testing round 3 |
| Q11 | Explicit and implicit feedback are equal | explicit is rare; implicit arrives for almost every response and gives the volume | S9, S1; testing round 3 |
| Q12 | A canary is compared on error rates and latency | it is compared on quality signals, because a wrong answer is a fast HTTP 200 | S9; testing round 1 |
| Q13 | An eval just scores outputs and reports a pass rate | yes, and its bars must be fixed before the run | S9; testing round 1 |
| Q14 | A failing scheduled rerun only raises an alert | the flag goes back off, users get the old behaviour, failing cases stay in the eval | S9; testing rounds 2-3 |
| Q15 | Every feedback row needs a trace ID, yet Lomem has none | session plus turn works where turns are stored; otherwise the trace ID is needed | X19, S9; testing round 2 |
| Q16 | The shadow judge is current Lomem code that ran for weeks | it existed only between commits 8fa41788f and bdd9ab7b8 on 2026-10-13; `judge.ts` is not on main | X1, X7; testing round 1 |
| Q17 | The judge reads the whole chat | it reads only the turns the learner answered, plus the extracted facts | X1; fact-check |
| Q18 | Two levels apart is rejected, so three apart is accepted | two or more levels apart is rejected (`Math.abs(gap) > 1`) | X3; fact-check |
| Q19 | Overheard always returns a 503 after three failed tries | it serves the best refused try that may still ship and returns a 503 only when none may | X12, X13; fact-check |
| Q20 | Lomem stores every turn with its input and output | there is no evidence of that; the feedback `session_id` is a free-form string, not a foreign key | X19; fact-check |
| Q21 | `server_context` stores what the user saw | only the AI tutor fills it, with turn number, level and languages; other session types store null | X20, X21; fact-check |
| Q22 | "Dark launch" comes from the Fowler Feature Toggles article | that article does not use the term | S3; fact-check |
| Q23 | The Spring sketch's flag does nothing | in the current sketch, `NEW_GRADER_ON` true returns the candidate-or-current level; false runs the shadow and returns current | S9; testing round 3 (fixed) |
| Q24 | The 15% bar was written before any guard was measured | git cannot show this: the bar and the 0 percent measurement landed in the same squashed commit | fact-check |

## Open questions

- Unverified: whether the placement judge ever ran in production or stored any rows; it was added at 07:25 and removed at 20:18 on 2026-10-13. (testing fact-check)
- Unverified: why the judge was removed; the #624 commit message says only "drop the shadow judge" and "The blind shadow judge and its columns are removed (follow-up migration)." Was it a failure of the approach or a cost decision? (testing final read)
- Unverified: that a person writes the bar-3 count into the pull request beside the gate output; the repo does not record this process. (testing fact-check)
- Unverified: that Lomem has too few users for the guard log to give a rate per language and level. (testing fact-check)
- Unverified: that the new translation verdicts reached learners before any gate measured them; consistent with the code, no deploy records. (testing fact-check)
- Open: should a reader copy or avoid letting verdicts go live before a gate? (testing final read)
- Open: where `rolloutPercent` lives in the canary; if it is a constant, each step from 5 to 25 to 100 needs a deploy. (testing final read)
- Open: how implicit signals such as edit distance become a pass/fail bar; only the discard rate gets a bar in the inputs. (testing final read)
- Open: how many eval cases are enough before 95% bars mean anything; the gate asks for at least 20 hand-checked real rows and the plan for 10 to 20 teacher-placed chats, but the inputs give no general rule. (testing final read, X17, X8)
- Code versus comment: `judge.ts` says "Never throws" (lines 41-42), but line 99 rethrows the two undegradable codes; the background runner then catches them. (X1, X2)
- Code versus comment: `acceptJudge`'s doc says "Two apart: rejected"; the code rejects any gap above 1. (X3)
- Code versus comment: `judge.ts` header says the judge reads "the probe-tagged transcript", but the prompt gets only answered turns; unanswered turns still feed `rows`. (X1)
- Code versus drafts: the drafts state the up-move rule as "two cited turns that meet a B2 rule"; the code also requires no real breakdown at the judge's level anywhere in the chat. (X3, X4)
- Code versus comment: `guards.ts` says the rate must be "under about 15 percent"; the rates script requires under 15% in the worst cell of every language and band. (X9, X11)
- Disagreement: ADR-049 lists "question rules out a choice" as part of the grammar-check model call and enforced; the code also has a guard of that name, enforced and ranked GIVEAWAY. Not a conflict, but two mechanisms share the name. (X22, X9, X13)
- Research map versus code: the Lomem research says `TD_JUDGE_MARKS` "is used at lines 108, 138, 155 and 174"; only line 108 reads the constant, the others read `marksEnabled`. (S5, X15)
- Research map versus code: the Lomem research cites `level-chat/judge.ts` as if current; it is not on main. (S5, testing)
- Assumption: E5's "3 in 1,000" assumes refusals on successive tries are independent; the next try's prompt carries the refusal reason, so they are probably not. (E5, X12)
- Not covered: whether the translation drill offers a feedback button with `wrong_correction`; the E9 story is made up. (E9, S9)
- Not covered: implementation of a flag service, automated canary comparison, or a scheduled eval job in Lomem; none exist (no Lomem CI workflow references the gate or rates scripts).
- Not covered: Eugene Yan's "Defensive UX" pattern details beyond "citations, confidence, an easy undo". (S4)
- Not covered: Hamel Husain's CI/CD guidance; the research did not read that part of the FAQ. (S4)
- Not covered: whether `staging` holds real learner data; a reader asked. (testing round 3)

## Sources

| id | title | author or publisher | date | URL | what it supports |
|---|---|---|---|---|---|
| S1 | Patterns for Building LLM-based Systems & Products | Eugene Yan | about Aug 2023 | https://eugeneyan.com/writing/llm-patterns/ | "Collect user feedback" (explicit and implicit feedback, data flywheel), "Defensive UX" |
| S2 | Scientist | GitHub | not given | https://github.com/github/scientist | candidate code run next to control, control result returned, mismatches published |
| S3 | Feature Toggles (aka Feature Flags) | Pete Hodgson, martinfowler.com | not given | https://martinfowler.com/articles/feature-toggles.html | feature flags, canary releasing; does not use "dark launch" |
| S4 | Web research catalogue, block 16 and the request-path summary | internal (research-web.md) | 2026 | `sources/research-web.md` | feedback loop analogue, minimal and mature feedback, drift, feedback attached to trace ID, failures into eval datasets gating CI; backend analogues are the researcher's own |
| S5 | Lomem code map, sections 6c, 7, 13 | internal (research-lomem.md) | 2026 | `sources/research-lomem.md` | locations of the shadow judge, gate, fixture, flag, guard modes, runtime switches; no flag service |
| S6 | Langfuse prompt management | Langfuse | not given | https://langfuse.com/docs/prompt-management/overview | prompt versions and labels; promotion gated on eval; rollback by moving a label (via S4) |
| S7 | AI Evals: Everything You Need to Know | Hamel Husain and Shreya Shankar | updated Sep 2026 | https://hamel.dev/blog/posts/evals-faq/ | online evals on sampled traffic, error analysis cadence (via S4) |
| S8 | Building A Generative AI Platform | Chip Huyen | 25 Jul 2024 | https://huyenchip.com/2024/07/25/genai-platform.html | request-path ordering in which feedback attaches to traces (via S4) |
| S9 | Section 16 long fact-checked draft and short tested version | this project (sources/sections-long, sources/sections-tested) | 2026-10 | `sources/sections-long/17-rollout.html`, `sources/sections-tested/17-rollout.html` | the block's framing, all made-up examples (readout, canary, Java sketch, rerun cost, cognate example, fixture story) |
