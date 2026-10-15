---
id: observability
number: 13
title: Observability for LLM calls
summary: Observability for LLM calls keeps one record per model call (exact text in and out, model and prompt version, tokens, cost, latency) and scores a sample of live traffic, because a wrong model answer returns HTTP 200 with no exception and quality can change when nobody deployed anything.
lomem_status: partly
depends_on: [gateway, prompts]
related: [evals, caching, guardrails, governance, structured, agents, tools, rollout]
---

# Observability for LLM calls

## Story

### Hook
- Headline: Log every model call with its input and output. ==A 200 status says nothing about whether the answer was right.==
- Setup: A language app asks a model (an LLM, a service that takes text and returns text) to grade a learner's Portuguese. In this made-up incident, learners type `Eu sou um barista.`, which is correct, and the app marks it wrong. Nothing was deployed for a week, the logged call returned 200 in 1.4 seconds, and the error tracker is empty.
- Teaser: A log can show what every model call cost. Nothing in it says whether the answer was right.

### Panel
- Title: GPT-4 finding prime numbers, same API name, three months apart
- Row: March 2023 version | 84% | correct answers | struck
- Row: June 2023 version | 51% | correct answers | accent
- Row: Quality lost with no deploy | 33 points | | big
- Source: Real numbers from a 2023 study. The 33-point drop is the difference of the two.
- Refs: E7, N9, N10, C23

### Idea
- Sentence: Write ==one record per model call== with the exact text, the prompt version (which revision of your instructions to the model was sent) and the model that actually answered. Then score a sample of live calls to catch quality drops that no deploy of yours explains.
- Analogy: It is distributed tracing plus APM plus a billing meter. The model call is one more timed downstream call. It also carries tokens (the units of text the vendor bills by) and cost. The analogy breaks at correctness. APM counts a fast 200 as a success, but a model's reply can be fast, return 200 and still be wrong. So you keep the reply text and score it, which APM never does.

### Walkthrough
- Title: A model changes behind its name. Here is how the records catch it.
- Lead: A made-up incident on a real feature, with real model names. Every number in it is made up unless a step says otherwise. The grading prompt is at version 14. The app requests `gemini-flash-latest`, an alias: a model name the vendor can point at a different model.
- Lanes: Wrapper, Gemini, Records, Checker, Owner
- Step 1 · A wrong grade comes back as a success | refs: F1.6, F1.7, E1, P2
  - Arrow: Wrapper → Gemini: grade, model gemini-flash-latest
  - Reply: Gemini → Wrapper: 200 in 1.4 s · verdict wrong | bad
  - Text: On Monday morning Google points the alias at a preview (pre-release) model. The grading feature now marks correct answers wrong. Every call is fast, returns 200 and throws nothing.
- Step 2 · The wrapper writes one record per call | refs: F1.11, F1.14, C15, E2, N16
  - Event: Wrapper → Records: v14 · preview model · $0.000196
  - Event: Wrapper → Records: redacted prompt and reply
  - Text: Every model call goes through one wrapper, a single function in your code. It logs the prompt version and the model the reply says answered, not only the one requested. It also stores the prompt and reply with names and emails scrubbed out. That text goes to a restricted table kept 14 days.
  - Fact: The response model name `gemini-2.5-flash-preview-09-2025` is real.
- Step 3 · A second model scores a 2% sample | refs: F1.15, F2.4, F2.6, C17, C25, N17, M6, M11
  - Self: Wrapper: trace-ID hash mod 100 < 2
  - Arrow: Records → Checker: redacted text and rubric
  - Reply: Checker → Records: DISAGREE, stored as 0 | bad
  - Text: Calls that finished normally (finish reason `STOP`, not failed and not cut off at the length limit or by the content filter) enter a random 2% draw. Drawn calls go on a queue, off the request path. A checker model, a second pinned model, reads the redacted text, the grader's verdict and a rubric (a written list of what counts as correct). It answers AGREE if the verdict is correct and DISAGREE if not, stored as 1 or 0.
- Step 4 · The nightly job sees Monday fall below its band | refs: F2.7, F2.8, C29, C30, N20, N21, N23, N24, N25, Q9
  - Self: Records: Monday 0.81, alert line 0.92
  - Event: Records → Owner: alert at 06:00 Tuesday | bad
  - Text: The agreement rate is the share of a day's scored calls where the checker agrees with the grader's verdict. The alert line is 0.92. It sits three standard deviations (how far the rate usually moves) below the rate's 30-day mean. Monday scores 0.81, so the alert fires at 06:00 Tuesday. The first learner reports come that afternoon.
- Step 5 · Grouping by version shows the model moved | refs: F3.2, F3.4, C15, N26, Q7
  - Arrow: Owner → Records: group by prompt_version, model
  - Reply: Records → Owner: v14 both days · graded wrong 4% to 19%
  - Text: The prompt version is 14 on every call, so no prompt edit caused it. The response model changes on Monday. With it, the share of answers graded wrong goes from 4% to 19%. The stored text lets the owner read the five reported calls.
- Step 6 · Pin the model and replay ten times | refs: F3.6, F3.7, F3.8, C33, N27, M16
  - Tag: Wrapper: request gemini-2.5-flash, pinned
  - Arrow: Owner → Gemini: 5 stored prompts × 10 runs
  - Reply: Gemini → Owner: 50 of 50 pass | ok
  - Text: The team requests a fixed version name instead of the alias. The same prompt can give a different reply each run, so the owner replays each of the five stored prompts ten times. All fifty runs pass. The barista case joins the test set.

### Takeaways
1. A wrong answer returns 200 | The call is fast, throws nothing and leaves the error tracker empty. Only a quality score catches it. | P2, P7, Q16, M5
2. Pin the checker and bill it | A checker on a moving alias changes along with the model it checks. Send its calls through the same wrapper under their own feature name, so its cost shows. | M11, M12
3. Score about 200 calls a day | That keeps chance noise near 1.5 percentage points of the agreement rate. 200 is 2% of 10,000 calls a day, or 20% of 1,000. Score from a queue, never inside the request. | C31, E4, E10, N18, N19, M6
4. Redact names inside the prompt text | A prompt is one long text field with names and emails under no sensitive key. Redact the text itself and keep it in a restricted table. | P8, M4, M10

### Trap
- Title: Keeping the text only for the sampled calls
- Assume: "We score 2% of calls, so we only need the text of those 2%." | So the wrapper saves prompt and reply only when a call is picked for scoring.
- Actually: With a 2% sample, a reported call is almost never in it. | Store the redacted text of every call for a short window, 14 days in the example, so the owner can read the five reported calls. Sample only the scoring.
- Refs: M7, Q1, N16, E1

### Build
- Title: The smallest version is one wrapper that writes a record per call
- Lead: Record the call, keep the redacted text, and sample it for scoring. This Java sketch is shortened from the made-up wrapper in example E9. It is a teaching sketch, not production code.
- Refs: E9, F3.6
- Code:
```java
static final String MODEL = "gemini-2.5-flash";             // [6] a fixed name, never an alias
public GradeResult grade(GradeRequest req, long userId) {
  Prompt prompt = prompts.get("translation_grade");         // name, version, text from the DB
  String text = prompt.render(req), traceId = tracer.currentSpan().context().traceId();
  long start = System.nanoTime();
  ModelReply reply = null; GradeResult result = null;
  try {
    reply = client.call(MODEL, text);                       // [1] a wrong answer is still a 200
    return result = parse(reply.text());
  } finally {
    long latencyMs = (System.nanoTime() - start) / 1_000_000;
    CallRecord rec = CallRecord.of(traceId, "translation_grading", userId,
        prompt, MODEL, reply, result, latencyMs);           // [2] response model read from reply
    callLog.write(rec.withCost(prices.cost(rec)));          // [2] one line per call, failures too
    callText.save(traceId, redactor.scrub(text),             // [2] redacted text, every call
        reply == null ? null : redactor.scrub(reply.text()));
    if (result != null && "STOP".equals(rec.finishReason())
        && Math.floorMod(traceId.hashCode(), 100) < 2) evalQueue.send(traceId); // [3] finished normally, 2% drawn
  }
}
```
- Note: The checker (step 3), the nightly job (step 4) and the query (step 5) run over these records, outside the wrapper. One gap to fix before production: if the code in `finally` throws, its exception replaces the call's return value or the call's own exception. It needs its own try and a logged warning.

## Summary

Observability for LLM calls records what the model saw, what it said and what it cost, in one record per model call: the exact text sent, the text that came back, the model and prompt version, the token counts, the cost and the time taken.
On top of those records you sample live traffic, score it off the request path, and watch the daily scores for changes that no deploy of yours explains.
It exists because an LLM call can return a confident wrong answer with HTTP 200, no exception and no log line, so the only evidence of a bug is the text that went in and came out.
Compared with a classic backend, the "logic" is prompt text plus a model you do not run, every call has a variable price, the prompt can change without a code deploy, the model can change behind the same name, and the stored payload is your users' personal data.

## Problem

