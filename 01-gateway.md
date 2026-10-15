---
id: gateway
number: 1
title: The model gateway
summary: The model gateway is the one module or proxy every model call must pass through, so the key, retries, time budget, fallback and per-call spend record live in one place.
lomem_status: yes
depends_on: []
related: [structured, tools, observability, caching, guardrails, governance, evals, prompts, rollout]
---

# The model gateway

## Summary

A model gateway is one module, or one proxy service, that every part of a system must use to call a language model [S1].
It exists because each model call costs a different amount of money, fails and slows down in its own ways, needs a secret key, and must be charged to a user or a job [S1].
In a classic backend an outbound call has a fixed price and a replica behind a load balancer gives the same answer; a model call is priced per token after the fact, and its fallback is a different model with different answers and a different price [S1].
In Lomem the gateway is a shared package that every app except MyTube calls; it refuses unattributed calls, picks the model list, retries inside a time budget, falls back, and records the spend of every attempt [X1, X56].

## Problem

- P1 · Cost is charged per token, so the price of a call is not fixed and one bad loop is a real bill [S1, S4].
- P2 · Without one door, no one can say which feature or which user spent the money [S1].
- P3 · Providers return HTTP 429 (rate limit) and 5xx errors and have outages; without a gateway each feature retries in its own way, or not at all [S1, S4].
- P4 · Moving a feature to a cheaper model, or to a backup model while the main one is down, means editing every call site [S1].
- P5 · The provider API key spreads across services and is read in a dozen places; anyone holding it spends the owner's money [S1, S4].
- P6 · Several providers each have their own API [S4].
- P7 · Cheap requests should go to a small model and hard ones to a large model; choosing the target is a business decision that a load balancer never weighs [S1, S4].
- P8 · A fallback model is not a replica: it writes different answers at a different price [S1].
- P9 · A failed or timed-out attempt can still have been billed by the provider [S1].
- P10 · Unbounded consumption (cost and denial of service) is a named LLM risk: OWASP LLM10:2025 [S4, S12].

## Concepts

### C1 · Model (LLM)
- Definition: A model, or large language model (LLM), is a program that takes text in and writes text back.
- Facts:
  - ChatGPT is a chat screen in front of a model [S1].
  - The model runs on the provider's servers; the app does not host it [S1].
- Relations: C1 is sold by C2. C1 is called through C15. C1 comes in sizes (C10).

### C2 · Model provider
- Definition: A model provider is a company that runs models on its servers and sells access over an HTTP API.
- Facts:
  - Examples: OpenAI, Anthropic, Google (Gemini) [S1].
  - A model call is made the way one would call Stripe: send a request, get a response [S1].
  - Lomem's provider is Google Gemini, reached at `https://generativelanguage.googleapis.com/v1beta` [X19, X22].
  - The provider's billing console is the source of truth for spend; the app's own totals should be compared with it [S1].
- Relations: C2 issues C4. C2 charges per C6. C2 enforces C31.

### C3 · Provider SDK (client library)
- Definition: A provider SDK is the provider's client library that wraps its HTTP calls.
- Facts:
  - Without a gateway, each feature imports the provider's client library and reads the key itself [S1].
  - Lomem does not use Google's SDK for text calls; `GeminiProvider` calls the REST API with `fetch` [X22].
  - Testing readers did not know the term "SDK" or what the "Gemini client" was [testing].
- Relations: C3 is replaced by K3 in Lomem. C3 scattered across services is M1.

### C4 · API key
- Definition: An API key is the secret string a provider gives the account owner; every request carries it, and the provider bills the account that owns it.
- Facts:
  - Anyone holding the key spends the owner's money [S1].
  - In Lomem the key is read when the app starts and builds its models (`process.env.GEMINI_API_KEY`), and feature code never sees it [S1, X11].
  - tunatutor reads `GEMINI_API_KEY` in `services/llm/registry.ts:16` and again in `src/index.ts:657` for the image model [S3, X11, X55].
  - An earlier draft said the key is read "in exactly one place"; the fact-check found that false [S3].
  - The tested short version still says "The key is read once, when the app starts"; tunatutor reads it at two sites [S2, X11, X55].
  - `GeminiProvider` sends the key in the `x-goog-api-key` header [X22].
  - The key is a private field of the provider; observers never see it ("the key never leaves the provider") [X20, X2].
  - With no key, `createAppLlm` builds a gateway with no provider; a call fails with "No LLM provider available" and the app still boots [X50].
  - A mature proxy keeps the real provider keys inside the proxy and gives teams virtual keys (C48) [S1, S7].
- Relations: C4 is held by C15. C4 is replaced for teams by C48.

### C5 · Prompt, system prompt and messages
- Definition: A prompt is the text sent to the model: instructions plus the user's input.
- Facts:
  - Every gateway request carries `systemPrompt` and a list of `messages` [X2].
  - Gemini receives the system prompt as `systemInstruction` and the messages as `contents` with roles `user` and `model` [X22 file, gemini.ts:153-185, 324-329].
  - When there are no messages, Gemini needs at least one content entry, so the system prompt moves into `contents` [gemini.ts:320-329].
  - The OpenAI-style request body is a list of messages with roles, such as `{ "role": "user", "content": "Rate this answer: ..." }` [S1].
  - Testing readers asked why the body is a list of messages with roles instead of one prompt string; the research did not answer it [S3].
- Relations: C5 is measured in C6. C5 is the input of F1.

### C6 · Token
- Definition: A token is the unit of text a model reads and writes.
- Facts:
  - A token is roughly three quarters of an English word (unverified) [S1, S3].
  - Providers charge per token [S1].
  - Testing readers confused "token" with the cancellation token or signal (C34) [testing].
- Relations: C6 is counted as C7. C6 is priced by C23.

### C7 · Input tokens, output tokens and usage metadata
- Definition: Input tokens are what is sent; output tokens are what the model writes; every response reports both counts.
- Facts:
  - Providers charge separate prices for input and output tokens [S1].
  - Gemini's response ends with a `usageMetadata` block such as `{ "promptTokenCount": 1200, "candidatesTokenCount": 150 }` (counts made up) [S1].
  - `candidatesTokenCount` is Gemini's name for the output count; "candidates" are Gemini's answer alternatives [S1, X25].
  - Lomem maps `promptTokenCount` to `inputTokens` and `candidatesTokenCount` to `outputTokens` [X25].
  - A longer learner answer means more input tokens and a higher price, so two calls to the same endpoint can cost very different amounts [S1].
- Relations: C7 is recorded by C20. C7 times C23 gives cost.

### C8 · Cached input tokens
- Definition: Cached input tokens are prompt tokens the provider served from its context cache and bills at a reduced rate.
- Facts:
  - Gemini reports them as `cachedContentTokenCount` [X25].
  - Lomem writes them as a separate ledger row with key `<model>:text-input-cached` [X26, X30].
  - Flash cached input costs $0.03 per 1M tokens; Flash Lite $0.01 [X35].
  - The running example does not use cached input [S1].
  - Testing readers asked whether the meter needs a cached-input column from day one; Lomem writes cached input as its own row from day one [S3, X26].
  - No explicit `cachedContents` API use was found in Lomem [S5].
- Relations: C8 is part of C7. C8 belongs to block caching.

### C9 · Thinking tokens
- Definition: Thinking tokens are tokens a model spends reasoning before it answers; the provider bills them as output.
- Facts:
  - Gemini reports them as `thoughtsTokenCount` [X25].
  - Lomem adds them to the output row [X26, X30].
  - Gemini 2.5 models have thinking on by default, and it consumes output tokens from the `maxOutputTokens` budget [X24].
  - Lomem turns thinking off by default on 2.5 models because "thinking wastes tokens and causes truncation" for JSON [X24].
  - The level chat passes `thinking: "off"` [X40].
- Relations: C9 limits C13. C9 is priced as output by C23.

### C10 · Model size and tier
- Definition: A provider sells several models of different sizes; a bigger model answers better and costs more.
- Facts:
  - Gemini 2.5 Flash is a mid-size model (unverified); Flash Lite is a smaller, cheaper one [S1, S3].
  - The rater does a narrow scoring job, so it runs on the cheaper model [S1, X39].
  - Testing readers did not know Flash and Flash Lite as model tiers [testing].
  - tunatutor can choose between exactly two models: `gemini-2.5-flash` and `gemini-2.5-flash-lite` [X12].
- Relations: C10 is chosen by C25 and C50. C10 sets C23.

### C11 · Finish reason
- Definition: A finish reason is the provider's statement of why the model stopped writing.
- Facts:
  - STOP means it finished; MAX_TOKENS means it hit the output limit and the answer is cut off; SAFETY means the provider's content filter blocked it [S1, X47].
  - Only STOP means a complete answer [S1].
  - Gemini's finish-reason names were left unverified by the fact-check [S3]; the names STOP, MAX_TOKENS and SAFETY appear in Lomem's classifier [X47].
  - Other names Lomem knows: RECITATION, PROHIBITED_CONTENT, BLOCKLIST, SPII, IMAGE_SAFETY, IMAGE_PROHIBITED_CONTENT, IMAGE_RECITATION, MALFORMED_FUNCTION_CALL, UNEXPECTED_TOOL_CALL, TOO_MANY_TOOL_CALLS [X47].
  - A prompt can also be blocked: Gemini returns `promptFeedback.blockReason` [X47, X25].
  - A Gemini stream that ends with no finish reason is treated as cut off and throws `GeminiStreamError` [X49].
  - Returning the finish reason lets the caller see that an answer was cut off [S1].
  - Testing readers saw finishReason only implied through MAX_TOKENS [testing].
- Relations: C11 is classified by C12. C11 caused by C13 (MAX_TOKENS).

### C12 · Stop reason classification
- Definition: Lomem maps each provider finish reason once to a provider-neutral stop reason: `end_turn`, `max_tokens`, `blocked`, `malformed_tool_call` or `stop_sequence`.
- Facts:
  - `classifyFinish` lives in `packages/shared/src/llm/finish.ts` [X47].
  - A blocked prompt is `blocked` whatever the finish reason says [X47].
  - `callJson` throws `LlmOutputError` for a blocked answer and names the finish reason when a cut answer fails to parse [X46].
  - Plain `call` returns `finishReason` and `blockReason` for the caller to read; it does not throw on them [X56].
- Relations: C12 is used by C42. C12 refines C11.

### C13 · Output limit (maxTokens)
- Definition: The output limit caps how many tokens the model may write, which also caps the output cost.
- Facts:
  - The rater's limit is 500 tokens; the tutor's is 700 [S1, X39].
  - Tool calls default to 2048 [X2].
  - Image calls use 8192; an image answer measured about 1,100 to 1,500 tokens on 2026-10-10 [gateway.ts:207-208].
  - Gemini receives it as `maxOutputTokens` [X24].
- Relations: C13 limits C7 output. C13 is reduced by C9.

### C14 · Temperature
- Definition: Temperature is a model setting that controls how varied the output is.
- Facts:
  - The rater runs at 0.1, the tutor at 0.6 [X39].
  - `callJson` defaults to 0.2 [X46].
  - `GeminiProvider` defaults to 0.8 when the caller sets none [X24].
  - Testing readers did not know the term [testing].
- Relations: C14 is passed through C15 unchanged.

### C15 · Model gateway
- Definition: A model gateway is one module, or one proxy service, that every part of a system must use to call a language model.
- Facts:
  - It holds the key, the retries, the time budget, the fallback and the spend record [S1].
  - In Lomem it is `createLlmGateway` in `packages/shared/src/llm/gateway/` [X1, X56].
  - Every LLM call in tunatutor, Mealy and Billpod goes through it; MyTube still calls a provider directly (`createLlmClient`) [X56].
  - It exposes `call`, `callJson`, `callWithTools`, `callImage`, `stream`, `streamWithTools` [X2].
  - Chip Huyen names it step 3 of a generative AI platform: "model router and gateway" [S6].
  - Chip Huyen's build order: enhance context, then guardrails, then router and gateway, then cache, then complex logic and write actions [S4].
  - In Chip Huyen's platform, observability and orchestration run across all the steps [S4].
  - The research ranks Chip Huyen's article second of five newcomer sources, as the only one that is a system architecture diagram that maps onto a backend [S4].
  - The smallest version is a wrapper class with five jobs; a mature version is a separate proxy shared by many teams [S1].
- Relations: C15 contains C16, C27, C30, C33, C20. C15 is the "Gateway, then model" step of F11.

### C16 · Usage context (who pays)
- Definition: A usage context is the required record on every gateway call that says who pays: a user and a feature, or a written reason for system work.
- Facts:
  - User shape: `{ userId, feature, surface?, sessionId?, actor? }` [X3, X56].
  - Example: `{ userId: 42, feature: "onboarding_level_chat" }`; the user id is made up, the feature name is real [S1, S3, X40].
  - A call with no context, an empty feature, a non-positive or non-integer userId, or a system call with no reason throws `MissingUsageContextError` before any HTTP request is made [S1, X4, X56].
  - The error code is `FST_MISSING_USAGE_CONTEXT` with HTTP status 500 [X5].
  - TypeScript already makes a missing context unreachable; the runtime check catches untyped callers and casts [X4].
  - A test pins the rule: the call must "FAIL loudly, never fall through to the provider with metering quietly skipped" [S1, X7].
  - In tunatutor the field is called `conversationType`; it is mapped to `feature` before the gateway [X6, tunatutor services/llm/index.ts:31-47].
- Relations: C16 is checked at F1.2. C16 feeds C20. C16 contains C17, optionally C18 or C19.

### C17 · Feature label
- Definition: A feature label is the name a call's spend is reported under, stored as the usage row's `conversation_type`.
- Facts:
  - tunatutor's level chat uses `onboarding_level_chat` [X40].
  - An earlier draft used `level_chat`; the fact-check corrected it to `onboarding_level_chat` [S3].
  - Billpod uses four features: `capture`, `assistant`, `paperwork`, `avatar` [S5, X51].
  - A surface inside a feature (Billpod: `app`, `mcp`, `email`, `drop`, `drive`) is kept in the row's metadata [X3, X51].
  - tunatutor keeps labels as constants so one feature reports under one name [X52].
  - In a proxy the same idea is a "tag": a free-form label the caller attaches [S1].
- Relations: C17 is part of C16. C17 groups reports (F4.7). C17 equals C49 in a proxy.

### C18 · System usage context
- Definition: A system usage context marks a deliberately unattributed call (cron, startup, content scripts, admin jobs) and must state a reason.
- Facts:
  - Shape: `{ system: true, feature, reason }` [X3, X56].
  - Example: `{ system: true, feature: "content_import", reason: "nightly lesson import" }` (made up) [S1].
  - The row is written with no user, `actor_kind = 'system'` and the reason as `system_reason` [X3, X31].
  - A system row with no reason gets `unattributed` [X57].
  - System spend counts in the app's cost and is never debited [X26, X57].
  - A cron job with no user id is spend no report will ever show, so it must state a reason [S1].
- Relations: C18 is a variant of C16.

### C19 · Admin actor
- Definition: An admin actor marks an admin's own tooling call under their user id.
- Facts:
  - Context field `actor: "admin"` [X3].
  - The row keeps the admin's user id with `actor_kind = 'admin'`, so account erasure still covers it (ADR-037) [X3].
  - Admin spend is never debited from an allowance and stays out of per-user rankings [X3, X57].
- Relations: C19 is a variant of C16.

### C20 · Metering
- Definition: Metering means recording what each call used (tokens, model, who asked) so it can be priced and reported later.
- Facts:
  - After each model's attempt, success or failure, the gateway hands the token counts to the app's meter [S1, X17].
  - The meter is a port: tunatutor's ledger plus allowance settle, or the shared `createProviderUsageMeter` [X1].
  - The meter writes in the background, so a slow database never delays the learner's reply; the cost is that a crash can lose a few rows [S1, X17].
  - Tunatutor accepts losing rows for internal reports; invoicing from these rows needs an outbox (C45) [S1].
  - Testing readers did not know the term "metering" [testing].
  - Testing readers asked whether the "recorder" of step 5 and the `spend` object of the Java sketch were the same thing under two names; both are the meter [testing, S1].
- Relations: C20 is triggered by C21. C20 writes C22. C20 is priced by C23.

### C21 · Settle point and spend event
- Definition: The settle point is the one place where the gateway records each provider attempt exactly once, as a spend event.
- Facts:
  - A spend event carries operation, provider, usage (absent on failure), latency, `isError` and `aborted` [X18].
  - The gateway calls `meter.record` exactly once per provider attempt and never awaits it [X18, X56].
  - A meter that throws or rejects is logged and the call still returns [X17, X56].
  - `callJson` settles before it validates, so a wrong answer is still recorded [X46, X56].
  - "Every LLM call in tunatutor converges on ONE settle site, so ~90 call sites are correct by construction" [X58].
  - Testing readers did not know "settle" until late in an earlier draft [testing].
- Relations: C21 is part of C15. C21 produces C22.

### C22 · Ledger row (provider_usage_events)
- Definition: A ledger row is one row in `provider_usage_events` for one billable line of one attempt.
- Facts:
  - A successful attempt writes one row per kind of token: input, cached input (only when present), output [S1, X26, X30].
  - Row keys are `<model>:text-input`, `:text-input-cached`, `:text-output` [X26].
  - A failed attempt writes a single zero-token row with `is_error = true`, keyed `<model>:text-input` [S1, X26].
  - So the failure marker row has kind "input"; testing readers had asked this [S3, X26].
  - Columns include user_id, actor_kind, system_reason, session_id, conversation_type, provider_key, capability, billable_quantity, computed_usd_micros, is_estimated, latency_ms, is_error, metadata_json, occurred_at, price_config_id [X34].
  - A spend report is a GROUP BY over this table by feature, user or model [S1].
  - Testing readers asked what columns a ledger row has [testing].
- Relations: C22 is written by K9. C22 is priced by C23. C22 is read by C38 and C39.

### C23 · Price table and pricing at write time
- Definition: The price table holds the provider's list price per block of units for each price key, and each ledger row is priced when it is written.
- Facts:
  - Table `provider_price_config`, one effective-dated row per key, price in USD micros per block of units [X34 file, _shared.45-provider-usage.prisma:25-58].
  - The rows are seeded on boot from Google's price page and editable by the owner on the admin Billing → Provider Costs page [S1, X35, X57].
  - The seed inserts only missing keys, so an owner's edit is never overwritten [X35].
  - Tunatutor prices each row when it writes it, so a later price edit applies only to rows written after it [S1, X31].
  - A key with no active price row is written at $0 with `is_estimated` [X31, X57].
  - A price lookup is cached 5 minutes; a miss is remembered 30 seconds [X33, X57].
  - Cost in micros = billable quantity × micros per block ÷ units per block, integer division [X32].
  - Testing readers' sketches priced rows at report time; that is not what tunatutor does [testing].
- Relations: C23 is checked by C44. C23 prices C22.

### C24 · Model registry: enabled, priority, active
- Definition: tunatutor's model registry keeps one config row per model with an enabled flag and a priority number, plus one model marked active (the default).
- Facts:
  - Config rows live in `llmModelConfig`; the active model lives in app setting `llm.activeProvider` [X11].
  - The owner sets enabled, priority and active on an admin page [S1, X37].
  - Lower priority number means earlier in the fallback order [X10].
  - On a fresh database Flash gets priority 1 and is seeded as active; Flash Lite gets 100 [X11].
  - Disabling the active model makes the first enabled model active and persists it [X38].
  - The provider list is re-read on every call, so admin edits take effect at once [X14].
  - Testing readers did not know where enabled and active models are set, or how they differ [testing].
- Relations: C24 feeds C25 and C26. C24 is changed by C28 (in memory) and F7 (persisted).

### C25 · Lead model and per-call model
- Definition: The lead model is the first model a call tries: the model the caller named if it is enabled, otherwise the active model.
- Facts:
  - Every request may carry an optional `model` id [X2, X56].
  - The app decides whether to honour it, through `resolveModel` [X2, X56].
  - tunatutor honours it only for an enabled model; a disabled or unknown id silently runs on the active model [X9].
  - The level chat pins its rater to Flash-Lite this way [X9, X56].
  - The active model does not keep second place; testing readers assumed it did [testing].
- Relations: C25 is the first entry of C26. C25 is not changed by C28 for named calls.

### C26 · Candidate list (fallback list)
- Definition: The candidate list is the lead model followed by every other enabled model in priority order.
- Facts:
  - The followers are the fallback list, and they apply even when the caller named a model [S1, X8].
  - With `fallback: false`, the list is the lead only [X8].
  - Gateway function `candidates()` builds it [X8].
  - Testing readers assumed a named model has no fallback [testing].
- Relations: C26 is walked by C27. C26 is built from C24 and C25.

### C27 · Fallback
- Definition: Fallback means trying the next model in the candidate list, with a fresh time budget, when a model still fails after its retries.
- Facts:
  - Each model may use its whole budget, so the ceiling on total wait is budget × number of models [S1].
  - With the 120 s default and three enabled models, that is 6 minutes [S1].
  - In the level chat, a route-level abort signal caps the whole call at one budget, so this ceiling does not apply there (see Open questions) [X40, E7].
  - If every model fails, the gateway throws "All LLM providers failed" and the feature must have a plan for it [S1, X16].
  - A provider that does not implement the operation is skipped [X16, X56].
  - A caller abort never triggers fallback [X16, X56].
  - The backup model is a different model, not a replica: it writes different answers, sometimes worse, at a different price [S1].
  - Instructions written and tested against one model may work less well on another [S1].
  - A fallback can quietly move a cheap job onto a model four times as expensive [S1].
  - A mature proxy has fallback chains across providers and regions [S1, S4].
  - Testing readers described fallback only as "try the next one in the list" and missed that it changes answers and price [testing].
- Relations: C27 uses C26. C27 causes C28. C27 changes cost (C23) and quality (block evals).

### C28 · Sticky switch
- Definition: tunatutor's sticky switch makes a fallback model that succeeded the new active model, in that server's memory only.
- Facts:
  - Calls that name no model then start on a model that works [S1].
  - The rater still names Flash Lite, so it keeps trying Flash Lite first [S1, X9].
  - Nothing tests the old model again; it leads again only after a restart or when the owner sets the active model [S1, X13].
  - It is a crude circuit breaker [S1].
  - `onSwitch` fires for any fallback win, also on a call that named its model [X15, E3].
  - Testing readers did not know how the old model comes back [testing].
- Relations: C28 is triggered by C27. C28 changes C24 in memory. C28 resembles C29.

### C29 · Circuit breaker
- Definition: A circuit breaker stops calling a failing service for a while, then tries it again.
- Facts:
  - It appears in the Java analogy: RestClient plus Resilience4j retry and time limiter plus a circuit breaker [S1].
  - Lomem's gateway has no real circuit breaker; the sticky switch never re-tests the old model [S1].
  - Testing readers did not know the term or whether "active until restart" was the equivalent [testing].
- Relations: C29 is approximated by C28.

### C30 · Retry policy (retryable statuses)
- Definition: The retry policy says which failures are retried on the same model and how many times.
- Facts:
  - Gemini client retries 429, 500, 502, 503 and 504 [S1, X19].
  - Up to 3 HTTP requests in total [S1, X19].
  - A network failure with no response at all is retried the same way (`retryNetworkErrors` defaults to true) [S1, S3, X19].
  - It never retries another 4xx: a 400 means the request is wrong; a 401 or 403 means the key is bad; a retry fails the same way [S1, X22].
  - Each retry of a 400 or 401 may cost money [S1].
  - An earlier draft said "never 4xx", which contradicted the 429 retry [testing].
  - The gateway itself does not retry on bad output; callers do [S5].
- Relations: C30 is part of F2. C30 is bounded by C33. C30 uses C32.