- P1 · The bug is in the text. A wrong answer is usually explained by what the prompt contained (a missing rule, a truncated document, the wrong user's data), so you debug by reading the prompt and the reply, not a stack trace. (S20; testing; S22 block 12)
- P2 · A wrong answer leaves no trace in classic telemetry. The call returns HTTP 200, takes normal time, throws no exception and the error tracker stays empty. (S20)
- P3 · Every call has a variable price. Cost depends on how many tokens each call used, so one feature with a long prompt can double the monthly bill with no change in traffic. (S20)
- P4 · The prompt changes outside a code deploy. Many teams, Lomem included, store prompt templates in a database so they can edit them without a release. A record that does not say which prompt version ran cannot show whether an edit caused a regression. (S20; X25)
- P5 · Quality can change when nobody on your team deployed anything (drift). Causes: the provider updates the model behind the same name, a provider bug degrades answers, or users start sending input you never tested. (S20; S2; S3; S22 adds "the corpus goes stale")
- P6 · Stored prompts contain your users' words (names, emails, account numbers), so a store of prompts is a store of personal data. (S20; S22: "Traces contain PII")
- P7 · Latency and error alerts never fire on drift, because a drifted answer is fast and returns 200. (S20)
- P8 · Classic log redaction removes fields by key name; that cannot help with a prompt, which is one long prose field holding personal data under no sensitive key. (S20; X10)
- P9 · A requested model name may be a moving alias, so the name you sent does not tell you which model version answered. (S20)

## Concepts

### C1 · Model (LLM)
- Definition: A model, or LLM (large language model), is a service you send text to and get text back from.
- Facts:
  - Examples are Google's Gemini and Anthropic's Claude. (S20)
  - GPT-4 is an OpenAI model. (S20)
  - A model can give a different reply to the same prompt on each run. (S20; testing round 3)
- Relations: C1 is run by C2. C1 is called with C3. C1 is billed in C6.

### C2 · Provider
- Definition: The provider is the company that runs a model and sells access to it through an HTTP API.
- Facts:
  - Testing readers asked whether "provider" means the vendor or the API; the draft means the company. (testing round 2)
  - In the made-up record the provider is written `gcp.gemini`. (S20, made up)
  - In Lomem a "provider" object is one model entry (id such as `gemini-2.5-flash`) in the registry, not a company. (X26)
- Relations: C2 runs C1. C2 may move C16 to a new model. C2 reports C15 and C17.

### C3 · Prompt
- Definition: The prompt is the text you send to the model: fixed instructions written by your team plus the user's data.
- Facts:
  - A prompt holds whatever the user typed, including names, emails and account numbers. (S20)
  - In the running example the prompt carries the English sentence, the expected answer and the learner's answer. (S20)
  - In Lomem the request a model sees has a system prompt, messages and optionally tools (`LlmRequestSnapshot`). (X4)
  - Testing readers did not know "system prompt", "messages" or "tools" as parts of a model request. (testing round 1)
- Relations: C3 is built from C4. C3 contains C22. C3 is measured by C7.

### C4 · Prompt template
- Definition: A prompt template is the fixed part of a prompt: a text with placeholders that your code fills in.
- Facts:
  - Testing readers asked how a template differs from a prompt; the template is the fixed text, the prompt is the filled-in result. (testing round 1)
  - Lomem stores templates in a `prompt_templates` table with one current `content` per `key`. (X25)
  - The OTel attribute for the template name is `gen_ai.prompt.name`. (S1; testing fact-check)
- Relations: C4 has versions C5. C4 renders C3. prompts.C* covers how templates are managed.

### C5 · Prompt version
- Definition: A prompt version is one edit of a prompt template; each edit is a new version.
- Facts:
  - The call record must name the prompt version so a quality drop can be tied to the edit that caused it. (S20)
  - In the barista incident `prompt_version` was 14 throughout, which ruled out a prompt edit. (S20, made up)
  - OTel defines `gen_ai.prompt.version`, marked Conditionally Required. (S1; testing fact-check)
  - An earlier draft wrongly said OTel has no prompt-version attribute and suggested a custom `app.prompt.version`; the fact-check fixed that. (testing fact-check)
  - Lomem keeps one `prompt_template_versions` row per historical revision (`template_key`, `content`, `created_at`); there is no version number column. (X25)
  - Lomem's usage ledger rows carry no prompt version. (X5, X11)
  - The S22 catalogue's minimal prompt setup: log "the version hash" on every call when prompts are versioned template files in the repo. (S22 block 2; S7)
  - S22 mature prompt setup: each prompt version is linked to traces and eval scores. (S22 block 2; S7)
- Relations: C5 is a field of C10. C5 is a chart dimension of C29. C5 is part of prompts.

### C6 · Token
- Definition: A token is a chunk of text of roughly three or four characters that models read and write and providers bill by.
- Facts:
  - The provider bills per token, in and out. (S20)
  - Token counts come in three kinds: input, cached input and output. (S20)
- Relations: C6 splits into C7, C8, C9. C6 drives C19.

### C7 · Input tokens
- Definition: Input tokens are the tokens of the whole prompt.
- Facts:
  - OTel attribute: `gen_ai.usage.input_tokens`. (S1)
  - Gemini reports them as `promptTokenCount`, which includes cached tokens. (X16, X17; testing fact-check)
- Relations: C7 contains C8 (for Gemini, OpenAI, OTel). C7 is a field of C10.

### C8 · Cached input tokens
- Definition: Cached input tokens are the part of the input that matches the start of a prompt the provider received recently; the provider reuses its earlier work on them and bills them at a lower price.
- Facts:
  - "Recently" is "in the last few minutes" in the draft; this matches Anthropic's and OpenAI's default cache lifetimes, but Gemini's implicit cache lifetime was not found in the docs fetched. (S20; testing fact-check, unverified)
  - Putting the fixed instructions first and the user's data last makes the shared start longer. (S20; S23 §11b)
  - In Gemini's and OpenAI's counts, and in the OTel names, cached tokens are a subset of the input tokens, not an addition. (S20; testing fact-check)
  - Anthropic's API reports cached tokens in a separate field. (testing fact-check)
  - OTel attribute: `gen_ai.usage.cache_read.input_tokens`. (S1; testing fact-check)
  - Gemini field: `cachedContentTokenCount`. (X16)
  - Lomem clamps cached input to at most the input count and writes uncached input as input minus cached. (X5, X11)
  - Lomem prices cached input under its own key `<providerId>:text-input-cached`. (X5)
  - Readers in two testing rounds left cached input out of the record fields and reported it as undefined. (testing rounds 1, 2)
  - A reader asked whether the cache discount applies only to your own recent prompts or to any customer's; the inputs do not answer this. (testing final read)
- Relations: C8 is part of C7. C8 lowers C19. C8 is explained further in caching.

### C9 · Output tokens
- Definition: Output tokens are the tokens of the reply.
- Facts:
  - OTel attribute: `gen_ai.usage.output_tokens`. (S1)
  - Gemini reports visible answer tokens as `candidatesTokenCount` and reasoning ("thinking") tokens as `thoughtsTokenCount`. (X16, X17)
  - The provider bills thinking tokens as output, so Lomem adds them to the output row. (X5, X11, X17)
- Relations: C9 is a field of C10. C9 is the most expensive line of C19 in E3.

### C10 · Call record
- Definition: The call record is the one structured record the wrapper writes for every model call, failed calls included.
- Facts:
  - Fields: trace ID, feature, user (or account billed), prompt template name and version, provider, requested model, responding model, input, cached input and output tokens, finish reason, latency, cost, and the parsed result. (S20; testing key points)
  - A failed call has null where it has no value. (S20)
  - S22 minimal list also includes tool calls. (S22 block 12)
  - The record answers what happened, which version ran, how much and how slow. (S20 heading)
  - The wrapper parses the reply into the feature's own result type (here score and verdict) and stores it in the record, so quality can be queried without re-reading text. (S20)
  - The record's metadata holds no user text, so it can be kept as long as your logs. (S20)
  - In the smallest version the record is one log line, which cannot be updated later; scores therefore live in their own table joined by trace ID. (testing round 2)
- Relations: C10 is written by K1. C10 carries C12. C10 is joined to C29 by C12. C10 is shaped by C34.

### C11 · Wrapper (one door)
- Definition: The wrapper is one piece of your code that every model call goes through, so one place writes the record.
- Facts:
  - Without Spring AI, a hand-written wrapper is enough for the smallest version. (S20; E9)
  - In Lomem the shared gateway is "the one door every app's LLM calls go through" and exposes `observe` request/response taps. (X1)
  - Testing readers did not know "gateway" in Lomem's sense. (testing round 1)
- Relations: C11 is gateway (block 1). C11 writes C10. C11 sends C25 samples.

### C12 · Trace and trace ID
- Definition: A trace ID is the ID your tracing library gives each incoming request and passes to every downstream call, so all work for one request shares it.
- Facts:
  - Tracing libraries named: Micrometer Tracing (which Spring Boot uses) and OpenTelemetry. (S20)
  - A background job starts a new trace when it starts. (S20)
  - Trace IDs are random, so a hash of the trace ID modulo 100 gives a random sample that every instance agrees on. (S20)
  - Made-up trace ID in the record: `4f2a9c1e7b0d4c55`. (S20, made up)
  - User feedback attaches to the trace ID. (S22)
  - Lomem has no OpenTelemetry or distributed tracing. (S23 §9)
- Relations: C12 keys C20 and C29. C12 drives C25. C12 contains C13.

### C13 · Span and client span
- Definition: A span is one timed operation inside a trace, such as one outgoing HTTP call; a client span is a span for a call your service makes.
- Facts:
  - A model call is a client span in the OTel GenAI conventions. (S20; S1)
  - A mature setup has one span per model call when a request makes several, all under one trace. (S20)
  - S22: model, tool and agent steps each get a span. (S22)
  - Testing readers met "span" before its definition and did not know "client span". (testing rounds 2, 3)
- Relations: C13 is part of C12. C13 carries C34 attributes. C13 is produced by C14.

### C14 · Micrometer observation
- Definition: A Micrometer observation is one instrumented operation that Micrometer turns into a timer metric and, when tracing is on, into a span.
- Facts:
  - Spring AI is Spring's library for calling models. (S20)
  - Spring AI emits an observation named `gen_ai.client.operation` for every chat call. (S20; S4)
  - It carries model names, token counts and finish reasons. (S20)
  - Prompt and reply text are off by default; `spring.ai.chat.observations.log-prompt` and `spring.ai.chat.observations.log-completion` switch them on. (S20; S4; testing fact-check)
  - You still add feature, prompt version, cost and parsed result yourself. (S20)
  - Readers in three rounds left out that this logging is off by default. (testing)
- Relations: C14 produces C13. C14 is K15.

### C15 · Requested model versus response model
- Definition: The requested model is the model name you sent; the response model is the model version the provider says actually answered.
- Facts:
  - Gemini reports it in `modelVersion`; OpenAI and Anthropic in `model`. (S20; testing fact-check for Gemini)
  - OTel attributes: `gen_ai.request.model` and `gen_ai.response.model`. (S1)
  - Recording only the requested name is a mistake: the reply often names a more specific version, and that is the one that changed. (S20)
  - The provider does not always report a more specific version; when response equals request, only quality scores reveal a silent model change. (S20)
  - Lomem's Gemini adapter does not read `modelVersion`; no Lomem `.ts` file under `apps` or `packages` mentions it. (X16; code search 2026-10-15)
  - Lomem's ledger metadata holds `providerId` and `providerName` (tunatutor) or also `modelId` (shared meter), all request-side. (X5, X11)
- Relations: C15 is a field of C10. C15 is a chart dimension of C29. C15 exposes C16.

### C16 · Model alias, preview model and pinning
- Definition: A model alias is a moving name that the provider points at its newest model; pinning means requesting a fixed version name instead.
- Facts:
  - `gemini-flash-latest` is a real alias that Google points at its newest Flash model. (S20; testing fact-check)
  - Flash is Google's name for its cheaper, faster Gemini models. (S20)
  - `gemini-2.5-flash-preview-09-2025` is a real preview (pre-release) model name. (S20; testing fact-check)
  - Requesting a moving alias in production instead of a fixed version name is a mistake. (S20)
  - The checker model must also be pinned to a fixed version so it does not change along with the model it checks. (S20)
  - Readers did not know "alias", "preview" or "pinning" and asked why a preview is riskier; the inputs do not say. (testing rounds 2, 3)
  - Lomem's tunatutor offers only `gemini-2.5-flash` and `gemini-2.5-flash-lite`. (X26)
- Relations: C16 causes C23. C16 is detected by C15 and C29. C16 is part of gateway model choice.

### C17 · Finish reason
- Definition: The finish reason says why the model stopped writing.
- Facts:
  - Gemini values: `STOP` (finished), `MAX_TOKENS` (hit the length limit), `SAFETY` (the provider's content filter cut it off). (S20; testing fact-check)
  - OTel attribute: `gen_ai.response.finish_reasons`. (S1)
  - Calls that stopped at `MAX_TOKENS` or `SAFETY` are not scored by the online eval; their rate is charted from the log records. (S20)
  - Lomem classifies finish reasons once: `STOP` → `end_turn`, `MAX_TOKENS` → `max_tokens`, a set of blocked reasons → `blocked`, malformed tool calls → `malformed_tool_call`, anything else → `stop_sequence`; a prompt block reason makes it `blocked` whatever the finish reason. (X14)
  - Lomem's blocked set: SAFETY, RECITATION, PROHIBITED_CONTENT, BLOCKLIST, SPII, IMAGE_SAFETY, IMAGE_PROHIBITED_CONTENT, IMAGE_RECITATION. (X14)
  - Lomem's root CLAUDE.md says to capture the real `finishReason` when a call misbehaves. (X24)
  - A reader noted that only STOP was named in one version; later versions name all three. (testing round 2)
- Relations: C17 is a field of C10. C17 gates C25. C17 is detailed in structured and guardrails.

### C18 · Content filter
- Definition: The content filter is the provider's own safety check that can cut off or block an answer.
- Facts:
  - It shows up as finish reason `SAFETY` (Gemini). (S20)
  - Readers flagged "content filter" as mentioned but not explained. (testing round 2)
  - Lomem has no separate moderation step; the only safety handling is the provider's finish and block reasons mapped in `finish.ts`. (S23 §8)
- Relations: C18 produces C17. C18 belongs to guardrails.

### C19 · Price table and cost
- Definition: Cost per call is computed from the token counts and a price table that holds prices per million tokens per model.
- Facts:
  - Draft table `model_prices`: model name, the date from which a price holds, three prices per million tokens (input, cached input, output). (S20)
  - Someone adds a row when the provider changes its prices. (S20)
  - If the responding model has no row, write no cost and count the miss, so a new model shows up as a gap rather than a free call. (S20)
  - Lomem's `provider_price_config` is keyed by `<providerId>:text-input`, `:text-input-cached`, `:text-output`, with `effectiveFrom`, `effectiveTo` and `isActive`. (X12, X13)
  - Lomem writes a key with no price row at $0 with `isEstimated`, never dropping the tokens, and logs a warning once per miss window. (X12)
  - Lomem refuses to make a model active or a fallback unless all three price rows exist (`assertModelPriced`). (X13)
  - Lomem stores cost in `computedUsdMicros` (millionths of a dollar). (X12 fields)
- Relations: C19 is a field of C10. C19 depends on C7, C8, C9. C19 feeds governance and gateway budgets.

### C20 · Prompt and reply text store
- Definition: The text store keeps the redacted prompt and reply of every call in a separate table keyed by trace ID, with short retention and restricted access.
- Facts:
  - Draft table `llm_call_text`: `trace_id`, `created_at`, redacted prompt, redacted reply. (S20)
  - A nightly job deletes rows older than 14 days. (S20)
  - Only the engineers on call can read it. (S20)
  - Text is kept for every call over the short window; only scoring is sampled. (testing round 1)
  - The 14-day window is what lets you read the five barista prompts when the reports arrive. (S20)
  - If the record moves into tracing spans later, keep the text in the restricted table unless the tracing backend has the same short retention and narrow access. (S20; testing round 2)
  - S22 minimal says "sample full payloads, with redaction". (S22 block 12)
  - Lomem's closest equivalent is the postmortem mirror, a ring buffer enabled outside production. (X8, X9)
- Relations: C20 is keyed by C12. C20 is filled through C21. C20 is read by K9.

### C21 · Content redaction
- Definition: Content redaction scrubs personal data out of the text itself, rather than removing fields by key name.
- Facts:
  - Pattern matching catches emails, phone numbers and IBANs (international bank account numbers). (S20)
  - A detector library such as Microsoft Presidio also finds names. (S20)
  - Redaction runs inside the wrapper before the write. (S20)
  - The checker model reads only redacted text. (S20)
  - Lomem's shared `redact()` scrubs by key name (password, token, authorization, API keys…); `scrubEmails()` scrubs email addresses inside any string. (X10)
  - Lomem's own comment: `redact()` "scrubs by KEY NAME, which is the wrong tool for an address: an email arrives inside prose". (X10)
  - The postmortem mirror calls `redact()` and `truncateLargeBody()`, not `scrubEmails()`. (X8)
  - Whether the unredacted prompt may be sent to the provider at all is a contract question with that provider. (S20)
- Relations: C21 protects C22. C21 feeds C20. C21 belongs to guardrails and governance.

### C22 · PII
- Definition: PII (personally identifiable information) is data that identifies a person, such as a name, email or account number.
- Facts:
  - The OTel spec says the input "is likely to contain sensitive information including user/PII data". (S1; testing fact-check: exact quote)
  - Readers did not know PII or IBAN. (testing rounds 1, 3)
  - A reader asked whether `user_id` in the record itself is personal data with its own retention; the inputs do not answer. (testing final read)
- Relations: C22 is contained in C3. C22 is removed by C21. C22 makes C35 opt-in.

### C23 · Drift
- Definition: Drift is a change in answer quality when nobody on your team deployed anything.
- Facts:
  - Causes: the provider updates the model behind the same name, a provider bug degrades answers, or users send a kind of input you never tested. (S20)
  - S22 adds: the corpus goes stale. (S22)
  - GPT-4 identified prime numbers with 84% accuracy in March 2023 and 51% in June 2023 under the same API name. (S2)
  - Anthropic's postmortem covers provider bugs that degraded answers for weeks, August to mid-September 2025. (S3; testing fact-check)
  - Latency and error alerts do not fire on drift. (S20)
  - Drift is detected by scoring a sample of live traffic every day. (S20)
  - If replayed old prompts fail too, the model changed; if they pass while live scores fall, users' inputs changed. (S20)
- Relations: C23 is caused by C16. C23 is detected by C24, C29, C30, C32.

### C24 · Eval and online eval
- Definition: An eval is a check that scores a model's answers; an online eval runs on live production calls rather than a fixed test set.
- Facts:
  - Readers noted "eval" itself was never defined in one version. (testing round 1)
  - The online eval runs off the request path, from a queue. (S20)
  - Running the online eval inside the user's request adds a second model call to every response. (S20)
  - S22: online evals score sampled traces asynchronously; online evals are like synthetic monitoring or canary analysis. (S22 blocks 11 and request path)
- Relations: C24 uses C25, C27, C28. C24 produces C29. C24 belongs to evals.

### C25 · Random sample by trace-ID hash
- Definition: The random sample picks a fixed share of calls by hashing the trace ID, so every instance makes the same choice for the same ID.
- Facts:
  - Rule: send the trace ID to the queue when its hash modulo 100 is below 2, a random 2%. (S20)
  - Failed calls and calls stopped at `MAX_TOKENS` or `SAFETY` are not scored. (S20)
  - Set the rate per feature to reach about 200 scored calls a day: 2% of 10,000 calls, or 20% of 1,000. (S20)
  - A feature with fewer calls is scored in full or charted per week. (S20)
  - A random sample gives the rate you chart. (S20)
  - A reader asked whether excluding MAX_TOKENS, SAFETY and failed calls biases the agreement rate. (testing final read)
- Relations: C25 feeds C24. C25 is sized by C31. C25 complements C26.

### C26 · Targeted sample (uncertain answers)
- Definition: A targeted sample picks answers where the grader is least sure, to find problems with fewer human reviews.
- Facts:
  - Use it in addition to the random sample, not instead. (S20)
  - Lomem's hand-made one: in a Tunatutor checkpoint (a level test) every answer scored between 50 and 85 is logged for a person to review. (S20; X22)
  - Just above the "wrong" line is where the grading is least sure. (S20)
  - The Lomem log line puts the learner's own answer into the normal production log. (S20; X22)
  - A reader read the borderline sample as conflicting with the random 2%. (testing round 2)
- Relations: C26 complements C25. C26 violates C20's rule in Lomem (M4).

### C27 · Deterministic check
- Definition: A deterministic check is plain code with a fixed answer, such as "is the score between 0 and 100".
- Facts:
  - Use it where one exists, before a checker model. (S20)
  - Readers found the term inferable but undefined. (testing round 3)
  - Lomem's translation judge runs a deterministic pre-pass before the model; exact matches never reach the model. (S23 §6a)
- Relations: C27 is part of C24. C27 is preferred over C28.

### C28 · Checker model and rubric
- Definition: The checker model is a second model that judges a sampled answer against a rubric, a written list of what counts as correct.
- Facts:
  - Use a strong model pinned to a fixed version name. (S20)
  - Send its calls through the same wrapper under their own feature name, so its cost is logged too. (S20)
  - A person can also score. (S20)
  - Nobody has to write the correct verdict for each sampled call in advance. (S20)
  - It replies AGREE or DISAGREE; the consumer stores 1 or 0 and rejects any other reply as a failed check. (S20)
  - Earlier versions called it "the judge" or "grader", which collided with the grading feature; readers could not tell which judge was meant. (testing rounds 2, 3)
  - A reader asked whether provider-side drift could hit the checker and the checked model at once if both come from the same provider. (testing final read)
- Relations: C28 is part of C24. C28 is evals' LLM-as-judge. C28 produces C29.

### C29 · Eval score and agreement rate
- Definition: The eval score is the per-call score the online eval stores; its daily average is the number you chart (in the running example, the agreement rate).
- Facts:
  - Stored in an `llm_eval` row: `trace_id`, `eval_score`, checker and rubric version, time. (S20)
  - Joined to the call records by trace ID. (S20)
  - Scores hold no user text, so they are kept for months. (S20)
  - Charted as a daily average per prompt version and per response model. (S20)
  - The eval score must not be confused with the grading feature's own score; testing readers could not say which number the drift chart plots when both were called "score". (testing round 1)
  - Readers wrongly wrote eval_score "back to the call's record"; a log line cannot be updated. (testing round 2)
- Relations: C29 is produced by C28 or C27. C29 is compared to C30. C29 is keyed by C12.

### C30 · Alert band
- Definition: The alert band is the usual range of a daily figure; a day below it fires an alert.
- Facts:
  - Example band: three standard deviations below the mean of the last 30 days. (S20)
  - A standard deviation is a measure of how far the daily figure usually moves. (S20)
  - A rise is worth a look but needs no alert. (S20)
  - Readers flagged standard deviation as assumed knowledge. (testing round 3)
- Relations: C30 is applied to C29. C30 triggers F3.

### C31 · Sampling error
- Definition: Sampling error is how much a measured daily rate moves by chance because only some calls are scored.
- Facts:
  - A daily rate p on n scored calls moves by about √(p(1−p)/n) by chance. (S20)
  - With p = 0.95 and n = 200 that is about 0.015, or 1.5 percentage points. (S20; testing fact-check: arithmetic correct)
  - Readers did not know "points" meant percentage points. (testing round 3)
- Relations: C31 sizes C25. C31 sets the noise floor for C30.

### C32 · Replay of stored prompts
- Definition: Replay sends stored prompts to a model again to compare answers.
- Facts:
  - When the provider reports no specific version, keep a fixed set of a few dozen old prompts with known-good answers and replay them each day. (S20)
  - A mature setup replays stored, redacted prompts against a new model or prompt version before switching. (S20)
  - Because output varies per run, the incident team sent each of the five stored prompts ten times. (S20; testing round 3)
- Relations: C32 detects C23. C32 belongs to evals and rollout.

### C33 · Non-determinism
- Definition: Non-determinism means the same prompt can produce a different reply on each run.
- Facts:
  - It is why one replay proves little and the incident used ten runs per prompt. (S20; testing round 3)
  - S22: output is non-deterministic and open-ended, so `assertEquals` does not work. (S22 block 11)
- Relations: C33 shapes C32. C33 is why evals exist.

### C34 · OpenTelemetry GenAI semantic conventions
- Definition: The OTel GenAI semantic conventions are agreed attribute names for model-call spans, so any tracing backend understands them.
- Facts:
  - OpenTelemetry is the open tracing standard most monitoring tools read. (S20)
  - Attributes: `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cache_read.input_tokens`, `gen_ai.response.finish_reasons`, `gen_ai.prompt.name`, `gen_ai.prompt.version`. (S1)
  - Status is "Development", so names can change between releases. (S1; S5)
  - The conventions moved in 2026 to their own repo; the old `opentelemetry.io/docs/specs/semconv/gen-ai/` pages say "Moved". (S5)
  - Coverage: client inference, model and agent spans, token and duration metrics, input and output events, MCP, and provider pages (Anthropic, OpenAI, Bedrock, Azure). (S5)
  - Use these names for your log fields too, so the record moves into spans later without renaming. (S20)
  - Readers in three rounds left out the Development status. (testing)
- Relations: C34 names the fields of C10. C34 includes C35.

### C35 · Opt-in content attributes
- Definition: Opt-in content attributes are the OTel attributes that carry prompt and reply text, off unless you turn them on.
- Facts:
  - Names: `gen_ai.input.messages` and `gen_ai.output.messages`. (S1)
  - They are opt-in because the input "is likely to contain sensitive information including user/PII data". (S1)
  - Readers in three rounds left this out. (testing)
- Relations: C35 is part of C34. C35 exists because of C22.

### C36 · Feature label
- Definition: The feature label names which product feature made a call, so cost and quality group per feature.
- Facts:
  - Running example label: `translation_grading`. (S20, made up)
  - Lomem calls it `conversationType` (tunatutor) or `feature` (shared gateway) on `provider_usage_events`. (X5, X11)
  - Lomem keeps labels as constants because two route files spelling their own string "splits one feature's cost across two rows that nobody thinks to add back together". (X20)
  - Drill-family labels are derived in one file so "a family cannot label itself". (X21)
  - Lomem's gateway refuses a call without a usage context naming a feature. (S23 §1b)
- Relations: C36 is a field of C10. C36 is a dimension of dashboards. C36 is enforced by gateway.

### C37 · Usage ledger (Lomem)
- Definition: The usage ledger is Lomem's table `provider_usage_events`, holding one row per billable line of each provider attempt.
- Facts:
  - Rows per call: uncached input, cached input, output; each with latency. (X5, X11)
  - A failed call writes one zero-quantity error row, so errors show in the same table. (X5, X11)
  - An aborted call is written with usage known so far (or one zero-quantity row) and `aborted` in metadata. (X11)
  - System calls are written with no user, `actor_kind = 'system'` and a reason; admin calls keep the admin user id as `actor_kind = 'admin'`. (X11)
  - Spend recording never sits on the caller's path; the meter is not awaited. (X4)
  - Tunatutor's own comment on the usage context: an unattributed call "is money we spend and can never see", because the free-tier cap, the daily spend guardrails and the per-surface cost reports all read `provider_usage_events`; `callLLM` "REFUSES to run rather than silently skipping metering". (`apps/tunatutor/backend/src/services/llm/types.ts:4-20`; S23 §1c)
  - A test pins the runtime refusal: the call "must FAIL loudly, never fall through to the provider with metering quietly skipped". (`apps/tunatutor/backend/src/services/llm/__tests__/usage-context-required.test.ts:1-4`; S23 §1c)
- Relations: C37 is Lomem's C10 for cost only. C37 lacks C5, C15 and the text.

### C38 · Postmortem mirror (Lomem)
- Definition: The postmortem mirror is Lomem's in-memory ring buffer that captures each external API request and response for debugging.
- Facts:
  - The gateway's `observe` hook mirrors system prompt, messages, tools, max tokens; and on response text, usage, finish or stop reason, block reason and latency. (X7)
  - Enabled when NODE_ENV is development, staging or test; disabled in production unless `POSTMORTEM_ENABLED=true`. (X9)
  - The mirror-helpers header comment says "All mirrors are no-ops outside dev". (X8)
  - Caps: 10,000 entries and about 64 MB by default, oldest evicted in batches of 100. (apps/tunatutor/backend/src/dev/postmortem/README.md; buffer-singleton.ts:14-15)
  - Read with `curl /api/dev/postmortem`. (lomem CLAUDE.md:257)
  - Payloads pass through key-name `redact()` and a 10,000-character truncation per string field. (X8, X10)
- Relations: C38 is Lomem's nearest C20. C38 fails C21.

### C39 · Admin error stream (Lomem)
- Definition: The admin error stream pushes each failed provider attempt to the admin page live over server-sent events (SSE).
- Facts:
  - `emitLlmError` emits an `llm_error` event with model id, model name, error and timestamp. (X18)
  - `routes/admin/sse.ts` line 64 subscribes and writes each event as an SSE `data:` line. (X19)
- Relations: C39 is an error alert, not a quality alert (see P7).

### C40 · User feedback on traces
- Definition: User feedback is a thumbs up or down, or a support ticket, attached to the trace it is about.
- Facts:
  - Part of the mature setup. (S20)
  - Minimal feedback loop: thumbs up or down plus "edit before send", logged against the trace ID. (S22 block 16)
- Relations: C40 is keyed by C12. C40 feeds evals datasets.

### C41 · Grading feature (running example)
- Definition: The grading feature is Tunatutor's translation-drill call that asks a model whether a learner's Portuguese translation is correct.
- Facts:
  - Inputs to the model: the English sentence, the expected answer, the learner's answer. (S20)
  - The model replies with a score 0-100 and a separate verdict, correct or not. (S20; testing fact-check)
  - Its instructions give a wrong answer a score of 0-50. (X23; testing fact-check)
  - An earlier draft wrongly said the verdict is derived from the score (below 50 means wrong). (testing fact-check)
  - Lomem's parsed reply carries `score: number` and `correct: boolean` as separate fields, and a reply with no boolean `correct` is rejected as "The judge's reply had no verdict". (`apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-reply.ts:37-39`, `:147`; testing fact-check)
  - Tunatutor is a language-learning app in Lomem, the author's repository of small apps. (S20)
  - Lomem's judge-gate fixture contains the real row `source: "I am a barista."`, `key: "Eu sou barista."`, `answer: "Eu sou um barista."`, `expected: "right"`. (S23 §7b)
- Relations: C41 is the system observed in E1. C41's score is not C29.

### C42 · APM
- Definition: APM (application performance monitoring) is the classic tooling that times calls and tracks errors, such as Datadog or New Relic.
- Facts:
  - APM never stored the payload and a quality score, which a model call needs. (S20)
  - APM payloads are rarely personal data; prompts usually are. (S20)
- Relations: C42 is the classic analogue of this block.

### C43 · Structured log line
- Definition: A structured log line is one log entry written as JSON with one field per value.
- Facts:
  - The smallest useful version is one structured log line per call. (S20)
  - `kv` comes from logstash-logback-encoder, a Logback encoder that writes each log line as JSON and each `kv` pair as a field. (S20; fact-check unverified but "as far as I know" matches the real API)
  - Lomem's logs are pino logs. (S23 §9)
  - Readers flagged MDC ("logging context") and logstash-logback-encoder as unexplained in one version. (testing round 2)
- Relations: C43 holds C10 in the minimal version.

### C44 · Retention and access
- Definition: Retention is how long a store keeps data; access is who may read it.
- Facts:
  - Text: short retention (14 days in the draft), on-call engineers only. (S20)
  - Metadata (tokens, cost, versions, scores): kept longer, as long as your logs; scores for months. (S20)
  - Storing full prompts in the normal application log is a mistake because retention is long and access is wide. (S20)
  - A reader asked whether 14 days is a legal rule or just how long reports take; the inputs do not say. (testing final read)
  - Governance minimal: an immutable audit log of prompt version, model version, inputs, outputs and approver. (S22 block 15)
- Relations: C44 governs C20 and C29. C44 belongs to governance.

### C45 · Settle point and meter (Lomem)
- Definition: The settle point is the one place per provider attempt where Lomem's gateway hands spend and errors to the meter.
- Facts:
  - The gateway settles "spend and errors at ONE point per provider attempt". (X1)
  - The meter is "called exactly once per provider attempt, success or failure. Not awaited". (X4)
  - `callJson` settles before it validates, "so a wrong answer is still recorded". (X15; ADR-057 §5)
  - A meter failure is logged and swallowed. (X3)
  - The daily spend cap is deliberately not checked per call: "This layer's job is attribution, not admission". The cap is an activity-entry gate instead. (`apps/tunatutor/backend/src/services/llm/index.ts:62-66`; S23 §1e)
  - Readers did not know "settle", "meter" or "ledger row". (testing rounds 1, 2)
- Relations: C45 writes C37. C45 is part of gateway.

### C46 · Mature setup
- Definition: The mature setup is what a team adds on top of the per-call record and the online eval once the basics run.
- Facts:
  - Nested spans: one span per model call (and per step) under one trace. (S20; S22 block 12)
  - Dashboards of cost, latency, finish reasons and eval scores per feature, prompt version and model. (S20)
  - User feedback attached to its trace. (S20; S22)
  - Alerts on eval scores and on spend per feature per day. (S20)
  - Replay of stored, redacted prompts against a new model or prompt version, compared before switching. (S20)
  - Drift alerts on score distributions. (S22 block 12)
  - Tools such as Langfuse and Arize Phoenix store traces, scores and prompts, with a UI to read and score them. (S20)
  - Readers in three rounds left the mature list out, and one called it padding. (testing rounds 1-3)
- Relations: C46 extends C10, C24. C46 uses C13, C40, C32.

### C47 · Request path position
- Definition: Observability is not one step in the request path; it runs across every step.
- Facts:
  - Chip Huyen presents observability and orchestration as running across all platform parts. (S6)
  - Across every step: tracing with OTel GenAI spans per model, tool and agent step, carrying tokens, cost, prompt version and model version. (S22 request path step 10)
  - That trace is also the audit log for governance. (S22 request path step 10)
  - Failures flow into offline eval datasets, which gate the next prompt or model change in CI. (S22 request path step 10)
  - The Fowler/Subramaniam pattern catalogue has nothing on tracing. (S10)
- Relations: C47 links this block to gateway, agents, tools, evals, governance.

## Components

| id | name | role | inputs | outputs | where it lives |
|---|---|---|---|---|---|
| K1 | LLM call wrapper | single place every model call goes through; writes the record | feature, user, prompt, request | parsed result; call record; text row; sample message | generic (S20); Lomem: `packages/shared/src/llm/gateway/gateway.ts` |
| K2 | Tracer | gives each request a trace ID and spans | incoming request | trace ID, spans | generic: Micrometer Tracing or OpenTelemetry (S20); absent in Lomem (S23 §9) |
| K3 | Prompt store | holds templates and versions, editable without a release | admin edits | template name, version, text | generic DB (S20); Lomem: `prompt_templates` and `prompt_template_versions` (X25) |
| K4 | Price table | prices per million tokens per model and date | model name, date | price per token kind | generic `model_prices` (S20); Lomem: `provider_price_config` (X12) |
| K5 | Call log | stores one structured record per call | call record | log line, queryable by field | generic log pipeline (S20); Lomem cost side: `provider_usage_events` (X5, X11) |
| K6 | Redactor | scrubs personal data out of text | prompt and reply text | redacted text | generic: patterns plus Microsoft Presidio (S20); Lomem: `packages/shared/src/redaction/redact.ts` (X10) |
| K7 | Text store | keeps redacted prompt and reply per trace ID, short-lived, restricted | trace ID, redacted text | rows for on-call reading and scoring | generic `llm_call_text` (S20); Lomem nearest: postmortem ring buffer (X8) |
| K8 | Retention job | deletes old text rows | clock | deleted rows older than 14 days | generic nightly job (S20) |
| K9 | Eval queue | carries sampled trace IDs off the request path | trace ID | messages for the consumer | generic (S20) |
| K10 | Eval consumer | scores sampled calls | trace ID; text from K7 | eval score | generic (S20) |
| K11 | Checker model | judges an answer against a rubric | redacted text, verdict, rubric | AGREE or DISAGREE | generic, strong pinned model (S20) |
| K12 | Eval table | stores scores keyed by trace ID | eval score, checker and rubric version, time | `llm_eval` rows | generic (S20) |
| K13 | Chart and alert job | computes daily averages and compares with the band | `llm_eval` joined to call log | chart; alert to feature owner | generic nightly job at 06:00 (S20, made up time) |
| K14 | Replay set | fixed known-good prompts replayed daily | stored prompts, expected answers | pass or fail per day | generic (S20) |
| K15 | Spring AI observation | emits `gen_ai.client.operation` per chat call | chat call | timer metric, span with model, tokens, finish reason | Spring AI (S4) |
| K16 | Tracing or LLM-observability backend | stores and shows traces, scores, prompts | spans, scores | UI, queries | Langfuse, Arize Phoenix, OpenLLMetry, Datadog LLM Observability, Helicone, Jaeger, Grafana Tempo (S20; S22) |
| K17 | Gateway observer hooks | taps each provider attempt's request and response | request snapshot; result, latency | calls to the app's observer | Lomem `gateway.ts:87-102`, `:312`, `:318` (X2, X4) |
| K18 | Gateway settle and meter port | hands every attempt's spend and errors to the meter, once | spend event, usage context | `meter.record` call | Lomem `gateway.ts:240-280` (X3) |
| K19 | Tunatutor meter | writes ledger rows and debits the learner's allowance | provider, usage, context, latency, isError | `provider_usage_events` rows; allowance debit | Lomem `apps/tunatutor/backend/src/services/llm/index.ts:96-234` (X5, X6) |
| K20 | Shared usage meter | same row split for other apps | spend event, context | priced rows; optional debit | Lomem `packages/shared/src/llm/gateway/provider-usage-meter.ts` (X11) |
| K21 | Provider usage writer | prices each line and writes it | usage lines | rows with `computedUsdMicros`, `isEstimated` | Lomem `packages/shared/src/billing/provider-usage-writer.ts` (X12) |
| K22 | Price coverage check | refuses to activate a model with no prices | model id | error or pass | Lomem `apps/tunatutor/backend/src/services/llm/registry.ts:199-212` (X13) |
| K23 | Finish classifier | maps provider finish reasons to stop reasons | finishReason, blockReason | `end_turn`, `max_tokens`, `blocked`, `malformed_tool_call`, `stop_sequence` | Lomem `packages/shared/src/llm/finish.ts` (X14) |
| K24 | Postmortem mirror | captures requests and responses in a ring buffer | mirror context, payload | buffer entries, read over `/api/dev/postmortem` | Lomem `apps/tunatutor/backend/src/dev/postmortem/` (X8, X9) |
| K25 | Admin error stream | pushes provider failures live | `llm_error` events | SSE `data:` lines to the admin page | Lomem `services/llm/llm-events.ts`, `routes/admin/sse.ts:64` (X18, X19) |
| K26 | Feature label constants | one name per feature for cost grouping | none | `conversationType` strings | Lomem `services/llm/surfaces.ts`, `session-types/core-drill/usage.ts` (X20, X21) |
| K27 | Borderline logger | logs checkpoint answers scored 50-85 for human review | judge input and result | `td_checkpoint_borderline` log line | Lomem `translation-drill/engine/checkpoint-rules.ts:63-76` (X22) |

## Flows

### F1 · One model call through the wrapper
Purpose: write one record per model call, failed calls included, plus the redacted text, and pick the call for scoring. Trigger: feature code asks the wrapper for a model answer.

- F1.1 · feature code → wrapper: request a grade | condition: always | data: grade request, user ID | ref: E9
- F1.2 · wrapper → prompt store: load the template | condition: always | data: template name `translation_grade` → name, version, text | ref: E9; S20
- F1.3 · wrapper: render the prompt | condition: always | data: template + request → prompt text | ref: E9
- F1.4 · wrapper → tracer: read the current trace ID and note the start time | condition: always | data: trace ID, start time | ref: S20; E9
- F1.5 · wrapper: record the request side | condition: always | data: provider, requested model, template name and version, feature, user billed | ref: S20
- F1.6 · wrapper → provider: make the call | condition: always | data: prompt text, requested model | ref: S20
- F1.7 · provider → wrapper: reply | condition: call succeeded | data: reply text, response model version, token counts, finish reason | ref: S20
- F1.7b · if the call throws: wrapper notes the error class and rethrows after recording → continues at F1.10 with reply and result null | ref: E9
- F1.8 · wrapper: parse the reply into its own result type | condition: F1.7 | data: reply text → score and verdict | ref: S20
- F1.8b · if parsing throws: same as F1.7b, the error is recorded with the reply present → continues at F1.10 | ref: E9 (made-up code)
- F1.9 · wrapper: return the result to feature code (the `finally` block still runs) | condition: F1.8 succeeded | data: result | ref: E9
- F1.10 · wrapper: compute latency | condition: always | data: now − start, in ms | ref: E9
- F1.11 · wrapper: read response model, token counts and finish reason from the reply if any | condition: always | data: `modelVersion`/`model`, input, cached, output tokens, finish reason | ref: S20; E9
- F1.12 · wrapper → price table: compute cost | condition: responding model has a price row | data: tokens × prices → cost | ref: S20; E3
- F1.12b · if the responding model has no price row: write no cost (null) and count the miss → continues at F1.13 | ref: S20
- F1.13 · wrapper → call log: write one structured line | condition: always | data: the call record, null where a failed call has no value | ref: S20; E2
- F1.14 · wrapper → redactor → text store: save redacted prompt and reply by trace ID | condition: always | data: trace ID, scrubbed prompt, scrubbed reply or null | ref: S20; F5
- F1.15 · wrapper → eval queue: send the trace ID | condition: no error, finish reason STOP, and trace-ID hash mod 100 < 2 | data: trace ID | ref: S20; F2
- F1.15b · if the call failed, stopped at MAX_TOKENS or SAFETY, or was not drawn: nothing is queued; failures and non-STOP rates are charted from the log → flow ends | ref: S20
- F1.16b · if any step F1.10-F1.15 throws: log a warning "llm_call record failed" and keep the call's own result or exception → flow ends | ref: E9
- F1.17 · wrapper → feature code: the original result or the original exception surfaces | condition: always | data: result or exception | ref: E9

### F2 · Online eval of sampled live calls
Purpose: produce a daily quality number on real traffic that falls when the model or the inputs change. Trigger: a trace ID arrives on the eval queue (from F1.15).

- F2.1 · eval queue → consumer: deliver trace ID | condition: sampled in F1.15 | data: trace ID | ref: S20
- F2.2 · consumer → text store: read the call's redacted text within minutes | condition: always | data: prompt, reply | ref: S20
- F2.3 · consumer: run the deterministic check | condition: a deterministic check exists for this feature | data: e.g. "is the score between 0 and 100" → pass or fail | ref: S20; C27
- F2.3b · if no deterministic check fits: consumer → checker model through the same wrapper under its own feature name → continues at F2.4 | ref: S20
- F2.3c · person: alternatively scores the call → continues at F2.6 | ref: S20
- F2.4 · consumer → checker model: send sentence, expected answer, learner answer, the feature's verdict and the rubric | condition: F2.3b | data: redacted text, rubric | ref: S20; E5
- F2.5 · checker model → consumer: reply AGREE or DISAGREE | condition: F2.4 | data: one word | ref: S20
- F2.5b · if the reply is anything else: reject as a failed check, store no score → flow ends | ref: S20
- F2.6 · consumer → eval table: write an `llm_eval` row | condition: a score exists | data: trace ID, eval score (AGREE 1, DISAGREE 0), checker and rubric version, time | ref: S20
- F2.7 · chart job: join `llm_eval` to call records by trace ID; compute the daily average per prompt version and per response model | condition: nightly | data: daily rates | ref: S20
- F2.8 · chart job: compare the day with its band | condition: always | data: daily rate vs mean − 3 SD of the last 30 days | ref: S20; C30
- F2.8b · if the day is below the band: alert the feature's owner → continues at F3.1 | ref: S20
- F2.8c · if the day is above the band: worth a look, no alert → flow ends | ref: S20

### F3 · Investigating a drift alert (barista incident)
Purpose: find whether a quality drop came from a prompt edit, a model change or an input change. Trigger: F2.8b alert, or user reports.

- F3.1 · alert → owner: daily agreement rate below band | condition: F2.8b | data: Monday's rate 0.81 vs alert line 0.92 | ref: S20 (made up)
- F3.2 · owner → call log: group the "wrong" rate by day, prompt_version and response_model | condition: always | data: rates per group | ref: S20
- F3.3 · owner: check prompt version | condition: always | data: prompt_version constant (14) → prompt ruled out | ref: S20
- F3.3b · if prompt_version changed on the day of the drop: the edit is the suspect; compare versions (not detailed in inputs) | ref: S20 P4
- F3.4 · owner: check response model | condition: response_model is reported more specifically than request_model | data: `gemini-2.5-flash` until Sunday, preview model from Monday → model changed | ref: S20
- F3.4b · if response_model equals request_model (no specific version reported): run F4 replay to tell model change from input change | ref: S20
- F3.5 · owner → text store: read the stored prompts of the reported calls | condition: within the 14-day window | data: five barista prompts | ref: S20
- F3.6 · team → wrapper config: set request_model to a fixed name | condition: model change found | data: `gemini-2.5-flash` | ref: S20
- F3.7 · team → model: replay each stored prompt ten times on the pinned model | condition: always (output varies per run) | data: 5 prompts × 10 runs | ref: S20; C33
- F3.7b · if any replay fails: not described in inputs → see Open questions | ref: none
- F3.8 · team → test set: add the barista case | condition: all fifty runs pass | data: the case | ref: S20; evals

### F4 · Daily replay of known-good prompts
Purpose: tell a model change from an input change when the provider reports no specific version. Trigger: daily schedule.

- F4.1 · replay job → model: send a fixed set of a few dozen old prompts with known-good answers | condition: daily | data: stored prompts | ref: S20
- F4.2 · replay job: compare replies with the known-good answers | condition: always | data: pass/fail per prompt | ref: S20
- F4.3 · if old prompts start failing: the model changed → pin or switch model (F3.6) | ref: S20
- F4.3b · if old prompts still pass while live scores (F2) fall: users' inputs changed → error analysis of new inputs (evals) | ref: S20

### F5 · Redacting text before storage
Purpose: keep personal data out of stored prompts and replies. Trigger: F1.14.

- F5.1 · wrapper → redactor: pass prompt text and reply text | condition: always, before any write | data: raw text | ref: S20
- F5.2 · redactor: replace pattern matches | condition: always | data: emails, phone numbers, IBANs → placeholders such as `<EMAIL>` | ref: S20; E6
- F5.3 · redactor: replace detected names | condition: a detector such as Presidio is used | data: names → `<PERSON>` | ref: S20; E6
- F5.4 · redactor → text store: write redacted text | condition: always | data: redacted prompt and reply | ref: S20
- F5.5 · checker model: reads only the redacted text | condition: F2 | data: redacted text | ref: S20
- F5.6b · wrapper → provider: the unredacted prompt still goes to the provider in F1.6; whether that is allowed is a contract question with the provider | ref: S20

### F6 · Lomem gateway: one provider attempt with observe and settle
Purpose: try providers in order, tap each attempt and settle spend exactly once per attempt. Trigger: any `call`, `callJson`, `callWithTools`, `callImage` (non-streaming) in an app.

- F6.1 · caller → gateway: request with usage context | condition: always | data: system prompt, messages, max tokens, context | ref: X2; gateway.ts:341-351 (`call`)
- F6.1b · if the usage context is missing, has no feature, a system context has no reason, or the user id is not a positive integer: throw `MissingUsageContextError` before any provider call → flow ends | ref: S23 §1b (`packages/shared/src/llm/gateway/context.ts:50-66`)
- F6.2 · gateway: order candidate providers (leading one first, then the rest unless fallback is off) | condition: always | data: provider list | ref: X2; gateway.ts:236-237
- F6.3 · gateway: skip a provider that does not support the operation | condition: provider lacks the method | data: debug log line | ref: X2
- F6.4 · gateway → observer: `onRequest` with operation, provider, index, request snapshot | condition: always for a tried provider | data: system prompt, messages, max tokens, tools | ref: X2; X7
- F6.5 · gateway → provider: invoke; start timer | condition: always | data: request | ref: X2
- F6.6 · provider → gateway: result | condition: success | data: text, usage, finishReason, blockReason | ref: X2; X16
- F6.7 · gateway → observer: `onResponse` with latency and result | condition: F6.6 | data: result, latency | ref: X2; X7
- F6.8 · gateway → meter: settle a success event | condition: F6.6 | data: operation, provider, usage, latency, isError false | ref: X2; X3
- F6.9 · gateway: if this was a fallback (index > 0), call `fallback.onSwitch` (tunatutor makes it the active provider in memory) | condition: index > 0 and fallback not false | data: provider | ref: gateway.ts:282-285; X7
- F6.10 · gateway → caller: return result | condition: F6.6 | ref: X2
- F6.6b · if the caller's abort signal fired: settle as aborted (isError false, no `onError`, no fallback), log "LLM call aborted by the caller", rethrow → flow ends | ref: X2; X3
- F6.6c · if the provider threw: settle an error event (isError true, no usage), call `onError` (tunatutor: emit `llm_error`, log, mirror the failure) → continues at F6.3 with the next provider | ref: X2; X3; X7
- F6.11b · if every provider failed: throw "All LLM providers failed" (for tools: with the last error; if none tried: "No LLM provider supports …") → flow ends | ref: X2

### F7 · Lomem tunatutor meter: one attempt to ledger rows
Purpose: turn one settled attempt into priced ledger rows and allowance debits. Trigger: F6.8, F6.6b or F6.6c calls `meter.record`.

- F7.1 · gateway → tunatutor meter: event and context | condition: once per attempt | data: provider id and name, usage, context, latency, isError | ref: X5; X7
- F7.2 · meter: build metering context and base metadata `{ providerId, providerName }` | condition: always | ref: X5
- F7.3b · if isError or no usage: write one zero-quantity error row under `:text-input` with isError true → flow ends | ref: X5
- F7.4 · meter: cachedInput = clamp(cached, 0, input); uncachedInput = input − cachedInput; output = output + thought tokens | condition: usage present | ref: X5; E8
- F7.5 · meter → ledger: write `:text-input` row and settle a debit | condition: uncachedInput > 0 | data: quantity, latency | ref: X5
- F7.6 · meter → ledger: write `:text-input-cached` row and settle a debit | condition: cachedInput > 0 | ref: X5
- F7.7 · meter → ledger: write `:text-output` row (`llm_response`) and settle a debit | condition: output > 0 | ref: X5
- F7.8 · settle: return without debit | condition: system context, admin actor, or tokens ≤ 0 | ref: X6
- F7.9 · settle → billing: `recordAndConsumeProviderUsage` with `recordEvent: false`, fire-and-forget | condition: a learner's own call | data: user, session, feature, provider key, tokens | ref: X6
- F7.9b · if the debit fails: log "allowance deduction failed (swallowed — the ledger row is already written)" → flow ends | ref: X6

### F8 · Lomem usage writer: pricing a line
Purpose: price each usage line without ever dropping tokens. Trigger: the shared meter (X11) or a ledger write.

- F8.1 · writer: look up the active price row for the provider key at the event time | condition: line has billable quantity | data: `providerKey`, `effectiveFrom ≤ at`, `effectiveTo` null or > at | ref: X12
- F8.1b · if the line has no billable quantity (error row, aborted with no usage): skip lookup, write at $0 with `isEstimated` | ref: X12 (comment)
- F8.2 · writer: use cached price | condition: cached and not expired (5 minutes) | ref: X12
- F8.3b · if no row is found: remember the miss for 30 seconds, warn once per window "no active provider_price_config row for this key; recording it at $0 (estimated)", write at $0 with `isEstimated` | ref: X12
- F8.3c · if the lookup fails: do not cache the failure; write at $0 with `isEstimated` and say so in metadata | ref: X12
- F8.4 · writer → `provider_usage_events`: write the priced row with `computedUsdMicros` | condition: always | ref: X12

### F9 · Lomem price coverage check
Purpose: stop a model being used before its prices exist. Trigger: an admin makes a model active or enables it as a fallback.

- F9.1 · admin settings → registry: `assertModelPriced(id)` | condition: activation or fallback enable | ref: X13
- F9.2 · registry: find missing `:text-input`, `:text-input-cached`, `:text-output` price keys | condition: always | ref: X13
- F9.2b · if any key is missing: throw `ValidationError` "…has no active price for … Add the rows on Billing → Provider Costs first" → activation refused | ref: X13
- F9.3 · admin settings: activation proceeds | condition: no key missing | ref: X13

### F10 · Lomem structured call: settle before validate
Purpose: record spend even when the answer is unusable, and name a cut answer. Trigger: `callJson`.

- F10.1 · `callJson` → `run`: call `run` → runs F6 | condition: always | data: JSON options, temperature 0.2 default, response schema | ref: X15
- F10.2 · gateway: classify the finish reason | condition: run returned | data: finishReason, blockReason → stop reason | ref: X15; X14
- F10.2b · if blocked: throw `LlmOutputError` "LLM answer was blocked: …" carrying finish and block reasons (spend already settled) → flow ends | ref: X15
- F10.3 · gateway: parse with the zod schema and return data | condition: parses | ref: X15
- F10.3b · if parsing fails and the stop reason is not `end_turn` (for example MAX_TOKENS): rethrow `LlmOutputError` naming the cause → flow ends | ref: X15

### F11 · Lomem checkpoint grading with borderline log
Purpose: grade a level-test answer, recheck a self-contradiction once, and log uncertain scores for a person. Trigger: a checkpoint answer reaches the LLM judge.

- F11.1 · checkpoint → judge model: first call | condition: always | data: judge input | ref: X22
- F11.2 · if the reply contradicts itself: one recheck call | condition: `result.contradictory` | ref: X22
- F11.2b · if the recheck also contradicts itself: the item is wrong, score capped at 49 (`BORDERLINE_MIN − 1`) → continues at F11.3 | ref: X22
- F11.2c · if the recheck is consistent: it replaces the first result → continues at F11.3 | ref: X22
- F11.3 · `logBorderline`: write `td_checkpoint_borderline` with attemptId, userAnswer, score, correct | condition: 50 ≤ score ≤ 85 | ref: X22
- F11.3b · if the score is outside 50-85: no log line | ref: X22
- F11.4 · grader: return the result | ref: X22

### F12 · Lomem live error stream
Purpose: show provider failures on the admin page as they happen. Trigger: F6.6c.

- F12.1 · gateway → emitter: `onError` calls `emitLlmError` | condition: a provider attempt failed | data: model id, model name, message | ref: X7; X18
- F12.2 · emitter: emit `llm_error` with ISO timestamp | ref: X18
- F12.3 · SSE route: write `data: <json>` to each connected admin page | condition: an admin page holds the stream open | ref: X19

### F13 · Text retention
Purpose: keep stored prompt text short-lived. Trigger: nightly schedule.

- F13.1 · retention job → text store: delete rows with `created_at` older than 14 days | condition: nightly | ref: S20
- F13.2 · retention job: leaves metadata in the call log and scores in `llm_eval`; they stay (logs' retention; months) | ref: S20

## States

### L1 · Model call attempt
- States:
  - started: the wrapper noted start time and trace ID.
  - answered: the provider returned a reply.
  - parsed: the reply became the feature's result.
  - failed: the call or the parse threw.
  - cut: the model stopped at the length limit (MAX_TOKENS).
  - blocked: the provider's filter stopped it (SAFETY or a block reason).
  - aborted: the caller gave up (Lomem only).
  - recorded: the record and text row are written.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| started | provider replies | finish STOP | answered | reply, tokens, finish reason available | F1.7 |
| started | provider replies | finish MAX_TOKENS | cut | not scored; counted in rate | F1.15b; X14 |
| started | provider replies | finish SAFETY or block reason | blocked | not scored; Lomem `callJson` throws | F1.15b; F10.2b |
| started | provider throws | not aborted | failed | error class recorded; Lomem settles error row and tries next provider | F1.7b; F6.6c |
| started | caller signal fires | Lomem | aborted | settled with `aborted: true`, no fallback | F6.6b |
| answered | parse | parse ok | parsed | result returned | F1.8 |
| answered | parse | parse fails | failed | error recorded | F1.8b; F10.3b |
| parsed, failed, cut, blocked, aborted | `finally` block | always | recorded | record line, text row, maybe sample | F1.13-F1.15 |

### L2 · Stored prompt text row
- States:
  - written: redacted text saved by trace ID.
  - readable: within 14 days, readable by on-call engineers and the eval consumer.
  - deleted: removed by the nightly job.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| (none) | F1.14 | always | written | row created | F1.14 |
| written | time passes | age ≤ 14 days | readable | incident readers and scorer can use it | F3.5; F2.2 |
| readable | nightly job | age > 14 days | deleted | text gone; metadata and scores remain | F13.1 |

### L3 · Online eval of one call
- States:
  - not sampled: hash rule did not pick it, or call failed or was not STOP.
  - queued: trace ID sent to the eval queue.
  - scored: a score was stored.
  - failed check: the checker replied something other than AGREE or DISAGREE.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| (call recorded) | F1.15 | no error, STOP, hash mod 100 < 2 | queued | message on queue | F1.15 |
| (call recorded) | F1.15 | otherwise | not sampled | none | F1.15b |
| queued | consumer scores | deterministic check, checker AGREE/DISAGREE, or person | scored | `llm_eval` row | F2.6 |
| queued | checker reply | other reply | failed check | no score | F2.5b |

### L4 · Daily quality monitor per feature
- States:
  - within band: daily rate inside its usual range.
  - below band: alert fired.
  - above band: worth a look, no alert.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| within band | nightly chart job | rate < mean − 3 SD of last 30 days | below band | alert to feature owner | F2.8b |
| within band | nightly chart job | rate above band | above band | none | F2.8c |
| below band | fix deployed (pin model) | next days back in band | within band | incident closed (implied) | F3.6 (S20, made up) |

### L5 · Model alias target (provider side)
- States:
  - stable target: alias points at a released model (`gemini-2.5-flash` in E1).
  - moved: alias points at a new or preview model (`gemini-2.5-flash-preview-09-2025` in E1).
  - pinned: the team requests a fixed name, so alias moves no longer reach it.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| stable target | provider moves alias | team requests the alias | moved | drift with no deploy | E1; C16 |
| moved | team sets fixed request_model | always | pinned | answers return to the fixed model | F3.6 |

### L6 · Lomem postmortem mirror switch
- States:
  - enabled: mirror writes entries.
  - disabled: `mirrorRequest` and `mirrorResponse` return at once.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| (module load) | `isPostmortemEnabled()` | `POSTMORTEM_ENABLED=true` | enabled | entries captured | X9 |
| (module load) | `isPostmortemEnabled()` | `POSTMORTEM_ENABLED=false` | disabled | nothing captured | X9 |
| (module load) | `isPostmortemEnabled()` | unset, NODE_ENV not production | enabled | dev, staging, test capture | X9 |
| (module load) | `isPostmortemEnabled()` | unset, NODE_ENV production | disabled | production captures nothing | X9 |

### L7 · Lomem price cache entry (per provider key)
- States:
  - absent: no cached lookup.
  - cached price: row found, kept 5 minutes.
  - cached miss: no row, remembered 30 seconds.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| absent | line priced | row found | cached price | priced row | X12 |
| absent | line priced | no row | cached miss | warn once; $0 `isEstimated` | X12 |
| absent | line priced | lookup throws | absent | not cached; $0 `isEstimated` | X12 |
| cached price | 5 minutes pass | always | absent | next line asks DB again | X12 |
| cached miss | 30 seconds pass | always | absent | an added price is picked up soon | X12 |

## Worked examples

### E1 · The barista incident
- Values: made up incident on a real feature (Tunatutor translation grading). Model names are real (testing fact-check). (S20)
- Inputs:
  - Drill sentence: "I am a barista." Expected answer: `Sou barista.` Learner answer: `Eu sou um barista.` (adds the pronoun "eu", I, and the article "um", a; still correct Portuguese).
  - Five learners report it marked wrong on a Tuesday afternoon.
  - Nothing deployed for a week. Application log: call took 1.4 s, returned 200. Error tracker empty.
- Steps:
  - Monday morning: Google moves the alias `gemini-flash-latest` to `gemini-2.5-flash-preview-09-2025`, a pre-release version (L5 stable target → moved).
  - Tuesday 06:00: the nightly chart job computes Monday's agreement rate, 0.81 (F2.7).
  - 0.81 is below the alert line 0.92 (band from E5), so the feature owner is alerted hours before the learners write in (F2.8b, F3.1).
  - The owner groups the "wrong" rate by day, `prompt_version` and `response_model` (F3.2): up to Sunday every call has `response_model` `gemini-2.5-flash` and a "wrong" rate of 4%; from Monday it is the preview model and 19%.
  - `prompt_version` is 14 throughout, so the prompt did not change; the model behind the name did (F3.3, F3.4).
  - The team sets `request_model` to the fixed name `gemini-2.5-flash` (F3.6; L5 → pinned).
  - They send each of the five stored prompts ten times; all fifty runs pass (F3.7).
  - The barista case goes into their test set (F3.8).
- Outcome: drift caused by a provider alias move, found by the online eval before user reports, diagnosed from `response_model` in the call records.
- Four things the logs lacked at the start: the exact prompt, the exact reply, which model version answered, whether the mistake happens on other answers too. (S20)
- Timeline order was misread by testing readers in one round (Tuesday reports, Monday alert); the current order is: alias moves Monday morning, alert 06:00 Tuesday, learners report Tuesday afternoon. (testing round 3)
- Lomem's real judge-gate fixture holds the same case with key `Eu sou barista.` and expected "right". (S23 §7b)
- In testing round 1 neither reader saw the incident end in what they read, so the record that answers the opening question was never shown to them. (testing round 1)

### E2 · One call record from that Tuesday
- Values: made up. (S20)
- Inputs: request for alias `gemini-flash-latest`; reply names the version that answered.
- Record:

```json
{
  "trace_id": "4f2a9c1e7b0d4c55",
  "feature": "translation_grading", "user_id": 8812,
  "prompt_template": "translation_grade", "prompt_version": 14,
  "provider": "gcp.gemini", "request_model": "gemini-flash-latest",
  "response_model": "gemini-2.5-flash-preview-09-2025",
  "input_tokens": 912, "cached_input_tokens": 640, "output_tokens": 38,
  "finish_reason": "STOP", "latency_ms": 1412, "cost_usd": 0.000196,
  "score": 41, "verdict": "wrong"
}
```

- Notes:
  - `score` 41 and `verdict` "wrong" are the grading feature's own output (C41), not the eval score (C29).
  - 41 falls in the 0-50 band the instructions give a wrong answer. (X23)
  - A testing reader could not link score 41 to "wrong" when the below-50 rule came later in the text. (testing round 2)
  - Produced by F1.13. Cost from E3.

### E3 · Cost of the E2 call
- Values: made up prices in dollars per million tokens: input 0.30, cached input 0.03, output 2.50. (S20)
- Steps (F1.12):
  - Uncached input: 912 − 640 = 272 tokens × 0.30 = 81.6.
  - Cached input: 640 × 0.03 = 19.2.
  - Output: 38 × 2.50 = 95.
  - Sum 195.8, divided by 1,000,000 = 0.0001958 dollars.
- Outcome: `cost_usd` 0.000196. Arithmetic checked in the fact-check. (testing fact-check)
- The output line is about half the cost from 38 tokens; input and cached input together are the other half. (derived from the values above)

### E4 · Sampling error at 200 scored calls a day
- Values: illustrative numbers. (S20)
- Formula: √(p(1−p)/n).
- Steps: p = 0.95, n = 200 → √(0.95 × 0.05 / 200) = √0.0002375 ≈ 0.015.
- Outcome: the daily rate moves by about 1.5 percentage points by chance. (S20; testing fact-check)

### E5 · Checker rubric and agreement band
- Values: made up. (S20)
- Checker input: English sentence, expected answer, learner's answer, the grading feature's verdict, plus the rubric.
- Rubric text: "A word the expected answer leaves out that keeps the meaning, such as the pronoun 'Eu' or the article 'um', a one-letter typo in a long word, or formal versus informal 'you' does not make a translation wrong. Reply AGREE if the verdict is correct under these rules, otherwise DISAGREE."
- Storage: AGREE → 1, DISAGREE → 0, any other reply → failed check (F2.5b).
- Daily average = agreement rate. Last 30 days between 0.94 and 0.97; the band puts the alert at 0.92 (F2.8).
- The rubric's typo and 'you' rules mirror Lomem's real checkpoint rules (one-letter typo in a word of 5+ letters is right; formal or informal 'you' is right). (`checkpoint-rules.ts:9-10` and `:28-35`, not excerpted)
- Lomem's checkpoint rules also say "A word of the key that is missing is WRONG"; the made-up rubric covers the other direction, a word the expected answer leaves out that the learner adds. (`checkpoint-rules.ts:34`)

### E6 · Content redaction
- Values: made up. (S20)
- Input: `my name is Ana Silva, write to ana@example.com`
- Steps: name detector (F5.3) → `<PERSON>`; email pattern (F5.2) → `<EMAIL>`.
- Output: `my name is <PERSON>, write to <EMAIL>`
- Lomem's real email placeholder is `[EMAIL_REDACTED]`, and its key-name redactor writes `[REDACTED]`. (X10)

### E7 · GPT-4 drift on prime numbers
- Values: real. (S2; testing fact-check verified)
- GPT-4 identified prime numbers with 84% accuracy in its March 2023 version and 51% in its June 2023 version, under the same API name.
- Outcome: the same model name gave much worse answers three months later, with no change on the caller's side.

### E8 · The E2 tokens through Lomem's meter
- Values: made-up token counts from E2, applied to the real code in X5. Provider id `gemini-2.5-flash` is real (X26).
- Inputs: inputTokens 912, cachedInputTokens 640, outputTokens 38, thoughtTokens 0.
- Steps (F7.4-F7.7):
  - cachedInput = max(0, min(640, 912)) = 640.
  - uncachedInput = max(0, 912 − 640) = 272.
  - output = 38 + 0 = 38.
  - Rows: `gemini-2.5-flash:text-input` 272 tokens (`llm_request`); `gemini-2.5-flash:text-input-cached` 640 tokens (`llm_request`); `gemini-2.5-flash:text-output` 38 tokens (`llm_response`).
- Outcome: three ledger rows with latency each; each row also triggers an allowance debit for a learner's call. No row holds prompt version, response model or text.

### E9 · Minimal Java wrapper
- Values: made-up code. (S20)
- Long version (with error capture and a guarded recorder):

```java
public GradeResult grade(GradeRequest req, long userId) {
    Prompt prompt = prompts.get("translation_grade"); // name, version, text from the DB
    String text = prompt.render(req);
    String traceId = tracer.currentSpan().context().traceId();
    long start = System.nanoTime();
    ModelReply reply = null;
    GradeResult result = null;
    String error = null;
    try {
        reply = client.call(MODEL, text);
        result = parse(reply.text());
        return result;
    } catch (RuntimeException e) {
        error = e.getClass().getSimpleName();
        throw e;
    } finally {
        try {
            long latencyMs = (System.nanoTime() - start) / 1_000_000;
            // of(...) reads modelVersion, token counts and finishReason from reply, if any
            CallRecord rec = CallRecord.of(traceId, "translation_grading", userId,
                    prompt, MODEL, reply, result, error, latencyMs);
            callLog.write(rec.withCost(prices.cost(rec))); // cost null if model unknown
            callText.save(traceId, redactor.scrub(text),
                    reply == null ? null : redactor.scrub(reply.text()));
            if (error == null && "STOP".equals(rec.finishReason())
                    && Math.floorMod(traceId.hashCode(), 100) < 2) {
                evalQueue.send(traceId); // 2% sample for the online eval, below
            }
        } catch (RuntimeException recordFailure) {
            log.warn("llm_call record failed", recordFailure); // keep the call's own outcome
        }
    }
}
```

- The tested short version has no `error` variable, no `catch`, no inner `try` and no `evalQueue.send`; `CallRecord.of` takes no `error` argument. (S21)
- `callLog.write` logs one line: `log.info("llm_call", kv("feature", ...), kv("prompt_version", ...), ...)`, one pair per record field, null where a failed call has no value. (S20)
- The inner `try` makes sure a failure while recording never replaces the model call's own result or exception. (S20)
- `tracer.currentSpan().context().traceId()` (Micrometer Tracing) and `kv()` (logstash-logback-encoder) were not checked line by line; as far as the fact-checker knew both match the real APIs. (testing fact-check, unverified)
- Testing round 2 readers listed missing steps that later versions added: error handling, user_id and template logged, redaction in code, how 2% is sampled. (testing round 2)
- Maps to F1.1-F1.17.

### E10 · Sample rate per feature
- Values: illustrative. (S20)
- 2% of 10,000 calls a day = 200 scored calls. 20% of 1,000 calls a day = 200 scored calls.
- A feature with fewer calls is scored in full or charted per week.

### E11 · Lomem checkpoint double contradiction
- Values: made-up scores applied to the real code in X22.
- Inputs: first reply contradictory; recheck reply also contradictory with score 60.
- Steps (F11.2b): result = recheck with `correct: false`, `score: min(60, 50 − 1)` = 49.
- F11.3: 49 < `BORDERLINE_MIN` 50, so no `td_checkpoint_borderline` line.
- Outcome: the item is wrong and not logged for review.

## Variants and options

- Minimal version:
  - One wrapper every model call goes through. (S20)
  - One structured log line per call, failed calls included, with trace ID, feature, user, prompt version, requested and responding model, input, cached and output tokens, finish reason, latency, cost and the parsed result. (S20)
  - A separate short-retention (14 days), restricted table of redacted prompt and reply text for every call, keyed by trace ID. (S20)
  - Log field names taken from the OTel GenAI conventions. (S20)
  - With Spring AI: the built-in `gen_ai.client.operation` observation plus your own feature, prompt version, cost and parsed result. (S20; S4)
  - Online eval on a random sample, scored off the request path, stored by trace ID, charted per day, prompt version and model with an alert band. (S20)
  - S22 minimal: log model, prompt version, input and output tokens, latency, cost, trace ID and tool calls for every call; sample full payloads, with redaction. (S22 block 12)
- Mature version:
  - Nested spans, one per model call or step, under one trace. (S20; S22)
  - Spans following the OTel GenAI conventions (client inference, model and agent spans, token and duration metrics, input and output events, MCP). (S22; S5)
  - Dashboards of cost, latency, finish reasons and eval scores per feature, prompt version and model. (S20; S22)
  - Online eval scores on traces. (S22)
  - User feedback attached to the trace. (S20; S22)
  - Alerts on eval scores and on spend per feature per day; drift alerts on score distributions. (S20; S22)
  - Replay of stored, redacted prompts against a new model or prompt version before switching. (S20)
  - A tool such as Langfuse or Arize Phoenix to store traces, scores and prompts with a UI. (S20)
  - Trace used as the governance audit log; failures flow into offline eval datasets that gate the next change in CI. (S22 request path)

- Options and trade-offs:

| id | option | when to choose | cost / risk |
|---|---|---|---|
| V1 | Spring AI `gen_ai.client.operation` observation | you call models through Spring AI | gives model names, tokens, finish reasons only; feature, prompt version, cost and parsed result still yours; text off by default (S20; S4) |
| V2 | Hand-written wrapper | no Spring AI, or you need full control | you own correctness of every field and the recording-failure guard (S20) |
| V3 | Record as a log line | smallest version | a log line cannot be updated, so scores need their own table joined by trace ID (S20; testing round 2) |
| V4 | Record as OTel spans | you already run a tracing backend | names still "Development"; keep text out of wide-access spans unless retention and access match (S20; S1) |
| V5 | Store text for every call, short window | you need to read reported calls after the fact | personal data stored; needs redaction, 14-day retention, on-call-only access (S20; testing round 1) |
| V6 | Store payloads only for a sample | S22's minimal | reported calls outside the sample cannot be read (testing round 1) |
| V7 | Deterministic check | a fixed rule decides correctness | covers only what code can decide (S20) |
| V8 | Checker model with rubric | correctness needs judgement | extra model cost (logged under its own feature); must be pinned; may share provider drift (S20; testing final read) |
| V9 | Human scoring | small volumes, high stakes | slow and costly (S20; cost unstated in inputs) |
| V10 | Random hash sample | to chart an unbiased daily rate | needs about 200 scored calls a day for ±1.5 points (S20) |
| V11 | Targeted sample of uncertain answers | to find problems with fewer human reviews | not a rate; in Lomem it wrote learner text to the normal log (S20; X22) |
| V12 | Request a moving alias | never in production | silent model change, as in E1 (S20) |
| V13 | Request a fixed version name | production | you must move it yourself when the provider retires a version (implied, not stated) |
| V14 | Unknown model price → null cost and a counted miss | draft's rule | gap visible; sums skip the call (S20) |
| V15 | Unknown model price → $0 row with `isEstimated` | Lomem's rule | tokens never dropped; $0 rows can understate spend unless `isEstimated` is filtered; Lomem also blocks unpriced models at activation (X12; X13) |
| V16 | Pattern-only redaction | emails, phones, IBANs | misses names (S20) |
| V17 | Detector library (Presidio) plus patterns | free text with names | extra dependency (S20; cost unstated) |
| V18 | Daily chart | about 200 or more scored calls a day | noise ±1.5 points at n = 200 (S20) |
| V19 | Weekly chart or full scoring | low-traffic feature | slower detection (S20) |
| V20 | Online eval inside the request | never | adds a second model call to every response (S20) |

- Tools and products:

| name | open source or hosted | what it does here | link |
|---|---|---|---|
| Langfuse | open source | stores traces, scores and prompts; prompt versions linked to traces | https://github.com/langfuse/langfuse ; https://langfuse.com/docs/prompt-management/overview |
| Arize Phoenix | open source | stores traces and scores with a UI | https://github.com/Arize-ai/phoenix |
| OpenLLMetry | open source, built on OTel | LLM instrumentation emitting OTel spans | https://github.com/traceloop/openllmetry |
| Datadog LLM Observability | hosted | LLM traces in Datadog | https://docs.datadoghq.com/llm_observability/ |
| Helicone | open source (per S22) | LLM observability | https://github.com/Helicone/helicone |
| Spring AI observability | open source | `gen_ai.client.operation` Micrometer observation per chat call | https://docs.spring.io/spring-ai/reference/observability/index.html |
| OpenTelemetry GenAI semantic conventions | open standard | attribute names for model-call spans | https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/client-inference.md |
| Micrometer Tracing | open source | trace IDs and spans in Spring Boot | not given in inputs |
| Jaeger, Grafana Tempo | open source | tracing backends (named only) | not given in inputs |
| Datadog APM, New Relic | hosted | classic APM, the analogy | not given in inputs |
| Microsoft Presidio | open source | detects names and other PII in text | not given in inputs |
| logstash-logback-encoder | open source | JSON log lines with `kv` fields | not given in inputs |
| LiteLLM spend logs | open source | gateway spend log used as an audit trail | not given in inputs (S22 block 15) |

## Facts and numbers

| id | fact | value | source id | verified |
|---|---|---|---|---|
| N1 | Characters per token | roughly 3 to 4 | S20 | unverified |
| N2 | Grading feature score range | 0 to 100 | S20; X23 | yes |
| N3 | Score band the grading instructions give a wrong answer | 0 to 50 | X23 | yes |
| N4 | Partially correct band in the grading rubric | 60 to 85 | X23 | yes |
| N5 | Correct band in the grading rubric | 95 to 100 | X23 | yes |
| N6 | Reports in the incident | 5 learners | S20 | made up |
| N7 | Days since last deploy in the incident | a week | S20 | made up |
| N8 | Logged call time in the incident | 1.4 s (`latency_ms` 1412) | S20 | made up |
| N9 | GPT-4 prime identification, March 2023 | 84% | S2 | yes |
| N10 | GPT-4 prime identification, June 2023 | 51% | S2 | yes |
| N11 | Anthropic postmortem date | 17 September 2025 | S3 | yes |
| N12 | Period of the Anthropic-postmortem bugs | August to mid-September 2025 | S3 | yes |
| N13 | Made-up record tokens | input 912, cached 640, output 38 | S20 | made up |
| N14 | Made-up prices per million tokens | input 0.30, cached 0.03, output 2.50 USD | S20 | made up |
| N15 | Made-up record cost | 0.000196 USD | S20 | yes (arithmetic) |
| N16 | Text table retention | 14 days | S20 | made up design value |
| N17 | Random sample rate | 2% (hash mod 100 < 2) | S20 | design value |
| N18 | Target scored calls per feature per day | about 200 | S20 | design value |
| N19 | Sampling error at p 0.95, n 200 | about 0.015 (1.5 points) | S20 | yes (arithmetic) |
| N20 | Alert band | 3 standard deviations below the 30-day mean | S20 | design value |
| N21 | Band window | last 30 days | S20 | design value |
| N22 | Agreement rate range over 30 days | 0.94 to 0.97 | S20 | made up |
| N23 | Alert line | 0.92 | S20 | made up |
| N24 | Monday's agreement rate | 0.81 | S20 | made up |
| N25 | Nightly alert time | 06:00 | S20 | made up |
| N26 | "Wrong" rate before and after the alias move | 4% → 19% | S20 | made up |
| N27 | Replay runs | 5 prompts × 10 = 50 | S20 | made up |
| N28 | Fixed replay set size | a few dozen prompts | S20 | design value |
| N29 | Cache-hit window | "last few minutes" | S20 | unverified (Gemini implicit cache lifetime not found) |
| N30 | Anthropic prompt cache lifetime | 5 minutes default, 1 hour at extra cost | S22 block 13 | yes (per S22) |
| N31 | OTel GenAI conventions status | Development | S1; S5 | yes |
| N32 | OTel GenAI conventions moved to own repo | 2026 | S5 | yes (per S22) |
| N33 | `gen_ai.prompt.name`, `gen_ai.prompt.version` requirement level | Conditionally Required | S1 | yes (testing fact-check) |
| N34 | Lomem borderline band | 50 to 85 (`BORDERLINE_MIN`, `BORDERLINE_MAX`) | X22 | yes |
| N35 | Lomem borderline log lifetime | remove two weeks after release | X22 | yes |
| N36 | Lomem score after double contradiction | at most 49 (`BORDERLINE_MIN − 1`) | X22 | yes |
| N37 | Lomem rows per successful call | up to 3 (uncached input, cached input, output) | X5; X11 | yes |
| N38 | Lomem price cache lifetime | 5 minutes | X12 | yes |
| N39 | Lomem price miss memory | 30 seconds | X12 | yes |
| N40 | Lomem postmortem caps | 10,000 entries; 64 MB | buffer-singleton.ts:14-15 | yes |
| N41 | Lomem postmortem eviction batch | 100 entries | postmortem README | yes |
| N42 | Lomem mirror truncation | 10,000 characters per string field | X10 (`MAX_BODY_BYTES`) | yes |
| N43 | Lomem event emitter max listeners | 20 | X18 | yes |
| N44 | Lomem `callJson` default temperature | 0.2 | X15 | yes |
| N45 | Lomem LLM call sites converging on one settle site | about 90 | S23 §12b (speech-usage.ts) | yes (per comment) |
| N46 | Lomem tunatutor models | `gemini-2.5-flash`, `gemini-2.5-flash-lite` | X26 | yes |
| N47 | Spring AI prompt and completion logging default | off | S4 | yes (testing fact-check) |
| N48 | Hand error analysis size in evals minimal | 30 to 100 real traces | S22 block 11 | per S22 |
| N49 | Testing scores, round 1 | senior 7/6/7, skimmer 7/6/7 (clarity/self-contained/examples), both fail | testing | yes |
| N50 | Testing scores, round 2 | senior 7/7/9, skimmer 7/7/8, both fail | testing | yes |
| N51 | Testing scores, round 3 | senior 8/7/9, skimmer 7/7/7, both fail | testing | yes |


## Code in Lomem

### X1 · The gateway as the one door, with observe taps
- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:1-14` (Lomem main branch as read on 2026-10-15)
- Implements: C11, C45, K1, K17, K18

```ts
// The LLM gateway (ADR-057 §5): the one door every app's LLM calls go through.
//
// It owns what must be identical everywhere — refuse an unattributed call,
// pick the provider, fall back to the next one when it fails, and settle
// spend and errors at ONE point per provider attempt — and delegates what is
// app-specific to injected ports:
//
//   - `providers` / `resolveModel` / `fallback.onSwitch` — which models exist,
//     which one leads, and what happens when a fallback wins (tunatutor's
//     admin-configured registry and its sticky switch; Billpod's one model).
//   - `meter.record(event, ctx)` — write the spend (the shared
//     `createProviderUsageMeter`, or tunatutor's ledger + allowance settle).
//   - `onError(err, ctx, info)` — report a failed provider attempt.
//   - `observe` — request/response taps (tunatutor's postmortem mirror).
```

- Notes:
  - The gateway settles spend and errors at one point per provider attempt.
  - `observe` is the request/response tap; tunatutor plugs its postmortem mirror into it.
  - `meter.record` is where spend is written; `onError` reports a failed attempt.
  - Every Lomem app except MyTube calls models through this file (S23 §14, ADR-057 §5).

### X2 · The provider-attempt loop with observe, settle, fail and abort
- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:292-339` (Lomem main branch as read on 2026-10-15)
- Implements: F6.2-F6.11b, L1

```ts
  async function run<R extends LLMChatResult | LLMResultWithTools>(
    operation: LlmOperation,
    context: LlmUsageContext,
    request: LlmRequestSnapshot,
    signal: AbortSignal | undefined,
    invoke: (p: LLMProvider) => Promise<R>,
    model?: string,
  ): Promise<R> {
    const method = OPERATION_METHOD[operation];
    const ordered = candidates(operation, context, model);
    let lastError: unknown;
    let tried = 0;
    for (let i = 0; i < ordered.length; i++) {
      const provider = ordered[i];
      if (typeof provider[method] !== "function") {
        log?.debug({ provider: provider.id, operation }, "LLM gateway: provider does not support this operation, skipped");
        continue;
      }
      if (i > 0) log?.info({ provider: provider.id }, "LLM falling back to provider");
      const pref = ref(provider);
      config.observe?.onRequest?.({ operation, provider: pref, index: i, request }, context);
      const start = performance.now();
      tried++;
      try {
        const result = await invoke(provider);
        const latencyMs = performance.now() - start;
        config.observe?.onResponse?.({ operation, provider: pref, index: i, latencyMs, result }, context);
        settle({ operation, provider: pref, usage: result.usage, latencyMs, isError: false }, context);
        switched(provider, i);
        return result;
      } catch (err: unknown) {
        if (signal?.aborted) {
          // The caller gave up: no provider failed, and no fallback is wanted.
          abandoned(context, { operation, provider: pref, latencyMs: performance.now() - start });
          throw err;
        }
        lastError = err;
        fail(err, context, { operation, provider: pref, index: i, latencyMs: performance.now() - start });
      }
    }
    if (operation === "tools") {
      throw new Error(
        `All LLM providers failed (or none support tool-use). Last error: ${getErrorMessage(lastError)}`,
      );
    }
    if (tried === 0) throw new Error(`No LLM provider supports ${method}`);
    throw new Error("All LLM providers failed");
  }
```

- Notes:
  - `onRequest` fires before each tried provider and `onResponse` after a success (lines 312, 318).
  - Latency is measured around the provider call only (`performance.now()`).
  - An abort settles as `abandoned` and rethrows without fallback; any other error settles via `fail` and the loop moves on.
  - Index 0 is the leading provider; a higher index is a fallback.

### X3 · settle, fail and abandoned
- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:240-280` (Lomem main branch as read on 2026-10-15)
- Implements: C45, F6.6b, F6.6c, F6.8

```ts
  function settle(event: LlmSpendEvent, ctx: LlmUsageContext): void {
    try {
      const pending = config.meter.record(event, ctx);
      if (pending && typeof pending.then === "function") {
        pending.then(undefined, (err: unknown) =>
          log?.error({ err: getErrorMessage(err), provider: event.provider.id }, "LLM gateway: meter failed"),
        );
      }
    } catch (err: unknown) {
      log?.error({ err: getErrorMessage(err), provider: event.provider.id }, "LLM gateway: meter failed");
    }
  }

  function fail(err: unknown, ctx: LlmUsageContext, info: Omit<LlmFailureInfo, "message">): void {
    const message = getErrorMessage(err);
    settle({ operation: info.operation, provider: info.provider, latencyMs: info.latencyMs, isError: true }, ctx);
    try {
      config.onError?.(err, ctx, { ...info, message });
    } catch (hookErr: unknown) {
      log?.error({ err: getErrorMessage(hookErr) }, "LLM gateway: onError hook failed");
    }
  }

  /** The caller aborted: settled as aborted, never reported as a provider failure. */
  function abandoned(
    ctx: LlmUsageContext,
    info: { operation: LlmOperation; provider: LlmProviderRef; latencyMs: number; usage?: LLMUsageDetails },
  ): void {
    settle(
      {
        operation: info.operation,
        provider: info.provider,
        latencyMs: info.latencyMs,
        isError: false,
        aborted: true,
        ...(info.usage ? { usage: info.usage } : {}),
      },
      ctx,
    );
    log?.info({ provider: info.provider.id, operation: info.operation }, "LLM call aborted by the caller");
  }
```

- Notes:
  - A meter failure (sync or async) is logged as "LLM gateway: meter failed" and swallowed.
  - A failed attempt is settled with `isError: true` and no usage.
  - An aborted call is settled with `isError: false` and `aborted: true`, with usage if any chunk carried it.

### X4 · The spend event, the meter contract and the observer contract
- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:42-102` (Lomem main branch as read on 2026-10-15)
- Implements: C37, C45, K17, K18

```ts
/** One settled provider attempt: what the meter records. */
export interface LlmSpendEvent {
  operation: LlmOperation;
  provider: LlmProviderRef;
  /**
   * Provider-reported usage; undefined when the attempt failed. For an
   * aborted stream, the usage reported so far (if any chunk carried it).
   */
  usage?: LLMUsageDetails;
  latencyMs: number;
  isError: boolean;
  /**
   * The caller gave up (its `options.signal` fired, or it stopped reading a
   * stream) — not a provider failure: `isError` is false, the fallback chain
   * is not run and `onError` is not called.
   */
  aborted?: boolean;
}

export interface LlmMeter {
  /**
   * Called exactly once per provider attempt, success or failure. Not awaited
   * — spend recording never sits on the caller's path; a rejected promise is
   * logged and swallowed.
   */
  record(event: LlmSpendEvent, ctx: LlmUsageContext): void | Promise<void>;
}

export interface LlmFailureInfo {
  operation: LlmOperation;
  provider: LlmProviderRef;
  /** 0 for the leading provider, n for the n-th fallback. */
  index: number;
  latencyMs: number;
  message: string;
}

/** What a request looked like, for observers (no secrets: the key never leaves the provider). */
export interface LlmRequestSnapshot {
  systemPrompt: string;
  messages: LLMMessage[];
  maxTokens: number;
  tools?: ProviderToolDefinition[];
}

export interface LlmGatewayObserver {
  onRequest?(
    info: { operation: LlmOperation; provider: LlmProviderRef; index: number; request: LlmRequestSnapshot },
    ctx: LlmUsageContext,
  ): void;
  onResponse?(
    info: {
      operation: LlmOperation;
      provider: LlmProviderRef;
      index: number;
      latencyMs: number;
      result: LLMChatResult | LLMResultWithTools;
    },
    ctx: LlmUsageContext,
  ): void;
}
```

- Notes:
  - `record` is called exactly once per provider attempt and is not awaited, so spend recording never sits on the caller's path.
  - The request snapshot holds system prompt, messages, max tokens and tools; the comment says no secrets, since the key never leaves the provider.
  - There is no field for prompt version or response model in either contract.

### X5 · Tunatutor's meter: error row and the uncached-input row
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/index.ts:125-191` (Lomem main branch as read on 2026-10-15)
- Implements: F7.1-F7.5, C8, C9, C37, E8

```ts
/**
 * tunatutor's metering port: the gateway calls it once per provider attempt with
 * the context it has ALREADY validated — one validation, one place, and no
 * second spelling of "is this attributable" that could drift from the first.
 */
function recordLlmUsageCost(
  providerId: string,
  providerName: string,
  tokens:
    | { inputTokens?: number; outputTokens?: number; cachedInputTokens?: number; thoughtTokens?: number }
    | undefined,
  ctx: LLMUsageContext,
  latencyMs: number,
  isError: boolean,
): void {
  // A system call has no learner: its rows are written with no user,
  // `actor_kind = 'system'` and the context's reason (`toMeteringContext`), and
  // `settleLlmSpend` debits nothing for them.
  const metering = toMeteringContext(ctx);
  const baseMetadata = { providerId, providerName };

  if (isError || !tokens) {
    // Record a zero-quantity error event so errors are tracked
    recordProviderUsageEvent({
      metering,
      providerKey: `${providerId}:text-input`,
      displayName: `${providerName} Input`,
      category: "llm",
      sourceEventType: "llm_request",
      billableQuantity: 0n,
      billableUnit: "tokens",
      latencyMs,
      isError: true,
      metadata: baseMetadata,
    });
    return;
  }

  // One debit per ledger row, each paired with the row it prices (AC-11a):
  // uncached input, cached input (Gemini bills context-cached prompt tokens at
  // a reduced rate, `:text-input-cached`) and output. Thinking tokens are
  // billed as output, so they join the output row — the same split the shared
  // meter (`createProviderUsageMeter`) writes for every other app.
  const cachedInput = Math.max(0, Math.min(tokens.cachedInputTokens ?? 0, tokens.inputTokens ?? 0));
  const uncachedInput = Math.max(0, (tokens.inputTokens ?? 0) - cachedInput);
  const output = (tokens.outputTokens ?? 0) + (tokens.thoughtTokens ?? 0);
  if (uncachedInput > 0) {
    recordProviderUsageEvent({
      metering,
      providerKey: `${providerId}:text-input`,
      displayName: `${providerName} Input`,
      category: "llm",
      sourceEventType: "llm_request",
      billableQuantity: BigInt(uncachedInput),
      billableUnit: "tokens",
      latencyMs,
      isError: false,
      metadata: baseMetadata,
    });
    settleLlmSpend(
      ctx,
      `${providerId}:text-input`,
      `${providerName} Input`,
      "llm_request",
      uncachedInput,
    );
  }
```

- Notes:
  - A failed attempt or one with no usage writes a zero-quantity error row under `:text-input`.
  - Cached input is clamped to the input count; uncached = input − cached; thinking tokens join output.
  - Lines 192-233 (not shown) write the `:text-input-cached` and `:text-output` rows the same way; output rows use `sourceEventType: "llm_response"`.
  - Metadata is only `{ providerId, providerName }`: no prompt version, no response model, no text.

### X6 · The allowance settle: fire-and-forget debit
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/index.ts:68-123` (Lomem main branch as read on 2026-10-15)
- Implements: F7.8, F7.9, F7.9b

```ts
/**
 * THE settle point for LLM spend (spec § R20, ruling L3/L8).
 *
 * `recordLlmUsageCost` already writes the priced ledger row for the tokens the
 * provider actually returned; this is the matching allowance DEBIT, dispatched
 * once per ledger row.
 *
 * Three properties, each of them load-bearing:
 *
 *  - **`recordEvent: false`.** The caller has just written the real
 *    `provider_usage_events` row. A second, estimated row would double-count
 *    the same tokens in every per-surface cost report and in the daily spend
 *    aggregate. (`tutor-speech-pipeline.usage-access.test.ts` pins this.)
 *  - **Fire-and-forget, swallow-on-failure.** The deduction opens a
 *    `Serializable` transaction; awaiting it inside the LLM path would put that
 *    transaction on the learner's critical path for every call. Same posture as
 *    the daily spend alert at `usage-access.ts`. A settle failure is logged, not
 *    raised: the ledger row is already written, so the spend stays visible even
 *    when the debit loses a retry.
 *  - **Priced through `getProviderPriceForBilling`** (inside
 *    `recordAndConsumeProviderUsage`) — the cache-first / DB-fallback path, not
 *    the sync cache read the ledger writer uses. `gemini-2.5-flash:text-input`
 *    is requested by no other deduction site, so a cache-only read would price
 *    it at `$0` forever (spec § R22, AC-12).
 *
 * The scope is resolved inside the settle from `ctx.conversationType`; nothing
 * is threaded from here.
 */
function settleLlmSpend(
  ctx: LLMUsageContext,
  providerKey: string,
  displayName: string,
  sourceEventType: string,
  tokens: number,
): void {
  // System and admin spend is recorded, never debited: no learner's bucket pays for it.
  if (isSystemUsageContext(ctx) || ctx.actor === "admin" || tokens <= 0) return;
  const conversationType = ctx.conversationType;
  void recordAndConsumeProviderUsage({
    userId: ctx.userId,
    sessionId: ctx.sessionId ?? undefined,
    conversationType,
    providerKey,
    displayName,
    category: "llm",
    sourceEventType,
    billableQuantity: BigInt(tokens),
    billableUnit: "tokens",
    recordEvent: false,
  }).catch((err: unknown) => {
    logger.error(
      { err: getErrorMessage(err), providerKey, conversationType },
      "LLM settle: allowance deduction failed (swallowed — the ledger row is already written)",
    );
  });
}
```

- Notes:
  - `recordEvent: false` avoids a second, estimated row that would double-count tokens in per-surface cost reports.
  - The debit is not awaited, so its Serializable transaction stays off the learner's critical path.
  - A failed debit is logged and swallowed because the ledger row is already written.
  - System and admin calls are recorded but never debited.

### X7 · Tunatutor's onError and observe ports
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/index.ts:292-343` (Lomem main branch as read on 2026-10-15)
- Implements: F6.4, F6.6c, F6.7, F12.1, C38, C39

```ts
  onError: (_err, ctx, info) => {
    emitLlmError(info.provider.id, info.provider.name, info.message);
    logger.error(
      { provider: info.provider.id, err: info.message },
      info.operation === "tools"
        ? "LLM tool-use provider failed"
        : info.index === 0
          ? "LLM provider failed"
          : "LLM fallback provider also failed",
    );
    mirrorResponse(
      mirrorCtx(info.provider, ctx),
      `${info.provider.id}:${METHOD_LABEL[info.operation]}:failed`,
      { error: info.message, latencyMs: info.latencyMs },
      "error",
    );
  },
  observe: {
    onRequest: ({ operation, provider, index, request }, ctx) => {
      mirrorRequest(
        mirrorCtx(provider, ctx),
        `${provider.id}:${METHOD_LABEL[operation]}${index === 0 ? "" : ":fallback"}`,
        {
          provider: provider.id,
          model: provider.name,
          systemPrompt: request.systemPrompt,
          messages: request.messages,
          ...(request.tools ? { tools: request.tools } : {}),
          maxTokens: request.maxTokens,
        },
      );
    },
    onResponse: ({ operation, provider, latencyMs, result }, ctx) => {
      const payload =
        "toolCalls" in result
          ? {
              text: result.text,
              toolCallCount: result.toolCalls.length,
              stopReason: result.stopReason,
              usage: result.usage,
              latencyMs,
            }
          : {
              text: result.text,
              usage: result.usage,
              finishReason: result.finishReason,
              blockReason: result.blockReason,
              latencyMs,
            };
      mirrorResponse(mirrorCtx(provider, ctx), `${provider.id}:${METHOD_LABEL[operation]}:done`, payload);
    },
  },
```

- Notes:
  - `onError` does three things: emits `llm_error` for the admin stream, logs, and mirrors the failure.
  - The mirrored request carries the full system prompt and messages; the mirrored response carries text, usage, finish or stop reason, block reason and latency.
  - `model: provider.name` is the registry's display name for the requested model, not a provider-reported version.
  - Labels end in `:fallback` for a fallback attempt, `:done` for a success, `:failed` for an error.

### X8 · Postmortem mirror producer API
- File: `~/projects/lomem/apps/tunatutor/backend/src/dev/postmortem/mirror-helpers.ts:1-44` (Lomem main branch as read on 2026-10-15)
- Implements: C38, K24, L6

```ts
// apps/tunatutor/backend/src/dev/postmortem/mirror-helpers.ts
//
// Helpers for external API mirrors. Each call site emits one entry on request,
// one on response (success or error). All mirrors are no-ops outside dev.

import { getPostmortemBuffer } from "./buffer-singleton.js";
import { isPostmortemEnabled } from "./enabled.js";
import { redact, truncateLargeBody } from "./redaction.js";
import type { CaptureSource } from "./types.js";

// Evaluate the gate once at module load — the env doesn't change at runtime
// and these mirror helpers are on the hot path of every external API call.
const enabled = isPostmortemEnabled();

export interface MirrorContext {
  source: CaptureSource;
  namespace: string;
  userId?: number;
  sessionId?: string;
  turnId?: string;
  requestId?: string;
  wsConnectionId?: string;
}

export function mirrorRequest(ctx: MirrorContext, label: string, payload: Record<string, unknown>): void {
  if (!enabled) return;
  try {
    getPostmortemBuffer().add({
      source: ctx.source,
      kind: "ext-api-req",
      level: "info",
      userId: ctx.userId,
      sessionId: ctx.sessionId,
      turnId: ctx.turnId,
      requestId: ctx.requestId,
      wsConnectionId: ctx.wsConnectionId,
      namespace: ctx.namespace,
      label,
      data: truncateLargeBody(redact(payload)),
    });
  } catch {
    /* never throw from a mirror */
  }
}
```

- Notes:
  - The enabled flag is read once at module load.
  - Payloads go through `redact()` (key names) and `truncateLargeBody()`, not `scrubEmails()`, so prompt prose is stored as written.
  - A mirror never throws.
  - The header says mirrors are no-ops outside dev; `enabled.ts` (X9) also enables staging and test.

### X9 · When the postmortem mirror is on
- File: `~/projects/lomem/apps/tunatutor/backend/src/dev/postmortem/enabled.ts:1-20` (Lomem main branch as read on 2026-10-15)
- Implements: L6

```ts
// apps/tunatutor/backend/src/dev/postmortem/enabled.ts
//
// Single source of truth for whether the postmortem subsystem is active.
// Replaces the original 3-layer NODE_ENV === "development" gate so that
// user-initiated bug reports submitted from staging can attach a postmortem
// bundle. See docs/plans/2026-05-26-user-bug-reporting.md.
//
// Default behaviour:
//   - NODE_ENV in {development, staging, test} → enabled
//   - NODE_ENV = production                    → disabled
//
// Override with the POSTMORTEM_ENABLED env var ("true" / "false"). Production
// stays off-by-default on purpose — explicit opt-in only.

export function isPostmortemEnabled(): boolean {
  const explicit = process.env.POSTMORTEM_ENABLED;
  if (explicit === "true") return true;
  if (explicit === "false") return false;
  return process.env.NODE_ENV !== "production";
}
```

- Notes:
  - Default: on for development, staging and test; off for production.
  - `POSTMORTEM_ENABLED` overrides in both directions.
  - Staging was enabled so user bug reports could attach a postmortem bundle.

### X10 · Shared redactor: key-name redaction versus email scrubbing
- File: `~/projects/lomem/packages/shared/src/redaction/redact.ts:9-53, 70-90` (Lomem main branch as read on 2026-10-15)
- Implements: C21, K6, P8, E6

```ts
const REDACT_KEYS = [
  "password", "passwordHash", "currentPassword", "newPassword",
  "accessToken", "refreshToken", "token",
  "authorization", "cookie",
  "x-api-key", "apiKey", "secret",
  "JWT_SECRET", "GEMINI_API_KEY",
  "AZURE_SPEECH_KEY", "OPENAI_API_KEY", "STRIPE_SECRET_KEY",
];

export const REDACT_KEYS_LOWER = new Set(REDACT_KEYS.map((k) => k.toLowerCase()));

const REDACTED = "[REDACTED]";

/** Max byte length for a single string field before truncation kicks in. */
export const MAX_BODY_BYTES = 10_000;

/** What an email address is replaced with once scrubbed. */
export const EMAIL_PLACEHOLDER = "[EMAIL_REDACTED]";

/**
 * Address-shaped substring. Local part requires at least one character, so
 * package specifiers (`node_modules/@repo/shared`) and npm version pins
 * (`pkg@2.0.0`, whose "TLD" is digits) do not match.
 */
const EMAIL_PATTERN =
  /[\p{L}\p{N}.!#$%&'*+/=?^_`{|}~-]+@[\p{L}\p{N}](?:[\p{L}\p{N}-]*[\p{L}\p{N}])?(?:\.[\p{L}\p{N}](?:[\p{L}\p{N}-]*[\p{L}\p{N}])?)*\.\p{L}{2,}/gu;

/** Replace every email address in a single string. */
export function scrubEmailsFromString(value: string): string {
  return value.replace(EMAIL_PATTERN, EMAIL_PLACEHOLDER);
}

/**
 * Deep, non-mutating scrub of email addresses out of every STRING VALUE
 * (and string key) in a structure.
 *
 * `redact()` above scrubs by KEY NAME, which is the wrong tool for an address:
 * an email arrives inside prose — "signed in as alice@example.com" in a crash
 * message or a breadcrumb label — under no sensitive key at all. Erasing an
 * account cannot reach text like that by user id, so the durable half of the
 * fix is never storing it (ADR-037 §1: deletion is complete erasure).
 */
export function scrubEmails<T>(value: T): T {
  return scrubEmailsInner(value) as T;
}
...
/** Recursive deep-clone redactor. Does not mutate input. */
export function redact<T>(value: T): T {
  return redactInner(value) as T;
}

function redactInner(value: unknown): unknown {
  if (value === null || value === undefined) return value;
  if (Array.isArray(value)) return value.map(redactInner);
  if (typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (REDACT_KEYS_LOWER.has(k.toLowerCase())) {
        out[k] = REDACTED;
      } else {
        out[k] = redactInner(v);
      }
    }
    return out;
  }
  return value;
}
```

- Notes:
  - `redact()` replaces values under listed key names with `[REDACTED]`; it cannot reach personal data inside prose.
  - `scrubEmails()` replaces email-shaped substrings in every string with `[EMAIL_REDACTED]`.
  - The comment names the exact problem this block describes: an email inside prose sits under no sensitive key.
  - No name, phone or IBAN detection exists here.

### X11 · Shared usage meter for other apps
- File: `~/projects/lomem/packages/shared/src/llm/gateway/provider-usage-meter.ts:46-103` (Lomem main branch as read on 2026-10-15)
- Implements: C37, F7 (shared variant), K20

```ts
/**
 * Rows per call: an uncached-input row, a cached-input row (when the provider
 * served part of the prompt from its context cache) and an output row
 * (visible answer plus thoughts — the provider bills both as output), priced
 * by `<providerId>:text-input` / `:text-input-cached` / `:text-output` like
 * tunatutor's ledger. A key with no price row, or whose lookup fails, is written
 * at $0 with `isEstimated` — the tokens are never dropped. A failed call
 * writes one zero-quantity error row, so errors show in the same table; a
 * call the caller aborted is written with the usage known so far (or one
 * zero-quantity row) and `aborted` in its metadata. A system context is
 * written too, with no user, `actor_kind = 'system'` and its reason; an admin
 * context keeps the admin's user id as `actor_kind = 'admin'`. Neither is
 * debited: `debit` runs for a person's own calls only.
 */
export function createProviderUsageMeter(
  prisma: ProviderUsagePrisma,
  options: ProviderUsageMeterOptions = {},
): ProviderUsageMeter {
  const writer = options.writer ?? createProviderUsageWriter(prisma, options);
  const pending = new Set<Promise<void>>();

  async function write(event: LlmSpendEvent, ctx: LlmUsageContext): Promise<void> {
    const system = isSystemLlmContext(ctx);
    const { id, name } = event.provider;
    let metadata: UsageMetadata = {
      providerId: id,
      providerName: name,
      operation: event.operation,
      ...(event.provider.modelId ? { modelId: event.provider.modelId } : {}),
      ...(ctx.surface ? { surface: ctx.surface } : {}),
    };
    if (event.aborted) metadata = { ...metadata, aborted: true };
    const base = {
      userId: system ? null : ctx.userId,
      ...(system ? { systemReason: ctx.reason } : ctx.actor === "admin" ? { actorKind: "admin" as const } : {}),
      sessionId: ctx.sessionId ?? null,
      conversationType: ctx.feature,
      category: "llm",
      billableUnit: "tokens",
      latencyMs: event.latencyMs,
      metadata,
    };

    const u = event.usage;
    if (event.isError || !u) {
      await writer.write([
        {
          ...base,
          providerKey: `${id}:text-input`,
          displayName: `${name} Input`,
          sourceEventType: "llm_request",
          billableQuantity: 0n,
          isError: event.isError,
          metadata: event.isError ? metadata : { ...metadata, incomplete: true },
        },
      ]);
      return;
    }
```

- Notes:
  - Metadata adds `operation`, `modelId` and `surface` when present, and `aborted: true` for an aborted call.
  - A call with no usage and no error is written as one zero row with `incomplete: true`.
  - System rows carry `systemReason` and no user; admin rows carry `actorKind: "admin"`.

### X12 · Usage writer: price lookup, cache and $0 estimated rows
- File: `~/projects/lomem/packages/shared/src/billing/provider-usage-writer.ts:203-257` (Lomem main branch as read on 2026-10-15)
- Implements: C19, F8, L7, V15

```ts
/**
 * Each line is priced by its `providerKey` and stamped with the capability
 * that key bills. A line without a user is written as a `system` row
 * (`user_id` null, `actor_kind` `system`, its `system_reason`). A line with no billable quantity
 * (an error row, an aborted call with no usage) is not looked up and is
 * written at $0 and `isEstimated`. A key with no price row, or whose lookup
 * fails, is written at $0 and `isEstimated` too — the quantity is never
 * dropped — and a failed lookup says so in the row's metadata.
 */
export function createProviderUsageWriter(
  prisma: ProviderUsagePrisma,
  options: ProviderUsageWriterOptions = {},
): ProviderUsageWriter {
  const ttl = options.priceCacheTtlMs ?? 5 * 60 * 1000;
  const missTtl = options.priceMissTtlMs ?? 30 * 1000;
  const now = options.now ?? (() => new Date());
  // The in-flight lookup is cached, so concurrent calls share one query.
  const prices = new Map<string, { row: Promise<ProviderPriceRow | null>; expiresAt: number }>();
  const pending = new Set<Promise<unknown>>();

  function cachedPrice(providerKey: string, at: Date): Promise<ProviderPriceRow | null> {
    const cached = prices.get(providerKey);
    if (cached && cached.expiresAt > Date.now()) return cached.row;
    const row = prisma.providerPriceConfig
      .findFirst({
        where: {
          providerKey,
          isActive: true,
          effectiveFrom: { lte: at },
          OR: [{ effectiveTo: null }, { effectiveTo: { gt: at } }],
        },
        orderBy: [{ effectiveFrom: "desc" }, { id: "desc" }],
      })
      .then(
        (found) => {
          if (!found) {
            // A miss is remembered only briefly (a price seeded or added on
            // the admin page is picked up soon), and said once per window.
            prices.set(providerKey, { row, expiresAt: Date.now() + missTtl });
            options.logger?.warn(
              { providerKey },
              "provider usage: no active provider_price_config row for this key; recording it at $0 (estimated)",
            );
          }
          return found;
        },
        (err: unknown) => {
          // A failed lookup is not cached: the next call asks again.
          prices.delete(providerKey);
          throw err;
        },
      );
    prices.set(providerKey, { row, expiresAt: Date.now() + ttl });
    return row;
  }
```

- Notes:
  - The active price row is the newest with `effectiveFrom ≤ at` and `effectiveTo` null or later.
  - A miss is cached for 30 s and warned once per window; a found row for 5 minutes; a failed lookup is not cached.
  - Unpriced lines are written at $0 with `isEstimated`; tokens are never dropped.

### X13 · Refusing a model with no prices
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/registry.ts:199-212` (Lomem main branch as read on 2026-10-15)
- Implements: F9, K22

```ts
/**
 * Refuses a model whose calls would be priced at $0: every one of its
 * `:text-input`, `:text-input-cached` and `:text-output` keys needs an active
 * `provider_price_config` row (ADR-057 §5, price coverage). The admin LLM
 * settings call it before making a model active or enabling it as a fallback.
 */
export async function assertModelPriced(id: string): Promise<void> {
  const missing = await missingLlmPriceKeys(prisma, id);
  if (missing.length > 0) {
    throw new ValidationError(
      `${id} has no active price for ${missing.join(", ")}. Add the rows on Billing → Provider Costs first, so its calls are not recorded at $0.`,
    );
  }
}
```

- Notes:
  - All three keys (`:text-input`, `:text-input-cached`, `:text-output`) must have an active price row.
  - This is called before a model becomes active or a fallback, so normal traffic should not hit the $0 path of X12.

### X14 · Finish reasons classified once
- File: `~/projects/lomem/packages/shared/src/llm/finish.ts:6-38` (Lomem main branch as read on 2026-10-15)
- Implements: C17, C18, K23, L1

```ts
/** The provider refused or cut the answer: its text is empty or partial. */
const BLOCKED_FINISH_REASONS: ReadonlySet<string> = new Set([
  "SAFETY",
  "RECITATION",
  "PROHIBITED_CONTENT",
  "BLOCKLIST",
  "SPII",
  "IMAGE_SAFETY",
  "IMAGE_PROHIBITED_CONTENT",
  "IMAGE_RECITATION",
]);

/** The model tried to call a tool and produced an invalid call. */
const MALFORMED_CALL_FINISH_REASONS: ReadonlySet<string> = new Set([
  "MALFORMED_FUNCTION_CALL",
  "UNEXPECTED_TOOL_CALL",
  "TOO_MANY_TOOL_CALLS",
]);

/**
 * The stop reason of an answer with no tool calls, from the provider's finish
 * reason (Gemini `candidate.finishReason`) and prompt block reason
 * (`promptFeedback.blockReason`). A blocked prompt is `blocked` whatever the
 * finish reason says.
 */
export function classifyFinish(finishReason: string | undefined, blockReason?: string): LLMStopReason {
  if (blockReason) return "blocked";
  if (finishReason === "STOP") return "end_turn";
  if (finishReason === "MAX_TOKENS") return "max_tokens";
  if (finishReason && BLOCKED_FINISH_REASONS.has(finishReason)) return "blocked";
  if (finishReason && MALFORMED_CALL_FINISH_REASONS.has(finishReason)) return "malformed_tool_call";
  return "stop_sequence";
}
```

- Notes:
  - A prompt block reason wins over any finish reason.
  - Anything unknown maps to `stop_sequence`.
  - Read by providers, the gateway's `callJson` and callers.

### X15 · callJson: spend settled before validation
- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:369-392` (Lomem main branch as read on 2026-10-15)
- Implements: F10, C45

```ts
    // The spend is already settled: a wrong answer still cost money.
    const stop = classifyFinish(result.finishReason, result.blockReason);
    const cause = result.blockReason
      ? `the prompt was blocked (${result.blockReason})`
      : `the model stopped with ${result.finishReason ?? "no finish reason"}`;
    if (stop === "blocked") {
      throw new LlmOutputError(`LLM answer was blocked: ${cause}`, result.text, undefined, {
        finishReason: result.finishReason,
        blockReason: result.blockReason,
      });
    }
    try {
      return { data: parseStructured(req.schema, result.text), result };
    } catch (err: unknown) {
      // A cut answer (MAX_TOKENS, …) fails to parse: name that, not just "invalid JSON".
      if (err instanceof LlmOutputError && stop !== "end_turn") {
        throw new LlmOutputError(`${err.message} — ${cause}`, err.rawText, err.issues, {
          finishReason: result.finishReason,
          blockReason: result.blockReason,
        });
      }
      throw err;
    }
  }
```

- Notes:
  - The comment states the rule: a wrong answer still cost money, so spend is settled inside `run` before parsing.
  - A blocked answer throws `LlmOutputError` with finish and block reasons.
  - A parse failure on a non-`end_turn` stop (for example MAX_TOKENS) names the cut instead of just "invalid JSON".

### X16 · Gemini usage and finish fields read from the reply
- File: `~/projects/lomem/packages/shared/src/llm/providers/gemini.ts:187-195, 445-456` (Lomem main branch as read on 2026-10-15)
- Implements: C7, C8, C9, C15, C17, F1.11

```ts
function usageOf(data: GeminiResponse): Required<LLMUsageDetails> {
  const u = data.usageMetadata;
  return {
    inputTokens: u?.promptTokenCount ?? 0,
    outputTokens: u?.candidatesTokenCount ?? 0,
    cachedInputTokens: u?.cachedContentTokenCount ?? 0,
    thoughtTokens: u?.thoughtsTokenCount ?? 0,
  };
}
...
    const data = await this.generate(body, options);
    const candidate = data.candidates?.[0];
    const images = answerImages(data);
    return {
      text: answerText(data),
      usage: usageOf(data),
      ...(images.length ? { images } : {}),
      // Diagnostic surface for empty/blocked completions — see LLMChatResult.
      finishReason: candidate?.finishReason,
      blockReason: data.promptFeedback?.blockReason,
      safetyRatings: candidate?.safetyRatings,
    };
```

- Notes:
  - Token counts map from Gemini's `usageMetadata`.
  - The chat result carries `finishReason`, `blockReason` and `safetyRatings`.
  - `modelVersion` is not read, so the response model is lost.

### X17 · Token usage fields
- File: `~/projects/lomem/packages/shared/src/llm/types.ts:43-52` (Lomem main branch as read on 2026-10-15)
- Implements: C7, C8, C9

```ts
export interface LLMUsageDetails {
  /** Prompt tokens, including cached ones (Gemini `promptTokenCount`). */
  inputTokens?: number;
  /** Visible answer tokens (Gemini `candidatesTokenCount`), not thoughts. */
  outputTokens?: number;
  /** The part of `inputTokens` served from the context cache. */
  cachedInputTokens?: number;
  /** Reasoning tokens (Gemini `thoughtsTokenCount`); billed as output by the provider. */
  thoughtTokens?: number;
}
```

- Notes:
  - Input includes cached tokens (Gemini `promptTokenCount`).
  - Thought tokens are billed as output by the provider.

### X18 · llm_error event emitter
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/llm-events.ts:1-23` (Lomem main branch as read on 2026-10-15)
- Implements: C39, F12.1-F12.2, K25

```ts
import { EventEmitter } from "node:events";

export interface LlmErrorEvent {
  type: "llm_error";
  modelId: string;
  modelName: string;
  error: string;
  timestamp: string;
}

export const llmEvents = new EventEmitter();
llmEvents.setMaxListeners(20);

export function emitLlmError(modelId: string, modelName: string, error: string): void {
  const event: LlmErrorEvent = {
    type: "llm_error",
    modelId,
    modelName,
    error,
    timestamp: new Date().toISOString(),
  };
  llmEvents.emit("llm_error", event);
}
```

- Notes:
  - The event carries model id, model name, error message and an ISO timestamp, no prompt text.
  - It is an in-process emitter, so each backend instance streams only its own errors (inferred from `EventEmitter`; unverified).

### X19 · Admin SSE route forwards llm_error
- File: `~/projects/lomem/apps/tunatutor/backend/src/routes/admin/sse.ts:61-64` (Lomem main branch as read on 2026-10-15)
- Implements: F12.3, K25

```ts
    const llmListener = (event: LlmErrorEvent) => {
      raw.write(`data: ${JSON.stringify(event)}\n\n`);
    };
    llmEvents.on("llm_error", llmListener);
```

- Notes:
  - Each event becomes one SSE `data:` line on the admin page.
  - This is an error stream, not a quality signal.

### X20 · Feature labels as constants
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/surfaces.ts:1-21` (Lomem main branch as read on 2026-10-15)
- Implements: C36, K26

```ts
// apps/tunatutor/backend/src/services/llm/surfaces.ts
//
// The `conversationType` labels the non-drill LLM surfaces write onto
// `provider_usage_events`. They exist as constants because per-surface cost
// reporting is only meaningful if one feature reports under ONE name — two
// route files each spelling their own string ("help_panel" here,
// "conjugation_panel" there) splits one feature's cost across two rows that
// nobody thinks to add back together.
//
// Drill-family surfaces have their own derivation in
// `session-types/core-drill/usage.ts`; don't duplicate them here.

/**
 * The whole help/panel feature — the help panel routes AND every info panel
 * (word / sentence / answer / conjugation / router), whichever route file
 * happens to serve them.
 */
export const HELP_PANEL_SURFACE = "help_panel";

/** Document ingest for open chat: URL fetch + PDF extract, and their summaries. */
export const OPEN_CHAT_EXTRACT_SURFACE = "open_chat_extract";
```

- Notes:
  - The comment gives the reason: two spellings split one feature's cost across two rows.
  - Drill-family labels live in `core-drill/usage.ts` (X21).

### X21 · Drill-family labels derived in one place
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/core-drill/usage.ts:1-19` (Lomem main branch as read on 2026-10-15)
- Implements: C36, K26

```ts
// apps/tunatutor/backend/src/session-types/core-drill/usage.ts
//
// One place that names the drill-family LLM surfaces, so per-surface provider
// cost stays queryable (`conversationType` on provider_usage_events) instead of
// collapsing into an unlabelled blob.
import type { DrillMode } from "@tunatutor/shared";
import { userUsageContext, type LLMUserUsageContext } from "../../services/llm/types.js";

// The surface names below stay module-private on purpose: this file's whole
// job is that a family cannot label itself, so the public API is the `*Usage`
// builders, never the raw strings they are built from.

/** The endless single-card "Drill Me" runner (ADR-041) — not an arc. */
const LEXICON_DRILL_SURFACE = "lexicon_drill";

/** `drill_translation`, `drill_cloze`, `drill_overheard`, … */
function drillSurface(mode: DrillMode): string {
  return `drill_${mode}`;
}
```

- Notes:
  - The raw strings are module-private so a family cannot label itself.
  - Labels follow `drill_<mode>`, plus `lexicon_drill`.

### X22 · Checkpoint grading with a recheck and a borderline log
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/checkpoint-rules.ts:19-21, 48-76` (Lomem main branch as read on 2026-10-15)
- Implements: C26, F11, K27, E11

```ts
/** A checkpoint answer scored in this band is logged for the two-week review. */
export const BORDERLINE_MIN = 50;
export const BORDERLINE_MAX = 85;
...
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
  - Answers scored 50-85 inclusive are logged for a person to review.
  - The log line includes `userAnswer`, the learner's own text, in the normal production log.
  - The comment says to remove the line two weeks after release, once the owner has hand-checked the 50s and decided on a third-call tie-break.
  - A second self-contradiction makes the item wrong with score at most 49.

### X23 · Grading rubric bands (0-50 wrong)
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/translation-drill/engine/judge-translation-prompt.ts:30-52` (Lomem main branch as read on 2026-10-15)
- Implements: C41, E2

```ts
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
    case "relaxed":
      return `Grading rules (RELAXED):
- A learner answer that matches the canonical OR any variant in meaning (allowing minor punctuation, capitalization, missing/wrong accents, and single-letter typos where the word is still clearly recognizable) is correct. Score 95-100. When the only differences are in these categories, still acknowledge the slip in the "feedback" field so the learner knows — just don't lower the score.
- A near-miss with one small error (tense, article, wrong word form) is partially correct. Score 60-85.
- A wrong meaning, missing key words, or broken grammar is incorrect. Score 0-50.`;
    default: {
      const _exhaustive: never = leniency;
      throw new Error(`Unhandled grading leniency: ${String(_exhaustive)}`);
    }
  }
}
```

- Notes:
  - All three leniency levels give a wrong answer 0-50 and a correct one 95-100.
  - The model also returns a separate boolean `correct` (lines 132-133 and 176-177), so the verdict is not derived from the score.

### X24 · Debugging rule: capture the real response
- File: `~/projects/lomem/CLAUDE.md:256` (Lomem main branch as read on 2026-10-15)
- Implements: P1, C17

```markdown
- API keys are **paid tier** (Gemini/Anthropic/etc.). When an LLM call misbehaves, capture the real response (status, `finishReason`, error body) and reproduce in isolation before theorizing — never assume quota/rate limits or add throttles without direct evidence (an actual 429).
```

- Notes:
  - The repository's own rule: read the real status, `finishReason` and error body before theorizing.
  - The next line (257) points at the postmortem endpoint `curl /api/dev/postmortem`.

### X25 · Prompt templates and their version history
- File: `~/projects/lomem/apps/tunatutor/backend/prisma/schema.prisma:2075-2099` (Lomem main branch as read on 2026-10-15)
- Implements: C4, C5, K3, P4

```prisma
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
  - A template has one current `content`; each change archives the old content as a version row (`archiveCurrentContent`, `apps/tunatutor/backend/src/services/prompt-templates.ts:99-103`).
  - Version rows have an autoincrement `id` and `created_at`, but no per-template version number.
  - Nothing links a version row to a model call or a ledger row.

### X26 · The models tunatutor can choose
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/models.ts:1-11` (Lomem main branch as read on 2026-10-15)
- Implements: C16, F9

```ts
// The Gemini models tunatutor's admin LLM settings can choose between. The
// registry builds one provider per entry; each needs its three price rows
// (`dev/provider-prices.ts`, checked by `provider-prices.test.ts`), and a
// switch to a model without them is refused (`assertModelPriced`).
export const TUNATUTOR_LLM_MODELS = [
  { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash" },
  { id: "gemini-2.5-flash-lite", name: "Gemini 2.5 Flash Lite" },
] as const;

/** Leads a fresh database (`llm.activeProvider` is seeded with it). */
export const TUNATUTOR_DEFAULT_LLM_MODEL = "gemini-2.5-flash";
```

- Notes:
  - Only fixed version names are offered, no `-latest` alias.
  - Each model needs its three price rows; a switch to an unpriced model is refused.

## Analogy to classic backend

| AI-side item (id) | classic Java/Spring equivalent | holds where | breaks where |
|---|---|---|---|
| Call record (C10) | a span or APM transaction for a downstream call, with extra attributes | one timed downstream call in the request's trace, like a call to a payment provider, with tokens and cost as extra attributes (S20) | success is a judgement about the text, so the record needs the payload and a score, which APM never stored (S20) |
| Whole block | distributed tracing plus APM plus a billing meter (S20; S22) | trace IDs, spans, latency, error rates, per-call cost metering; S22 names OTel and Jaeger as the tracing half, with prompt and completion as the span payload (S22 block 12) | three breaks: success is a judgement, the model changes under the same name, the payload is personal data (S20; testing key points) |
| Model call outcome (L1) | HTTP status code of a payment API | errors, timeouts and 429s still show as failures | a wrong answer returns 200; the status code does not say whether it worked (S20) |
| Model behind a name (C16) | a versioned external API | a fixed version name behaves like a pinned API version | a payment API behaves the same until it announces a new version; a model behind the same name can answer differently next week (S20) |
| Prompt and reply text (C20) | request and response payload logging | stored per call, keyed by trace ID | APM payloads are rarely personal data; prompts usually are, so they need content redaction, short retention and narrow access (S20) |
| Content redaction (C21) | Logback masking by field name (password, token, authorization) | patterns still work for emails, phones, IBANs | a prompt is one long prose field, so field-name masking cannot reach data inside it (S20; X10) |
| Prompt version (C5) | the deployed build version or git SHA on every log line | ties behaviour to a change | prompts change outside a deploy (database edits), so the build version does not identify the prompt (S20; P4) |
| Online eval (C24) | synthetic monitoring or canary analysis (S22 block 11) | runs continuously on production, off the request path | the check is a judgement, often by another model, and the measured rate has sampling error (S20) |
| Alert band (C30) | a latency or error-rate SLO alert | a threshold on a daily figure | the alerted figure is a quality score, because latency and errors do not move on drift (S20) |
| Feature label (C36) | a metric tag such as `endpoint` or `tenant` | groups cost and quality per feature | per-call cost varies by tokens, so a mislabelled feature hides real money (X20) |
| Usage ledger (C37) | a billing meter or usage table | one row per billable line per call | price per row depends on token kind and model; Lomem writes $0 `isEstimated` rows when a price is missing (X12) |
| Postmortem mirror (C38) | a debug request/response capture filter | captures every external call in dev and staging | key-name redaction only, and off in production by default (X8, X9) |
| Admin error stream (C39) | an error-tracker live feed | shows provider failures as they happen | blind to wrong answers that return 200 (P2, P7) |
| Replay of prompts (C32) | replaying recorded traffic against a new build | compares behaviour before switching | output varies per run, so each prompt needs several runs (S20; C33) |
| Settle point (C45) | one AOP advice or interceptor around every outbound client | one place sees every call | a wrong answer still costs money, so spend is settled before validation (X15) |

- Testing: in rounds 1 and 3 readers left the analogy and its three break points out of their explain-backs; in round 1 the analogy box sat near the end of the section. (testing rounds 1, 3)

## Pitfalls

| id | mistake | consequence | what to do instead | source |
|---|---|---|---|---|
| M1 | Logging token counts but not the prompt version | a quality drop cannot be tied to the edit that caused it | record template name and version on every call (`gen_ai.prompt.version`) | S20 |
| M2 | Recording only the requested model name | the version that actually changed is invisible | record the response model from the reply as well | S20 |
| M3 | Requesting a moving alias such as `gemini-flash-latest` in production | silent model change, as in E1 | request a fixed version name | S20 |
| M4 | Storing full prompts in the normal application log | long retention and wide access to personal data | separate text table, redacted by content, 14-day retention, on-call access only | S20; X22 does this with `userAnswer` |
| M5 | Alerting only on errors and latency | drift never fires an alert | alert on the daily eval score against its band | S20 |
| M6 | Running the online eval inside the user's request | a second model call on every response | score from a queue, off the request path | S20 |
| M7 | Storing text only for sampled calls | the reported calls cannot be read | store redacted text for every call over a short window; sample only the scoring | testing round 1 |
| M8 | Writing the eval score back into the call's log line | a log line cannot be updated | store scores in their own table keyed by trace ID and join | testing round 2 |
| M9 | Moving prompt text into wide-access tracing spans | personal data with long retention and wide access | keep text in the restricted table unless the backend has the same retention and access | S20; testing round 2 |
| M10 | Redacting prompts by key name only | names, emails and account numbers inside prose are stored | scrub the text itself: patterns plus a detector such as Presidio | S20; X10 |
| M11 | Letting the checker model follow a moving alias | the checker changes along with the model it checks | pin the checker to a fixed version | S20 |
| M12 | Leaving the checker's calls unattributed | its cost is invisible | send its calls through the same wrapper under their own feature name | S20 |
| M13 | Treating a missing price as a free call | a new model looks like $0 spend | write no cost and count the miss (draft), or flag the row as estimated and refuse unpriced models (Lomem) | S20; X12; X13 |
| M14 | Letting a recording failure replace the call's result | an observability bug breaks the feature | guard the recording code with its own try and log a warning | S20 (E9) |
| M15 | Sampling too few calls per day | the daily rate moves by chance more than the drift you want to see | size the rate to about 200 scored calls a day, or chart weekly | S20 |
| M16 | Judging a fix with one replay | output varies per run | replay each prompt several times (ten in E1) | S20 |
| M17 | Two spellings of one feature label | one feature's cost split across rows nobody adds back together | keep labels as constants in one place | X20 |
| M18 | Calling "score" both the feature's output and the eval result | readers and dashboards mix up which number is charted | name them differently (`score` versus `eval_score`) | testing round 1 |
| M19 | Calling both the feature and the second model "judge" | readers cannot tell which judge is meant | name the second model "checker model" | testing rounds 2, 3 |
| M20 | Theorizing about a misbehaving call without its real response | wrong fixes, such as throttles with no 429 | capture status, `finishReason` and error body and reproduce in isolation | X24 |

## Misconceptions

| id | what a newcomer believed | correct statement | evidence |
|---|---|---|---|
| Q1 | Prompt text is kept only for the sampled calls | text is kept for every call over a short window (14 days); only scoring is sampled | testing round 1; S20 |
| Q2 | The eval score is written back to the call's record | the record is a log line that cannot be updated; scores go to `llm_eval` keyed by trace ID | testing round 2; S20 |
| Q3 | The drift chart plots the grading feature's own score | it plots the online eval's agreement rate (eval score), not the feature's 0-100 score | testing round 1; S20 |
| Q4 | "Move the record into spans later" means the text goes into wide-access spans | the text stays in the restricted table unless the tracing backend has the same short retention and narrow access | testing round 2; S20 |
| Q5 | The judge (feature) and the LLM judge (checker) are the same thing | the grading feature is observed; the checker model is a second, pinned model that scores sampled answers | testing rounds 2, 3 |
| Q6 | Cached input tokens are extra tokens added to input | for Gemini, OpenAI and OTel they are a subset of input tokens; Anthropic reports them in a separate field | testing round 2; testing fact-check |
| Q7 | The 4%→19% query and the 0.81 eval figure are unrelated mechanisms | the eval alert (0.81) flagged the drop; the grouping by `response_model` showed the switch from `gemini-2.5-flash` to the preview model on Monday | testing round 2; S20 |
| Q8 | The borderline sample conflicts with the random 2% sample | they serve different purposes: the random sample gives the charted rate, the targeted sample finds problems with fewer human reviews; use both | testing round 2; S20 |
| Q9 | The timeline is contradictory (Tuesday reports, Monday alert, Tuesday record shows preview) | alias moves Monday morning; nightly job alerts at 06:00 Tuesday about Monday; learners report Tuesday afternoon | testing round 3; S20 |
| Q10 | Replaying five prompts once proves the fix | model output varies per run; each prompt was sent ten times and all fifty passed | testing round 3; S20 |
| Q11 | Personal data is only a redaction step, not one of the problems | stored prompts being personal data is one of the five problems LLM calls bring | testing round 1; S20 |
| Q12 | The verdict is computed from the score (under 50 means wrong) | in Lomem the model returns its own score and a separate boolean verdict; the instructions give a wrong answer 0-50 | testing fact-check; X23 |
| Q13 | OTel has no prompt-version attribute, so you invent `app.prompt.version` | OTel defines `gen_ai.prompt.name` and `gen_ai.prompt.version` (Conditionally Required) | testing fact-check; S1 |
| Q14 | Using the `gen_ai.*` names is all OTel says | the conventions are in "Development" status, and content attributes are opt-in because they hold personal data | testing rounds 1-3; S1 |
| Q15 | Spring AI logs prompts and replies out of the box | prompt and completion logging are off by default | testing rounds 1-2; S4 |
| Q16 | Latency and error alerts will catch a quality drop | a drifted answer is fast and returns 200; only quality scores catch it | S20 |
| Q17 | The model behind a name stays the same until the provider announces a version | the provider can move an alias or ship a bug that degrades answers for weeks | S20; S2; S3 |
| Q18 | Lomem already has distributed tracing for model calls | Lomem has no OpenTelemetry or distributed tracing; it has pino logs, the usage ledger and the postmortem mirror | S23 §9 |
| Q19 | Lomem's postmortem mirror only runs in dev | it is on in development, staging and test unless `POSTMORTEM_ENABLED=false`; off in production unless set to true | X9 (code read 2026-10-15) |
| Q20 | Lomem's mirror redacts prompts | it redacts by key name and truncates; prompt prose is not scrubbed | X8; X10 |
| Q21 | The mature list is padding | the mature setup (nested spans, dashboards, feedback, score and spend alerts, replay) is part of the block's content | testing round 3 |
| Q22 | "Provider" means the API | provider is the company that runs the model and sells access through an HTTP API | testing round 2; S20 |

Terms newcomer readers did not know (all rounds): prompt template versus prompt, prompt version, system prompt, messages, tools as part of a request, retrieval, multi-step request, cached input tokens, context caching, provider attempt, gateway, settle, meter, ledger row, safety filter, content filter, eval, online eval, rubric, Lomem, checkpoint, translation drill, `td_` prefix, AC-11a, ADR-037, Spring AI, Langfuse, Arize Phoenix, OpenLLMetry, Datadog LLM Observability, Microsoft Presidio, PII, IBAN, Sonnet 4, GPT-4, trace, trace ID, distributed trace, span, client span, APM, hook (observe, onRequest, onResponse), tenant, Micrometer observation, Micrometer Tracing, Jaeger, Grafana Tempo, score band, usual band, `kv()`, price table format, the key (in the rubric), labelled answers, preview, STOP and other finish values, MDC, logstash-logback-encoder, "Development" status, `BORDERLINE_MIN` and `BORDERLINE_MAX` values, pinning a model version, Flash, third-call tie-break, deterministic check, standard deviation, alias, points, on-call role, Lomem's shared redactor. (testing rounds 1-3) Each now has a concept above or is a name only.

## Open questions

- (unverified) The cache-hit window "the last few minutes" matches Anthropic and OpenAI defaults; Gemini's implicit cache lifetime was not found. (testing fact-check)
- (unverified) The Micrometer Tracing call `tracer.currentSpan().context().traceId()` and logstash-logback-encoder `kv()` in E9 were not checked line by line. (testing fact-check)
- Does a cached-token discount apply only to your own recent prompts or to any customer's? Not answered by the inputs. (testing final read)
- If the checker model comes from the same provider as the checked model, can provider-side drift hit both at once and hide the change? Not answered. (testing final read)
- Does excluding MAX_TOKENS, SAFETY and failed calls from the sample bias the agreement rate, and should their rates have their own alerts? The draft only says to chart their rate from the log. (testing final read)
- Why 14 days of text retention: a legal rule or how long reports take to arrive? Not stated. (testing final read)
- Should `user_id` in the record be treated as personal data with its own retention? Not stated. (testing final read)
- Why is a preview model riskier than a released one? Readers asked; the inputs do not say. (testing round 3)
- How are prompt versions assigned (number, hash)? The draft uses an integer (14); S22 says "version hash"; Lomem's version rows have only an autoincrement id and a timestamp. (testing round 1; S22; X25)
- What happens if the replay in F3.7 still fails after pinning? Not described. (S20)
- Who checks the checker? Testing round 2 listed it as a missing step; the draft's answer is pinning plus "a person can also score", with no validation of the checker against human labels (S22 block 11 recommends validating LLM judges against human labels). (testing round 2; S22)
- Disagreement: S22's minimal setup samples full payloads; the draft stores redacted text for every call and samples only scoring. (S22 block 12; S20)
- Disagreement: S22's minimal record includes tool calls; the draft's record does not. (S22 block 12; S20)
- Disagreement: on a missing price the draft writes no cost and counts the miss; Lomem writes $0 with `isEstimated` and warns. (S20; X12)
- Code versus comment: `mirror-helpers.ts` lines 3-4 say "All mirrors are no-ops outside dev", but `enabled.ts` enables the mirror in staging and test too. (X8; X9)
- Code versus doc: the postmortem README says `redaction.ts` holds `redact()` and to "Edit `REDACT_KEYS` in `redaction.ts`", but `redaction.ts` is now a re-export shim and the keys live in `packages/shared/src/redaction/redact.ts`. (X10; `apps/tunatutor/backend/src/dev/postmortem/redaction.ts:1-11`)
- Research versus code: S23 §9 says the mirror "only runs in dev" and its payloads "are redacted"; the code shows staging and test too, and key-name redaction only, so system prompts and messages are mirrored as written. (S23 §9; X8; X9; X10)
- Research line number: S23 §14 cites root `CLAUDE.md` line 254 for the debugging rule; on 2026-10-15 it is line 256. (X24)
- Line drift: every X block matches the local Lomem `main` checkout at `8e3f5d5db` (2026-10-15). `origin/main` (`a56647425`, one commit ahead) moves X25 to `schema.prisma:2103-2127` and X24 to `CLAUDE.md:257` (and the postmortem curl line to 258); the other cited files are unchanged. (git diff checked 2026-10-15)
- Lomem gaps against this block's minimal version: no prompt version on ledger rows, no response model (`modelVersion` not read), no finish reason on ledger rows, no production text store, no online eval of live traffic, no OpenTelemetry. (X4; X5; X16; S23 §9)
- Lomem's `logBorderline` writes `userAnswer` to the normal production log, which the draft names as the next problem; the comment says to remove it two weeks after release. Whether it has been removed on schedule is unknown. (X22; S20)
- The draft's incident uses expected answer `Sou barista.`; Lomem's real fixture row has key `Eu sou barista.` with the same learner answer. (S20; S23 §7b)
- The draft says Lomem stores prompt templates in a database "so they can edit them without a release"; Lomem does, but its mirror and ledger do not record which version ran. (S20; X25; X5)
- Not covered by the research: alert routing and on-call process, cost of the checker model per day, OTel metric names (token and duration metrics exist per S22 but are not named), how user feedback is captured in the UI, and how the record works for streaming calls outside Lomem.
- Whether an in-process `EventEmitter` (X18) means each backend instance streams only its own errors is inferred, not verified.

## Sources

| id | title | author or publisher | date | URL | what it supports |
|---|---|---|---|---|---|
| S1 | GenAI client inference semantic conventions | OpenTelemetry | current as read (Development status) | https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/client-inference.md | attribute names, opt-in content, PII quote, prompt name and version, cache-read tokens |
| S2 | How is ChatGPT's behavior changing over time? | Lingjiao Chen, Matei Zaharia, James Zou | 2023 | https://arxiv.org/abs/2307.09009 | GPT-4 prime accuracy 84% (March) to 51% (June) under the same name |
| S3 | A postmortem of three recent issues | Anthropic | 17 September 2025 | https://www.anthropic.com/engineering/a-postmortem-of-three-recent-issues | provider bugs that degraded answers for weeks (August to mid-September 2025) |
| S4 | Spring AI observability | Spring AI project | not given | https://docs.spring.io/spring-ai/reference/observability/index.html | `gen_ai.client.operation` observation; log-prompt and log-completion off by default |
| S5 | GenAI semantic conventions README | OpenTelemetry | moved to own repo in 2026 | https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/README.md | Development status; coverage (spans, metrics, events, MCP, provider pages); old pages say "Moved" |
| S6 | Building A Generative AI Platform | Chip Huyen | 25 July 2024 | https://huyenchip.com/2024/07/25/genai-platform.html | observability runs across all platform parts |
| S7 | Langfuse prompt management | Langfuse | not given | https://langfuse.com/docs/prompt-management/overview | prompt versions linked to traces and eval scores |
| S8 | Patterns for Building LLM-based Systems & Products | Eugene Yan | about August 2023 | https://eugeneyan.com/writing/llm-patterns/ | collect user feedback; defensive UX |
| S9 | AI Evals: Everything You Need to Know | Hamel Husain, Shreya Shankar | updated September 2026 | https://hamel.dev/blog/posts/evals-faq/ | read 30 to 100 traces; golden sets from production traces; online evals on sampled traffic |
| S10 | Emerging Patterns in Building GenAI Products | Bharani Subramaniam, Martin Fowler | 28 January to 25 February 2025 | https://martinfowler.com/articles/gen-ai-patterns/ | the catalogue has nothing on tracing |
| S20 | Long fact-checked draft, block 12 | this learning project | 2026 | `sources/sections-long/13-observability.html` | running example, record, wrapper, online eval, redaction, mature setup, mistakes |
| S21 | Short version tested on newcomer readers, block 12 | this learning project | 2026 | `sources/sections-tested/13-observability.html` | shorter wrapper; same facts in fewer words |
| S22 | Web research catalogue | this learning project | 2026 | `sources/research-web.md` | block 12 entry, request path, tools list, related blocks 2, 11, 13, 15, 16 |
| S23 | Lomem code map | this learning project | 2026 | `sources/research-lomem.md` | §9 observability, §1 gateway, §6-7 judge and evals, §12b settle point, §14 ADRs |
| testing | Testing notes, block 12 | this learning project | 2026 | `sources/testing-notes/13-observability-testing.md` | key points, misreads, unknown terms, fact-check fixes, open questions |

- The S1-S4 links resolved when the fact-check ran. (testing fact-check)
- The S5-S10 links were checked with a live HTTP request by the web research. (S22 intro)