### C31 · HTTP 429 (rate limit)
- Definition: HTTP 429 "too many requests" is the provider's rate limit on the key.
- Facts:
  - 429 is retried [S1, X19].
  - tunatutor logs "Gemini rate limited, retrying" on a 429 retry [tunatutor providers/gemini.ts:11-19].
  - Whether parallel fallbacks onto one model add rate-limit pressure was asked by readers and not covered by the research [S3].
  - Lomem's root `CLAUDE.md` rule: when an LLM call misbehaves, capture the real response (status, `finishReason`, error body) and reproduce in isolation before theorizing; never assume quota or rate limits or add throttles without direct evidence (an actual 429) [S5, lomem CLAUDE.md:256].
  - The same `CLAUDE.md` line states that Lomem's API keys are paid tier (Gemini, Anthropic and others) [lomem CLAUDE.md:256].
  - The shared gateway has no rate limiter or throttle of its own: `packages/shared/src/llm/gateway/` has no match for "rate limit" or "throttl" [grep of Lomem main, 2026-10-15].
  - Lomem's rate controls sit outside the gateway: Billpod's capture tool allows 30 calls per user per 60 s (`CAPTURE_TOOL_LIMIT = { max: 30, windowMs: 60_000 }`); eval scripts run worker pools (`CONCURRENCY = 3` in the judge gate; default 4, max 8 in the fidelity eval); judge calls are capped per session (ADR-032 §6) [S5, capture.ts:24].
  - Testing readers did not know "throttles" or "throttling" [testing].
- Relations: C31 triggers C30.

### C32 · Backoff, Retry-After and retryDelay
- Definition: Backoff is the wait between retries.
- Facts:
  - Lomem's backoff is linear: 3 s, then 6 s (base 3000 ms × attempt number) [S1, X23].
  - It waits as long as the provider asks when the response sets the `Retry-After` header or Gemini's `retryDelay` in the error body [S1, S3, X21, X22].
  - No wait is longer than 30 s [S1, X19].
  - A retry whose wait does not fit what is left of the budget is not made [S1, X23].
  - A testing reader called it "exponential backoff using Resilience4j"; it is linear, honours Retry-After and is capped at 30 s [testing].
  - Testing readers did not know the term "backoff" [testing].
- Relations: C32 is part of C30. C32 is bounded by C33.

### C33 · Time budget (timeoutMs)
- Definition: The time budget is the longest the app will wait for one model, waits between retries included.
- Facts:
  - The waits count against the budget [S1, X19, X22].
  - The rater's budget is 2 s; the tutor's 4 s [S1, X39].
  - The default budget, for calls that set none, is 120 s [S1, X20].
  - The budget is per model, not per call: each fallback model gets a fresh budget [S1, testing, X16].
  - The rater's 2 s budget is shorter than the first 3 s wait, so the rater retries on the same model only when the provider asks for a wait shorter than what is left [S1, S3, X23].
  - For a stream, the budget runs until the stream opens, then becomes the longest allowed silence between two chunks [X19].
  - A chat turn that waits 120 s is broken even if the answer arrives [S1].
  - Size the budget to what the user can wait for (chat 2 to 4 s; a nightly batch job can take minutes), then multiply by the number of models for the worst case [S1].
  - Testing readers took the budget to cover the whole call; in Lomem `timeoutMs` goes to each provider call [testing].
  - Testing readers saw the 2 s budget against the 3 s first backoff as a contradiction; it is intended [testing].
- Relations: C33 bounds C30. C33 multiplied by C26 length gives the worst case. C33 differs from C34.

### C34 · Caller abort (AbortSignal)
- Definition: A caller abort is the caller giving up on a call, by firing its `options.signal` or stopping reading a stream.
- Facts:
  - It is not a failure: the attempt is settled with `aborted: true`, `isError: false` [X17, X56].
  - The fallback chain is not run and `onError` is not called [X16, X56].
  - Example: the learner left the page [S1].
  - The shared meter writes an aborted attempt with its known usage, or one zero-quantity row, marked `aborted` [X30].
  - tunatutor's meter writes an aborted attempt with no usage as a zero-token error row [S3, X26].
  - The level chat route passes `AbortSignal.timeout(timeoutMs)`, so its own deadline counts as a caller abort [X40].
  - Testing readers did not know `signal`, `aborted` or `AbortSignal` [testing].
- Relations: C34 ends F1 at F1.8b. C34 overrides C27.

### C35 · Attempt
- Definition: An attempt is one model's turn in the candidate list, with all its HTTP retries inside it.
- Facts:
  - One attempt means one model, retries included: three HTTP requests to Flash Lite still write one attempt [S1, X16].
  - Spend is recorded once per attempt [S1, X17].
  - The Java sketch in an earlier draft recorded once per HTTP retry, which contradicted the Lomem code; readers carried that contradiction [testing].
- Relations: C35 contains C30. C35 is settled by C21.

### C36 · Degrade path
- Definition: The degrade path is what a feature does instead of failing when every model has failed.
- Facts:
  - In tunatutor's chat a model failure never reaches the learner as an error [S1, S3].
  - If the tutor call fails, the chat uses a line written in advance for that question (the bank line) [S1, X42].
  - If the rater fails, the turn is saved with no score [S1, X41].
  - After two rater failures in a row, the chat switches to a scorer written in plain code (word count, the answer's language, past-tense words) and shows its result as the tutor's "guess" [S1, X43, X44].
  - Testing readers read "the feature decides" as no answer to what happens when every model fails [testing].
- Relations: C36 follows F1.10. C36 excludes C37.

### C37 · Undegradable errors
- Definition: Undegradable errors are errors a degrade or retry chain must never swallow.
- Facts:
  - tunatutor's list: `FST_MISSING_USAGE_CONTEXT` and `FST_DAILY_SPEND_CAP` [S3, X45].
  - A swallowed missing context would silently reopen the metering hole [X45].
  - The spend-cap error is an admission decision already made at the door; retrying past it would burn the budget it refused [X45].
  - An earlier draft said the chat "never shows the learner an error"; the fact-check narrowed it to model failures [S3].
- Relations: C37 limits C36.

### C38 · Allowance and debit
- Definition: An allowance is a learner's spend budget; a debit takes each priced ledger line off it.
- Facts:
  - tunatutor debits once per ledger row through `settleLlmSpend`, fire-and-forget [S5, X27].
  - The debit is skipped for system and admin calls and zero tokens [X27].
  - A failed debit is logged and swallowed because the ledger row is already written [X27].
  - Billpod's Free account spend draws its one-time trial down; Plus is never debited [X51 file header].
  - Testing readers did not know "allowance" [testing].
- Relations: C38 reads C22. C38 differs from C39.

### C39 · Daily spend cap (checked at the door)
- Definition: The daily spend cap stops a learner from starting new activities once their provider spend for the UTC day crosses a limit.
- Facts:
  - Tunatutor checks it once, when the learner starts a lesson or chat (an activity), not on every model call [S1, X28, X29].
  - A check between two calls of one chat turn could cut the turn off halfway [S1].
  - Doors: a tutor or conversation session create, a drill-arc start, a help request, a "Drill Me" start, a document ingest [X29].
  - A proxy's per-team budget is a different control: it limits a whole team's key, not one person's conversation [S1].
  - Testing readers did not know "activity" or "daily spend cap" [testing].
- Relations: C39 reads C22. C39 is not part of F1.

### C40 · Injected ports
- Definition: Ports are the app-specific functions the gateway receives from outside instead of hard-coding them.
- Facts:
  - Lomem ports: `providers`, `resolveModel`, `fallback.onSwitch`, `meter.record`, `onError`, `observe`, `logger` [X1, X56].
  - Testing readers did not know the term [testing].
- Relations: C40 configures C15.

### C41 · Streaming fallback rule
- Definition: A streamed call may fall back only while nothing has reached the consumer.
- Facts:
  - "Text already reached the consumer: another provider cannot continue it." [X48]
  - Spend is settled when the stream ends, fails, or the consumer stops early [X2, X48].
  - A consumer that stops reading is recorded as aborted with the usage reported so far [X48].
- Relations: C41 is a variant of C27 for F5.

### C42 · Structured call (callJson)
- Definition: `callJson` asks the model for JSON that matches a zod schema, settles the spend, then validates.
- Facts:
  - When the model was asked for JSON and stopped at MAX_TOKENS, the half-written JSON fails to parse, and the error names MAX_TOKENS [S1, X46].
  - The spend is recorded first, because the cut-off answer was still billed [S1, X46].
  - A mismatch or non-JSON is an `LlmOutputError`, never a cast [X56].
- Relations: C42 belongs to block structured. C42 uses C12.

### C43 · Error and observation hooks
- Definition: The gateway's `onError` and `observe` ports report failed attempts and mirror requests and responses.
- Facts:
  - tunatutor's `onError` emits an `llm_error` event that the admin page receives over server-sent events [S5, X53, X54].
  - tunatutor's `observe` mirrors system prompt, messages, tools, finish reason, usage and latency into a dev-only ring buffer (the postmortem mirror) [S5, X53].
  - No OpenTelemetry or distributed tracing was found in Lomem [S5].
  - The postmortem mirror emits one entry per request and one per response (success or error), redacts and truncates each payload, and is a no-op outside dev [S5, mirror-helpers.ts:1-4, 39].
  - Lomem's observability for model calls is pino logs, the usage ledger and the dev mirror [S5].
  - A mature gateway adds an OTel export [S4].
  - Testing readers did not know "tracing" in an LLM context [testing].
- Relations: C43 belongs to block observability.

### C44 · Price coverage
- Definition: Price coverage means every model the app can call has an active price row for each of its keys, so no call is silently recorded at $0.
- Facts:
  - tunatutor's admin settings refuse to make a model active, or enable it as a fallback, while a key has no price row [X36, X37].
  - A unit test requires the three rows for every selectable model [X35, X57].
- Relations: C44 guards C23.

### C45 · Outbox
- Definition: An outbox is a table written in the same transaction as the business change, from which events are delivered later, so none are lost.
- Facts:
  - If customers are invoiced from usage rows, write the rows through an outbox in the same transaction as the business change [S1].
  - Tunatutor does not; it accepts losing a few rows on a crash for internal reports [S1].
  - Testing readers did not know the term [testing].
- Relations: C45 is an option for C20.

### C46 · OpenAI-compatible API format
- Definition: The OpenAI-compatible format is the JSON request shape of OpenAI's chat completions API, which most providers and tools now accept.
- Facts:
  - Example: `POST /v1/chat/completions` with `{ "model": "gemini-2.5-flash", "messages": [ { "role": "user", "content": "Rate this answer: ..." } ] }` [S1].
  - The `/v1/chat/completions` path is not on the linked LiteLLM page, which says "one OpenAI-compatible endpoint" and shows `client.chat.completions.create` (path unverified) [S3].
  - Testing readers did not know the format [testing].
- Relations: C46 is the interface of C47.

### C47 · Proxy gateway
- Definition: A proxy gateway is a separate service that applications send model requests to, which forwards them to the right provider.
- Facts:
  - Example: the open-source LiteLLM [S1, S7, S8].
  - The proxy translates the request for whichever provider sits behind the model name [S1].
  - Moving a team from one provider to another is then a proxy setting, with no change to the calling code [S1].
  - Adds virtual keys, fallback chains across providers and regions, and spend reports per key, team and tag [S1, S4].
  - Also: exact and semantic caching, PII redaction hooks, an OTel export, and a router that classifies requests [S4].
  - A fallback chain can go from one provider to another, or to the same model hosted in another region [S1].
- Relations: C47 is the mature form of C15. C47 contains C48, C49, C50.

### C48 · Virtual key
- Definition: A virtual key is a key issued by the proxy to a team, with its own budget and rate limit.
- Facts:
  - The real provider keys stay inside the proxy [S1].
  - A leaked team key can be revoked without touching the others [S1].
  - Testing readers wanted the gateway key versus provider key distinction sharper [testing].
- Relations: C48 replaces C4 for teams. C48 carries C39-like budgets per team.

### C49 · Tag and spend reports
- Definition: A tag is a free-form label the caller attaches to a proxy request, used to group spend.
- Facts:
  - It is like tunatutor's feature name [S1].
  - Spend reports per key, team and tag come without each app writing its own meter [S1].
  - Testing readers did not know what a tag is in LiteLLM [testing].
- Relations: C49 equals C17.

### C50 · Model router
- Definition: A model router classifies each request and picks the model or workflow for it.
- Facts:
  - Part of the mature gateway: "a router that classifies requests and picks the model" [S4].
  - In the request path, a cheap classifier picks the workflow (or agent) and the model tier [S4].
  - Chip Huyen's step 3 is "model router and gateway" [S6].
  - Lomem has no router; callers name models directly [X9, X39].
  - Testing readers did not know the term [testing].
- Relations: C50 chooses C10. C50 sits before C15 in F11.

### C51 · Operation
- Definition: An operation is the kind of gateway call: `call`, `json`, `tools`, `stream` or `image`.
- Facts:
  - The operation is recorded on each spend event [X18].
  - Each operation maps to a provider method: `chat`, `chatWithTools` or `chatStream` [X16 file, gateway.ts:210-216].
  - Testing readers did not know "operation" (a field in settle) [testing].
- Relations: C51 is part of C21.

### C52 · Unbounded consumption (OWASP LLM10:2025)
- Definition: Unbounded consumption is the OWASP LLM Top 10 2025 risk covering the cost and denial-of-service side of model calls.
- Facts:
  - The research names it as the cost and DoS source for this block [S4, S12].
- Relations: C52 is mitigated by C39, C48, C33. C52 belongs also to block guardrails.

### C53 · Lomem and its apps
- Definition: Lomem is one repository that holds several small apps sharing packages.
- Facts:
  - tunatutor is a language tutor built on Gemini [S1].
  - Billpod is a household-bills app with an in-app assistant and an MCP server [S5].
  - Billpod runs the minimal version: one model, no fallback, spend tagged with four feature names [S1, X50, X51].
  - Mealy builds its LLM the same way as Billpod [X50].
  - MyTube calls a provider directly, outside the gateway [X56].
  - Testing readers did not know what Lomem, tunatutor or Billpod were, or "monorepo" [testing].
- Relations: C53 hosts K1-K20.

### C54 · ADR
- Definition: An ADR (architecture decision record) is a short document that records one design decision and its reasons.
- Facts:
  - Lomem's gateway decision is ADR-057 §5 [X56, X57].
  - Testing readers did not know "ADR" or "ADR-057 §5" [testing].
- Relations: C54 documents C15.

### C55 · Request-path position
- Definition: The gateway sits after context assembly and before the model in one user request.
- Facts:
  - Order: edge and controller, input guardrails, cache check, router, context assembly, gateway then model, agent or workflow loop, output handling, response and memory write-back; tracing, online evals and feedback run across all steps [S4].
  - At the gateway step: virtual key, budget and rate limit, then fallback and retry, then the provider call [S4].
- Relations: C55 places C15 in F11.

## Components

| id | name | role | inputs | outputs | where it lives |
|---|---|---|---|---|---|
| K1 | Shared gateway (`createLlmGateway`) | One door for every model call: refuse unattributed calls, build candidates, try each, settle each attempt | request (system prompt, messages, maxTokens, options, context, model?) and ports | model result or "All LLM providers failed" | `packages/shared/src/llm/gateway/gateway.ts` |
| K2 | Usage context check (`assertLlmUsageContext`) | Refuse a call with no valid payer | usage context | the context, or `MissingUsageContextError` | `packages/shared/src/llm/gateway/context.ts` |
| K3 | `GeminiProvider` | HTTP client for Gemini with retry policy and time budget | system prompt, messages, maxTokens, options | `LLMChatResult` with text, usage, finishReason, blockReason | `packages/shared/src/llm/providers/gemini.ts` |
| K4 | tunatutor model registry | Holds providers, enabled/priority config and the active model | `GEMINI_API_KEY`, `llmModelConfig` rows, `llm.activeProvider` setting | enabled providers by priority, active provider | `apps/tunatutor/backend/src/services/llm/registry.ts` |
| K5 | `resolveLeadProvider` | Picks the lead model | optional model id | named enabled model or active model | `apps/tunatutor/backend/src/services/llm/index.ts` |
| K6 | Sticky switch (`onSwitch` → `switchActiveProviderInMemory`) | Makes a winning fallback the active model in memory | provider that won | new in-memory active model | `services/llm/index.ts`, `services/llm/registry.ts` |
| K7 | tunatutor meter port (`recordLlmUsageCost`) | Turns a spend event into ledger rows and debits | spend event, usage context | ledger rows, allowance debits | `apps/tunatutor/backend/src/services/llm/index.ts` |
| K8 | Allowance settle (`settleLlmSpend`) | Debits the learner's allowance per ledger row | context, price key, token count | debit (fire-and-forget) | `apps/tunatutor/backend/src/services/llm/index.ts` |
| K9 | Shared usage writer | Prices each line at write time and inserts it | usage lines | priced rows | `packages/shared/src/billing/provider-usage-writer.ts` |
| K10 | `provider_usage_events` table | The spend ledger | priced rows | reports by feature, user, model | `_shared.45-provider-usage.prisma` (each app) |
| K11 | `provider_price_config` table and seed | Effective-dated prices per key | seed file, admin edits | price per block in USD micros | `_shared.45-provider-usage.prisma`, `apps/tunatutor/backend/src/dev/provider-prices.ts` |
| K12 | Shared meter (`createProviderUsageMeter`) | Meter port for Billpod and Mealy | spend event, context | ledger rows, optional debit | `packages/shared/src/llm/gateway/provider-usage-meter.ts` |
| K13 | `createAppLlm` | Builds the minimal gateway: one model, no fallback | API key, model, prisma, logger | gateway and meter | `packages/shared/src/llm/gateway/app-llm.ts` |
| K14 | Error and observe hooks | Report failures and mirror traffic | failure info, request and response | `llm_error` SSE events, logs, postmortem mirror entries | `services/llm/index.ts`, `services/llm/llm-events.ts`, `routes/admin/sse.ts` |
| K15 | Admin LLM settings routes | Owner sets active model, enabled flag, priority | HTTP requests from the admin page | persisted config | `apps/tunatutor/backend/src/routes/admin/index.ts` |
| K16 | Activity-entry spend cap | Refuses a new activity over the daily cap | learner's spend for the UTC day | allow or `FST_DAILY_SPEND_CAP` | `apps/tunatutor/backend/src/services/cost-guardrails/activity-entry.ts` |
| K17 | Level chat caller | Runs rater and tutor calls in parallel and degrades on failure | learner answer | tutor line, score or no score | `apps/tunatutor/backend/src/routes/level-chat.ts`, `use-cases/level-chat/` |
| K18 | Degraded scorer | Code-only scoring after two rater failures | answer text | the tutor's "guess" | `apps/tunatutor/backend/src/use-cases/level-chat/degraded.ts` |
| K19 | Finish classifier (`classifyFinish`) | Maps provider finish reasons to stop reasons | finishReason, blockReason | stop reason | `packages/shared/src/llm/finish.ts` |
| K20 | Secret store / environment | Holds the provider key | deployment config | `GEMINI_API_KEY` | environment (`env.generated.ts` validates it) |
| K21 | Proxy gateway | Separate service shared by teams | OpenAI-format requests with virtual keys | provider calls, spend reports | generic (LiteLLM, Portkey, Kong AI Gateway, OpenRouter) |
| K22 | Virtual key store | Per-team keys with budgets and rate limits | team identity | allow or refuse | generic (inside the proxy) |
| K23 | Provider billing console | Source of truth for what was billed | provider account | invoices and totals | generic (provider's console) |
| K24 | Provider Costs admin page | Owner edits prices and reads spend | price edits, `GET /billing/usage-insights` | price rows, cost views | `packages/admin-ui` (shared `ProviderCostsPage`) |

## Flows

### F1 · One non-streaming gateway call
Purpose: run one model call through the gateway with attribution, fallback and metering. Trigger: a feature calls `call`, `callJson`, `callWithTools` or `callImage`.

1. F1.1 · Feature → Gateway: send request | condition: always | data: system prompt, messages, maxTokens, options (temperature, timeoutMs, signal), usage context, optional model | ref: X2
2. F1.2 · Gateway → K2: check usage context | condition: always, before any HTTP request | data: usage context | ref: X4
   - F1.2a · if no context, empty feature, bad userId or system without reason → throw `MissingUsageContextError` (`FST_MISSING_USAGE_CONTEXT`), no provider called → ends; caller must not degrade it (C37) | ref: X4, X5, X45
3. F1.3 · Gateway → K5 (`resolveModel`): get lead model | condition: app supplies `resolveModel` | data: operation, context, model id | ref: X8, X9
   - F1.3a · if no `resolveModel` → first provider leads → continues at F1.4 | ref: X8
   - F1.3b · if named model is disabled or unknown → active model leads → continues at F1.4 | ref: X9
4. F1.4 · Gateway → K4 (`providers()`): list enabled models by priority; build [lead, every other enabled model] | condition: always | data: provider list | ref: X8, X10
   - F1.4a · if no provider at all → throw "No LLM provider available" → ends | ref: X8, X50
   - F1.4b · if `fallback: false` → list is [lead] only (Billpod, Mealy) → continues at F1.5 | ref: X8, X50
5. F1.5 · Gateway: take candidate i | condition: candidates left | data: provider | ref: X16
   - F1.5a · if provider does not implement the operation's method → skip, no attempt, no settle → continues at F1.5 with i+1 | ref: X16
6. F1.6 · Gateway → K14 (`observe.onRequest`): mirror request; log "LLM falling back to provider" when i > 0 | condition: always | data: request snapshot, index | ref: X16, X53
7. F1.7 · Gateway → K3: invoke provider with the same options (fresh budget per model) → runs F2 | condition: always | data: request, timeoutMs, signal | ref: X16, X22
8. F1.8 · K3 → Gateway: success | condition: 2xx with a parsed body (any finish reason, SAFETY included) | data: text, usage, finishReason, blockReason | ref: X16
   - F1.8b · if the attempt throws and the caller's signal has fired → `abandoned()`: settle `aborted: true, isError: false` → rethrow, no fallback → ends | ref: X16, X17
   - F1.8c · if the attempt throws otherwise (HTTP error after retries, timeout, network) → `fail()`: settle `isError: true`, no usage; `onError` logs, emits `llm_error`, mirrors → continues at F1.5 with i+1 | ref: X16, X17, X53
9. F1.9 · Gateway → K14 (`observe.onResponse`) and settle success → runs F4 | condition: success | data: usage, latency, `isError: false` | ref: X16, X17
10. F1.10 · Gateway → K6 (`switched`): if i > 0, `onSwitch(provider)` → tunatutor makes it the in-memory active model | condition: success on a fallback | data: provider | ref: X15, X13
11. F1.11 · Gateway → Feature: return result | condition: success | data: result with finishReason | ref: X16
12. F1.12 · Gateway → Feature: throw "All LLM providers failed" | condition: every candidate failed | data: error | ref: X16
   - F1.12a · if operation is `tools` → message also says "or none support tool-use" and carries the last error | ref: X16
   - F1.12b · if no candidate supported the method → "No LLM provider supports <method>" | ref: X16
13. F1.13 · Feature: degrade (see F3.6-F3.8) | condition: the feature has a plan | ref: S1, X41

### F2 · One provider attempt with retries inside the time budget
Purpose: send one model's HTTP request and retry transient failures without exceeding the budget. Trigger: F1.7.

1. F2.1 · K3: set budget = `options.timeoutMs` or 120000 ms; endsAt = now + budget | condition: always | data: timeoutMs | ref: X22, X20
2. F2.2 · K3: if no time left → throw `GeminiTimeoutError` → back to F1.8c | condition: left ≤ 0 | ref: X22
3. F2.3 · K3: arm a deadline for what is left, linked to the caller's signal | condition: always | data: deadline signal | ref: X22, gemini.ts:251-286
4. F2.4 · K3 → Gemini: `POST {base}/models/{model}:generateContent` with header `x-goog-api-key` | condition: always | data: request JSON, API key | ref: X22
5. F2.5 · Gemini → K3: 2xx → return response; body is read under the same deadline → back to F1.8 | condition: `resp.ok` | ref: X22, gemini.ts:424-433
   - F2.5a · if fetch throws because the deadline or the caller aborted → throw the abort reason, no retry → back to F1.8b (caller) or F1.8c (deadline) | ref: X22
   - F2.5b · if fetch throws with no response (network failure) and retries are allowed and attempts remain → continues at F2.7 with no status | ref: X22, X19
   - F2.5c · if network failure and no retry allowed or last attempt → throw → back to F1.8c | ref: X22
6. F2.6 · K3: non-2xx → read error body | condition: `!resp.ok` | data: status, body | ref: X22
   - F2.6a · if status not in [429, 500, 502, 503, 504] (for example 400, 401, 403) → throw `GeminiApiError` at once → back to F1.8c | ref: X22, X19
   - F2.6b · if this was the 3rd request → throw → back to F1.8c | ref: X22, X19
7. F2.7 · K3: wait = Retry-After header, else body `retryDelay`, else 3000 ms × attempt number; capped at 30000 ms | condition: retryable | ref: X21, X22, X23
8. F2.8 · K3: if now + wait ≥ endsAt → throw the last error, no sleep → back to F1.8c | condition: wait does not fit | ref: X23
9. F2.9 · K3: call `onRetry` hook (log), sleep the wait | condition: wait fits | ref: X23, tunatutor providers/gemini.ts:11-19
   - F2.9a · if the caller's signal fires during the sleep → reject → back to F1.8b | ref: X23, gemini.ts:229-242
10. F2.10 · K3: next request → continues at F2.2 | condition: after the sleep | ref: X22

### F3 · Level chat turn: two parallel calls and their degrade paths
Purpose: answer one learner reply with a score and a tutor line, never showing a model error. Trigger: the learner posts an answer in the level chat.

1. F3.1 · Use case → repo: if a turn with the same `turnId` is stored → return the stored reply, no model call → ends | condition: retried post | ref: X41
2. F3.2 · Use case: build candidate lines; decide `needsRater` (not degraded, stage not S4, a probe in play, non-empty text) | condition: answer, not a tap or silence | ref: X41
   - F3.2a · if the input is a "don't understand" tap or a silence → no model call; bank rephrase answers → continues at F3.9 | ref: X41
3. F3.3 · Route → gateway: rater call `callLLMJson` with model `gemini-2.5-flash-lite`, temperature 0.1, 500 tokens, `timeoutMs` 2000, `signal: AbortSignal.timeout(2000)`, context `{ userId, "onboarding_level_chat", levelChatId }` → runs F1 | condition: `needsRater` | ref: X40, X39, X41
4. F3.4 · Route → gateway: tutor call on `gemini-2.5-flash`, temperature 0.6, 700 tokens, 4000 ms, same signal pattern → runs F1, in parallel with F3.3 | condition: candidates exist | ref: X40, X39, X41
5. F3.5 · Use case: for each failed call, `rethrowIfUndegradable` | condition: a call failed | ref: X41, X45
   - F3.5a · if the error is `FST_MISSING_USAGE_CONTEXT` or `FST_DAILY_SPEND_CAP` → rethrow to the learner → ends | ref: X45
6. F3.6 · Use case: rater failed → facts = null; log "level chat: rater failed — no_data"; the turn is saved with no score | condition: rater failed | ref: X41, S1
7. F3.7 · Policy: facts null → `raterFailStreak` + 1 | condition: rater failed | ref: X43
   - F3.7a · if `raterFailStreak` ≥ 2 → `degraded = true`; from now on the code-only ladder scores answers and later turns make no rater call → continues at F3.9 | ref: X43, X44
   - F3.7b · if rater succeeded → `raterFailStreak` = 0 | ref: X43
8. F3.8 · Use case: tutor failed → the bank's pre-written line; `lineCheckFailed` = "timeout" or "error" | condition: tutor failed | ref: X42
   - F3.8a · if the tutor's line is missing or fails `checkTutorLine` → bank line → continues at F3.9 | ref: X42
9. F3.9 · Use case → repo: save state and turn in one transaction; return the reply | condition: always | ref: X41

### F4 · Settle and meter one attempt (tunatutor)
Purpose: turn one attempt into priced ledger rows and allowance debits without delaying the caller. Trigger: F1.9, F1.8b or F1.8c.

1. F4.1 · Gateway → K7: `meter.record(event, ctx)`, not awaited | condition: once per attempt | data: provider, usage, latency, isError, aborted | ref: X17, X18, X14
   - F4.1a · if the meter throws or rejects → log "LLM gateway: meter failed"; the call still returns → ends | ref: X17
2. F4.2 · K7: if `isError` or no usage → one zero-quantity row, key `<model>:text-input`, `isError: true` → continues at F4.4 | condition: failure or abort with no usage | ref: X26
3. F4.3 · K7: split usage: cached = min(cached, input); uncached = input − cached; output = output + thoughts | condition: usage present | ref: X26
4. F4.4 · K7 → K9: `recordProviderUsageEvent` per non-zero line (detached write) | condition: per line | data: metering context, key, quantity, latency, isError | ref: X32, X26
5. F4.5 · K9: price the line at write time from the active price row; no row → $0 and `is_estimated` | condition: quantity > 0 | ref: X31, X32
   - F4.5a · if the price lookup fails → $0, `is_estimated`, `priceLookupFailed` in metadata | ref: X31
6. F4.6 · K7 → K8: `settleLlmSpend` per line → `recordAndConsumeProviderUsage` with `recordEvent: false`, fire-and-forget | condition: user context, not admin, tokens > 0 | ref: X27
   - F4.6a · if system or admin context → no debit | ref: X27
   - F4.6b · if the debit fails → log, swallow; the ledger row stays | ref: X27
7. F4.7 · Owner → K10: report = GROUP BY feature, user or model | condition: on demand | ref: S1, X57

### F4S · Settle and meter one attempt (shared meter: Billpod, Mealy)
Purpose: the same as F4 for apps on `createAppLlm`. Trigger: F1.9, F1.8b or F1.8c.

1. F4S.1 · Gateway → K12: `record(event, ctx)` starts a detached write and tracks it for `flush()` | ref: X30
2. F4S.2 · K12: if `isError` or no usage → one zero-quantity row; an error keeps `isError: true`, an abort without usage gets `incomplete` and `aborted` in metadata and `isError: false` | ref: X30
3. F4S.3 · K12: otherwise write uncached-input, cached-input and output lines, priced by K9 | ref: X30, X31
4. F4S.4 · K12: if a `debit` is configured and the context is a person's own → debit each priced line | condition: not system, not admin | ref: X30

### F5 · Streamed call
Purpose: stream text deltas to the consumer, with fallback only before the first event. Trigger: `stream` or `streamWithTools`.

1. F5.1 · Gateway: check usage context on the first read (the method is a generator) | ref: X2 file, gateway.ts:507-509
2. F5.2 · Gateway: build candidates as F1.3-F1.4 | ref: X48
3. F5.3 · Gateway → K3: open the stream; retries and the budget apply until it opens, then the budget becomes the idle window between chunks | ref: X19, gemini.ts:459-521
4. F5.4 · Gateway → consumer: forward each event; remember the latest reported usage | ref: X48
5. F5.5 · Gateway: on `done` → settle success, `switched(i)` | ref: X48
   - F5.5a · if the stream ends with no finish reason → `GeminiStreamError` → as F5.6 | ref: X49
6. F5.6 · Gateway: on failure before any event reached the consumer → `fail()` → continues at F5.3 with the next candidate | ref: X48
   - F5.6a · if a failure comes after events reached the consumer → `fail()` and rethrow, no fallback → ends | ref: X48
   - F5.6b · if the caller's signal fired → `abandoned()` with usage so far → rethrow → ends | ref: X48
   - F5.6c · if the consumer stops reading → `finally` settles aborted with usage so far → ends | ref: X48

### F6 · Structured call after the provider answers (callJson)
Purpose: turn a JSON answer into typed data without hiding spend or cut-offs. Trigger: `callJson` after F1 returns.

1. F6.1 · Gateway: options get temperature 0.2 (unless set), `json: true`, response schema from zod | ref: X46
2. F6.2 · Gateway: run F1; spend is settled inside F1 | ref: X46
3. F6.3 · Gateway → K19: classify finish | ref: X46, X47
   - F6.3a · if `blocked` → throw `LlmOutputError` "LLM answer was blocked" → ends | ref: X46
4. F6.4 · Gateway: parse and validate with the zod schema → return `{ data, result }` | ref: X46
   - F6.4a · if parsing fails and the stop was not `end_turn` (for example MAX_TOKENS) → throw `LlmOutputError` naming the finish reason → ends | ref: X46, S1
   - F6.4b · if parsing fails on a complete answer → throw the `LlmOutputError` → ends | ref: X46

### F7 · Owner changes model configuration
Purpose: change which models run and in what order. Trigger: the owner uses the admin LLM settings.

1. F7.1 · Owner → K15: `PUT /llm/active-provider { providerId }` | ref: X37
   - F7.1a · if the model lacks a price row → refuse with `ValidationError` naming the keys → ends | ref: X36, X37
2. F7.2 · K15 → K4: `setActiveProvider` → in-memory and persisted to `llm.activeProvider` | ref: X13 file, registry.ts:185-197
3. F7.3 · Owner → K15: `PATCH /llm/providers/:id/config { enabled?, priority? }` | ref: X37
   - F7.3a · if enabling an unpriced model → refuse → ends | ref: X37
4. F7.4 · K15 → K4: `updateModelConfig` → database and in-memory config | ref: X38
   - F7.4a · if the active model was disabled → first enabled model becomes active and is persisted; if none, active = null | ref: X38
5. F7.5 · K1: the next call re-reads the provider list, so the change applies at once | ref: X14

### F8 · App start: build the models
Purpose: read the key and load model config. Trigger: tunatutor boots (`initLLMRegistry`).

1. F8.1 · K4 → environment: read `GEMINI_API_KEY` | ref: X11
   - F8.1a · if no key → no providers are built; calls fail with "No LLM provider available" | ref: X11, registry.ts:103-108
2. F8.2 · K4: build one `GeminiProvider` per model in `TUNATUTOR_LLM_MODELS` | ref: X11, X12
3. F8.3 · K4 → DB: upsert each model's config; new rows enabled, Flash priority 1, others 100 | ref: X11
   - F8.3a · if the DB is unavailable → all models enabled, priority 100 | ref: registry.ts:59-65
4. F8.4 · K4 → DB: seed `llm.activeProvider` = Flash if missing | ref: X11
5. F8.5 · K4: load the active model; if missing or disabled → first enabled by priority, persisted | ref: X11

### F9 · Daily spend cap at the activity door
Purpose: stop a learner over the daily cap from starting new activities without cutting off a running one. Trigger: an activity-entry route (session create, drill-arc start, help request, "Drill Me" start, document ingest).

1. F9.1 · Route `preHandler` → K16: sum the learner's provider spend for the UTC day | ref: X29
2. F9.2 · K16: under the cap → allow; the activity's model calls run uncapped | ref: X29, X28
   - F9.2a · if over the cap → refuse with `FST_DAILY_SPEND_CAP` → ends | ref: X29, X45
   - F9.2b · if the route is unauthenticated → skipped | ref: X29

### F10 · Request through a mature proxy gateway
Purpose: let many teams call many providers through one shared service. Trigger: an application sends a model request to the proxy.

1. F10.1 · App → K21: `POST /v1/chat/completions` in OpenAI format with a virtual key (path unverified) | data: model name, messages | ref: S1, S3, S7
2. F10.2 · K21 → K22: check the virtual key, its budget and rate limit | ref: S1, S4
3. F10.3 · K21: translate the request for whichever provider sits behind the model name | ref: S1
4. F10.4 · K21 → provider: call with the real provider key, retry | ref: S1, S4
   - F10.4a · if the provider fails → next entry in the fallback chain, across providers or regions | ref: S1, S4
5. F10.5 · K21: record spend per key, team and tag | ref: S1, S4

### F11 · The gateway's place in one user request
Purpose: show which blocks run before and after the gateway. Trigger: a user request to an LLM feature.

1. F11.1 · Edge and controller: auth; tenant and entitlements resolved and carried downstream, because retrieval and tools must enforce them | ref: S4
2. F11.2 · Input guardrails (block guardrails): PII redaction, an injection or moderation classifier, topical scope | ref: S4
   - F11.2a · if a guardrail trips → canned reply → ends | ref: S4
3. F11.3 · Cache check (block caching): exact or semantic, scoped per tenant | ref: S4
   - F11.3a · if the cache hits → return at once → ends | ref: S4
4. F11.4 · Router: a cheap classifier picks the workflow and model tier (C50) | ref: S4
5. F11.5 · Context assembly (blocks prompts, context, memory, rag, tools) | ref: S4
6. F11.6 · Gateway, then model: virtual key, budget and rate limit, then fallback and retry, then the provider (this block); the call uses structured output or strict tool schemas | ref: S4
7. F11.7 · Agent or workflow loop (blocks agents, tools, sandbox, hitl) | ref: S4
8. F11.8 · Output handling (blocks structured, guardrails) | ref: S4
9. F11.9 · Response and memory write-back; memory is written asynchronously through a queue | ref: S4
10. F11.10 · Across every step: tracing with OTel GenAI spans per model, tool and agent step, carrying tokens, cost, prompt version and model version (the trace is also the audit log); online evals on sampled traces; user feedback on the trace ID; failures flow into offline eval datasets that gate the next prompt or model change in CI | ref: S4

## States

### L1 · Gateway call
- States:
  - received: the request reached the gateway.
  - refused: the usage context was invalid; no provider was called.
  - trying(i): candidate i is being attempted.
  - succeeded: a candidate returned a result.
  - aborted: the caller gave up; no fallback.
  - exhausted: every candidate failed.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| received | context check | context invalid | refused | throw `MissingUsageContextError` | X4 |
| received | context check | valid, candidates exist | trying(0) | observe.onRequest | X8, X16 |
| received | build candidates | no provider | refused | throw "No LLM provider available" | X8 |
| trying(i) | provider lacks method | none | trying(i+1) | no settle | X16 |
| trying(i) | provider returns | none | succeeded | settle success; if i > 0 onSwitch | X16, X15 |
| trying(i) | provider throws | caller signal fired | aborted | settle aborted; rethrow | X16 |
| trying(i) | provider throws | not aborted, more candidates | trying(i+1) | settle error; onError | X16 |
| trying(i) | provider throws | not aborted, last candidate | exhausted | settle error; throw "All LLM providers failed" | X16 |

### L2 · Provider attempt (HTTP retry loop)
- States:
  - requesting(n): HTTP request n of at most 3 is in flight.
  - waiting: sleeping before the next request.
  - ok: a 2xx response arrived.
  - gave-up: thrown to the gateway as a failure.
  - timed-out: the budget ran out.
  - cancelled: the caller's signal fired.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| requesting(n) | 2xx | none | ok | return response | X22 |
| requesting(n) | 429/500/502/503/504 or network failure | n < 3 and wait fits budget | waiting | onRetry log | X22, X23 |
| requesting(n) | 429/5xx or network failure | n = 3, or wait does not fit | gave-up | throw last error | X22, X23 |
| requesting(n) | other status (400, 401, 403 …) | none | gave-up | throw `GeminiApiError` | X22 |
| requesting(n) | deadline fires | none | timed-out | throw `GeminiTimeoutError` | X22 |
| requesting(n) | caller signal fires | none | cancelled | throw abort reason | X22 |
| waiting | wait elapsed | none | requesting(n+1) | new request | X22 |
| waiting | caller signal fires | none | cancelled | reject | X23 |

### L3 · tunatutor active model
- States:
  - none: no provider (no key, or all disabled).
  - active(M) persisted: M is in memory and in `llm.activeProvider`.
  - active(M) in memory only: a sticky switch moved the in-memory value away from the stored one.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| none | boot with key, fresh DB | Flash built | active(Flash) persisted | seed `llm.activeProvider` | X11 |
| boot | stored active missing or disabled | enabled models exist | active(first enabled) persisted | upsert setting | X11 |
| active(M) persisted | fallback F wins any call | fallback on | active(F) in memory only | log "LLM sticky switch" | X13, X14, X15 |
| active(F) in memory only | server restart | none | active(stored) persisted | stored value reloaded | X11, S1 |
| any | owner sets active model | model priced | active(M) persisted | database write | X37, X13 file |
| active(M) | owner disables M | other enabled exists | active(first enabled) persisted | `setActiveProvider` | X38 |
| active(M) | owner disables M | none enabled | none | warn log | X38 |

### L4 · Level chat rater mode
- States:
  - normal(streak 0): the rater scores answers.
  - normal(streak 1): one rater failure in a row.
  - degraded: the code-only ladder scores answers; no rater calls.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| normal(0) | rater fails | none | normal(1) | turn saved with no score | X43, X41 |
| normal(1) | rater succeeds | none | normal(0) | streak reset | X43 |
| normal(1) | rater fails | none | degraded | code scorer; result shown as the tutor's "guess" | X43, X44 |
| degraded | any answer | none | degraded | `needsRater` false | X41, X43 |

### L5 · Ledger row
- States:
  - priced: quantity > 0 with an active price row; cost computed at write time.
  - estimated: quantity > 0 and no price row or a failed lookup; $0, `is_estimated`.
  - error marker: zero quantity, `is_error = true`.
  - aborted marker (shared meter): zero or partial quantity, `aborted` in metadata, `is_error = false`.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| (new line) | write | quantity > 0, price found | priced | `price_config_id` set | X31 |
| (new line) | write | quantity > 0, no price or lookup failed | estimated | warn log | X31 |
| (new line) | write | failed attempt | error marker | none | X26, X30 |
| (new line) | write (tunatutor) | aborted, no usage | error marker | counted as an error | X26 |
| (new line) | write (shared meter) | aborted | aborted marker | `incomplete` if no usage | X30 |

### L6 · Stream attempt
- States:
  - opening: retries and the budget apply.
  - streaming(not yielded): open, nothing forwarded yet.
  - streaming(yielded): at least one event forwarded.
  - done: final event arrived; settled success.
  - failed-fallback: failed before any event; next candidate.
  - failed-final: failed after events; rethrown.
  - abandoned: caller aborted or stopped reading; settled aborted.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| opening | stream opens | none | streaming(not yielded) | budget becomes the idle window | X19 |
| streaming(not yielded) | first event | none | streaming(yielded) | forwarded | X48 |
| streaming(*) | done event | none | done | settle; switched | X48 |
| streaming(not yielded) | error | not aborted | failed-fallback | settle error | X48 |
| streaming(yielded) | error | not aborted | failed-final | settle error; rethrow | X48 |
| streaming(*) | caller signal or stop reading | none | abandoned | settle aborted with usage so far | X48 |

### L7 · Price row
- States:
  - seeded: inserted on boot when the key was missing.
  - active: `is_active` and inside its effective window.
  - superseded: a newer effective row or `effective_to` passed.
- Transitions:

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| (missing) | boot seed | key missing | seeded/active | insert | X35 |
| active | owner edits on Provider Costs | none | active (new values) | applies to rows written after it, after cache expiry (up to 5 min) | X35, X33, S1 |
| active | `effective_to` passes or replaced | none | superseded | lookups use the newer row | X34 file, provider-costs.ts:41-54 |

## Worked examples

### E1 · Cost of one rater call on Flash Lite versus Flash
- Values: real prices [X35, S1], made-up token counts [S1].
- Inputs: 1,200 input tokens, 150 output tokens, from `"usageMetadata": { "promptTokenCount": 1200, "candidatesTokenCount": 150 }` (made up).
- Steps:
  - F4.3: no cached or thinking tokens, so uncached input = 1,200, output = 150.
  - F4.5 on Flash Lite: 1,200 × $0.10/1M = $0.00012; 150 × $0.40/1M = $0.00006; total $0.00018.
  - F4.5 on Flash: 1,200 × $0.30/1M = $0.00036; 150 × $2.50/1M = $0.000375; total $0.000735.
- Outcome: the bigger model costs about four times as much for the same request (0.000735 ÷ 0.00018 ≈ 4.08) [S1].
- In micros, as Lomem stores them: Flash Lite 120 + 60 = 180 micros; Flash 360 + 375 = 735 micros (derived from X32's formula).

### E2 · A large document re-sent many times a day
- Values: real price, made-up volume [S1].
- Inputs: a 50,000-token document sent to Flash 10,000 times a day.
- Steps: 50,000 × 10,000 × $0.30/1M.
- Outcome: $150 a day on input alone [S1].

### E3 · One rater call when Flash Lite is down (503)
- Values: made-up timeline [S1]; behaviour confirmed by running the real `createLlmGateway` and `GeminiProvider` with a mocked `fetch` on 2026-10-15 [X16, X22, X23].
- Inputs: the owner has enabled Flash (priority 1, active) and Flash Lite (priority 2) (made up); the rater names Flash Lite; budget 2 s.
- Steps (source timeline):
  - F1.3-F1.4: t = 0 s, the list is [Flash Lite (named by the rater), Flash].
  - F2.6 → F2.7: Flash Lite answers 503; the first retry would wait 3 s.
  - F2.8: 3 s does not fit the 2 s budget, so the gateway gives up on Flash Lite.
  - F1.8c → F4.2: one error row with zero tokens.
  - F1.5-F1.7: t ≈ 0.2 s, the gateway calls Flash with a new 2 s budget.
  - F1.8: Flash answers at t ≈ 1.1 s with 1,200 input and 150 output tokens.
  - F1.9 → F4.5: the meter writes the success rows priced at Flash's rates: $0.000735 instead of $0.00018.
- Steps (simulation output, mocked Flash answering after 900 ms):
  - `1ms gemini-2.5-flash-lite:generateContent`, then `8ms gemini-2.5-flash:generateContent`; result `ok at 909 ms STOP`.
  - Spend events: `["gemini-2.5-flash-lite", isError true, aborted false, 0, 0]`, `["gemini-2.5-flash", isError false, aborted false, 1200, 150]`, then `["switch", "gemini-2.5-flash"]`.
- Outcome: the fallback quietly moved a cheap job onto a model four times as expensive; tunatutor accepts that because the outage is short and a missing rating is worse [S1].
- Outcome: the sticky switch fired although the rater named its model [X15, run].

### E4 · Spend rows for E3
- Values: made up [S1].

| user | feature | model | kind | tokens | error | cost |
|---|---|---|---|---|---|---|
| 42 | onboarding_level_chat | gemini-2.5-flash-lite | input | 0 | yes | $0 |
| 42 | onboarding_level_chat | gemini-2.5-flash | input | 1,200 | no | $0.00036 |
| 42 | onboarding_level_chat | gemini-2.5-flash | output | 150 | no | $0.000375 |

- Steps: F4.2 writes the first row; F4.3-F4.5 write the other two.
- Outcome: a GROUP BY feature gives $0.000735 for this turn's rater call.

### E5 · Usage context values
- Values: made up, except the feature name `onboarding_level_chat`, which is real [S1, S3, X40].
- User call: `{ userId: 42, feature: "onboarding_level_chat" }` passes F1.2.
- System call: `{ system: true, feature: "content_import", reason: "nightly lesson import" }` passes F1.2.
- Failing cases (F1.2a): no context; `feature: ""`; `{ system: true, feature: "x" }` with no reason; `userId: 0` or a non-integer [X4, X7].

### E6 · Worst-case wait
- Values: real defaults, made-up model count [S1].
- Inputs: default budget 120 s; three enabled models.
- Steps: F2 may use the full 120 s per model; F1.8c moves to the next model with a fresh budget.
- Outcome: 120 s × 3 = 6 minutes [S1].
- tunatutor has only two selectable models, so its ceiling for a call with no signal is 120 s × 2 = 4 minutes (derived from X12, X16).
- For the level chat rater with no route signal: 2 s × 2 models = 4 s; the source says the learner could wait up to 4 s for a rating [S1]. E7 shows the route's signal caps it at 2 s.

### E7 · Rater call when Flash Lite hangs (route signal present)
- Values: simulation with the real gateway and provider code and a mocked `fetch`, 2026-10-15 [X16, X22, X40].
- Inputs: Flash Lite never answers; Flash would answer in 900 ms; `timeoutMs: 2000`; `signal: AbortSignal.timeout(2000)` as the level chat route passes it.
- Steps:
  - F2.4: request to Flash Lite at 1 ms.
  - F2.5a: at 2000 ms the route's signal fires; the attempt is cancelled.
  - F1.8b: the gateway sees `signal.aborted` and settles the attempt as aborted; no fallback.
- Outcome: `threw at 2001 ms: TimeoutError The operation was aborted due to timeout`; spend events `[["gemini-2.5-flash-lite", false, true, 0, 0]]`; Flash was never called.
- In tunatutor the aborted event with no usage becomes a zero-token error row (F4.2) [X26].
- The rater result is `no_data` (F3.6).
- Control run with no route signal: Flash Lite timed out at 2 s (error row), Flash was called at 2002 ms with a fresh budget and succeeded at 2919 ms.

### E8 · 429 with Retry-After inside a 2 s budget
- Values: simulation of `GeminiProvider` with a mocked `fetch`, 2026-10-15 [X21, X22, X23].
- Inputs: two 429 responses with `Retry-After: 1`; budget 2000 ms.
- Steps: F2.6 → F2.7 wait 1000 ms (from the header) → F2.8 fits → F2.9 `onRetry attempt=0 wait=1000` → request 2 at 1008 ms → 429 again → F2.8 the next 1000 ms wait would end at about 2008 ms, past the budget → throw.
- Outcome: one retry on the same model, then `GeminiApiError 429` at 1009 ms; the rater would then fall back (F1.8c).

### E9 · 503 with the default 120 s budget
- Values: simulation, 2026-10-15 [X22, X23].
- Inputs: 503 responses with no Retry-After and no `retryDelay`.
- Steps: request 1 at 1 ms → wait 3000 ms → request 2 at 3009 ms → wait 6000 ms → request 3 at 9010 ms → third failure is the last attempt → throw.
- Outcome: `GeminiApiError 503` at 9010 ms; with a 200 on request 3 instead, `ok STOP at 9012ms`.
- Same 503 with a 2000 ms budget: request 1 at 0 ms, thrown at 7 ms with no retry, because the 3000 ms wait does not fit.

### E10 · 400 is never retried
- Values: simulation, 2026-10-15 [X22].
- Inputs: a 400 response; budget 120000 ms.
- Outcome: one request, `GeminiApiError 400` at 8 ms; no retry.

### E11 · A cut-off JSON answer
- Values: described, no concrete values [S1, X46].
- Inputs: a `callJson` request whose answer hits the output limit.
- Steps: F1 returns with finishReason MAX_TOKENS → F4 settles the tokens → F6.3 stop is `max_tokens` → F6.4a parsing fails.
- Outcome: `LlmOutputError` whose message names MAX_TOKENS; the spend is already recorded because the cut-off answer was still billed.

### E12 · Volume example that weakened the message
- Values: from testing; derived from E1's Flash price [testing].
- Inputs: 100,000 calls at $0.000735.
- Outcome: about $73; readers took the small total as evidence that cost does not matter [testing].

### E13 · Image generation cost
- Values: real, from the price seed comment [provider-prices.ts:105-135].
- Inputs: one 512 px image measured at 1,150 output tokens; image output price $60.00 per 1M tokens.
- Outcome: about $0.069 per image.

### E14 · The smallest version in Java (long draft, not Lomem code)
- Values: sketch from the long draft; the tested short version keeps only `call()` and returns `new LlmAnswer(r.text(), m)` without the finish reason [S1, S2].
- Code (verbatim from the long draft):
```java
public record UsageContext(Long userId, String feature, String systemReason) {
  void validate() {
    if (feature == null || (userId == null && systemReason == null))
      throw new MissingUsageContextException();
  }
}
static final Set<Integer> RETRYABLE = Set.of(429, 500, 502, 503, 504);
static final Duration MAX_WAIT = Duration.ofSeconds(30);
public LlmAnswer call(UsageContext ctx, String model, String prompt, Duration budget) {
  ctx.validate();                                    // 1. who pays, before any HTTP request
  for (String m : modelList(model)) {                // 2. named or default model, then fallbacks
    try {
      ProviderResponse r = postWithRetries(m, prompt, budget);   // 3. fresh budget per model
      spend.record(ctx, m, r.inputTokens(), r.outputTokens(), false);  // 5. one row per model
      return new LlmAnswer(r.text(), m, r.finishReason());
    } catch (ProviderException e) {                  // gave up on this model
      spend.record(ctx, m, 0, 0, true);              // 5. zero-token error row
    }                                                // 4. try the next model
  }
  throw new AllModelsFailedException();              // the caller must degrade
}
ProviderResponse postWithRetries(String m, String prompt, Duration budget) {
  Instant deadline = Instant.now().plus(budget);
  for (int attempt = 1; ; attempt++) {
    try {
      return post(m, prompt, apiKey, deadline);      // times out at the deadline
    } catch (ProviderHttpException e) {
      Duration wait = min(e.retryAfter().orElse(Duration.ofSeconds(3L * attempt)), MAX_WAIT);
      if (!RETRYABLE.contains(e.status()) || attempt == 3
          || Instant.now().plus(wait).isAfter(deadline)) throw e;
      sleep(wait);
    }
  }
}
```
- Steps: `validate()` is F1.2; `modelList` is F1.3-F1.4; `postWithRetries` is F2; the two `spend.record` calls are F1.9 and F1.8c; `AllModelsFailedException` is F1.12.
- Outcome: with a list of one model it is the minimal version (V1, V3) [S1].
- Gaps against Lomem: it catches only `ProviderException`, so a timeout or network error outside it is not recorded (M7); it has no caller-abort branch (C34); `UsageContext.validate()` does not reject a non-positive user id (X4) [testing, X4, X16].

## Variants and options

- Minimal version:
  - One class that every service must use [S1].
  - It reads the key from the secret store, and nothing else does [S1].
  - It requires a usage context on every call [S1].
  - It retries only 429 and the listed 5xx codes, with capped backoff inside a time budget [S1].
  - It records every attempt, timeouts and network errors included [S1, testing].
  - It lets the caller name a model, with a default [S1].
  - Research catalogue phrasing: one client wrapper, provider key in a vault, retry with backoff, token counts logged [S4].
  - In Lomem: Billpod and Mealy, built by `createAppLlm`: one model, no fallback, spend tagged with feature names [S1, X50, X51].
- Mature version:
  - A self-hosted proxy with one OpenAI-compatible endpoint [S4, S7].
  - Virtual keys per team, with budgets and rate limits [S1, S4, S7].
  - Fallback chains across providers or regions [S1, S4].
  - Spend recorded per key, team or tag [S1, S4].
  - Exact and semantic caching, PII redaction hooks, and an OTel export [S4].
  - A router that classifies requests and picks the model [S4].
  - In Lomem, tunatutor sits between: an admin-configured registry with fallback and a sticky switch, a ledger and allowance debit, but no proxy, no virtual keys, no router [X14, X24-X27].

| id | option | when to choose | cost / risk |
|---|---|---|---|
| V1 | In-process wrapper class (library gateway) | One app or a few services in one codebase | Each app runs its own meter; no cross-team keys [S1, X50] |
| V2 | Separate proxy service (LiteLLM and similar) | Many teams, many providers | Another service to run; requests use the OpenAI format [S1, S4] |
| V3 | Single model, no fallback | Small app; failures can show an error or be retried later | An outage stops the feature [X50] |
| V4 | Fallback list of enabled models | Availability matters more than cost or identical answers | Different answers and price; worst case budget × models [S1] |
| V5 | Sticky switch on fallback success | Avoid paying the failed model's timeout on every call during an outage | Old model never re-tested until restart or owner action; a named-model fallback also moves the default [S1, X15] |
| V6 | Real circuit breaker | Need automatic recovery to the primary model | More code; not in Lomem [S1] |
| V7 | Price each row at write time | Reports must reflect the price in force at the time of the call | A price edit does not reprice old rows [S1, X31] |
| V8 | Price at report time | Simpler meter | Old rows change when prices change; not what tunatutor does [testing] |
| V9 | Detached meter writes | Keep the user path fast | A crash can lose a few rows [S1, X17] |
| V10 | Usage rows through an outbox in the business transaction | Invoicing customers from the rows | More writes on the request path [S1] |
| V11 | Spend cap checked at activity entry | Must never cut a conversation mid-turn | A learner can overshoot the cap by one activity's tail [X29] |
| V12 | Spend check on every call | Hard ceiling matters more than conversations | Can end a turn halfway [S1, X28] |
| V13 | Per-call budget only (`timeoutMs`) | Background jobs; fallback should get full time | Worst case is budget × models [S1, X16] |
| V14 | Per-call budget plus an overall abort signal (level chat) | Interactive calls with a hard wait limit | A hang on the first model uses the whole time and no fallback runs [X40, E7] |
| V15 | Route cheap jobs to a small model | Narrow tasks such as scoring | Quality may drop; a fallback can undo the saving [S1] |

| name | open source or hosted | what it does here | link |
|---|---|---|---|
| LiteLLM | open source | Self-hosted proxy with one OpenAI-compatible endpoint, virtual keys, budgets, fallbacks, spend per key/team/tag | https://github.com/BerriAI/litellm and https://docs.litellm.ai/docs/simple_proxy |
| Portkey gateway | open source and hosted | AI gateway (features not detailed in the research) | https://github.com/Portkey-AI/gateway |
| Kong AI Gateway | product (license not stated in the research) | AI gateway on Kong (features not detailed in the research) | https://developer.konghq.com/ai-gateway/ |
| OpenRouter | hosted | Hosted router across providers (features not detailed in the research) | https://openrouter.ai/docs |
| LiteLLM caching | open source | Exact-match cache at the gateway (block caching) | https://docs.litellm.ai/docs/proxy/caching |
| Resilience4j | open source | Java analogy only: retry, time limiter, circuit breaker | (no link in the research) |

## Facts and numbers

| id | fact | value | source id | verified |
|---|---|---|---|---|
| N1 | Size of one token | about 3/4 of an English word | S1, S3 | unverified |
| N2 | Gemini 2.5 Flash input price | $0.30 per 1M tokens (300,000 micros) | S1, X35 | yes |
| N3 | Gemini 2.5 Flash output price (thinking included) | $2.50 per 1M tokens | S1, X35 | yes |
| N4 | Gemini 2.5 Flash cached input price | $0.03 per 1M tokens | X35 | yes |
| N5 | Gemini 2.5 Flash Lite input price | $0.10 per 1M tokens | S1, X35 | yes |
| N6 | Gemini 2.5 Flash Lite output price | $0.40 per 1M tokens | S1, X35 | yes |
| N7 | Gemini 2.5 Flash Lite cached input price | $0.01 per 1M tokens | X35 | yes |
| N8 | Gemini 3.5 Flash prices (input / cached / output) | $1.50 / $0.15 / $9.00 per 1M tokens | provider-prices.ts:75-104 | yes (code) |
| N9 | Gemini 3.1 Flash Image prices (input / cached / image output) | $0.50 / $0.50 (no cached rate listed) / $60.00 per 1M tokens | provider-prices.ts:105-135 | yes (code) |
| N10 | One 512 px image | 1,150 tokens, about $0.069 | provider-prices.ts:134 | yes (code) |
| N11 | Date the 2.5 prices were read | 2026-10-03 (3.5 Flash 2026-09-27; image 2026-10-10) | X35 | yes (code comment) |
| N12 | Rater model, budget, output limit, temperature | gemini-2.5-flash-lite, 2 s, 500 tokens, 0.1 | S1, X39 | yes |
| N13 | Tutor model, budget, output limit, temperature | gemini-2.5-flash, 4 s, 700 tokens, 0.6 | S1, X39 | yes |
| N14 | Default time budget | 120 s (120,000 ms) | S1, X19, X20 | yes |
| N15 | Maximum HTTP requests per attempt | 3 | S1, X19 | yes |
| N16 | Backoff waits | 3 s, then 6 s (3000 ms × attempt) | S1, X23, E9 | yes (run) |
| N17 | Cap on any single wait | 30 s | S1, X19 | yes |
| N18 | Retried statuses | 429, 500, 502, 503, 504 | S1, X19 | yes |
| N19 | Worst-case wait, 120 s × 3 models | 6 minutes | S1 | yes (arithmetic; model count made up) |
| N20 | tunatutor selectable models | 2 | X12 | yes |
| N21 | Rater call cost on Flash Lite (made-up tokens) | $0.00018 | S1 | yes (arithmetic) |
| N22 | Same call on Flash | $0.000735 | S1 | yes (arithmetic) |
| N23 | Flash versus Flash Lite cost ratio for that call | about 4× (4.08) | S1 | yes (arithmetic) |
| N24 | 50,000-token document × 10,000 calls a day on Flash | $150 a day, input only | S1 | yes (arithmetic) |
| N25 | 100,000 calls at Flash's rater-call price | about $73 | testing | yes (arithmetic) |
| N26 | Rater failures in a row before degraded mode | 2 | S1, X43 | yes |
| N27 | Default priority for Flash on a fresh DB / other models | 1 / 100 | X11 | yes |
| N28 | Price cache: found / miss | 5 min / 30 s | X33, X57 | yes |
| N29 | `callJson` default temperature | 0.2 | X46 | yes |
| N30 | `GeminiProvider` default temperature | 0.8 | X24 | yes |
| N31 | Tool-call default output limit | 2048 tokens | X2 | yes |
| N32 | Image call output limit; measured image answer | 8192; about 1,100-1,500 tokens (2026-10-10) | gateway.ts:207-208 | yes (code comment) |
| N33 | `MissingUsageContextError` code and HTTP status | `FST_MISSING_USAGE_CONTEXT`, 500 | X5 | yes |
| N34 | Billpod feature labels | 4 (capture, assistant, paperwork, avatar) | S5, X51 | yes |
| N35 | Call sites converging on tunatutor's one LLM settle site | about 90 | X58 | yes (code comment) |
| N36 | Shared default model for apps on `createAppLlm` | gemini-3.5-flash | X50 | yes |
| N37 | Gemini API base | https://generativelanguage.googleapis.com/v1beta | gemini.ts:23 | yes |
| N38 | Ledger rows per successful attempt | up to 3 (input, cached input, output) | X26, X30 | yes |
| N39 | Ledger rows per failed attempt | 1, zero tokens | S1, X26 | yes |
| N40 | Chip Huyen article date | 25 Jul 2024 | S4, S6 | yes |
| N41 | OWASP risk for cost and DoS | LLM10:2025 Unbounded Consumption | S4, S12 | yes |
| N42 | Fowler/Subramaniam catalogue | 9 patterns, 28 Jan to 25 Feb 2025, nothing on gateways | S4, S13 | yes |
| N43 | Level chat budgets range | 2 to 4 s | S1 | yes |
| N44 | Simulated rater fallback (E3) | Flash Lite gave up at about 7 ms; Flash answered; done at 909 ms | X16, X22 | yes (run) |
| N45 | Simulated hang with route signal (E7) | thrown at 2001 ms, no fallback | X16, X40 | yes (run) |
| N46 | Lomem gateway source range cited by the long draft | gateway.ts lines 229-344 (`candidates()` to the start of `call()`) | S1, S3 | yes |
| N47 | Newcomer reader scores, round 1 (clarity, self-contained, examples) | senior 8, 6, 8; skimmer 6, 5, 7; both failed | testing | yes |
| N48 | Newcomer reader scores, round 2 | senior 8, 7, 9; skimmer 7, 7, 8; both failed | testing | yes |
| N49 | Newcomer reader scores, round 3 | senior 7, 8, 9; skimmer 7, 7, 9; both failed | testing | yes |
| N50 | Envoy AI Gateway | not cited: `aigateway.envoyproxy.io` redirects to an unrelated domain | S4 | yes (as reported) |
| N51 | Lomem's `createPromptClient` defaults | 2048 output tokens, temperature 0.2, thinking "low" | X50 | yes |

## Code in Lomem

### X1 · The gateway's job list and its injected ports

- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:1-14` (Lomem main branch as read on 2026-10-15)
- Implements: C15, C40, K1

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
  - The header lists what the gateway owns: refuse an unattributed call, pick the provider, fall back, settle spend once per provider attempt.
  - Everything app-specific is a port passed in: `providers`, `resolveModel`, `fallback.onSwitch`, `meter.record`, `onError`, `observe`.
  - "Ports" is the hexagonal-architecture word for an interface the host supplies; in Spring terms, beans injected into the gateway.

### X2 · The gateway's public operations and request shape

- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:32, 133-153, 181-205, 543` (Lomem main branch as read on 2026-10-15)
- Implements: C15, C25, C51

```ts
export type LlmOperation = "call" | "json" | "tools" | "stream" | "image";
...
interface BaseRequest {
  systemPrompt: string;
  messages: LLMMessage[];
  /** Provider options (temperature, JSON, thinking, timeout, signal). */
  options?: LLMOptions;
  /** Who pays. Required: a call without it throws `MissingUsageContextError`. */
  context: LlmUsageContext;
  /** Names the caller in the refusal message (default: the gateway method). */
  caller?: string;
  /**
   * An optional per-call model id ("gemini-2.5-flash-lite"), handed to
   * `resolveModel`. Without `resolveModel`, or when the app does not honour
   * it, the call leads with the app's usual provider. The fallback chain is
   * unchanged: the rest of `providers`, in order.
   */
  model?: string;
}

export interface LlmCallRequest extends BaseRequest {
  maxTokens: number;
}
...
export interface LlmGateway {
  call(req: LlmCallRequest): Promise<LLMChatResult>;
  callJson<S extends z.ZodTypeAny>(req: LlmJsonRequest<S>): Promise<LlmJsonResult<z.output<S>>>;
  callWithTools(req: LlmToolsRequest): Promise<LLMResultWithTools>;
  /**
   * A picture from an image model. Metered like every call, in tokens on the
   * provider's own keys (an image model is its own provider, so its output key
   * carries the image price). An answer with no picture is an `LlmOutputError`
   * after the spend is settled — a refused picture still cost money.
   */
  callImage(req: LlmImageRequest): Promise<LlmImageResult>;
  /**
   * Text deltas as they arrive, then one `done` with the whole text and usage.
   * Falls back to the next provider only while nothing has been yielded yet.
   * Spend is settled when the stream ends, fails, or the consumer stops early.
   */
  stream(req: LlmCallRequest): AsyncGenerator<LLMStreamEvent>;
  /**
   * A tool-use turn, streamed: text deltas as they arrive, then one `done`
   * carrying the whole turn (text, tool calls with their signatures, stop
   * reason, usage). Same fallback and settle rules as `stream`; spend is
   * recorded as a `tools` operation.
   */
  streamWithTools(req: LlmToolsRequest): AsyncGenerator<LLMToolStreamEvent>;
}
...
  return { call, callJson, callWithTools, callImage, stream, streamWithTools };
```

- Notes:
  - Six operations: `call`, `callJson`, `callWithTools`, `callImage`, `stream`, `streamWithTools` (line 543).
  - `context` is required on every request type through `BaseRequest`.
  - `model` is an optional per-call model id; the fallback chain stays the same whether or not it is given.
  - `maxTokens` is required for `call`, `callJson` and `stream`; tool calls default to 2048.

### X3 · The usage context types: user or system

- File: `~/projects/lomem/packages/shared/src/llm/gateway/context.ts:1-48` (Lomem main branch as read on 2026-10-15)
- Implements: C16, C17, C18, C19

```ts
// Who pays for an LLM call (ADR-057 §5).
//
// Every gateway call carries one of these. A call without it is provider money
// that never reaches `provider_usage_events` — invisible to allowances, spend
// guardrails and per-feature cost reports — so the gateway REFUSES it
// (`MissingUsageContextError`) instead of running it unmetered.
import { MissingUsageContextError } from "../../errors/domain-errors.js";

/** A real person is behind the call (the normal case). */
export interface LlmUserUsageContext {
  /** The user this spend is attributed to. */
  userId: number;
  /**
   * The feature the spend belongs to, written as `conversation_type` on the
   * usage row so cost can be queried per feature (Billpod `capture`,
   * `assistant`; tunatutor's session labels).
   */
  feature: string;
  /** Where the call came from inside the feature (e.g. `app`, `mcp`), kept in the row's metadata. */
  surface?: string;
  /** Session / run id when there is one — carried onto the usage row. */
  sessionId?: string | null;
  /**
   * `admin`: an admin's own tooling call. The row keeps the admin's user id
   * (so account erasure still covers it, ADR-037) with `actor_kind = 'admin'`,
   * is never debited from an allowance, and stays out of per-user rankings.
   */
  actor?: "admin";
}

/**
 * A deliberately un-attributed call (cron, startup, content scripts, admin
 * jobs with no person to bill). It must say why: the row is written with no
 * user, `actor_kind = 'system'` and the reason as its `system_reason`.
 */
export interface LlmSystemUsageContext {
  system: true;
  feature: string;
  surface?: string;
  sessionId?: string | null;
  reason: string;
}

export type LlmUsageContext = LlmUserUsageContext | LlmSystemUsageContext;

export function isSystemLlmContext(ctx: LlmUsageContext): ctx is LlmSystemUsageContext {
  return "system" in ctx && ctx.system === true;
}
```

- Notes:
  - A user context carries `userId` and `feature`; `surface`, `sessionId` and `actor` are optional.
  - A system context carries `system: true`, `feature` and a required `reason`.
  - `feature` is written as `conversation_type` on the usage row.
  - `actor: "admin"` keeps the admin's user id, marks the row admin and is never debited.

### X4 · The runtime check that refuses an unattributed call

- File: `~/projects/lomem/packages/shared/src/llm/gateway/context.ts:50-66` (Lomem main branch as read on 2026-10-15)
- Implements: C16, F1.2, F1.2a, L1

```ts
/**
 * The runtime backstop: TypeScript makes a missing context unreachable, this
 * catches the shapes it cannot police (an untyped caller, a cast), so it must
 * survive `undefined` itself.
 */
export function assertLlmUsageContext(ctx: LlmUsageContext | undefined, where: string): LlmUsageContext {
  if (!ctx) throw new MissingUsageContextError(where);
  if (!ctx.feature) throw new MissingUsageContextError(`${where}: usage context feature is empty`);
  if (isSystemLlmContext(ctx)) {
    if (!ctx.reason) throw new MissingUsageContextError(`${where}: system usage context needs a reason`);
    return ctx;
  }
  if (!Number.isInteger(ctx.userId) || ctx.userId <= 0) {
    throw new MissingUsageContextError(`${where}: usage context userId is not a real user id`);
  }
  return ctx;
}
```

- Notes:
  - Four refusals: no context, empty `feature`, a system context with no `reason`, a `userId` that is not a positive integer.
  - The comment says TypeScript already makes a missing context unreachable; this is the runtime backstop for untyped callers and casts.

### X5 · The error the refusal throws

- File: `~/projects/lomem/packages/shared/src/errors/domain-errors.ts:88-92` (Lomem main branch as read on 2026-10-15)
- Implements: C16, C37, F1.2a

```ts
export const MissingUsageContextError = createError(
  "FST_MISSING_USAGE_CONTEXT",
  "LLM call refused: no usage context supplied (%s). Every provider call must be attributable.",
  500,
);
```

- Notes:
  - Error code `FST_MISSING_USAGE_CONTEXT`, HTTP status 500.
  - The message ends "Every provider call must be attributable."

### X6 · tunatutor's own usage context type

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/types.ts:4-20, 38-45` (Lomem main branch as read on 2026-10-15)
- Implements: C16, C18

```ts
/**
 * Who pays for an LLM call.
 *
 * This is REQUIRED on every call (see `LLMOptions` below). An un-attributed
 * provider call is money we spend and can never see — the free-tier cap, the
 * daily spend guardrails and the per-surface cost reports all read
 * `provider_usage_events`, and a call without a context never lands there.
 * `callLLM` therefore REFUSES to run rather than silently skipping metering.
 *
 * Two shapes, both explicit:
 *  - {@link LLMUserUsageContext} — a real learner is behind the call (normal case)
 *  - {@link LLMSystemUsageContext} — an admin/system path with genuinely no
 *    learner to bill. Must state a `reason`, so the exemption stays auditable
 *    and greppable instead of decaying back into "context was optional". Its
 *    spend is still recorded: a row with no user, `actor_kind = 'system'` and
 *    the reason as `system_reason` (ADR-057 §5). It is never debited.
 */
...
export interface LLMSystemUsageContext {
  /** Discriminant — marks a deliberately un-attributed (system) call. */
  system: true;
  sessionId?: string | null;
  conversationType: string;
  /** Why no learner can be attributed. Required: keeps the exemption honest. */
  reason: string;
}
```

- Notes:
  - tunatutor calls the feature `conversationType`; `toGatewayContext` in services/llm/index.ts maps it to the gateway's `feature`.
  - The comment names three readers of `provider_usage_events`: the free-tier cap, the daily spend guardrails and the per-surface cost reports.

### X7 · The test that pins the refusal

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/__tests__/usage-context-required.test.ts:1-4, 79, 93, 107, 121, 135, 147, 158, 176, 196` (Lomem main branch as read on 2026-10-15)
- Implements: C16, C39, F1.2a

```ts
// A provider call without a usage context is money we spend and can never see.
// The type system makes it unreachable from TypeScript; this pins the RUNTIME
// backstop — the call must FAIL loudly, never fall through to the provider with
// metering quietly skipped (the old behavior that hid the un-metered surfaces).
...
test("callLLM refuses a call with NO usage context — and never reaches the provider", async () => {
...
test("callLLM refuses a usage context with no real userId", async () => {
...
test("callLLM refuses a usage context with an empty conversationType (surface must be queryable)", async () => {
...
test("callLLM refuses a system context that does not say WHY it is un-attributed", async () => {
...
test("callLLMWithTools applies the same refusal", async () => {
...
test("a valid user context runs and lands on the ledger with its surface label", async () => {
...
test("a system context runs and lands on the ledger as a system row: no user, its reason", async () => {
...
test("an admin context keeps the admin's user id and is marked admin", async () => {
...
test("callLLM does NOT consult the daily spend cap — it can never evict a turn in progress", async () => {
```

- Notes:
  - The header is the quoted rule: "the call must FAIL loudly, never fall through to the provider with metering quietly skipped".
  - The last test pins that `callLLM` does not consult the daily spend cap.

### X8 · Building the candidate list: lead model first, then every other enabled model

- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:228-238` (Lomem main branch as read on 2026-10-15)
- Implements: C25, C26, C27, F1.3, F1.4

```ts
  /** Leading provider first, then (with fallback on) the rest in priority order. */
  function candidates(operation: LlmOperation, context: LlmUsageContext, model?: string): LLMProvider[] {
    const lead = config.resolveModel
      ? config.resolveModel({ operation, context, ...(model ? { model } : {}) })
      : undefined;
    const all = listProviders();
    const first = lead ?? all[0];
    if (!first) throw new Error("No LLM provider available");
    if (config.fallback === false) return [first];
    return [first, ...all.filter((p) => p.id !== first.id)];
  }
```

- Notes:
  - `lead` comes from the app's `resolveModel`; without it the first provider leads.
  - With `fallback: false` the list has one entry (Billpod, Mealy).
  - Otherwise the list is the lead plus every other provider in `providers` order, so a named model still has fallbacks.
  - An empty provider list throws "No LLM provider available".

### X9 · tunatutor picks the lead model

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/index.ts:254-266` (Lomem main branch as read on 2026-10-15)
- Implements: C24, C25, F1.3b

```ts
/**
 * The provider that leads a call: the caller's per-call model when it names an
 * ENABLED provider (the level chat's rater pins Flash-Lite), otherwise the
 * admin-chosen active one. A disabled or unknown model id never errors — the
 * call just runs on the active model.
 */
export function resolveLeadProvider(model: string | undefined) {
  if (model) {
    const pinned = getEnabledProviders().find((p) => p.id === model);
    if (pinned) return pinned;
  }
  return getActiveProvider();
}
```

- Notes:
  - A named model leads only when it is enabled; an unknown or disabled id silently falls through to the active model.
  - The comment names the level chat's rater as the caller that pins Flash-Lite.

### X10 · tunatutor's enabled models in priority order

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/registry.ts:114-127` (Lomem main branch as read on 2026-10-15)
- Implements: C24, C26, F1.4

```ts
/** Returns enabled providers sorted by priority (ascending — lower number = higher priority). */
export function getEnabledProviders(): LLMProvider[] {
  return Array.from(providers.entries())
    .filter(([key]) => {
      const cfg = modelConfigs.get(key);
      return cfg?.enabled !== false;
    })
    .sort(([a], [b]) => {
      const pa = modelConfigs.get(a)?.priority ?? 100;
      const pb = modelConfigs.get(b)?.priority ?? 100;
      return pa - pb;
    })
    .map(([, provider]) => provider);
}
```

- Notes:
  - Lower priority number means earlier in the list.
  - A model with no stored config counts as enabled with priority 100.

### X11 · Registry start-up: the key is read, models are built, defaults are seeded

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/registry.ts:15-50, 80-98` (Lomem main branch as read on 2026-10-15)
- Implements: C4, C24, F8

```ts
export async function initLLMRegistry(): Promise<void> {
  const geminiKey = process.env.GEMINI_API_KEY;
  if (geminiKey) {
    for (const m of TUNATUTOR_LLM_MODELS) providers.set(m.id, createTunatutorGeminiProvider(geminiKey, m.id, m.name));
  }

  // Sync providers to DB and load config
  try {
    for (const [key, provider] of providers) {
      // Gemini 2.5 Flash gets highest priority (1) so it's the default on fresh DB
      const defaultPriority = key === TUNATUTOR_DEFAULT_LLM_MODEL ? 1 : 100;
      await prisma.llmModelConfig.upsert({
        where: { id: key },
        update: {
          provider: provider.providerFamily,
          modelId: provider.modelId,
          displayName: provider.name,
        },
        create: {
          id: key,
          provider: provider.providerFamily,
          modelId: provider.modelId,
          displayName: provider.name,
          enabled: true,
          priority: defaultPriority,
        },
      });
    }

    // Seed Gemini 2.5 Flash as active provider on fresh DB
    const activeSetting = await prisma.appSetting.findUnique({ where: { key: "llm.activeProvider" } });
    if (!activeSetting && providers.has(TUNATUTOR_DEFAULT_LLM_MODEL)) {
      await prisma.appSetting.create({
        data: { key: "llm.activeProvider", value: TUNATUTOR_DEFAULT_LLM_MODEL },
      });
    }
...
  // Fall back to first enabled provider by priority and persist the choice
  if (!activeProviderId && providers.size > 0) {
    const enabled = getEnabledProviders();
    if (enabled.length > 0) {
      activeProviderId = enabled[0].id;
    } else {
      activeProviderId = providers.keys().next().value!;
    }
    // Persist fallback choice so it survives restarts
    try {
      await prisma.appSetting.upsert({
        where: { key: "llm.activeProvider" },
        update: { value: activeProviderId },
        create: { key: "llm.activeProvider", value: activeProviderId },
      });
    } catch {
      // Non-critical — in-memory value is set either way
    }
  }
```

- Notes:
  - `process.env.GEMINI_API_KEY` is read here at start-up; with no key no providers are built.
  - On a fresh database Flash gets priority 1 and Flash Lite priority 100; both are created enabled.
  - `llm.activeProvider` is seeded with Flash on a fresh database.
  - If the stored active model is missing or disabled, the first enabled model by priority becomes active and is persisted.

### X12 · The two models tunatutor can choose between

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/models.ts:1-11` (Lomem main branch as read on 2026-10-15)
- Implements: C10, C24

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
  - Only two models: `gemini-2.5-flash` and `gemini-2.5-flash-lite`.
  - Each needs three price rows, and a switch to an unpriced model is refused.

### X13 · The sticky switch: a winning fallback becomes the active model in memory

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/registry.ts:178-183` (Lomem main branch as read on 2026-10-15)
- Implements: C28, L3

```ts
export function switchActiveProviderInMemory(id: string): void {
  if (!providers.has(id)) {
    throw new Error(`Unknown provider: ${id}`);
  }
  activeProviderId = id;
}
```

- Notes:
  - Only the in-memory `activeProviderId` changes; nothing is written to the database.
  - Compare `setActiveProvider` (lines 185-197), which the admin route uses and which persists.

### X14 · tunatutor's gateway wiring: providers, lead, sticky switch, meter

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/index.ts:268-291` (Lomem main branch as read on 2026-10-15)
- Implements: C24, C28, C20, F1, F4

```ts
/**
 * THE gateway. The provider list is re-read from the registry on every call,
 * so admin enable/priority edits and the sticky switch take effect at once.
 */
const gateway = createLlmGateway({
  providers: () => getEnabledProviders(),
  resolveModel: ({ model }) => resolveLeadProvider(model),
  fallback: {
    onSwitch: (provider) => {
      switchActiveProviderInMemory(provider.id);
      logger.info({ provider: provider.id }, "LLM sticky switch: active provider changed (in-memory only)");
    },
  },
  meter: {
    record: (event, ctx) =>
      recordLlmUsageCost(
        event.provider.id,
        event.provider.name,
        event.usage,
        toTunatutorContext(ctx),
        event.latencyMs,
        event.isError,
      ),
  },
```

- Notes:
  - `providers` is a function, so the registry is re-read on every call and admin edits apply at once.
  - `onSwitch` calls `switchActiveProviderInMemory` and logs "(in-memory only)".
  - The meter port calls `recordLlmUsageCost` with the provider, usage, latency and `isError`; it does not pass `event.aborted`.

### X15 · switched(): fallback success tells the app

- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:282-285` (Lomem main branch as read on 2026-10-15)
- Implements: C28, F1.10

```ts
  function switched(provider: LLMProvider, index: number): void {
    if (index === 0 || config.fallback === false) return;
    config.fallback?.onSwitch?.(provider);
  }
```

- Notes:
  - Nothing happens when the lead (index 0) succeeds or fallback is off.
  - It fires for any fallback win, including a call whose caller named a model (verified by simulation, see E3).

### X16 · run(): the one loop every non-streaming operation shares

- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:287-339` (Lomem main branch as read on 2026-10-15)
- Implements: C27, C35, C34, F1.5-F1.12, L1

```ts
  /**
   * The one loop every non-streaming operation shares: try each candidate
   * that supports the operation, settle every attempt, return the first
   * success.
   */
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
  - Providers that do not implement the operation's method are skipped without an attempt.
  - Every attempt is settled exactly once: `settle` on success, `fail` on error, `abandoned` on caller abort.
  - A caller abort (`signal?.aborted`) rethrows at once and does not try the next provider.
  - When every candidate fails, the error is "All LLM providers failed"; for `tools` it adds the last error.
  - Each provider gets the same `invoke`, so the same `options.timeoutMs` budget applies afresh to each provider.

### X17 · settle(), fail() and abandoned(): the one settle point

- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:240-280` (Lomem main branch as read on 2026-10-15)
- Implements: C21, C34, F1.8b, F1.8c, F1.9, F4.1

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
  - `settle` never awaits the meter; a throw or a rejected promise is logged as "LLM gateway: meter failed" and swallowed.
  - `fail` settles with `isError: true` and no usage, then calls `onError`.
  - `abandoned` settles with `isError: false`, `aborted: true` and any usage known so far.

### X18 · The spend event and the meter contract

- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:42-68` (Lomem main branch as read on 2026-10-15)
- Implements: C21, C20

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
```

- Notes:
  - `usage` is undefined when the attempt failed.
  - `aborted` means the caller gave up: not an error, no fallback, no `onError`.
  - `record` is called exactly once per provider attempt and is not awaited.

### X19 · Gemini retry policy and its defaults

- File: `~/projects/lomem/packages/shared/src/llm/providers/gemini.ts:25-59` (Lomem main branch as read on 2026-10-15)
- Implements: C30, C32, C33

```ts
/** Statuses retried by default: rate limit and the transient server errors. */
const DEFAULT_RETRY_STATUSES = [429, 500, 502, 503, 504] as const;

export interface GeminiRetryPolicy {
  /** Total attempts, first included. Default 3. */
  maxAttempts?: number;
  /** Wait before retry n (1-based) is `baseDelayMs * n` unless the response sets Retry-After. Default 3000. */
  baseDelayMs?: number;
  /** Ceiling on any single wait, Retry-After included. Default 30000. */
  maxDelayMs?: number;
  /** HTTP statuses that are retried. Default 429, 500, 502, 503, 504. */
  statuses?: readonly number[];
  /** Wait what the server asks (Retry-After, Gemini's `retryDelay`), capped by `maxDelayMs`. Default true. */
  honorRetryAfter?: boolean;
  /**
   * Retry a network failure (the request got no response at all) like a 503.
   * Default true. False: it is thrown at once, so a caller with a fallback
   * chain hands over immediately.
   */
  retryNetworkErrors?: boolean;
}

export interface GeminiProviderOptions {
  /**
   * A call's time budget in ms: every attempt, every retry wait and reading
   * the answer; a retry whose wait does not fit is not made. For a stream it
   * runs until the stream opens, then becomes the longest silence allowed
   * between two chunks. Default 120000. 0 disables it. `LLMOptions.timeoutMs`
   * overrides it per call.
   */
  timeoutMs?: number;
  retry?: GeminiRetryPolicy;
  /** API root, for tests and proxies. Default the public v1beta endpoint. */
  baseUrl?: string;
}
```

- Notes:
  - Retried statuses default to 429, 500, 502, 503, 504.
  - Default 3 attempts in total, base delay 3000 ms, cap 30000 ms per wait.
  - Network failures (no response at all) are retried by default.
  - The time budget covers every attempt, every wait and reading the answer; default 120000 ms; 0 disables it; `LLMOptions.timeoutMs` overrides it per call.
  - For a stream the budget runs until the stream opens, then becomes the longest allowed silence between chunks.

### X20 · Gemini provider constructor: where the defaults are set

- File: `~/projects/lomem/packages/shared/src/llm/providers/gemini.ts:288-318` (Lomem main branch as read on 2026-10-15)
- Implements: C30, C33, C4

```ts
export class GeminiProvider implements LLMProvider {
  readonly id: string;
  readonly modelId: string;
  readonly name: string;
  readonly providerFamily = "gemini";
  private readonly timeoutMs: number;
  private readonly retry: Required<GeminiRetryPolicy>;
  private readonly baseUrl: string;

  constructor(
    private readonly apiKey: string,
    registryKey: string,
    model: string,
    name: string,
    private readonly hooks?: LLMProviderHooks,
    options?: GeminiProviderOptions,
  ) {
    this.id = registryKey;
    this.modelId = model;
    this.name = name;
    this.timeoutMs = options?.timeoutMs ?? 120_000;
    this.retry = {
      maxAttempts: options?.retry?.maxAttempts ?? 3,
      baseDelayMs: options?.retry?.baseDelayMs ?? 3000,
      maxDelayMs: options?.retry?.maxDelayMs ?? 30_000,
      statuses: options?.retry?.statuses ?? DEFAULT_RETRY_STATUSES,
      honorRetryAfter: options?.retry?.honorRetryAfter ?? true,
      retryNetworkErrors: options?.retry?.retryNetworkErrors ?? true,
    };
    this.baseUrl = options?.baseUrl ?? GEMINI_BASE;
  }
```

- Notes:
  - The API key is a private constructor field; it never leaves the provider.
  - `timeoutMs` default 120_000 is line 308.

### X21 · Reading the wait the server asks for

- File: `~/projects/lomem/packages/shared/src/llm/providers/gemini.ts:214-227` (Lomem main branch as read on 2026-10-15)
- Implements: C32

```ts
/** Retry-After in ms, from delta-seconds or an HTTP date. */
function retryAfterMs(header: string | null): number | undefined {
  if (!header) return undefined;
  const seconds = Number(header);
  if (Number.isFinite(seconds)) return Math.max(0, seconds * 1000);
  const at = Date.parse(header);
  return Number.isNaN(at) ? undefined : Math.max(0, at - Date.now());
}

/** Gemini puts its own wait in the error body: `RetryInfo.retryDelay: "12s"`. */
function retryDelayFromBody(body: string): number | undefined {
  const m = body.match(/"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"/);
  return m ? Number(m[1]) * 1000 : undefined;
}
```

- Notes:
  - Retry-After is read as seconds or as an HTTP date.
  - Gemini's own `retryDelay` is parsed out of the error body, for example "12s".

### X22 · post(): one provider attempt, with retries inside the budget

- File: `~/projects/lomem/packages/shared/src/llm/providers/gemini.ts:364-407` (Lomem main branch as read on 2026-10-15)
- Implements: C30, C32, C33, C35, F2

```ts
  /**
   * POST with the key in `x-goog-api-key`, the call's time budget, and
   * retries on the policy's statuses (and, if the policy says so, on network
   * failures) with a linear backoff that yields to Retry-After. The budget
   * spans every attempt and wait: a retry whose wait would outlast it is not
   * made, and the failure is thrown instead. Returns the OK response with its
   * deadline still armed, so the caller can read the body under the same
   * budget.
   */
  private async post(method: string, body: string, options: LLMOptions | undefined, query = "") {
    const timeoutMs = options?.timeoutMs ?? this.timeoutMs;
    const endsAt = timeoutMs > 0 ? Date.now() + timeoutMs : Number.POSITIVE_INFINITY;
    const url = `${this.baseUrl}/models/${this.modelId}:${method}${query}`;
    for (let attempt = 0; ; attempt++) {
      const left = endsAt - Date.now();
      if (left <= 0) throw new GeminiTimeoutError(timeoutMs);
      const d = deadline(timeoutMs, left, options?.signal);
      let resp: Response;
      try {
        resp = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json", "x-goog-api-key": this.apiKey },
          body,
          signal: d.signal,
        });
      } catch (err: unknown) {
        d.clear();
        if (d.signal.aborted) throw d.signal.reason ?? err;
        // Network failure: retried like a 503 when the policy allows it.
        if (!this.retry.retryNetworkErrors || attempt + 1 >= this.retry.maxAttempts) throw err;
        if (!(await this.backoff(attempt, undefined, undefined, endsAt, options?.signal))) throw err;
        continue;
      }
      if (resp.ok) return { resp, deadline: d };
      const errBody = await resp.text().catch(() => "");
      d.clear();
      const error = new GeminiApiError(resp.status, errBody);
      if (!this.retry.statuses.includes(resp.status) || attempt + 1 >= this.retry.maxAttempts) throw error;
      const after = this.retry.honorRetryAfter
        ? (retryAfterMs(resp.headers?.get?.("retry-after") ?? null) ?? retryDelayFromBody(errBody))
        : undefined;
      if (!(await this.backoff(attempt, after, resp.status, endsAt, options?.signal))) throw error;
    }
  }
```

- Notes:
  - The key travels in the `x-goog-api-key` header.
  - A status not in the retry list, or the last allowed attempt, throws at once.
  - Retry-After wins over the error body's `retryDelay`; either is capped by `maxDelayMs`.
  - A caller abort or the budget's own timer aborting the fetch is thrown, not retried.

### X23 · backoff(): linear wait, skipped when it does not fit

- File: `~/projects/lomem/packages/shared/src/llm/providers/gemini.ts:409-422` (Lomem main branch as read on 2026-10-15)
- Implements: C32, C33, F2.7, F2.8, F2.9

```ts
  /** Sleeps before a retry. False (and no sleep) when the wait would outlast the call's budget. */
  private async backoff(
    attempt: number,
    retryAfter: number | undefined,
    status: number | undefined,
    endsAt: number,
    signal?: AbortSignal,
  ): Promise<boolean> {
    const wait = Math.min(retryAfter ?? this.retry.baseDelayMs * (attempt + 1), this.retry.maxDelayMs);
    if (Date.now() + wait >= endsAt) return false;
    this.hooks?.onRetry?.({ attempt, waitMs: wait, modelId: this.modelId, ...(status !== undefined ? { status } : {}) });
    await sleep(wait, signal);
    return true;
  }
```

- Notes:
  - The wait is `baseDelayMs * (attempt + 1)`: 3000 ms, then 6000 ms. It is linear, not exponential.
  - If now + wait reaches the budget's end, no sleep happens and the caller throws the last error.
  - The sleep itself is cancelled by the caller's signal.

### X24 · Thinking is off by default on 2.5 models

- File: `~/projects/lomem/packages/shared/src/llm/providers/gemini.ts:331-362` (Lomem main branch as read on 2026-10-15)
- Implements: C9, C14, C13

```ts
  private generationConfig(maxTokens: number, options: LLMOptions | undefined, allowJson: boolean) {
    // An image model answers with a picture: no JSON, no thinking budget.
    if (options?.image) {
      return {
        maxOutputTokens: maxTokens,
        responseModalities: ["IMAGE"],
        imageConfig: {
          ...(options.image.aspectRatio ? { aspectRatio: options.image.aspectRatio } : {}),
          ...(options.image.size ? { imageSize: options.image.size } : {}),
        },
      };
    }
    // Gemini 2.5 models have "thinking" enabled by default, which consumes
    // output tokens from the maxOutputTokens budget. For structured JSON output
    // (our primary use case), thinking wastes tokens and causes truncation, so
    // it is off unless the caller asks for it.
    const thinking = options?.thinking ?? (this.modelId.includes("2.5") ? "off" : undefined);
    const thinkingConfig =
      thinking === "off"
        ? { thinkingBudget: 0 }
        : thinking
          ? { thinkingLevel: thinking }
          : undefined;
    const schema = allowJson ? options?.responseSchema : undefined;
    return {
      maxOutputTokens: maxTokens,
      temperature: options?.temperature ?? 0.8,
      ...(allowJson && (options?.json || schema) ? { responseMimeType: "application/json" } : {}),
      ...(schema ? { responseSchema: schema } : {}),
      ...(thinkingConfig ? { thinkingConfig } : {}),
    };
  }
```

- Notes:
  - The comment: thinking "consumes output tokens from the maxOutputTokens budget" and "wastes tokens and causes truncation" for JSON.
  - Default temperature in the provider is 0.8 when the caller sets none.

### X25 · Token counts read from Gemini's response

- File: `~/projects/lomem/packages/shared/src/llm/providers/gemini.ts:82-95, 187-195` (Lomem main branch as read on 2026-10-15)
- Implements: C6, C7, C8, C9

```ts
interface GeminiResponse {
  candidates?: Array<{
    content?: { parts?: GeminiResponsePart[] };
    finishReason?: string;
    safetyRatings?: unknown;
  }>;
  promptFeedback?: { blockReason?: string };
  usageMetadata?: {
    promptTokenCount?: number;
    candidatesTokenCount?: number;
    cachedContentTokenCount?: number;
    thoughtsTokenCount?: number;
  };
}
...
function usageOf(data: GeminiResponse): Required<LLMUsageDetails> {
  const u = data.usageMetadata;
  return {
    inputTokens: u?.promptTokenCount ?? 0,
    outputTokens: u?.candidatesTokenCount ?? 0,
    cachedInputTokens: u?.cachedContentTokenCount ?? 0,
    thoughtTokens: u?.thoughtsTokenCount ?? 0,
  };
}
```

- Notes:
  - `promptTokenCount` becomes `inputTokens`, `candidatesTokenCount` becomes `outputTokens`.
  - `cachedContentTokenCount` and `thoughtsTokenCount` are read too.

### X26 · tunatutor's meter port: error marker row or one row per token kind

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/index.ts:125-234` (Lomem main branch as read on 2026-10-15)
- Implements: C20, C22, C8, C9, F4, L5

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
  if (cachedInput > 0) {
    recordProviderUsageEvent({
      metering,
      providerKey: `${providerId}:text-input-cached`,
      displayName: `${providerName} Cached input`,
      category: "llm",
      sourceEventType: "llm_request",
      billableQuantity: BigInt(cachedInput),
      billableUnit: "tokens",
      latencyMs,
      isError: false,
      metadata: baseMetadata,
    });
    settleLlmSpend(
      ctx,
      `${providerId}:text-input-cached`,
      `${providerName} Cached input`,
      "llm_request",
      cachedInput,
    );
  }
  if (output > 0) {
    recordProviderUsageEvent({
      metering,
      providerKey: `${providerId}:text-output`,
      displayName: `${providerName} Output`,
      category: "llm",
      sourceEventType: "llm_response",
      billableQuantity: BigInt(output),
      billableUnit: "tokens",
      latencyMs,
      isError: false,
      metadata: baseMetadata,
    });
    settleLlmSpend(
      ctx,
      `${providerId}:text-output`,
      `${providerName} Output`,
      "llm_response",
      output,
    );
  }
}
```

- Notes:
  - `isError || !tokens` writes one zero-quantity row keyed `<model>:text-input` with `isError: true`.
  - An aborted attempt with no usage therefore lands as an error row here, although the gateway marked it not an error (see Open questions).
  - A success writes up to three rows: uncached input, cached input, output (thinking tokens join output).
  - Each row is followed by `settleLlmSpend`, the allowance debit.

### X27 · settleLlmSpend: the allowance debit, fire-and-forget

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/index.ts:68-123` (Lomem main branch as read on 2026-10-15)
- Implements: C38, F4.6

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
  - System and admin spend is never debited.
  - `recordEvent: false` prevents a second, estimated ledger row.
  - The debit opens a Serializable transaction, so it is not awaited on the learner's path; a failure is logged and swallowed.

### X28 · The daily spend cap is not checked per call

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/index.ts:62-66` (Lomem main branch as read on 2026-10-15)
- Implements: C39, M6

```ts
// NOTE: the daily spend cap is deliberately NOT checked here. It is an
// activity-ENTRY gate (`cost-guardrails/activity-entry.ts`) — checking it per
// call would let it end a conversation mid-turn, which is the mid-activity
// wall the product charter forbids. This layer's job is attribution, not
// admission: it refuses only calls that could never be attributed at all.
```

- Notes:
  - The cap is an activity-entry gate; a per-call check could end a conversation mid-turn.

### X29 · The spend cap is a door, not a tripwire

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/cost-guardrails/activity-entry.ts:1-17` (Lomem main branch as read on 2026-10-15)
- Implements: C39, F9

```ts
// apps/tunatutor/backend/src/services/cost-guardrails/activity-entry.ts
//
// The daily spend cap is a DOOR, not a tripwire.
//
// "The door decides; the room never evicts." A guardrail that fires inside
// `callLLM` can end a conversation mid-turn — the learner is talking, the
// tutor stops answering, and the only signal is an error bubble. That is the
// mid-activity wall the product charter forbids. So the cap is checked once,
// when an activity STARTS, and never again while it runs: a user who crosses
// the cap mid-conversation finishes that conversation and is stopped at the
// next door.
//
// Doors are: a tutor/conversation session create, a drill-arc start, a help
// request, a "Drill Me" start, and a document ingest. Everything downstream of
// a door (turns, answers, next-card, judges, summaries) runs uncapped by
// design — the cost of one activity's tail is bounded and already paid for by
// the decision to open the door.
```

- Notes:
  - Doors: a tutor or conversation session create, a drill-arc start, a help request, a "Drill Me" start, a document ingest.
  - Everything after a door runs uncapped by design.

### X30 · The shared meter used by Billpod and Mealy

- File: `~/projects/lomem/packages/shared/src/llm/gateway/provider-usage-meter.ts:46-59, 89-103, 134-141` (Lomem main branch as read on 2026-10-15)
- Implements: C20, C22, F4

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
...
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
...
  return {
    record(event: LlmSpendEvent, ctx: LlmUsageContext): void {
      const job = write(event, ctx).catch((err: unknown) => {
        options.onWriteError?.(new Error(`provider usage meter: ${getErrorMessage(err)}`), []);
      });
      pending.add(job);
      void job.finally(() => pending.delete(job));
    },
```

- Notes:
  - Same row split as tunatutor: uncached input, cached input, output.
  - A failed call writes one zero-quantity error row; an aborted one with no usage writes a zero row marked `incomplete` and `aborted` in metadata, not as an error.
  - `record` runs the write detached and keeps a set of pending writes for `flush()`.

### X31 · The shared usage writer prices each line when it writes it

- File: `~/projects/lomem/packages/shared/src/billing/provider-usage-writer.ts:204-211, 261-306` (Lomem main branch as read on 2026-10-15)
- Implements: C23, C22, L5

```ts
 * Each line is priced by its `providerKey` and stamped with the capability
 * that key bills. A line without a user is written as a `system` row
 * (`user_id` null, `actor_kind` `system`, its `system_reason`). A line with no billable quantity
 * (an error row, an aborted call with no usage) is not looked up and is
 * written at $0 and `isEstimated`. A key with no price row, or whose lookup
 * fails, is written at $0 and `isEstimated` too — the quantity is never
 * dropped — and a failed lookup says so in the row's metadata.
 */
...
  async function priceLine(line: ProviderUsageLine, at: Date): Promise<PricedUsageLine> {
    let price: ProviderPriceRow | null = null;
    let lookupFailed = false;
    if (line.billableQuantity > 0n) {
      try {
        price = await lookup(line.providerKey, at);
      } catch (err: unknown) {
        // The quantity is still recorded, unpriced, rather than losing the line.
        lookupFailed = true;
        options.logger?.warn(
          { providerKey: line.providerKey, err: getErrorMessage(err) },
          "provider usage: price lookup failed; recording it at $0 (estimated)",
        );
      }
    }
    const usdMicros = price
      ? computeCostMicros({
          billableQuantity: line.billableQuantity,
          unitsPerPriceBlock: BigInt(price.unitsPerPriceBlock),
          usdPerPriceBlockMicros: BigInt(price.usdPerPriceBlockMicros),
        })
      : 0n;
    const metadata = line.metadata ?? {};
    const isSystem = line.userId == null;
    const row: ProviderUsageRow = {
      userId: line.userId ?? null,
      actorKind: isSystem ? "system" : (line.actorKind ?? "user"),
      systemReason: isSystem ? line.systemReason || UNATTRIBUTED : null,
      sessionId: line.sessionId ?? null,
      conversationType: line.conversationType,
      providerKey: line.providerKey,
      capability: capabilityForProviderKey(line.providerKey),
      displayName: line.displayName,
      category: line.category,
      sourceEventType: line.sourceEventType,
      billableQuantity: line.billableQuantity,
      billableUnit: line.billableUnit,
      computedUsdMicros: usdMicros,
      isEstimated: !price,
      latencyMs: line.latencyMs == null ? null : Math.round(line.latencyMs),
      isError: line.isError ?? false,
      metadataJson: lookupFailed ? { ...metadata, priceLookupFailed: true } : metadata,
      occurredAt: line.occurredAt ?? at,
      priceConfigId: price?.id ?? null,
    };
    return { line, row, price };
```

- Notes:
  - A zero-quantity line is not looked up and is written at $0.
  - A key with no price row, or a failed lookup, is written at $0 with `isEstimated: true`; the quantity is kept.
  - The row stores `computedUsdMicros` and `priceConfigId`, so the price used is fixed at write time.

### X32 · tunatutor's ledger write and cost formula

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/provider-costs.ts:131-139, 141-151, 158-188` (Lomem main branch as read on 2026-10-15)
- Implements: C22, C23, F4.4, F4.5

```ts
/** Compute USD micros cost for a given billable quantity and pricing block. */
export function computeProviderCostMicros(
  billableQuantity: bigint,
  unitsPerPriceBlock: bigint,
  usdPerPriceBlockMicros: bigint,
): number {
  if (billableQuantity <= 0n || unitsPerPriceBlock <= 0n || usdPerPriceBlockMicros <= 0n) return 0;
  return Number((billableQuantity * usdPerPriceBlockMicros) / unitsPerPriceBlock);
}
...
/**
 * The ledger writer: the shared usage writer (`@repo/shared/billing`), the
 * one every app records AI and speech spend through. Its rows are priced by
 * `getProviderPriceForBilling` — the same lookup the allowance settle debits
 * by — so a row and its debit never disagree on the price.
 */
const usageWriter = createProviderUsageWriter(prisma, {
  price: (providerKey, at) => getProviderPriceForBilling(providerKey, at),
  onWriteError: (err, rows) =>
    logger.warn({ err: getErrorMessage(err), count: rows.length }, "Provider usage rows could not be written"),
});
...
/**
 * Write one ledger row, detached: the caller never waits on the database.
 * Usage with no user is written as a `system` row (no user id, its
 * `systemReason`, else "unattributed"), so its spend still counts in the
 * app's cost. A zero-quantity event that is not an error is dropped.
 */
export function recordProviderUsageEvent(input: RecordProviderUsageInput): void {
  // Allow zero-quantity events for error tracking (isError: true with billableQuantity: 0n)
  if (input.billableQuantity <= 0n && !input.isError) return;
  const userId = input.metering.userId && input.metering.userId > 0 ? input.metering.userId : null;

  usageWriter.record({
    userId,
    ...(userId === null
      ? { systemReason: input.metering.systemReason ?? null }
      : input.metering.actorKind === "admin"
        ? { actorKind: "admin" as const }
        : {}),
    sessionId: input.metering.sessionId ?? null,
    conversationType: input.metering.conversationType ?? null,
    providerKey: input.providerKey,
    displayName: input.displayName,
    category: input.category,
    sourceEventType: input.sourceEventType,
    billableQuantity: input.billableQuantity,
    billableUnit: input.billableUnit,
    latencyMs: input.latencyMs ?? null,
    isError: input.isError ?? false,
    metadata: input.metadata ? toUsageMetadata(input.metadata) : undefined,
    occurredAt: input.occurredAt,
  });
```

- Notes:
  - Cost in micros is `quantity * usdPerPriceBlockMicros / unitsPerPriceBlock`, integer division.
  - tunatutor passes `getProviderPriceForBilling` as the writer's price lookup, so a row and its debit use the same price.
  - A zero-quantity event that is not an error is dropped.

### X33 · Price cache in tunatutor

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/provider-costs.ts:32-38` (Lomem main branch as read on 2026-10-15)
- Implements: C23

```ts
// In-memory cache for active price configs — avoids a DB read per usage event.
// Configs change rarely (admin edits), so a short TTL is fine.
const PRICE_CACHE_TTL_MS = 5 * 60 * 1000;
const priceConfigCache = new Map<
  string,
  { config: ProviderPriceConfig | null; expiresAt: number }
>();
```

- Notes:
  - Active price configs are cached for 5 minutes.

### X34 · The provider_usage_events table

- File: `~/projects/lomem/apps/tunatutor/backend/prisma/_shared.45-provider-usage.prisma:60-94, 113-114` (Lomem main branch as read on 2026-10-15)
- Implements: C22

```prisma
/// One metered usage event: a single provider call with its billable quantity and computed cost, for a user, an admin's tooling, or the system.
model ProviderUsageEvent {
  id                Int       @id @default(autoincrement())
  /// FK to the user who incurred this usage; null on a system row (no person behind the call).
  userId            Int?      @map("user_id")
  /// Who the usage is for: "user" (a person using the app), "admin" (an admin's own tooling call, under their userId) or "system" (no user; see systemReason).
  actorKind         String    @default("user") @map("actor_kind")
  /// Why a system row has no user (e.g. the system usage context's reason); null on user and admin rows.
  systemReason      String?   @map("system_reason")
  /// Originating session ID, if the usage occurred within a session.
  sessionId         String?   @map("session_id")
  /// Conversation/session type that generated the usage, if applicable.
  conversationType  String?   @map("conversation_type")
  /// Provider/model key this usage was billed against, e.g. "gemini-2.5-flash".
  providerKey       String    @map("provider_key")
  /// What the usage bought, whatever the vendor: "llm.text", "voice.stt" or "voice.tts". Stamped from providerKey by the shared usage writer; null for a key of no known shape.
  capability        String?
  /// Human-readable provider name captured at event time.
  displayName       String    @map("display_name")
  /// Provider category: "llm" or "speech".
  category          String
  /// Type of upstream event that produced this usage record.
  sourceEventType   String    @map("source_event_type")
  /// Quantity of billable units consumed (e.g. token or character count).
  billableQuantity  BigInt    @map("billable_quantity")
  /// Unit the billable quantity is measured in, e.g. "tokens", "characters".
  billableUnit      String    @map("billable_unit")
  /// Computed cost of this event, in USD micros (millionths of a dollar).
  computedUsdMicros BigInt    @default(0) @map("computed_usd_micros")
  /// Whether the cost was estimated rather than derived from exact provider billing.
  isEstimated       Boolean   @default(false) @map("is_estimated")
  /// Provider call latency in milliseconds, if measured.
  latencyMs         Int?      @map("latency_ms")
  /// Whether the underlying provider call errored.
  isError           Boolean   @default(false) @map("is_error")
...
  @@map("provider_usage_events")
}
```

- Notes:
  - Columns include user_id, actor_kind, system_reason, session_id, conversation_type, provider_key, capability, billable_quantity, computed_usd_micros, is_estimated, latency_ms, is_error, metadata_json, price_config_id.
  - This file is generated from packages/shared/prisma/foundation/45-provider-usage.prisma.

### X35 · Seeded Gemini prices

- File: `~/projects/lomem/apps/tunatutor/backend/src/dev/provider-prices.ts:1-74` (Lomem main branch as read on 2026-10-15)
- Implements: C23, E1, N2-N11

```ts
// tunatutor's seeded `provider_price_config` rows (`seedProviderPriceConfigs` in
// `seed.ts` inserts each missing key on boot; the owner edits them on the
// admin Billing → Provider Costs page afterwards).

// Gemini prices: ai.google.dev/gemini-api/docs/pricing, paid tier, Standard,
// read 2026-10-03 (Gemini 3.5 Flash: the same rows Mealy and Billpod seed, read
// 2026-09-27). Every model tunatutor can call (`services/llm/models.ts`, plus the
// shared `DEFAULT_LLM_MODEL`) needs all three keys (`:text-input`,
// `:text-input-cached`, `:text-output`), and every speech key the code binds
// needs its row: `provider-prices.test.ts` checks both. A key without a row is
// written at $0 and `isEstimated`, and the admin LLM settings refuse to switch
// to a model without them. The seed only inserts missing keys,
// so a price set on the Provider Costs page is never overwritten.
export const DEFAULT_PROVIDER_PRICE_CONFIGS = [
  {
    providerKey: "gemini-2.5-flash:text-input",
    displayName: "Gemini 2.5 Flash Input",
    category: "llm",
    pricingModel: "per_million_units",
    unitName: "tokens",
    unitsPerPriceBlock: 1_000_000n,
    usdPerPriceBlockMicros: 300_000n,
    notes: "Gemini API paid tier, Standard: $0.30 / 1M input tokens",
  },
  {
    providerKey: "gemini-2.5-flash:text-input-cached",
    displayName: "Gemini 2.5 Flash Cached input",
    category: "llm",
    pricingModel: "per_million_units",
    unitName: "tokens",
    unitsPerPriceBlock: 1_000_000n,
    usdPerPriceBlockMicros: 30_000n,
    notes: "Gemini API paid tier, Standard: $0.03 / 1M context-cached input tokens",
  },
  {
    providerKey: "gemini-2.5-flash:text-output",
    displayName: "Gemini 2.5 Flash Output",
    category: "llm",
    pricingModel: "per_million_units",
    unitName: "tokens",
    unitsPerPriceBlock: 1_000_000n,
    usdPerPriceBlockMicros: 2_500_000n,
    notes: "Gemini API paid tier, Standard: $2.50 / 1M output tokens including thinking",
  },
  {
    providerKey: "gemini-2.5-flash-lite:text-input",
    displayName: "Gemini 2.5 Flash Lite Input",
    category: "llm",
    pricingModel: "per_million_units",
    unitName: "tokens",
    unitsPerPriceBlock: 1_000_000n,
    usdPerPriceBlockMicros: 100_000n,
    notes: "Gemini API paid tier, Standard: $0.10 / 1M input tokens",
  },
  {
    providerKey: "gemini-2.5-flash-lite:text-input-cached",
    displayName: "Gemini 2.5 Flash Lite Cached input",
    category: "llm",
    pricingModel: "per_million_units",
    unitName: "tokens",
    unitsPerPriceBlock: 1_000_000n,
    usdPerPriceBlockMicros: 10_000n,
    notes: "Gemini API paid tier, Standard: $0.01 / 1M context-cached input tokens",
  },
  {
    providerKey: "gemini-2.5-flash-lite:text-output",
    displayName: "Gemini 2.5 Flash Lite Output",
    category: "llm",
    pricingModel: "per_million_units",
    unitName: "tokens",
    unitsPerPriceBlock: 1_000_000n,
    usdPerPriceBlockMicros: 400_000n,
    notes: "Gemini API paid tier, Standard: $0.40 / 1M output tokens including thinking",
  },
```

- Notes:
  - Prices are in USD micros per 1,000,000 tokens: Flash input 300,000, cached 30,000, output 2,500,000; Flash Lite input 100,000, cached 10,000, output 400,000.
  - Source named in the comment: ai.google.dev/gemini-api/docs/pricing, paid tier, Standard, read 2026-10-03.
  - The seed inserts only missing keys, so an owner's edit on the Provider Costs page is never overwritten.

### X36 · Price coverage check before a model can be used

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/registry.ts:199-212` (Lomem main branch as read on 2026-10-15)
- Implements: C44, F7

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
  - The admin settings call it before making a model active or enabling it as a fallback.

### X37 · Admin routes that set the active model and the enabled/priority config

- File: `~/projects/lomem/apps/tunatutor/backend/src/routes/admin/index.ts:270-305` (Lomem main branch as read on 2026-10-15)
- Implements: C24, F7

```ts
  // PUT /llm/active-provider — Switch active provider
  app.put<{ Body: { providerId: string } }>(
    "/llm/active-provider",
    async (request, reply) => {
      const { providerId } = request.body;

      if (!providerId) {
        throw new ValidationError("providerId is required");
      }
      if (getProviderById(providerId)) await assertModelPriced(providerId);

      try {
        await setActiveProvider(providerId);
      } catch (err: unknown) {
        throw new ValidationError(getErrorMessage(err) || "Unknown error");
      }

      return reply.send({ activeProviderId: providerId });
    },
  );

  // PATCH /llm/providers/:id/config — Update model enabled/priority
  app.patch<{ Params: { id: string }; Body: { enabled?: boolean; priority?: number } }>(
    "/llm/providers/:id/config",
    async (request, reply) => {
      const { id } = request.params;
      const { enabled, priority } = request.body;

      if (enabled === undefined && priority === undefined) {
        throw new ValidationError("At least one of enabled or priority is required");
      }
      // Enabling a model makes it a fallback the gateway may switch to.
      if (enabled === true && getProviderById(id)) await assertModelPriced(id);

      try {
        await updateModelConfig(id, { enabled, priority });
```

- Notes:
  - `PUT /llm/active-provider` persists the active model (after the price check).
  - `PATCH /llm/providers/:id/config` sets `enabled` and `priority`; enabling runs the price check.

### X38 · Disabling the active model auto-switches

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/registry.ts:141-176` (Lomem main branch as read on 2026-10-15)
- Implements: C24, L3

```ts
export async function updateModelConfig(
  id: string,
  update: { enabled?: boolean; priority?: number },
): Promise<void> {
  if (!providers.has(id)) {
    throw new Error(`Unknown provider: ${id}`);
  }

  // Update DB
  await prisma.llmModelConfig.update({
    where: { id },
    data: {
      ...(update.enabled !== undefined ? { enabled: update.enabled } : {}),
      ...(update.priority !== undefined ? { priority: update.priority } : {}),
    },
  });

  // Update in-memory cache
  const current = modelConfigs.get(id) ?? { enabled: true, priority: 100 };
  modelConfigs.set(id, {
    enabled: update.enabled ?? current.enabled,
    priority: update.priority ?? current.priority,
  });

  // If we just disabled the active model, auto-switch to next enabled
  if (update.enabled === false && activeProviderId === id) {
    const enabled = getEnabledProviders();
    if (enabled.length > 0) {
      await setActiveProvider(enabled[0].id);
      logger.info({ provider: enabled[0].id }, "LLM active provider disabled, auto-switched");
    } else {
      activeProviderId = null;
      logger.warn("LLM active provider disabled and no other enabled providers available");
    }
  }
}
```

- Notes:
  - If the active model is disabled, the first enabled model becomes active and is persisted; with none left, active becomes null.

### X39 · Level chat: models and budgets

- File: `~/projects/lomem/apps/tunatutor/backend/src/use-cases/level-chat/prompts.ts:1-9, 27-33` (Lomem main branch as read on 2026-10-15)
- Implements: C10, C13, C14, C33, E1

```ts
// The level chat's three model prompts (spec §7) and the zod schemas their
// answers must match (§5.2). Pure: no I/O. Learner text only ever travels
// inside JSON fields, and every prompt says it is data.
//
//   tutor  — Flash, one call per answer: one shared reaction plus one line per
//            candidate outcome. It never sees the facts or the counts.
//   rater  — Flash-Lite, one call per answer: a factual checklist. It never
//            sees the candidates and never decides pass or fail.

...
// ─── Models and budgets (§5.1) ───

export const LEVEL_CHAT_RATER_MODEL = "gemini-2.5-flash-lite";
export const LEVEL_CHAT_TUTOR_MODEL = "gemini-2.5-flash";

export const RATER_CALL = { temperature: 0.1, timeoutMs: 2000, maxTokens: 500 } as const;
export const TUTOR_CALL = { temperature: 0.6, timeoutMs: 4000, maxTokens: 700 } as const;
```

- Notes:
  - Rater: Flash-Lite, temperature 0.1, 2000 ms, 500 output tokens.
  - Tutor: Flash, temperature 0.6, 4000 ms, 700 output tokens.
  - The header says "three model prompts" but lists two (see Open questions).

### X40 · Level chat: the route gives each call its budget and an abort signal

- File: `~/projects/lomem/apps/tunatutor/backend/src/routes/level-chat.ts:35-48` (Lomem main branch as read on 2026-10-15)
- Implements: C16, C17, C33, C34, F3.3

```ts
function levelChatJson(userId: number): LevelChatJsonCall {
  return async (req) => {
    const { data } = await callLLMJson(req.systemPrompt, [{ role: "user", content: req.userMessage }], req.maxTokens, {
      schema: req.schema,
      model: req.model,
      temperature: req.temperature,
      thinking: "off",
      timeoutMs: req.timeoutMs,
      signal: AbortSignal.timeout(req.timeoutMs),
      usageContext: userUsageContext(userId, "onboarding_level_chat", req.levelChatId),
    });
    return data;
  };
}
```

- Notes:
  - Feature name `onboarding_level_chat`.
  - `signal: AbortSignal.timeout(req.timeoutMs)` is a second clock: it caps the whole call, fallbacks included, at the same 2 s or 4 s.
  - When that signal fires, the gateway treats it as a caller abort: no fallback (verified by simulation, see E7).

### X41 · Level chat turn: two calls in parallel, failures as values

- File: `~/projects/lomem/apps/tunatutor/backend/src/use-cases/level-chat/level-chat-turn.ts:1-17, 209-231, 239-262` (Lomem main branch as read on 2026-10-15)
- Implements: F3, C36, C37

```ts
// One step of the level chat (spec §5.1): an answer, an "I don't understand"
// tap, or a silence the device noticed.
//
// For an answer:
//   1. Code lists the line each possible outcome would need (candidates).
//   2. Two model calls run at once: the rater (Flash-Lite) describes the answer
//      as facts; the tutor (Flash) writes one reaction plus one line per
//      candidate. Neither sees what the other sees.
//   3. Code computes the outcome from the facts and the probe's pass rule,
//      picks that candidate's line and checks it (`checkTutorLine`). A refused
//      line, a missing one or a model failure uses the bank's written line.
//   4. The state and a telemetry row are saved in one transaction.
//
// A retried post with the same `turnId` gets the stored reply back and is
// never rated twice. Model failures degrade (the bank line, or no_data, or
// after two rater failures the code-only ladder) — never a 500 mid-chat. Taps
// and silences need no model: the bank's rephrase (with its gloss) answers.
...
    const raterCall = async (): Promise<RaterFacts> => {
      const raw = await deps.json({
        kind: "rater",
        levelChatId: chat.id,
        systemPrompt: buildRaterSystemPrompt({ targetLanguage: language, nativeLanguage }),
        userMessage: buildRaterUserMessage({
          tutorLine: last.tutorLine,
          probe: probeTask(inPlay?.id) ?? { id: "", level: "A1", task: "" },
          isPush: inPlay?.pushed ?? false,
          isRephrase: (inPlay?.rephrased ?? 0) > 0,
          inputMode: req.inputMode,
          chip: req.chip ?? null,
          learnerAnswer: text,
        }),
        schema: raterFactsSchema,
        model: LEVEL_CHAT_RATER_MODEL,
        temperature: RATER_CALL.temperature,
        maxTokens: RATER_CALL.maxTokens,
        timeoutMs: RATER_CALL.timeoutMs,
      });
      return normalizeFacts(raw, text);
    };
    const tutorCall = async (): Promise<TutorReply> => {
...
      return deps.json({
        kind: "tutor",
        levelChatId: chat.id,
        systemPrompt: buildTutorSystemPrompt({
          tutorName: chat.tutorName ?? "",
          learnerName: chat.learnerName ?? "",
          targetLanguage: language,
          nativeLanguage,
          varietyClause: variety,
        }),
        userMessage: buildTutorUserMessage(tutorInput),
        schema: tutorReplySchema,
        model: LEVEL_CHAT_TUTOR_MODEL,
        temperature: TUTOR_CALL.temperature,
        maxTokens: TUTOR_CALL.maxTokens,
        timeoutMs: TUTOR_CALL.timeoutMs,
      });
    };

    [rater, tutor] = await Promise.all([
      needsRater ? timed(raterCall, nowMs) : Promise.resolve(null),
      candidates.length > 0 ? timed(tutorCall, nowMs) : Promise.resolve(null),
    ]);
    for (const r of [rater, tutor]) if (r && !r.ok) rethrowIfUndegradable(r.error);
```

- Notes:
  - Both calls run under `Promise.all` through `timed`, which turns a throw into `{ ok: false }`.
  - `rethrowIfUndegradable` runs first on any failure, so a missing usage context or a spend-cap error still surfaces.
  - A rater failure is logged as "level chat: rater failed — no_data".

### X42 · Level chat: a failed tutor call uses the bank line

- File: `~/projects/lomem/apps/tunatutor/backend/src/use-cases/level-chat/level-chat-turn.ts:148-155, 290-304` (Lomem main branch as read on 2026-10-15)
- Implements: F3.8, C36

```ts
function isTimeout(err: unknown): boolean {
  const name = err instanceof Error ? err.name : "";
  return name === "TimeoutError" || name === "AbortError" || /time ?out|aborted/i.test(getErrorMessage(err));
}

function failureLabel(result: Timed<unknown>): string {
  return !result.ok && isTimeout(result.error) ? "timeout" : "error";
}
...
  // ── Pick the line: the tutor's for the real outcome when it passes the check, else the bank's.
  const move = step.move;
  const outcomeKey = step.outcome?.outcome;
  const chosen =
    candidates.find((c) => c.key === (outcomeKey as TutorCandidateKey) && sameLine(c.move, move)) ??
    candidates.find((c) => sameLine(c.move, move));
  const fallback = bankLine(move, { ...lineCtx, state: step.state });
  const alreadySaid = [...turns.map((t) => t.tutorLine), last.tutorLine];

  let tutorLine = fallback.line;
  let gloss = fallback.gloss;
  let usedTutor = false;
  let lineCheckFailed: string | null = null;
  if (tutor && !tutor.ok) {
    lineCheckFailed = failureLabel(tutor);
```

- Notes:
  - The bank's pre-written line is the default; the tutor's line replaces it only when it exists and passes `checkTutorLine`.
  - A failure is labelled "timeout" or "error" in `lineCheckFailed`.

### X43 · Level chat: two rater failures in a row switch to the code-only scorer

- File: `~/projects/lomem/apps/tunatutor/backend/src/use-cases/level-chat/policy.ts:968-986` (Lomem main branch as read on 2026-10-15)
- Implements: F3.7, L4, C36

```ts
  if (state.degraded) return applyDegradedAnswer(state, probe, input);

  if (input.facts === null) {
    state.raterFailStreak += 1;
    if (state.raterFailStreak >= 2) {
      // Two rater failures in a row: switch to the code-only ladder.
      state.degraded = true;
      if (degradedNextProbe(state.scored, state.asked.filter((id) => id !== probe.id)) === probe.id) {
        return applyDegradedAnswer(state, probe, input);
      }
      state.probe = null;
      return advance(state, none);
    }
  } else {
    state.raterFailStreak = 0;
    state.raterRows += 1;
    if (input.facts.language === "target") state.targetAnswers += 1;
    addHooks(state, input.facts.hooks);
  }
```

- Notes:
  - `raterFailStreak` counts consecutive failures and resets on a success.
  - At 2 the chat sets `degraded = true` and stays degraded.

### X44 · The code-only scorer

- File: `~/projects/lomem/apps/tunatutor/backend/src/use-cases/level-chat/degraded.ts:1-26` (Lomem main branch as read on 2026-10-15)
- Implements: C36, L4

```ts
// The code-only scorer for degraded mode (spec §4.6). After 2 rater failures
// in a row the chat runs a fixed ladder and scores each answer with code
// alone: word count, the answer's language from its script and its common
// words, and past markers from a per-language list. Its result is only ever
// shown as a soft "{tutor}'s guess".

import type {
  AnswerLanguage,
  Level,
  LevelChatInputMode,
  PracticeLanguage,
} from "@tunatutor/shared";
import { LEVEL_CHAT_LEVELS } from "@tunatutor/shared";
import { findProbe } from "./probe-bank.js";
import type { ScoredOutcome, ScoredRow } from "./types.js";

/** The fixed ladder, in order. */
export const DEGRADED_LADDER = ["A1.self", "A2.why", "A2.past", "B1.story", "B2.speculate"] as const;

/** What an answer needs on each rung (voice; typed answers need 30% fewer words). */
const RUNG_NEEDS: Readonly<Record<(typeof DEGRADED_LADDER)[number], { words: number; past: number }>> = {
  "A1.self": { words: 3, past: 0 },
  "A2.why": { words: 8, past: 0 },
  "A2.past": { words: 10, past: 2 },
  "B1.story": { words: 30, past: 3 },
  "B2.speculate": { words: 50, past: 0 },
```

- Notes:
  - It uses word count, the answer's language and past markers.
  - Its result is shown only as "{tutor}'s guess".

### X45 · Errors that must never be degraded

- File: `~/projects/lomem/apps/tunatutor/backend/src/errors/index.ts:171-196` (Lomem main branch as read on 2026-10-15)
- Implements: C37

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

- Notes:
  - `FST_MISSING_USAGE_CONTEXT` is a programming error; `FST_DAILY_SPEND_CAP` is an admission decision already made.

### X46 · callJson: settle first, then classify the finish and validate

- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:353-392` (Lomem main branch as read on 2026-10-15)
- Implements: C11, C12, C42, F6

```ts
  async function callJson<S extends z.ZodTypeAny>(req: LlmJsonRequest<S>): Promise<LlmJsonResult<z.output<S>>> {
    const context = assertLlmUsageContext(req.context, req.caller ?? "llm.callJson");
    const options: LLMOptions = {
      temperature: 0.2,
      ...req.options,
      json: true,
      responseSchema: zodToResponseSchema(req.schema),
    };
    const result = await run(
      "json",
      context,
      { systemPrompt: req.systemPrompt, messages: req.messages, maxTokens: req.maxTokens },
      req.options?.signal,
      (p) => p.chat(req.systemPrompt, req.messages, req.maxTokens, options),
      req.model,
    );
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
  - Default temperature 0.2 for JSON calls.
  - The spend is already settled before parsing: "a wrong answer still cost money".
  - A blocked answer throws `LlmOutputError` whatever the text.
  - A parse failure on a non-`end_turn` stop names the finish reason, for example MAX_TOKENS.

### X47 · How an answer ended: classifyFinish

- File: `~/projects/lomem/packages/shared/src/llm/finish.ts:1-38` (Lomem main branch as read on 2026-10-15)
- Implements: C11, C12

```ts
// How a model's answer ended, provider-neutral: the finish reasons that mean
// "this is not an answer" are classified once here, and read by the providers
// (the tool-use stop reason), the gateway (`callJson`) and callers.
import type { LLMStopReason } from "./types.js";

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
  - STOP maps to `end_turn`, MAX_TOKENS to `max_tokens`, SAFETY and similar to `blocked`, a blocked prompt is always `blocked`.
  - Malformed tool-call reasons map to `malformed_tool_call`; anything else is `stop_sequence`.

### X48 · Streaming: fall back only before anything reached the consumer

- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:428-434, 456-501` (Lomem main branch as read on 2026-10-15)
- Implements: C41, F5, L6

```ts
  /**
   * The one streaming loop: try each candidate that implements the stream,
   * forward its events, settle once per attempt — on `done`, on failure, or
   * when the caller gives up (its signal fires, or it stops reading) — and
   * fall back only while nothing has reached the consumer and the caller has
   * not aborted.
   */
...
      let yielded = false;
      let settled = false;
      let done = false;
      // The usage reported so far, for an attempt that ends before `done`.
      let partialUsage: LLMUsageDetails | undefined;
      try {
        for await (const event of open(provider)) {
          if (event.type === "delta" && event.usage) partialUsage = event.usage;
          if (event.type === "done") {
            done = true;
            const latencyMs = performance.now() - start;
            const { usage, result } = finish(event);
            config.observe?.onResponse?.({ operation, provider: pref, index: i, latencyMs, result }, context);
            settle({ operation, provider: pref, usage, latencyMs, isError: false }, context);
            settled = true;
            switched(provider, i);
          }
          yielded = true;
          yield event;
        }
        if (!done) throw new Error("LLM stream ended without a final event");
        return;
      } catch (err: unknown) {
        if (signal?.aborted) {
          // The caller gave up: not a provider failure, and no fallback.
          if (!settled) {
            settled = true;
            abandoned(context, { operation, provider: pref, latencyMs: performance.now() - start, usage: partialUsage });
          }
          throw err;
        }
        if (!settled) {
          settled = true;
          fail(err, context, { operation, provider: pref, index: i, latencyMs: performance.now() - start });
        }
        lastError = err;
        // Text already reached the consumer: another provider cannot continue it.
        if (yielded) throw err;
      } finally {
        // The consumer stopped reading: the attempt still cost money, and the
        // provider bills the tokens it produced. Record it as aborted with the
        // usage reported so far (the final usage never arrived).
        if (!settled) {
          abandoned(context, { operation, provider: pref, latencyMs: performance.now() - start, usage: partialUsage });
        }
      }
```

- Notes:
  - `yielded` turns true after the first event; after that a failure is rethrown with no fallback.
  - The `finally` block settles an attempt the consumer stopped reading as aborted, with the usage reported so far.

### X49 · A stream that ends without a finish reason is an error

- File: `~/projects/lomem/packages/shared/src/llm/providers/gemini.ts:523-557` (Lomem main branch as read on 2026-10-15)
- Implements: C11, C41

```ts
  /**
   * Streamed plain chat. Yields each chunk's visible text as a `delta` (with
   * the usage so far, when the chunk reports it), then one `done` with the
   * whole text and the final usage (Gemini repeats `usageMetadata` on chunks;
   * the last one wins). A stream that ends with neither a finish reason nor a
   * prompt block reason was cut off: it throws {@link GeminiStreamError}
   * instead of passing partial text off as the answer.
   */
  async *chatStream(
    systemPrompt: string,
    messages: LLMMessage[],
    maxTokens: number,
    options?: LLMOptions,
  ): AsyncGenerator<LLMStreamEvent> {
    const body = JSON.stringify({
      ...this.framing(systemPrompt, toPlainContents(messages)),
      generationConfig: this.generationConfig(maxTokens, options, true),
    });
    let text = "";
    let usage: Required<LLMUsageDetails> = usageOf({});
    let finishReason: string | undefined;
    let blockReason: string | undefined;
    for await (const chunk of this.streamChunks(body, options)) {
      if (chunk.usageMetadata) usage = usageOf(chunk);
      finishReason = chunk.candidates?.[0]?.finishReason ?? finishReason;
      blockReason = chunk.promptFeedback?.blockReason ?? blockReason;
      const delta = answerText(chunk);
      if (delta) {
        text += delta;
        yield { type: "delta", text: delta, ...(chunk.usageMetadata ? { usage } : {}) };
      }
    }
    if (!finishReason && !blockReason) throw new GeminiStreamError("Gemini API: stream ended without a finish reason");
    yield { type: "done", text, usage, finishReason, blockReason };
  }
```

- Notes:
  - Partial text is never passed off as the answer: the provider throws `GeminiStreamError`.

### X50 · Billpod and Mealy: one model, no fallback

- File: `~/projects/lomem/packages/shared/src/llm/gateway/app-llm.ts:1-4, 18-23, 45-85, 110-129` (Lomem main branch as read on 2026-10-15)
- Implements: C15, V1, V3 (the minimal version)

```ts
// An app's LLM, the standard way (ADR-057 §5): one Gemini model through the
// shared gateway, every call's spend written by the shared meter. Billpod and
// Mealy build theirs here; tunatutor keeps its admin-chosen model registry and
// builds its gateway itself.
...
/**
 * The model every app calls unless it sets its own (`GEMINI_MODEL`). Its
 * prices must exist in each app's `provider_price_config`
 * (`<model>:text-input` / `:text-input-cached` / `:text-output`).
 */
export const DEFAULT_LLM_MODEL = "gemini-3.5-flash";
...
/**
 * One model, no fallback, spend recorded, and debited only through the app's
 * own `debit` (ADR-013). Without a key
 * the gateway has no provider: a call fails with "No LLM provider available"
 * instead of the app refusing to boot.
 */
export function createAppLlm(deps: AppLlmDeps): AppLlm {
  const model = deps.model?.trim() || DEFAULT_LLM_MODEL;
  const provider =
    deps.provider ??
    (deps.apiKey
      ? new GeminiProvider(deps.apiKey, model, model, `Gemini ${model}`, {
          onRetry: (info) =>
            deps.log.info(
              { retryMs: info.waitMs, attempt: info.attempt, model: info.modelId, status: info.status ?? "network error" },
              "Gemini: retrying",
            ),
        })
      : undefined);

  const meter = createProviderUsageMeter(deps.prisma, {
    debit: deps.debit,
    logger: deps.log,
    onWriteError: (err, rows) =>
      deps.log.error({ err: getErrorMessage(err), rows: rows.length }, "LLM usage rows could not be written"),
  });

  const gateway = createLlmGateway({
    providers: provider ? [provider] : [],
    fallback: false,
    meter,
    onError: (_err, ctx, info) =>
      deps.log.warn(
        { provider: info.provider.id, operation: info.operation, feature: ctx.feature, err: info.message },
        "LLM call failed",
      ),
    logger: deps.log,
  });

  return { gateway, meter, model: provider?.modelId ?? null };
}
...
export function createPromptClient(gateway: LlmGateway, options: PromptClientOptions = {}): PromptClient {
  const maxTokens = options.defaultMaxTokens ?? 2048;
  const base = { temperature: options.temperature ?? 0.2, thinking: options.thinking ?? "low" };
  const send = (call: PromptCall, json: boolean) =>
    gateway.call({
      systemPrompt: call.systemPrompt,
      messages: [{ role: "user", content: call.userPrompt }],
      maxTokens: call.maxTokens ?? maxTokens,
      options: json ? { ...base, json: true } : base,
      context: call.context,
    });
  return {
    async callJson<T>(call: PromptCall): Promise<T> {
      return parseJsonResponse<T>((await send(call, true)).text);
    },
    async callText(call: PromptCall): Promise<string> {
      return (await send(call, false)).text;
    },
  };
}
```

- Notes:
  - `fallback: false` and a single provider.
  - Default model `gemini-3.5-flash` unless the app sets `GEMINI_MODEL`.
  - With no key the gateway has no provider and a call fails with "No LLM provider available"; the app still boots.
  - `createPromptClient` (Billpod and Mealy's simple AI features) defaults to 2048 output tokens, temperature 0.2 and thinking `"low"`; on a thinking model the 2048 covers the thoughts too (lines 103-112).

### X51 · Billpod's feature labels

- File: `~/projects/lomem/apps/billpod/backend/src/ai/llm.ts:1-28` (Lomem main branch as read on 2026-10-15)
- Implements: C17

```ts
// Billpod's LLM gateway (ADR-057 §5): Gemini Flash through the shared gateway,
// with every call's spend written to `provider_usage_events` (foundation
// fragment 45) by the shared meter. Document capture (plan Phase 2) and the
// in-app assistant (Phase 3) call it; assistants connected over MCP use their
// own model and never reach it.
//
// A Free account's spend draws its one-time trial down (the meter's `debit`,
// passed in src/index.ts); Plus is never debited (ADR-013 §14).
import { createAppLlm, type AppLlm, type AppLlmDeps, type LlmUserUsageContext } from "@repo/shared/llm";

/**
 * The features Billpod's AI spend is reported under (`conversation_type` on
 * the usage row). One name per feature, so per-feature cost is one query.
 */
export const BILLPOD_LLM_FEATURES = ["capture", "assistant", "paperwork", "avatar"] as const;
export type BillpodLlmFeature = (typeof BILLPOD_LLM_FEATURES)[number];

/** Where inside a feature a call came from, kept in the usage row's metadata. */
export type BillpodLlmSurface = "app" | "mcp" | "email" | "drop" | "drive";

/** The usage context for a person's call: who pays and for which feature. */
export function billpodLlmUsage(
  userId: number,
  feature: BillpodLlmFeature,
  opts: { surface?: BillpodLlmSurface; sessionId?: string | null } = {},
): LlmUserUsageContext {
  return { userId, feature, surface: opts.surface, sessionId: opts.sessionId ?? null };
}
```

- Notes:
  - Four features: capture, assistant, paperwork, avatar.
  - Surfaces inside a feature: app, mcp, email, drop, drive.

### X52 · tunatutor's feature labels as constants

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/surfaces.ts:1-11` (Lomem main branch as read on 2026-10-15)
- Implements: C17, M5

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
```

- Notes:
  - One feature must report under one name, or its cost splits across rows nobody adds back together.

### X53 · Error and observation hooks in tunatutor

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/index.ts:292-343` (Lomem main branch as read on 2026-10-15)
- Implements: C43

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
  - `onError` emits an `llm_error` event, logs "LLM provider failed" or "LLM fallback provider also failed", and mirrors the failure.
  - `observe` mirrors each request and response (system prompt, messages, tools, usage, finish reason, latency) to the postmortem mirror.

### X54 · The llm_error event bus

- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/llm-events.ts:1-23` (Lomem main branch as read on 2026-10-15)
- Implements: C43

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
  - `routes/admin/sse.ts` line 64 subscribes to it and pushes events to the admin page over server-sent events.

### X55 · The image model's key read

- File: `~/projects/lomem/apps/tunatutor/backend/src/index.ts:654-660` (Lomem main branch as read on 2026-10-15)
- Implements: C4

```ts
  // The learner's avatar (shared avatars): a gallery pick, or three drawings from
  // a photo. The photo step has its own image gateway with no debit, so it never
  // draws on the allowance (ADR-013); its spend is still recorded under "avatar".
  const imageLlm = createTunatutorImageLlm({ apiKey: env.GEMINI_API_KEY, prisma, log: app.log });
  app.addHook("onClose", async () => {
    await imageLlm.meter.flush();
  });
```

- Notes:
  - A second read of `GEMINI_API_KEY`, through the validated `env`, for the avatar image gateway.
  - Its spend is recorded under "avatar" and never debited from the allowance.

### X56 · ADR-057 §5: the decision record for the gateway

- File: `~/projects/lomem/docs/adr/057-ai-tools-mcp-and-oauth-provider.md:383-433` (Lomem main branch as read on 2026-10-15)
- Implements: C15, C16, C21, C27, C34, C25

````markdown
### 5. LLM calls and usage metering

Every LLM call in tunatutor, Mealy and Billpod goes through one gateway in
`@repo/shared/llm` (`packages/shared/src/llm/gateway/`); MyTube, outside
this programme, still calls a provider directly (`createLlmClient`). It owns what must be identical
everywhere and takes what is app-specific as injected ports:

```ts
const gateway = createLlmGateway({
  providers,      // enabled LLMProviders in priority order (or a function re-read per call)
  resolveModel,   // optional: the provider that leads a call (default: the first); gets the call's `model`
  fallback,       // false, or { onSwitch(provider) } told when a fallback won
  meter,          // meter.record(event, ctx): once per provider attempt, success or failure
  onError,        // onError(err, ctx, info): a failed provider attempt
  observe,        // optional request/response taps
  logger,
});

gateway.call({ systemPrompt, messages, maxTokens, options, context })            // → LLMChatResult
gateway.callJson({ ..., schema })                                                // → { data, result }
gateway.callWithTools({ systemPrompt, messages, tools, maxTokens?, options, context }) // → LLMResultWithTools
gateway.stream({ systemPrompt, messages, maxTokens, options, context })          // → AsyncGenerator<delta… done>
gateway.streamWithTools({ systemPrompt, messages, tools, maxTokens?, options, context }) // → AsyncGenerator<delta… done{result}>
```

- **A usage context is required.** `context` is `{ userId, feature, surface?,
  sessionId?, actor? }`, or `{ system: true, feature, reason }` for a call no
  person is behind (cron, content scripts, admin jobs with no one to bill).
  `actor: "admin"` marks an admin's own tooling call under their user id. A call without one, with an empty `feature`, a
  non-positive `userId` or a reasonless system context throws
  `MissingUsageContextError` (`FST_MISSING_USAGE_CONTEXT`, `@repo/shared/errors`)
  before any provider is called. `feature` is what spend is reported under
  (the usage row's `conversation_type`).
- **One settle point.** The gateway calls `meter.record` exactly once per
  provider attempt — with the provider's usage on success, as an error with no
  usage on failure — and never awaits it: a meter that throws or rejects is
  logged, and the call still returns. `callJson` settles before it validates,
  so a wrong answer is still recorded. A stream settles when its `done` event
  arrives, when it fails, or when the consumer stops reading.
- **Caller abort is not a failure.** When the caller's `options.signal` has
  fired, or it stops reading a stream, the attempt is settled with
  `aborted: true` and `isError: false`, carrying the usage known so far (a
  stream's `delta` events carry the provider's running usage); `onError` is
  not called and the fallback chain is not run.
- **Per-call model.** Every request may carry an optional `model` id
  (`"gemini-2.5-flash-lite"`), handed to `resolveModel` as `{ operation,
  context, model }`. The app decides whether to honour it; without
  `resolveModel` it is ignored and the first provider leads. The fallback chain
  is the same either way. tunatutor honours it only for an ENABLED model in its
  registry (`resolveLeadProvider`), otherwise the active model runs the call —
  the level chat pins its rater to Flash-Lite this way.
````

- Notes:
  - MyTube still calls a provider directly (`createLlmClient`), outside the gateway.
  - States the four rules: usage context required, one settle point, caller abort is not a failure, per-call model.

### X57 · ADR-057 §5: usage metering and price coverage

- File: `~/projects/lomem/docs/adr/057-ai-tools-mcp-and-oauth-provider.md:462-532` (Lomem main branch as read on 2026-10-15)
- Implements: C22, C23, C44

```markdown
**Usage metering.** Every app records what its AI and speech calls cost in
`provider_usage_events` (foundation fragment `45-provider-usage`), one row per
billable line, in its own database. Each row answers three questions:

- *What was bought* — `capability`, a closed shared list
  (`@repo/shared/billing` → `CAPABILITIES`): `llm.text` (tokens), `voice.stt`
  (audio seconds, pronunciation assessment included) and `voice.tts`
  (characters). A person consumes a capability, not a vendor: each price key
  maps to exactly one capability by its shape (`capabilityForProviderKey`:
  `<model>:text-input` / `:text-input-cached` / `:text-output` → `llm.text`,
  `<vendor>-stt:<sku>` → `voice.stt`, `<vendor>-tts:<sku>` → `voice.tts`), so a
  provider switch changes the `provider_key` and keeps the capability. A key of
  no known shape is written with a null capability.
- *For whom* — `actor_kind`: `user` (a person using the app, `user_id` set),
  `admin` (an admin's own tooling call, under the admin's `user_id`) or
  `system` (no person: `user_id` is null and `system_reason` says why, from the
  system usage context's `reason`, else `unattributed`). `user_id` keeps
  `onDelete: Cascade`, so erasing a person erases their user and admin rows
  (ADR-037); system rows belong to no one. Admin and system spend counts in the
  app's cost and is never debited, never counted toward a person's daily spend
  cap, and never ranked among users.
- *For which feature* — `conversation_type`, the call's `feature` stored whole.
  tunatutor's labels carry a spender segment (`ai_tutor:open:tts`); its allowance
  bucket reads the base surface (`baseSurface`, ADR-013), and per-feature
  reports group by base surface too. Mealy's and Billpod's labels are flat.

**The usage writer.** Every row in every app is written by one writer,
`createProviderUsageWriter(prisma, { price?, onWriteError?, logger?, speechDebit? })`
(`@repo/shared/billing`): a duck-typed client over the fragment (ADR-003) that
prices each line from the active `provider_price_config` row for its key,
stamps its capability and actor, and inserts it. A line with no `userId` is a
`system` row. A key with no price row is written at $0 with `isEstimated` and a
`logger.warn` (once per key per miss window: a miss is remembered for 30 s, a
found price for 5 min); a price lookup that fails writes its row the same way
with `priceLookupFailed` in the metadata, so the quantity is never dropped; a
zero-quantity line is not looked up. `write` resolves to the rows written,
`record` runs detached for a hot path, and `recordSpeech(event, { userId, feature })`
turns a shared recognizer's or synthesizer's `SpeechUsageEvent` (ADR-023) into
one `speech` row, without the transcript. `price` replaces the writer's own
cached lookup: tunatutor passes the lookup its allowance settle debits by, so a row
and its debit are priced alike.

**Metering ports.** Three entry points reach the writer. The shared LLM meter,
`createProviderUsageMeter(prisma, { debit?, onWriteError?, logger?, writer? })`,
writes per call one uncached-input row, one cached-input row when part of the
prompt came from the provider's context cache, and one output row (visible
answer plus thoughts, which the provider bills as output), keyed
`<providerId>:text-input` / `:text-input-cached` / `:text-output`. A failed
attempt writes one zero-quantity error row, an aborted one its known usage (or
one zero-quantity row) with `aborted` in the metadata. A system context writes
system rows and an admin context admin rows; `debit`, the allowance hook
(ADR-013), runs for a person's own calls only. Mealy's voice records through
`recordSpeech`. tunatutor keeps its own ports — the allowance settle and guardrails
of ADR-013 — and writes through the same writer (`services/provider-costs.ts` →
`recordProviderUsageEvent`, and `recordAndConsumeProviderUsage` for its settle
with its in-memory idempotency claim); a call with no user (its voice preview,
one cached demo line per voice) is a system row there too.

**Price coverage.** A call priced at $0 is silent, so coverage is checked
three ways. Each app seeds the price rows for what it calls on boot,
inserting only a missing key (tunatutor `dev/provider-prices.ts` through
`seedProviderPriceConfigs`; Billpod and Mealy `prisma/seed/provider-prices.sql`,
run at boot); the owner changes them on the admin Billing → Provider Costs
page. Each app's price-coverage unit test requires the three LLM rows
(`llmPriceKeys`) for every model it can call — tunatutor's selectable models
(`services/llm/models.ts`) and the shared `DEFAULT_LLM_MODEL` — a row for every
speech key its code binds (`AZURE_STT_PRICE_KEY`, `AZURE_TTS_PRICE_KEY` in
`@repo/shared/speech`), and a capability for every seeded key. And tunatutor's
admin LLM settings refuse to make a model active, or enable it as a fallback,
while any of its three keys has no active row (`missingLlmPriceKeys`), naming
the missing keys.
```

- Notes:
  - Price cache: a miss is remembered 30 s, a found price 5 min.
  - The Provider Costs admin page reads cost by capability, people/admin/system spend and keys recorded at $0.

### X58 · Speech has its own settle point, modelled on the LLM one

- File: `~/projects/lomem/apps/tunatutor/backend/src/speech/speech-usage.ts:3-19` (Lomem main branch as read on 2026-10-15)
- Implements: C21

```ts
// THE settle point for speech spend — the missing sibling of
// `services/llm/index.ts`'s `settleLlmSpend`.
//
// ── Why this file exists (RC-2) ──────────────────────────────────────────
//
// Every LLM call in tunatutor converges on ONE settle site, so ~90 call sites are
// correct by construction. Speech had no equivalent: the Azure synthesizer and
// recognizer wrote a LEDGER ROW (`recordProviderUsageEvent`) and nothing
// more, while the DEBIT lived one layer up inside the tutor pipelines. The
// consequence was structural, not incidental: **every TTS/STT call made
// outside those pipelines spent real provider money and debited nothing** —
// `POST /api/language/voices/synthesize` (D3-01), the pronunciation-drill
// socket (D3-03), and any speech surface built next year.
//
// So the settle moved DOWN, next to the ledger write it belongs with. A
// recognizer or synthesizer that spends money now records AND debits in one
// place, and a new speech surface is correct because it uses one at all.
```

- Notes:
  - "Every LLM call in tunatutor converges on ONE settle site, so ~90 call sites are correct by construction."
  - Speech had no such site: TTS and STT calls outside the tutor pipelines wrote a ledger row and debited nothing; the settle moved next to the ledger write [S5].
  - Each speech settle carries an `idempotencyKey` minted from the provider's own per-call id, so a settle that arrives twice is applied once [S5, speech-usage.ts:27-28].

## Analogy to classic backend

The analogues are the researchers' own, not taken from a fetched source [S4].

| AI-side item (id) | classic Java/Spring equivalent | holds where | breaks where |
|---|---|---|---|
| Model gateway (C15) | A single outbound client bean: a `RestClient` wrapped in Resilience4j retry and time limiter, plus a circuit breaker [S1]; an API gateway plus outbound HTTP client with circuit breaker, retry and rate limiter [S4] | One place owns the key, retries, timeouts and logging for an external dependency | The price of a call is not fixed: it depends on how much text goes in and comes out, so cost is measured from every response, after the fact [S1] |
| Usage context (C16) | Requiring every call to carry a tenant id [S1] | Calls without attribution are refused, as a multi-tenant service refuses calls with no tenant | The attribution feeds per-token cost, not only access control [S1] |
| Spend cap and virtual-key budgets (C39, C48) | A per-tenant quota service [S1, S4] | A limit per tenant or team | Tunatutor's cap is checked at activity entry, never per call, so a conversation is not cut off [X29]; a proxy budget limits a whole team's key, not one conversation [S1] |
| Retry policy and backoff (C30, C32) | Resilience4j retry | Retry transient errors with a wait | Lomem's wait is linear (3 s, 6 s), honours Retry-After and Gemini's retryDelay, is capped at 30 s, and is skipped when it does not fit the budget [X23, testing] |
| Time budget (C33) | Resilience4j time limiter | A ceiling on waiting | The budget is per model; each fallback model gets a fresh one, so the worst case is budget × models [S1, X16] |
| Fallback (C27) | Failover to a replica behind a load balancer | Another target is tried when one fails | The backup is a different model, not a replica: different answers, sometimes worse, at a different price; prompts tested on one model may work less well on another [S1] |
| Picking the model (C25, C50) | Load balancing | A request is sent to one of several targets | Choosing the target is a business decision that trades quality for cost, which a load balancer never weighs [S1] |
| Sticky switch (C28) | Circuit breaker | A failing target stops being the default | Nothing tests the old model again; it leads again only after a restart or an owner action [S1] |
| Error marker row (C22) | Logging a failed outbound call | Failures are recorded | A failed attempt can still cost money: a call that times out on the caller's side may already have run and been billed, while the row shows zero tokens [S1] |
| Usage rows written detached (C20) | Async audit logging | Keeps the request path fast | For invoicing, rows must go through an outbox in the business transaction instead [S1] |
| Proxy gateway (C47) | A shared API gateway service | One service in front of many backends | It translates one request format (OpenAI's) into each provider's API [S1] |

## Pitfalls

| id | mistake | consequence | what to do instead | source |
|---|---|---|---|---|
| M1 | Client library calls scattered across services | Cost and failures cannot be seen in one place; every model change touches every service | Route every call through one gateway | S1, S2 |
| M2 | Retrying everything | A 400 or 401 fails the same way every time, and each retry may cost money | Retry only 429 and 500/502/503/504 (and network failures) | S1, X22 |
| M3 | No time budget, or one too long for the job | A chat turn that waits 120 s is broken even if the answer arrives | Size the budget to what the user can wait for, then multiply by the number of fallback models for the worst case | S1 |
| M4 | Unattributed calls | A cron job with no user id is spend no report will ever show | Require a user and feature, or a written reason for system work; refuse otherwise | S1, X4 |
| M5 | Two route files spelling one feature's label differently | One feature's cost splits across two rows nobody adds back together | Keep feature labels as constants | X52 |
| M6 | Checking a user's spending cap on every model call | A check between two calls of one chat turn can cut the turn off halfway | Check once at activity entry | S1, X28, X29 |
| M7 | Recording only successes | Failure rates disappear; timed-out calls that the provider billed are invisible | Write a zero-token error row for every failed attempt, timeouts and network errors included | S1, X26, testing |
| M8 | Recording one row per HTTP retry while also recording per model | Spend counts disagree | One settle per model attempt, retries inside it | testing, X16 |
| M9 | Pricing rows at report time from today's price table | Old rows change when prices change | Price each row when it is written | testing, X31 |
| M10 | Treating fallback as free | A fallback can move a cheap job onto a model four times as expensive | Expect fallback cost and quality changes; watch per-model spend | S1 |
| M11 | No plan for "all models failed" | The user sees an error mid-activity | Give each feature a degrade path: a pre-written line, an unscored turn, a code-only scorer | S1, X41-X44 |
| M12 | Degrading a missing usage context or a spend-cap refusal | The metering hole silently reopens, or the refused budget is burned | Rethrow undegradable errors first in any degrade `catch` | X45 |
| M13 | Reading the key in many places | Anyone holding the key spends the owner's money; rotation touches every service | Read it once when the app builds its models, keep it inside the provider | S1, X11, X20 |
| M14 | A model with no price row | Its calls are silently recorded at $0 | Seed price rows and refuse to activate an unpriced model | X36, X57 |
| M15 | Leaving thinking on for JSON calls on Gemini 2.5 | Thinking eats the output budget and truncates the JSON | Turn thinking off unless asked | X24 |
| M16 | Assuming quota or rate limits, or adding throttles, when an LLM call misbehaves | A fix aimed at the wrong cause | Capture the real response (status, `finishReason`, error body) and reproduce in isolation; act on rate limits only after an actual 429 | S5, lomem CLAUDE.md:256 |

## Misconceptions

| id | what a newcomer believed | correct statement | evidence |
|---|---|---|---|
| Q1 | Fallback just means "try the next one in the list" | A fallback model is a different model: its answers differ and its price differs | testing; S1 |
| Q2 | A model gateway is resilient HTTP plus logging, like a RestClient bean | It also prices every call from token counts, trades quality for cost when picking a model, and records failed attempts that may still have cost money | testing; S1 |
| Q3 | The rater's 2 s budget against a 3 s first wait is a contradiction | It is intended: a retry whose wait does not fit is skipped, so the rater moves to fallback unless the provider asks for a shorter wait | testing; X23; E3 |
| Q4 | Backoff is exponential, using Resilience4j | Backoff is linear (3 s × attempt), honours Retry-After and Gemini's retryDelay, and is capped at 30 s | testing; X23 |
| Q5 | A model named by the caller has no fallback | The fallback list applies even when a model is named | testing; X8 |
| Q6 | Routing to cheaper models and recording spend are optional extras | Both are gateway jobs; the smallest version records spend from token counts × prices | testing; S1 |
| Q7 | The time budget covers the whole call | In the gateway, `timeoutMs` applies to each provider; each fallback model gets a fresh budget (the level chat adds its own overall abort signal) | testing; X16; X40; E7 |
| Q8 | The active model keeps second place in the list | The list is the lead (named and enabled, else active) followed by every other enabled model in priority order | testing; X8; X9; X10 |
| Q9 | "Never retry 4xx" | 429 is a 4xx and is retried; 400, 401 and 403 are not | testing; X19; X22 |
| Q10 | Only HTTP errors need recording | Timeouts and network errors are failed attempts too and get error rows | testing; X16; X26 |
| Q11 | The sticky switch overrides a named model | It changes only calls that name no model; the rater keeps trying Flash Lite first | testing; X9; S1 |
| Q12 | The old model comes back by itself | It leads again only after a restart or when the owner sets the active model | testing; S1; X13 |
| Q13 | Spend is recorded once per HTTP retry | Spend is recorded once per model attempt, with the retries inside it | testing; X16 |
| Q14 | Rows are priced later from the price table | Rows are priced when written; a later price edit applies only to later rows | testing; X31 |
| Q15 | When every model fails, nothing is defined | The gateway throws "All LLM providers failed"; the level chat degrades to a bank line, an unscored turn, or the code-only scorer | testing; X16; X41-X44 |
| Q16 | A secret API key is only an access credential | Anyone holding the key spends the owner's money | testing; S1 |
| Q17 | Thousands of calls cost little, so cost does not matter | Costs grow with tokens and volume; a 50,000-token document sent 10,000 times a day to Flash costs $150 a day on input | testing; S1; E2; E12 |
| Q18 | "Token" in "cancellation token" is the same as a text token | A text token is a unit of model text; the cancellation handle is an `AbortSignal` | testing |
| Q19 | The gateway as described includes a circuit breaker | It has no real circuit breaker; the sticky switch is a crude one that never re-tests the old model | testing; S1 |
| Q20 | A 200 response with finish reason SAFETY makes the gateway fall back | A 2xx is a success in `run()`; no fallback; `callJson` then throws `LlmOutputError` for a blocked answer, and plain `call` returns the finish reason for the caller to read | S3 (reader question); X16; X46; X56 |
| Q21 | The failure marker row has no kind | It is keyed `<model>:text-input`, so its kind is input, with zero quantity and `is_error` | S3 (reader question); X26 |
| Q23 | Failed attempts are recorded only to show failure rates | They are also recorded because a call that timed out on the caller's side may already have run and been billed by the provider | testing; S1 |
| Q22 | Terms readers did not know (glossary gaps) | temperature (C14), judge (block evals), injected ports (C40), AbortSignal (C34), settle (C21), operation (C51), allowance (C38), daily spend cap (C39), activity (C39), OpenAI-style API (C46), caching (C8, block caching), redaction and tracing (C43, C47), model router (C50), ADR (C54), Flash tiers (C10), ledger row (C22), metering (C20), SDK (C3), backoff (C32), virtual keys (C48), candidates (C7, C26), enabled versus active model (C24), outbox (C45), circuit breaker (C29), tag (C49), text-input/text-output kinds (C22), seeded prices (C23), Lomem/tunatutor/Billpod (C53), finishReason values (C11), throttling (C31), `CLAUDE.md` (C31), model family (C10), building blocks (the series), Resilience4j time limiter (C33), time budget used in a table before it was defined (C33), the recorder versus `spend` (C20) | testing |

## Open questions

- The level chat route passes `signal: AbortSignal.timeout(timeoutMs)` as well as `timeoutMs` [X40]. A run of the real code (E7) showed that when the first model hangs, the signal fires at the budget, the gateway treats it as a caller abort, and no fallback runs. The long draft's line "the learner could have waited up to 4 s for a rating" and the "budget × models" ceiling therefore do not hold for the level chat [S1, X40, E7]. Whether this is intended is not documented.
- In the same setup, when the first model fails fast (503) the fallback model gets only what is left of the route's 2 s signal, not a fresh 2 s [X40]. A run of the real code on 2026-10-15 with Flash Lite answering 503 and a mocked Flash taking 2.5 s ended with spend events `[["gemini-2.5-flash-lite", isError true, aborted false], ["gemini-2.5-flash", isError false, aborted true]]` and a `TimeoutError`: the Flash attempt was cut by the route's signal and settled as aborted.
- tunatutor's meter writes a caller-aborted attempt with no usage as a zero-token row with `is_error = true`, because `recordLlmUsageCost` treats `!tokens` as an error and ignores `event.aborted` [S3, X26]. The shared meter writes the same event with `is_error = false` and `aborted` in metadata [X30]. The two apps disagree; ADR-057 says caller abort is not a failure [X56].
- `onSwitch` fires for any fallback win, including calls that named their model [X15, E3]. If the tutor (named Flash) fell back to Flash Lite, Flash Lite would become the in-memory active model for every unnamed call until restart. The sources describe the switch only from the rater's side [S1].
- The research cites `JUDGE_CALL` at 15 s in `level-chat/prompts.ts` lines 34-36 [S5]; the file on main has no `JUDGE_CALL` [X39]. The prompts.ts header says "three model prompts" and lists two [X39].
- The research cites ADR-057 §5 at lines 339-344 [S5]; on main §5 starts at line 383 [X56]. It cites `apps/billpod/backend/src/ai/llm.ts` lines 1-13 and 138-144 [S5]; that file has 39 lines, and it re-exports `createAppLlm`, and the gateway creation it describes is in `packages/shared/src/llm/gateway/app-llm.ts:72-82` (a 129-line file) [X50, X51].
- The research quotes Lomem's root `CLAUDE.md` at line 254; on main the rule is at line 256 [S5, lomem CLAUDE.md:256].
- The long draft says "Lomem puts the gateway in a shared package that every app calls" [S1]; ADR-057 §5 says MyTube still calls a provider directly [X56].
- The fact-check cites the image key read as "index.ts:657"; it is `apps/tunatutor/backend/src/index.ts:657`, not `services/llm/index.ts` [S3, X55].
- `/v1/chat/completions` is LiteLLM's standard path but is not shown on the linked LiteLLM page (unverified) [S3].
- About 3/4 of an English word per token, Gemini's finish-reason names, and Flash being "mid-size" were left without a source check [S3]. The finish-reason names do appear in Lomem's code [X47].
- That a request timed out on the caller's side may already have run and been billed by the provider is stated without a source (unverified) [S1].
- A price edit "applies only to rows written after it" [S1]; with a 5-minute price cache the edit can take up to 5 minutes to apply, unless the cache is invalidated [X33, X57]. Whether the admin price route calls `invalidatePriceConfigCache` was not checked.
- Readers asked whether parallel tutor and rater calls falling back to Flash add rate-limit pressure on Flash, making fallback a cause of 429s; the research did not cover it [S3].
- Readers asked why the request body is a list of messages with roles instead of one prompt string; the research did not answer it [S3].
- Portkey, Kong AI Gateway and OpenRouter are listed as tools, but the research did not describe their features [S4].
- OWASP LLM10:2025 is named as covering the cost and DoS side; its content was not read for this block [S4].
- The Java backend analogues are the researchers' own, not from a fetched source [S4].
- The long draft's Java sketch computes the default wait as `3L * attempt` with attempt starting at 1, which matches Lomem's 3 s then 6 s; the tested short version shows only the outer loop [S1, S2].
- The tested short version's Java sketch returns `new LlmAnswer(r.text(), m)` without the finish reason; the long draft returns `r.finishReason()` too [S1, S2].
- No OpenTelemetry or distributed tracing exists in Lomem; observability is pino logs, the usage ledger and the dev mirror [S5].
- The research found no feature-flag service; model on/off and priority are database config rows changed from the admin pages [S5, X37].

## Sources

| id | title | author or publisher | date | URL | what it supports |
|---|---|---|---|---|---|
| S1 | Long fact-checked draft, section 1 | this research (first workflow) | 2026-10-15 | `personal/Learning/AI-Building-Blocks/sources/sections-long/01-gateway.html` | Definitions, running example, five steps, costs, analogy, minimal and mature versions, mistakes |
| S2 | Short version tested on newcomer readers | this research (first workflow) | 2026-10-15 | `personal/Learning/AI-Building-Blocks/sources/sections-tested/01-gateway.html` | Same content, shortened; Java sketch variant |
| S3 | Testing notes for section 1 (key points, fact-check, final read) | this research (first workflow) | 2026-10-15 | `personal/Learning/AI-Building-Blocks/sources/testing-notes/01-gateway-testing.md` | Fact-check fixes, unverified items, reader questions left |
| S4 | Web research catalogue, block 1 and the request path | this research | 2026-10-15 | `personal/Learning/AI-Building-Blocks/sources/research-web.md` | New problems, minimal and mature versions, tools, request ordering, analogues |
| S5 | Lomem code map, section 1 and related sections | this research | 2026-10-15 | `personal/Learning/AI-Building-Blocks/sources/research-lomem.md` | File and line pointers, Billpod and observability facts |
| S6 | Building A Generative AI Platform | Chip Huyen | 2024-07-25 | https://huyenchip.com/2024/07/25/genai-platform.html | Step 3 "model router and gateway"; build order |
| S7 | LiteLLM proxy documentation | BerriAI (LiteLLM) | not stated | https://docs.litellm.ai/docs/simple_proxy | Proxy, one OpenAI-compatible endpoint, virtual keys, budgets, fallbacks |
| S8 | LiteLLM repository | BerriAI | not stated | https://github.com/BerriAI/litellm | Open-source proxy |
| S9 | Portkey AI gateway repository | Portkey | not stated | https://github.com/Portkey-AI/gateway | Gateway tool (listed only) |
| S10 | Kong AI Gateway | Kong | not stated | https://developer.konghq.com/ai-gateway/ | Gateway tool (listed only) |
| S11 | OpenRouter documentation | OpenRouter | not stated | https://openrouter.ai/docs | Hosted router (listed only) |
| S12 | OWASP Top 10 for LLM Applications 2025 | OWASP GenAI Security Project | 2025 | https://genai.owasp.org/llm-top-10/ | LLM10 Unbounded Consumption |
| S13 | Emerging Patterns in Building GenAI Products | Bharani Subramaniam and Martin Fowler | 2025-01-28 to 2025-02-25 | https://martinfowler.com/articles/gen-ai-patterns/ | Has nothing on gateways |
| S14 | LiteLLM caching documentation | BerriAI (LiteLLM) | not stated | https://docs.litellm.ai/docs/proxy/caching | Exact-match caching at the gateway |
| S15 | Gemini API pricing | Google | read 2026-10-03 (per the Lomem code comment) | https://ai.google.dev/gemini-api/docs/pricing | The seeded Gemini prices in X35 |
