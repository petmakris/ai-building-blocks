---
id: governance
number: 15
title: Governance and model risk
summary: Governance is the set of records and controls that let a regulated firm prove what its AI did, on whose authority and on what evidence, and it exists because the model is a third-party component nobody in the firm can inspect or reproduce, that can change without a release and that receives client data on every call.
lomem_status: partly
depends_on: [gateway, prompts, evals, observability]
related: [hitl, guardrails, structured, tools, memory, rag, agents, caching, sandbox, rollout]
---

# Governance and model risk

## Summary

Governance is the set of records and controls that let a bank or insurer answer its supervisor's questions about each AI feature: where it is used, how risky it is, what it produced on a given day, who approved it and how it was tested. It exists because the model is a third-party component that nobody in the firm can inspect, that can change without a code release, that may not give the same answer twice and that receives client data on every call. A classic Spring backend answers an auditor from git, the change ticket and the database; with a model, git does not hold the model, the provider may have moved the alias, a rerun gives a different output, and the output is lost unless it is stored on purpose. The engineering answer is an inventory with one row per use case and a risk class, a gateway that refuses unregistered calls, insert-only audit records that store the output, provider terms recorded per risk class, eval reports as validation evidence, monitoring, independent sign-off, and human approval for high-risk outputs. Lomem shows only the first step: it stamps lesson notes with a configured model name and a prompt version, and it refuses calls with no cost attribution.

## Problem

- P1 · The model belongs to a third party, and nobody in the firm can inspect it (S10, S12). A classic backend's components are code the firm can read.
- P2 · The model can change underneath the firm with no code release: a provider moves an alias to a newer build (S10, S12). In Lomem an admin screen can also switch the active model with no deployment (X13, X7).
- P3 · The model may not give the same answer twice, because it picks each word with some randomness (S10, testing). A rerun is not evidence; the output is lost unless it is stored at call time (S10).
- P4 · The model can state things that are not in its input (hallucination), and its outputs cannot be fully explained (S10, S12).
- P5 · Prompts and outputs carry client data to the provider's servers, and possibly across borders, on every call (S10, S12). The provider may keep copies under its own retention terms (S3, S10).
- P6 · Accountability is unclear when an agent acts (S12).
- P7 · Part of the specification is a plain-language prompt, so a one-word edit changes behaviour and needs the same review as code (S10, S11).
- P8 · Exact-match unit tests do not work because the output varies, so validation needs a scored test over many cases (S10).
- P9 · An internal audit asks five questions after the fact (which model and instructions, what the draft said, where the data went, how it was tested and who signed, whether it still worked), and git, the change ticket and the database cannot answer them for a model call (S10, S11).
- P10 · Firms define AI narrowly, so tools with a single model call go missing from the inventory (S1, S10).
- P11 · Providers retire old snapshots, after which calls to that name return an error (S10) (unverified: "usually months ahead" has no cited source).

## Concepts

### C1 · Model (LLM, large language model)
- Definition: A model is a program that takes text in and writes text back.
- Facts:
  - ChatGPT is a chat screen in front of a model (S10).
  - A model writes its answer one word at a time (S10).
- Relations: C1 is run by C5 (model provider); C1 is identified by C6 (model version); C1 causes C3 (non-determinism) and C4 (hallucination).

### C2 · Generative AI
- Definition: Generative AI means models that write new text, rather than only sort inputs into fixed categories.
- Facts:
  - Readers in rounds 1 and 2 did not know the term (testing).
  - A round-3 reader asked "classify what?" about the definition's "only sort inputs into fixed categories" wording (testing).
  - NIST AI 600-1 is the Generative AI Profile of the NIST AI RMF (S4, S5, S10).
- Relations: C2 is the kind of model C15 (model risk) now covers; C2 is the subject of C64 (NIST AI 600-1).

### C3 · Non-determinism (sampling randomness)
- Definition: A model picks each word with some randomness, so the same input can give a different text on the next call.
- Facts:
  - The same input can give a different text on the next call (S10).
  - The correct statement is "may not give the same answer twice", not "gives a different answer each time" (testing, round 3).
  - Because the output cannot be produced again, the audit record stores it (S10, S11).
  - Lomem's lesson-note writer calls the model with `temperature: 0.3`, so its output is sampled (X3).
- Relations: C3 causes P3; C3 is why C30 (audit record) stores the output; C3 is why C47 (eval) replaces exact-match tests.

### C4 · Hallucination
- Definition: Hallucination is the model stating things that are not in its input at all.
- Facts:
  - Hallucination is a normal failure of a model, not a bug in the calling code (S10).
  - In the running example the failure tested is an invented risk appetite: the draft states a risk appetite the client did not say (S10).
  - Round-3 readers flagged "hallucination or invented content as a normal model failure" as a concept never introduced (testing); the long draft then added it (S10).
- Relations: C4 is measured by C49 (code checks) and C50 (grader model); C4 is part of P4.

### C5 · Model provider
- Definition: A model provider is the company that runs the model on its servers and sells access over an HTTP API.
- Facts:
  - Examples are OpenAI, Anthropic and Google (S10).
  - The request, with any client data in it, travels to the provider's servers (S10, S11).
  - Under FINMA's rules the provider is managed as outsourcing (S10, S11).
  - Gemini is Google's model API, the one that reports the build in `modelVersion` (S10) and the one tunatutor calls (X13).
  - A round-1 reader did not know "Gemini" (testing).
- Relations: C5 is governed by C43 (outsourcing) and C44 (third-party risk process); C5 sets C35 (region) and C38 (abuse-monitoring logs).

### C6 · Model version
- Definition: The model version is the exact build that answered a call.
- Facts:
  - Providers publish fixed snapshots next to aliases that move to newer builds (S10).
  - The audit record stores the version the provider reports, not only the name the app asked for (S10, S11).
- Relations: C6 is named by C7 (snapshot) or C8 (alias); C6 is recorded in C30 (call row) via C34 (reported model version).

### C7 · Snapshot
- Definition: A snapshot is a fixed model build with a dated name, such as `gpt-4o-2024-08-06`.
- Facts:
  - `gpt-4o-2024-08-06` is the example snapshot (S10, S11).
  - A snapshot is like an image digest, next to the Docker tag `latest` (S10).
  - A round-2 reader did not know "digest (Docker)" (testing).
  - Snapshots have retirement dates (S10).
- Relations: C7 is used by C9 (pinning); C7 has C10 (retirement date); C7 keeps C53 (eval report) valid.

### C8 · Alias
- Definition: An alias is a model name such as `gpt-4o` that the provider moves to newer builds over time.
- Facts:
  - An alias is like the Docker tag `latest` (S10, S11).
  - An alias lets the provider replace the validated model with no change on the firm's side (S10).
  - Readers did not see on their own that the reported version matters because an alias can change (testing, round 2).
- Relations: C8 causes P2; C8 breaks C53 (eval evidence); C8 is avoided by C9 (pinning).

### C9 · Pinning
- Definition: Pinning a snapshot means the code always calls the snapshot name, never the alias.
- Facts:
  - Calling a pinned snapshot keeps the eval report valid (S10, S11).
  - With a pinned snapshot, the name sent is already exact even when a provider only echoes the name back (S10).
  - Round-3 readers flagged "pinned / pinned snapshot" as used repeatedly but never defined (testing); the long draft now defines it (S10).
  - The inventory row holds the pinned snapshot, and the gateway takes it from the row, not from the caller (S10, S11).
- Relations: C9 uses C7; C9 protects C53; C9 is stored in C23 (inventory).

### C10 · Snapshot retirement date
- Definition: The retirement date is the announced date after which a provider stops serving a snapshot and calls to that name return an error.
- Facts:
  - Providers retire old snapshots on announced dates, usually months ahead (S10) (unverified).
  - After the date, calls to that name return an error (S10).
  - The inventory row holds the snapshot's retirement date (S10, S11).
  - The gateway warns the row's owner 90 days before the date in the row (S10) (made up).
  - Round-3 readers said the consequence of calling a retired snapshot was not stated, and did not know "deprecation pages" (testing).
- Relations: C10 is held in C23; C10 triggers F8; C10 is answered by C45 (exit plan).

### C11 · Prompt
- Definition: The prompt is the text the code sends: fixed instructions written by the team, plus the case data for this request.
- Facts:
  - The prompt has two parts: fixed instructions and case data (S10, S11).
  - The gateway forwards the prompt unchanged (S10).
  - The full prompt exactly as sent is stored in the audit content store (S10).
  - Part of the specification is a plain-language prompt, so a one-word edit needs the same review as code (S10, S11).
- Relations: C11 is identified by C12 (prompt version); C11 is stored in C33; prompts.C* covers prompt management.

### C12 · Prompt version
- Definition: The prompt version is the id of the instruction file kept in git, such as `meeting-note/v7`.
- Facts:
  - Example: `meeting-note/v7` at git commit `3c9a1e0` (S10) (made up).
  - The caller sends it to the gateway in the `X-Prompt-Version` header (S10).
  - The eval must be rerun when the prompt version changes, including a one-word edit (S10, S11).
  - Lomem's lesson-note prompt version is a code constant `LESSON_NOTE_PROMPT_VERSION = "v1"` with the comment "bump when the prompt shape changes" (X2).
  - Lomem's tunatutor also keeps prompt templates in the database with archived versions and rollback (`upsertPromptTemplate`, `activatePromptTemplateVersion`) (X17, S13).
  - Admins edit those templates in `apps/tunatutor/admin/src/pages/PromptTemplatesPage.tsx`, backed by `apps/tunatutor/backend/src/routes/admin/prompt-templates.ts` (S13).
  - Lomem pins some rendered prompts byte for byte with golden tests, e.g. `apps/tunatutor/backend/src/session-types/ai-tutor/engine/scenario-prompts.golden.test.ts:1-6` (rendered at commit `6f2d612cc`); a changed prompt then fails a test (S13).
  - The research catalogue's request path fetches the system prompt from a prompt registry and records its version on the trace (S12).
- Relations: C12 is part of C30 (call row); C12 ties C53 (eval report) to a prompt; C12 is in C58 (model card).

### C13 · Use case
- Definition: A use case is one business purpose for which the firm calls a model, such as "draft the meeting note after a client call".
- Facts:
  - The use case is the unit that governance counts, classifies and controls (S10).
  - Round-1 readers flagged "use case" as used without definition (testing).
  - The caller names it in the `X-Use-Case` header (S10).
  - Examples (made up): `meeting-note-draft` (Medium), code assistant (Low), suitability letter (High), `meeting-note-eval` (Medium, the grader) (S10).
- Relations: C13 has one row in C23 (inventory); C13 has one C24 (risk class); C13 has one C58 (model card).

### C14 · Governance
- Definition: Governance is the set of records and controls that let a bank or insurer answer its supervisor's questions about each AI feature: where it is used, how risky it is, what it produced on a given day, who approved it and how it was tested.
- Facts:
  - Governance exists because the model is a third-party component nobody in the firm can inspect, that can change without a code release, that may not give the same answer twice and that receives client data on every call (S10).
  - The tested short version says the model cannot be inspected or reproduced (S11).
  - Governance lets a regulated firm prove what its AI did, on whose authority and on what evidence (S10, S11).
  - The tested short version frames the model as differing from a library in four ways: a provider runs it behind an HTTP API, snapshots sit next to moving aliases, it picks words with randomness and can state things not in its input, and its prompt is instructions plus case data (S11).
  - Round-1 readers got the core mechanics right: inventory, gateway refusal, audit record fields, residency recorded and managed as outsourcing, eval tied to model and prompt version, independent sign-off and approval of high-risk outputs (testing).
- Relations: C14 contains C23, C26, C30, C35, C47, C54, C60, C61; C14 answers P9.

### C15 · Model risk
- Definition: Model risk is the bank term for losses caused by a model that is wrong or misused.
- Facts:
  - Banks already manage model risk for credit-scoring models through model validation (S10).
  - Round-2 readers said "model risk" was in the title but never defined (testing).
  - FINMA's list names model risk as robustness, correctness, explainability and bias (S2, S12).
- Relations: C15 is managed by C16 (model validation); C15 is one item of C21 (FINMA risk list).

### C16 · Model validation
- Definition: Model validation is the bank discipline in which a team that did not build a model inspects it, re-runs it on test data and signs a report before it is used.
- Facts:
  - Model validation assumes the model can be inspected and reproduced; neither holds for a generative model (S10, S11).
  - So the firm tests from outside with evals and keeps every output (S10, S11).
  - The stored eval report, tied to the snapshot and prompt version, is the validation file (S10).
  - The research catalogue lists model validation "as banks already do it for statistical models" as a backend analogue (S12).
  - A round-2 reader did not know "model validation" as a bank discipline (testing).
- Relations: C16 is replaced in part by C47 (eval) and C53 (eval report); C16 is done by C60 (independent review).

### C17 · Supervisor and FINMA
- Definition: A supervisor is the state regulator of financial firms; in Switzerland it is FINMA, the Swiss Financial Market Supervisory Authority.
- Facts:
  - FINMA is the Swiss Financial Market Supervisory Authority (S10).
  - Round-1 readers did not know "FINMA" or "supervisor" as regulator (testing).
- Relations: C17 issued C19 (Guidance 08/2024); C17 is served by C18 (internal audit).

### C18 · Internal audit
- Definition: Internal audit is the firm's own team that checks controls on the supervisor's behalf.
- Facts:
  - In the running example internal audit asks five questions fourteen months after the call (S10).
  - Internal audit can read the audit content store (S10).
  - A round-2 reader did not know "internal audit" as a function (testing).
- Relations: C18 runs F2; C18 reads C30, C31, C33.

### C19 · FINMA Guidance 08/2024
- Definition: FINMA Guidance 08/2024, "Governance and risk management when using artificial intelligence", is FINMA's supervisory notice on AI, dated 18 December 2024.
- Facts:
  - Date: 18 December 2024 (S1, S10).
  - Switzerland has no AI-specific law (S1, S10, S11).
  - FINMA says the existing, technology-neutral rules on governance and risk management cover AI (S1, S10).
  - FINMA saw firms define AI narrowly (S1, S10).
  - Readers did not repeat that Switzerland has no AI-specific law and that existing rules apply (testing, round 1).
  - The guidance itself only mentions extra tests, controls and contract clauses for outsourcing (testing, fact-check).
  - The web research says the seven areas came from secondary sources because the official PDF did not parse; the fact-check says they were verified against the PDF (S12, testing).
- Relations: C19 lists C20 (seven areas); C19 names C22 (proportionality factors); C19 is the Swiss counterpart of C63, C65 and C66.

### C20 · FINMA's seven areas
- Definition: The seven areas are what FINMA checked at supervised firms: governance, inventory and risk classification, data quality, tests and ongoing monitoring, documentation, explainability, and independent review.
- Facts:
  - Each area maps to an engineering artefact (S10, S11); the full mapping is in the Analogy and Components sections and below.
  - Governance: FINMA looked for clear owners and extra checks when a third party supplies the AI; artefact is a named owner per use case and the provider contract on file (S10).
  - Inventory and risk classification: FINMA looked for a complete list with a broad definition of AI and a risk class per application; artefact is one inventory row per use case, enforced by the gateway (S10).
  - Data quality: FINMA looked for input data that is complete, correct and available; artefact is the row's "data sent" column plus a feature check that refuses an empty or cut-off transcript (S10).
  - Tests and ongoing monitoring: FINMA looked for quality measures and thresholds set in advance, detection of data drift, and analysis of outputs users changed; artefact is an eval report per release, weekly scores on live calls and the edit rate (S10).
  - Documentation: FINMA looked for purpose, data, model choice, limits, tests and fallback; artefact is a model card per use case (S10).
  - Explainability: FINMA looked at whether a result can be justified to the client, the auditor or FINMA; artefact is the stored input and draft, so a reviewer can check each statement against the transcript, plus who edited or approved it (S10).
  - Independent review: FINMA looked for separation between those who build and those who review; artefact is sign-off by someone outside the building team (S10).
  - Readers did not name the seven areas or the area-to-artefact mapping in rounds 1 and 2 (testing).
- Relations: C20 maps to C23, C57, C47, C54, C55, C58, C59, C60.

### C21 · FINMA's AI risk list
- Definition: FINMA's press release names the risks of AI use at supervised firms.
- Facts:
  - Model risk: robustness, correctness, explainability, bias (S2, S12).
  - Data risk (S2, S12).
  - IT and cyber risk (S2, S12).
  - Third-party dependencies (S2, S12).
  - Legal and reputational risk (S2, S12).
  - Readers in round 1 did not know robustness, stability and bias as test categories (testing).
- Relations: C21 includes C15; C21's third-party item is handled by C43.

### C22 · Proportionality (materiality factors)
- Definition: Proportionality means stronger controls only where more is at stake.
- Facts:
  - FINMA's guidance is proportional (S1, S10).
  - FINMA names the factors: which and how many clients are affected, the financial impact, and how far the output is used without a person checking it (S1, S10).
  - Short form: client impact, financial impact, whether a person checks the output (S11).
  - A firm turns these into a short rule (S10).
  - Readers in round 2 did not mention the factors and said only "High, Medium or Low" (testing).
  - Round-1 readers did not know "material application / proportional" (testing).
  - A round-2 reader said "proportional" was defined only inline (testing).
- Relations: C22 is input to C25 (firm risk rule); C22 decides C24.

### C23 · Inventory
- Definition: The inventory is a table with one row per use case.
- Facts:
  - Columns: business owner, pinned snapshot and its retirement date, data sent, provider region and retention option, who acts on the output, allowed service credentials, risk class (S10).
  - Risk or compliance owns the class definitions and approves each new row; the building team proposes the row (S10).
  - The row is made a precondition in code: the gateway refuses calls with no matching row, which keeps the inventory complete (S10, S11).
  - An internal tool with one model call belongs in the inventory (S10).
  - A credit-scoring use case would carry its EU AI Act tier in its inventory row (S10).
  - The research catalogue lists "an inventory of every AI use case, with a risk class" as minimal (S12).
  - Round-3 readers did not know "application register" (in the analogy) or "registry" (mature version) (testing).
- Relations: C23 holds C24, C9, C10, C35, C27; C23 is enforced by C26 (gateway); C23 maps to FINMA area "Inventory and risk classification" (C20); NIST "Map" (C63).

### C24 · Risk class
- Definition: The risk class is High, Medium or Low, set by a firm rule, and it decides which controls apply to a use case.
- Facts:
  - Each class carries every control of the class below it (S10).
  - "Low" means the lowest set of controls, not weak controls (testing, round 2).
  - Every class, Low included, writes the audit record (S10, testing round 3).
  - Low controls: inventory row, audit record, provider contract; provider's default region and 30-day retention allowed (S10) (made up).
  - Medium adds: Swiss or European processing region (at OpenAI this needs an approved abuse-monitoring control), eval before each release, weekly monitoring (S10) (made up).
  - High adds: zero data retention at the provider, a named approver per output, monthly monitoring report (S10) (made up).
  - The meeting note is Medium (S10, S11).
- Relations: C24 is set by C25; C24 decides C35, C39, C47, C54, C61.

### C25 · Firm risk rule
- Definition: The firm risk rule turns FINMA's proportionality factors into a short rule that assigns a class.
- Facts:
  - High if the output reaches a client or decides something about a client (credit, suitability, pricing) without a person rewriting it (S10) (made up).
  - Medium if client data is sent, but an employee reads and corrects every output before it is used (S10) (made up).
  - Low if no client data is sent and the output only helps employees (S10) (made up).
- Relations: C25 uses C22; C25 produces C24.

### C26 · Gateway (governed AI gateway)
- Definition: The gateway is a small internal service that alone holds the provider API keys and alone may open connections to the provider.
- Facts:
  - The gateway is a service, not a library (S10, testing round 2).
  - A calling service authenticates with its own service credential (S10).
  - The gateway refuses the call if no row has that use-case id with that credential, so one team cannot borrow another's id (S10).
  - The gateway takes the snapshot and region from the row, not from the caller (S10, S11).
  - The gateway forwards the prompt unchanged; what may be sent is the feature's job, described in the row (S10).
  - The gateway returns a `call_id` with the draft (S10, S11).
  - The gateway records the version the provider reports (S10).
  - If the reported version differs from the row, the gateway alerts the owner, and for a High use case it also refuses the call (S10).
  - The gateway warns the row's owner 90 days before the snapshot's retirement date (S10) (made up).
  - The gateway writes the call row (S10).
  - In the research catalogue, a gateway plus a tracing stack serves as the audit trail (LiteLLM spend logs, Langfuse) (S12).
  - Lomem's gateway refuses a call with no usage context, which is the same shape as a refusal with no inventory row, but for cost attribution (X10, S13).
- Relations: C26 enforces C23; C26 writes C30; C26 uses C27, C28; gateway.C* covers the general gateway block.

### C27 · Service credential
- Definition: A service credential is how a calling service proves who it is to the gateway, such as an OAuth client or an mTLS certificate.
- Facts:
  - It works as for any internal call (S10).
  - The inventory row lists the allowed credentials, for example `dev-tools`, `advisory-notes`, `advisory-letters` (S10) (made up).
  - Round-3 readers asked what form a service credential takes (testing); the long draft answers OAuth client or mTLS certificate (S10).
  - A round-3 reader missed that the gateway binds use-case ids to caller credentials; the fix added an "Allowed credential" column (testing).
- Relations: C27 is checked by C26 against C23.

### C28 · Gateway headers
- Definition: The caller sends three headers to the gateway: `X-Use-Case`, `X-Prompt-Version` and `X-On-Behalf-Of`.
- Facts:
  - `X-Use-Case` is the use-case id (S10).
  - `X-Prompt-Version` is the prompt version id (S10).
  - `X-On-Behalf-Of` is the logged-in user, trusted the way any downstream service trusts an authenticated caller's user claim (S10).
  - In Lomem, the usage context's `feature` plays the role of the use-case id and `userId` the role of `X-On-Behalf-Of`, but it is not bound to a caller credential (X10).
- Relations: C28 is read by C26; C28 values land in C30.

### C29 · call_id
- Definition: The `call_id` is the id the gateway returns for one model call, and every later event row points to it.
- Facts:
  - Example: `c-81f2` (S10) (made up).
  - The feature service stores the `call_id` on its note (S10).
  - Lomem's `callLLM` returns only text, so a caller cannot link later events to a call (X4).
- Relations: C29 keys C30 and C31; C29 names objects in C33.

### C30 · Audit record (call row)
- Definition: The call row is the insert-only audit row the gateway writes at call time.
- Facts:
  - Every call, in every class, writes a call row (S10, testing).
  - Fields: use case, user and service, model requested and reported, region, prompt version, pointers to the prompt and draft in the content store, time (S10).
  - The output is stored because it cannot be produced again (S10, S11).
  - A round-2 reader read an old heading, "audit record from which the output can be rebuilt", as a contradiction; the heading now says the output is stored because it cannot be produced again (testing).
  - The research catalogue's minimal version: "immutable audit log of prompt version, model version, inputs, outputs and approver" (S12).
  - The research catalogue's request path says the trace with prompt version and model version per span is also the audit log for governance (S12).
  - Lomem has no OpenTelemetry or distributed tracing; its observability is pino logs, the usage ledger and a dev-only mirror (S13).
- Relations: C30 is written by C26; C30 points into C33; C30 is followed by C31; C30 answers audit question 1.

### C31 · Event row
- Definition: An event row is an audit row a feature service inserts later, when a person edits, approves or deletes, keyed by `call_id`.
- Facts:
  - Event types in the inputs: edited, approved, deleted (S10, S11).
  - The feature service, which stored the `call_id` on the note, writes the event row (S10).
  - Example: `c-81f2 | 15:52:30 | edited | rm.jmuster | final text note/44120` (S10) (made up).
  - Readers saw a contradiction between an insert-only record and an edit 11 minutes after the call; the fix was a gateway call row plus feature-service event rows (testing, round 3).
- Relations: C31 references C29; C31 is part of C32; C31 answers part of audit question 2.

### C32 · Insert-only table
- Definition: An insert-only table accepts INSERT and never UPDATE or DELETE.
- Facts:
  - Both audit tables take INSERT only (S10, S11).
  - What happens later is a new row (S10).
  - Lomem's `tutor_lesson_notes` uses an upsert, which is the opposite pattern (X8).
  - Lomem's `provider_usage_events` has an `updatedAt` column (X12).
- Relations: C32 is the storage rule of C30 and C31; C32 is violated by C71 (upsert).

### C33 · Audit content store
- Definition: The audit content store is an encrypted bucket that holds the full prompt exactly as sent and the model's draft, and the audit tables hold pointers into it.
- Facts:
  - The bodies go in a separate store because they are large and are client data (S10).
  - Only audit, the validation team and the monitoring job's service identity can read it (S10).
  - Pointers in the example: `in/c-81f2`, `out/c-81f2` (S10) (made up).
  - The content store keeps the same retention period as the client file and is deleted with it (S10).
  - The deletion is one more event row, so a pointer that no longer resolves is explained (S10).
  - Keeping the draft next to the final text gives FINMA's "outputs users changed" signal for free (S10).
  - Round-2 readers did not know "audit content store" (testing).
  - Lomem's only copy of prompts and responses is the dev postmortem mirror: the gateway's `observe` hook writes redacted, size-capped payloads, and "All mirrors are no-ops outside dev" (`apps/tunatutor/backend/src/dev/postmortem/mirror-helpers.ts:1-4`, `:39`; S13). In production Lomem keeps no prompt or output.
- Relations: C33 is pointed to by C30; C33 is read by C54 (monitoring); C33 answers audit question 2.

### C34 · Reported model version
- Definition: The reported model version is the build the provider says answered, returned in its response.
- Facts:
  - OpenAI returns it in the `model` field (S10) (unverified: from knowledge of the API references, not a fetched page).
  - Google's Gemini API returns it in `modelVersion` (S10) (unverified, same reason).
  - Some providers only echo the name sent; with a pinned snapshot that name is already exact, and weekly monitoring is then the only way to notice a changed model (S10).
  - A round-2 reader was unsure whether Anthropic is covered (testing).
  - Lomem reads no `modelVersion`: `LLMChatResult` carries text, usage, finish reason, block reason, safety ratings and images, but no model version (X5).
- Relations: C34 is stored in C30; C34 is compared with C9 by C26.

### C35 · Data residency and region
- Definition: Data residency is where the provider stores and processes the firm's data, set at OpenAI per project and endpoint.
- Facts:
  - Where client data goes is set by the provider's terms and by the endpoint called (S10).
  - Residency and retention are provider terms that the firm checks and records per risk class (S10, S11).
  - An OpenAI project can be created with the region "Europe (EEA + Switzerland)" and called through `eu.api.openai.com`, with storage and processing in that region (S3, S10).
  - The region may process in Switzerland or in an EEA country; it does not promise Switzerland (S10, testing round 3).
  - Regional processing in Europe requires an approved control: Zero Data Retention, Modified Abuse Monitoring, Private Retention with PSP, or Safety Retention (S3, testing fact-check).
  - Data residency "does not apply to system data" (S3, S10).
  - The research catalogue names provider regional or zero-retention endpoints such as Bedrock and Azure (S12).
- Relations: C35 is recorded in C23 and C30; C35 depends on C40; C35 answers audit question 3.

### C36 · OpenAI project
- Definition: A project is a group of API keys and settings in the OpenAI account.
- Facts:
  - A project can be created with the region "Europe (EEA + Switzerland)" (S3, S10).
  - Round-2 and round-3 readers did not know the OpenAI project concept (testing).
- Relations: C36 carries C35.

### C37 · EEA
- Definition: The EEA (European Economic Area) is the EU plus Norway, Iceland and Liechtenstein.
- Facts:
  - Switzerland is not in the EEA, which is why "EEA + Switzerland" is named separately (S10).
  - Readers in rounds 1 and 2 did not know the term (testing).
- Relations: C37 is part of C35.

### C38 · Abuse-monitoring logs
- Definition: Abuse-monitoring logs are copies of requests a provider keeps to catch use that breaks its usage policy, such as generating malware or spam.
- Facts:
  - OpenAI: "By default, abuse monitoring logs are generated for all API feature usage and retained for up to 30 days." (S3, S10).
  - Readers in rounds 1 to 3 did not know the term or what counts as abuse (testing); the long draft adds malware and spam as examples (S10).
- Relations: C38 is avoided by C39 and C40; C38 is part of P5.

### C39 · Zero Data Retention (ZDR)
- Definition: Zero Data Retention is an OpenAI option that leaves the firm's content out of the abuse-monitoring logs.
- Facts:
  - ZDR is "subject to prior approval by OpenAI"; the firm applies for it (S3, S10).
  - High-class use cases require zero data retention at the provider (S10) (made up rule).
  - Readers did not know how to obtain ZDR (testing, round 2).
- Relations: C39 is one of C40's approved controls; C39 is required by C24 High.

### C40 · Modified Abuse Monitoring and other approved controls
- Definition: Modified Abuse Monitoring is an approved OpenAI control that, like ZDR, keeps customer content out of the abuse logs.
- Facts:
  - Approved controls named on the page: Zero Data Retention, Modified Abuse Monitoring, Private Retention with PSP, Safety Retention (S3, testing fact-check).
  - The Medium example row uses Modified Abuse Monitoring (S10) (made up).
  - Because the Europe region requires such a control, the 12 March transcript was kept out of the abuse logs (S10).
- Relations: C40 is required by C35 (Europe region); C40 answers audit question 3.

### C41 · System data
- Definition: System data is provider data that OpenAI says data residency does not apply to.
- Facts:
  - OpenAI: data residency "does not apply to system data" (S3, S10).
  - What system data includes is not answered (testing, final read).
- Relations: C41 limits C35.

### C42 · Training on API data
- Definition: Training on API data means a provider using the firm's requests to improve its models.
- Facts:
  - OpenAI: API data "is not used to train or improve OpenAI models" unless the firm opts in (S3, S10).
- Relations: C42 is a provider term recorded with C35.

### C43 · Outsourcing (FINMA)
- Definition: Under FINMA's rules, handing an important function to a vendor is outsourcing.
- Facts:
  - The firm vets the vendor, keeps a contract with audit rights, knows which subcontractors (such as cloud hosts) the vendor uses, and keeps an exit plan (S10) (unverified: these duties come from FINMA Circular 2018/3, not fetched).
  - The model provider is managed as outsourcing (S10, S11).
  - The provider file is the outsourcing file kept for any vendor that handles client data (S10).
  - Readers did not know outsourcing as a regulatory category, or what the outsourcing file contains (testing, round 2).
  - A round-1 reader did not know "outsourcing arrangement", "third-party risk process" or "due diligence" (testing).
- Relations: C43 is run by C44; C43 requires C45; C43 covers C5.

### C44 · Third-party risk process
- Definition: The third-party risk process is the firm's existing process, run by its third-party risk team, for managing vendors.
- Facts:
  - The third-party risk team already runs this process; engineering supplies the facts (S10).
  - The research catalogue lists vendor risk management and third-party (provider) risk management (S12).
  - Round-2 readers did not know "third-party risk team" (testing).
- Relations: C44 manages C43.

### C45 · Exit plan
- Definition: The exit plan is a second provider or snapshot the feature can switch to, with its own passing eval.
- Facts:
  - The exit plan has its own passing eval (S10, S11).
  - The smallest version keeps a one-paragraph exit plan on file (S10).
- Relations: C45 answers C10; C45 is required by C43.

### C46 · Subcontractors
- Definition: Subcontractors are the vendors the provider itself uses, such as cloud hosts.
- Facts:
  - The firm must know which subcontractors the vendor uses (S10) (unverified, Circular 2018/3).
  - Round-2 readers did not know "subcontractors the provider names" (testing).
- Relations: C46 is part of C43.

### C47 · Eval
- Definition: An eval is a test run over a fixed set of cases that produces a score against a pass bar agreed in advance.
- Facts:
  - An eval has a fixed set of cases, a scoring method and a pass bar, agreed before testing (S10).
  - The long draft says "a few hundred sample cases" and gives "99% of drafts state no risk preference the client did not express" as an example score (S10).
  - It replaces exact-match unit tests, because the output varies (S10).
  - For the meeting note the cases are 300 past transcripts, which the use-case owner's team picks and extends when a new failure is found (S10) (made up).
  - A script replaces names and account numbers with placeholders first; the checks do not depend on names (S10).
  - Round-3 readers asked how transcripts are anonymised (testing).
  - Free text is scored in three ways, often combined: code checks, a grader model, human reviewers (S10, S11).
  - Both round-1 readers found free-text scoring the hard part and could not say how to do it; one thought it was automated (testing).
  - Rerun the eval when either the snapshot or the prompt version changes, including a one-word prompt edit (S10, S11).
  - Medium and High classes require an eval before each release (S10) (made up rule).
  - The research catalogue's request path: failures flow into offline eval datasets, which gate the next prompt or model change in CI (S12).
- Relations: C47 uses C48, C49, C50, C52; C47 produces C53; evals.C* covers the general eval block.

### C48 · Pass bar
- Definition: The pass bar is the score a release must reach.
- Facts:
  - Example bar: at most 1% of drafts with an invented risk appetite (S10) (made up).
  - Monitoring uses the same 1% bar as release (S10).
  - An earlier draft had a 1% release bar and a 2% monitoring threshold; readers took it for a mistake (testing, round 2).
  - Round-2 readers did not know "pass bar" or "scoring rubric" (testing).
- Relations: C48 is part of C47 and C54.

### C49 · Code checks
- Definition: Code checks are program checks for what a program can verify in the output.
- Facts:
  - Example: every figure in the draft appears in the transcript (S10, S11).
- Relations: C49 is one scoring method of C47 and C54.

### C50 · Grader model
- Definition: A grader model is a second model call with a narrow question about a draft.
- Facts:
  - Example question: "does the draft state a risk appetite the client did not say? Answer yes or no" (S10).
  - A yes/no check is an easier task than writing the note, but it can still be wrong (S10).
  - The grader has its own inventory row, `meeting-note-eval` (Medium), used by the validation team's credential, on a pinned snapshot (S10) (made up).
  - A senior reader asked why a grader model can be trusted (testing, round 3).
- Relations: C50 needs C51; C50 is a use case in C23; evals.C21 covers LLM-as-judge and evals.C38 the grader/judge naming.

### C51 · Grader calibration
- Definition: Calibration is checking the grader's answers against human labels before trusting it.
- Facts:
  - People first label 50 cases by hand (S10, S11).
  - Bar: the grader's answer must match the human label on at least 47 of the 50 (S10) (made up).
  - If it does not, the grader's instructions are rewritten and retested (S10).
  - Readers did not retain the calibration in a usable form in round 2 (testing).
- Relations: C51 gates C50; C51 runs F5.

### C52 · Human reviewers
- Definition: Human reviewers score a sample of drafts for what neither code checks nor a grader can judge.
- Facts:
  - Human reviewers score a sample (S10, S11).
- Relations: C52 is one scoring method of C47; hitl.C* covers human review generally.

### C53 · Eval report (validation file)
- Definition: The eval report is the stored result of an eval, tied to the snapshot and prompt version it tested, and it is the validation evidence.
- Facts:
  - The stored report is the validation file (S10).
  - Eval reports tied to a model version and prompt version are the validation evidence (S10, S11, testing).
  - The report is attached to the change ticket (S10).
  - The research catalogue's mature version: "documented evals as validation evidence, plus ongoing monitoring" (S12).
  - The senior reader in round 1 dropped the point that a pinned snapshot keeps the evidence valid (testing).
- Relations: C53 is produced by C47; C53 is kept valid by C9; C53 answers audit question 4.

### C54 · Monitoring (ongoing)
- Definition: Monitoring scores a sample of live calls on a schedule against the same bar as release.
- Facts:
  - After go-live there is no correct answer to compare with (S10).
  - A weekly job reads 200 random calls from the content store and scores them with the same grader and code checks against the same 1% bar (S10) (made up numbers).
  - It also computes the edit rate (S10).
  - Either signal opens a review by the owner, who can hide the button (the fallback) until the cause is fixed (S10).
  - Medium requires weekly monitoring; High lists a monthly monitoring report (S10) (made up); readers found monthly for High backwards (testing, final read).
  - Whether the weekly grader re-sends live client transcripts to the provider, and whether that is allowed, is not answered (testing, final read).
  - The research catalogue's request path: online evals score sampled traces asynchronously (S12).
- Relations: C54 uses C50, C49, C55; C54 answers audit question 5; C54 maps to NIST "Measure" (C63).

### C55 · Edit rate
- Definition: The edit rate is the share of drafts a person changed heavily before saving, computed by diffing each stored draft with its final text.
- Facts:
  - Made-up definition: the share of notes where the relationship manager changed more than 30% of the characters (S10).
  - Made-up threshold: if the edit rate was 20% in the first month after go-live, anything above 30% raises an alert (S10).
  - A rise means the drafts got worse or the work changed (S10).
  - Round-2 readers said "edit rate" was used before it was defined and "heavily" was never defined (testing).
  - The research catalogue's feedback block logs "edit before send" against the trace id (S12).
- Relations: C55 needs C33 (stored draft) and C31 (final text); C55 is FINMA's "outputs users changed" (C20).

### C56 · Data drift
- Definition: Data drift is input data changing after go-live so the model no longer fits it.
- Facts:
  - The guidance (section 2.4) means data drift, the input data changing (testing, fact-check).
  - An earlier draft defined drift as "quality getting worse after go-live"; the fact-check corrected it (testing).
  - Round-1 readers did not know "drift / drift detection" (testing).
- Relations: C56 is part of FINMA area "Tests and ongoing monitoring" (C20); observability.C23 covers drift monitoring.

### C57 · Data quality check
- Definition: The data quality check is a check in the feature that refuses an empty or cut-off transcript before the model call.
- Facts:
  - FINMA looked for input data that is complete, correct and available (S10).
  - The row's "data sent" column describes the data (S10).
  - Lomem's note writer returns without a model call when the session is missing or the transcript is empty (X1, F10.5b).
- Relations: C57 maps to FINMA area "Data quality" (C20).

### C58 · Model card
- Definition: A model card is a one-page summary of one use case: purpose, model, prompt version, eval result, known limits and fallback.
- Facts:
  - The outside reviewer reads the model card and eval report before release (S10, S11).
  - The model card is the documentation artefact for FINMA (S10).
  - Readers in rounds 1 and 2 saw "model card" used before it was defined (testing).
  - A round-3 reader saw "RM" in the model card without the abbreviation being spelled out (testing).
- Relations: C58 maps to FINMA area "Documentation" (C20); C58 is attached to the change ticket (C60).

### C59 · Explainability
- Definition: Explainability is whether a result can be justified to the client, the auditor or FINMA.
- Facts:
  - The artefact is the stored input and draft, so a reviewer can check each statement against the transcript, plus who edited or approved it (S10).
  - Outputs cannot be fully explained (S12).
- Relations: C59 is served by C33, C31.

### C60 · Independent review (release sign-off)
- Definition: Independent review is sign-off by someone outside the building team before release.
- Facts:
  - Someone outside the building team reads the model card and eval report and records an approval on the change ticket (S10, S11).
  - Each release needs a reviewer from outside the building team (testing, key points).
  - The release approval applies to every class (S10).
  - The research catalogue lists "independent review" as mature, and "human sign-off for high-risk uses" as minimal (S12).
  - A round-3 reader assumed a release ticket is a Jira-like change ticket; the text never said (testing).
- Relations: C60 maps to FINMA "Independent review" (C20); C60 answers audit question 4.

### C61 · Run-time approval (PENDING / RELEASED)
- Definition: For the High class only, the feature saves each output with status PENDING until a named approver releases it.
- Facts:
  - It is like a payment waiting for a second signature (S10, S11).
  - The approver reads the output and releases it to the client (S10).
  - On release the service sets the note's status to RELEASED and inserts an `approved` event row with the approver's id (S10).
  - What happens when the approver rejects is not described (testing; old draft open question).
  - Whether approval (as opposed to rewriting) is enough to keep the High class is not answered (testing, final read).
- Relations: C61 is required by C24 High; C61 writes C31; hitl.C* covers approval flows.

### C62 · Fallback (feature off)
- Definition: The fallback is what the feature does when the model is taken out of use: in the example, the button is hidden and the relationship manager writes the note by hand.
- Facts:
  - The owner can hide the button until the cause is fixed (S10).
  - The fallback is listed on the model card (S10).
- Relations: C62 is triggered by C54; C62 is on C58.

### C63 · NIST AI RMF
- Definition: The NIST AI Risk Management Framework is a voluntary US framework with four functions: Govern, Map, Measure and Manage.
- Facts:
  - It is voluntary (S4, S10, testing fact-check).
  - Govern = owners and policy; Map = the inventory; Measure = evals and monitoring; Manage = acting on findings (S10).
  - Readers in every round left NIST out of their explain-back and called the paragraph name-dropping (testing).
  - Readers did not know what NIST stands for, or what the four functions mean (testing, round 2); a round-1 reader already flagged the four functions as listed but not explained (testing).
  - After round 3 the NIST and EU AI Act part was cut to three sentences that keep the four functions, AI 600-1, the high-risk examples and the 2 Dec 2027 date (testing).
  - The research catalogue's mature version: "a risk framework mapped to NIST AI RMF and its GenAI profile" (S12).
- Relations: C63 has C64 (profile); C63 maps to C23, C47, C54, C14.

### C64 · NIST AI 600-1 (Generative AI Profile)
- Definition: NIST AI 600-1 is the Generative AI Profile of the NIST AI RMF, which adds risks specific to text-writing models.
- Facts:
  - Published 26 July 2024 (S5, S12).
  - Round-2 and round-3 readers did not know "Generative AI Profile" or "NIST AI 600-1" (testing).
- Relations: C64 is part of C63.

### C65 · EU AI Act
- Definition: The EU AI Act is the EU law that sorts AI systems into risk tiers.
- Facts:
  - Credit scoring of individuals and pricing of life and health insurance are high-risk (S6, S10).
  - Those duties apply from 2 December 2027 (S6, S10).
  - They also apply to a Swiss firm offering such a system in the EU; non-EU providers are covered (S6, S10, testing fact-check).
  - The research catalogue's mature version lists "EU AI Act classification" (S12).
  - Readers in round 1 did not know "Annex III"; the long draft dropped it (testing).
- Relations: C65's tier is stored in C23; C65 overlaps C24.

### C66 · SR 26-2 (US)
- Definition: SR 26-2 is a US Federal Reserve supervisory letter on model risk.
- Facts:
  - Dated 17 April 2026 (S8, S12).
  - It replaces SR 11-7 and SR 21-8 (S8, S12).
  - The old SR 11-7 URL returns 404 (S12).
  - Whether it covers generative or agentic AI is unverified; commentators disagree, and the attachment was not read (S12).
- Relations: C66 is the US counterpart of C19.

### C67 · ISO/IEC 42001
- Definition: ISO/IEC 42001 is a management-system standard for AI.
- Facts:
  - The research catalogue lists an "ISO/IEC 42001 management system" as mature (S12).
  - The ISO page returned 403 to automated requests and was not read (S9, S12).
  - Round-1 readers did not know the term (testing).
- Relations: C67 is a mature option next to C63.

### C68 · Cost attribution (Lomem usage context)
- Definition: Cost attribution means every model call states who pays for it, and a call with no attribution is refused.
- Facts:
  - Lomem's shared gateway refuses a call with no usage context (`MissingUsageContextError`) (X10, S13).
  - A system call with no user must give a reason (X10, X11).
  - Spend lands in `provider_usage_events` with provider key, tokens, cost, latency and error flag, but no prompt or output (X12).
  - The motive is cost visibility, not regulation; the mechanism is the one governance needs (X11).
  - A usage row proves a call happened, not what it said (S10).
  - In round 1 both readers thought a Lomem cost-attribution snippet was meant to show the audit record (testing).
  - ADR-057 §5: "`callJson` settles before it validates, so a wrong answer is still recorded" (`docs/adr/057-ai-tools-mcp-and-oauth-provider.md:419-420`; S13, S15).
  - Billpod reports spend under fixed feature labels `["capture", "assistant", "paperwork", "avatar"]` (`apps/billpod/backend/src/ai/llm.ts:15`; S13), the nearest Lomem thing to a list of use cases.
- Relations: C68 is the Lomem shape of C26's refusal; C68 is not C30 (no content); observability.C37 covers the usage ledger.

### C69 · Token
- Definition: A token is the unit of text a model reads, writes and is billed in.
- Facts:
  - Readers in round 1 flagged "token" ("how many tokens") as undefined (testing).
  - Lomem's ledger writes separate rows for uncached input, cached input and output tokens (S13).
- Relations: C69 is counted in C68's usage rows; gateway.C6 and caching.C1 define it fully.

### C70 · Running-example domain terms
- Definition: The running example is a Swiss private bank whose relationship managers get model-drafted meeting notes from transcribed client calls.
- Facts:
  - Relationship manager (RM): the adviser who looks after the client (S10).
  - Risk appetite: how much loss the client says they can accept (S10).
  - Suitability letter: a letter to the client explaining why a product fits the client (S10).
  - Transcript: the written text of a recorded call, produced by a speech-to-text service (S10).
  - Readers did not know "relationship manager", "risk appetite", "suitability text" (round 1), "suitability" (round 2), "RM" (round 3), or how a transcript is produced (round 3) (testing).
  - The tested short version says "the client's adviser" instead of relationship manager (S11).
- Relations: C70 is the setting of F1, F2, F7 and E1-E8.

### C71 · Upsert
- Definition: An upsert inserts a row, or updates it if a row with the same key exists.
- Facts:
  - Lomem saves the lesson note with an upsert keyed on `conversationSessionId`, so a later write for the same session overwrites the earlier note (X8, testing fact-check).
  - Tunatutor has no user edit of lesson notes; the overwrite comes from a second write for the same session (testing, fact-check).
  - A bank that let people edit drafts the same way would lose the model's original (S10).
  - Round-2 readers did not know "upsert" (testing).
- Relations: C71 violates C32; C71 loses audit question 2.

### C72 · Injected dependency (`deps.model`)
- Definition: `deps.model` is the model name injected into Lomem's note-writer dependencies; the Java equivalent is a constructor-injected field.
- Facts:
  - `deps.model` is `getActiveProvider().modelId`, the model name the app was configured with (X3, testing fact-check).
  - It is taken when the job's dependencies are built, before the call (X3).
  - Round-2 readers said the TypeScript dependency-injection idiom was not obvious to a Java reader (testing).
- Relations: C72 is the Lomem stand-in for C34, and is weaker (requested, not reported).

### C73 · Lomem
- Definition: Lomem is a set of personal apps by the author of this guide; its tutoring app is tunatutor.
- Facts:
  - Lomem is personal software, not a regulated system (inferred from S10's description).
  - Round-1 readers did not know "Lomem", "cron" or "content scripts" (a term in a code comment) (testing).
  - In round 3 neither reader repeated the Lomem gap (configured name, not reported version; upsert overwrites) and both called it a detour; the excerpt was cut to the two lines `lesson-note-writer.ts:224-225` and the gap kept as two sentences (testing).
  - The fact-check confirmed the excerpt `lesson-note-writer.ts:224-225` verbatim and that `deps.model` is `getActiveProvider().modelId` (testing).
  - The tested short version does not name Lomem; it says "a small codebase of apps" (S11).
- Relations: C73 provides X1-X21.

### C74 · Backend-analogue terms from the research
- Definition: The research catalogue names classic controls that governance resembles.
- Facts:
  - SOX or ISO audit trails (S12).
  - Change-advisory boards (S12).
  - Data-processing agreements (S12).
  - Vendor risk management (S12).
  - Model validation as banks already do it for statistical models (S12).
  - Round-1 readers did not know SOX, change-advisory board or data-processing agreement (testing).
  - The web research marks the backend analogues as its author's own, not taken from a fetched source (S12).
- Relations: C74 is detailed in the Analogy section.

### C75 · Earlier-draft terms flagged by readers
- Definition: These terms appeared in earlier drafts and were flagged as unknown; the final drafts dropped or defined them.
- Facts:
  - "Unstructured data" (testing, round 1).
  - "Degree of autonomy" (testing, round 1).
  - "Override rate" (testing, round 1); the final drafts use the edit rate instead (S10).
  - "Records policy / retention period" (testing, round 1); the final draft says the content store keeps the client file's retention period (S10).
  - "Release ticket" and "change ticket" (testing, rounds 2 and 3).
  - "Snapshot retirement" and "deprecation pages" (testing, rounds 2 and 3).
  - "Risk appetite" and "suitability text" (testing, round 1).
  - `actor_kind` in a code snippet (testing, round 1); it is the column that says whether a usage row is for a user, an admin or the system (X12).
  - "Sources" in "stored prompt, sources and output" (testing, round 1).
- Relations: C75 feeds the Misconceptions section.

## Components

| id | name | role | inputs | outputs | where it lives |
|---|---|---|---|---|---|
| K1 | Relationship manager | Adviser who presses "draft note", edits and saves the note | client call, draft | edited final note | made-up bank (S10) |
| K2 | Speech-to-text service | Turns each recorded client call into a written transcript | call recording | transcript | made-up bank (S10) |
| K3 | advisory-notes service | Feature service: checks the transcript, calls the gateway, stores the `call_id` on the note, saves the final text, inserts event rows | transcript, RM action | gateway request, note, event rows | made-up bank (S10) |
| K4 | AI gateway | Internal service that alone holds the provider keys; checks the inventory row for use case and credential; takes snapshot and region from the row; records the reported version; writes the call row; returns `call_id` | service credential, `X-Use-Case`, `X-Prompt-Version`, `X-On-Behalf-Of`, prompt | provider call, call row, content-store objects, `call_id` + draft, alerts | made-up bank (S10); generic |
| K5 | Inventory table | One row per use case: owner, snapshot and retirement date, data sent, region and retention option, who acts on the output, allowed credentials, risk class | proposals from building team, approval by risk/compliance | row lookups for the gateway | made-up bank (S10) |
| K6 | Model provider (OpenAI) | Runs the model; Europe (EEA + Switzerland) region at `eu.api.openai.com`; snapshot `gpt-4o-2024-08-06` | prompt | draft, reported `model` field | OpenAI (S3, S10) |
| K7 | Audit content store | Encrypted bucket for the full prompt as sent and the draft; readable only by audit, the validation team and the monitoring job's identity | prompt, draft | objects `in/<call_id>`, `out/<call_id>` | made-up bank (S10) |
| K8 | Audit call table | Insert-only table of call rows written by the gateway | gateway writes | rows for audit and monitoring | made-up bank (S10) |
| K9 | Audit event table | Insert-only table of edited, approved and deleted events keyed by `call_id`, written by feature services | feature-service writes | rows for audit and edit rate | made-up bank (S10) |
| K10 | Eval runner | Runs the 300-case eval with code checks, grader and human sample | cases, snapshot, prompt version | eval report | made-up bank, validation team (S10) |
| K11 | Grader model | Second model call with a yes/no question; own inventory row `meeting-note-eval` (Medium), validation team's credential, pinned snapshot | draft, transcript | yes/no | provider via gateway (S10) |
| K12 | Weekly monitoring job | Reads 200 random calls from the content store, scores them, computes the edit rate, opens reviews | content store, event rows | weekly scores, alerts | made-up bank (S10) |
| K13 | Use-case owner | Named owner (e.g. Head of Advisory Tools); gets alerts; can hide the button | alerts, reviews | fallback decision | made-up bank (S10) |
| K14 | Outside reviewer | Someone outside the building team who reads model card and eval report and approves the change ticket | model card, eval report | approval on change ticket | made-up bank (S10) |
| K15 | Named approver | Releases High-class outputs from PENDING | PENDING output | release, `approved` event row | made-up bank (S10) |
| K16 | Risk or compliance | Owns the class definitions and approves each new inventory row | proposed row | approved row | made-up bank (S10) |
| K17 | Third-party risk team | Runs vendor vetting, contract with audit rights, subcontractor list and exit plan | facts from engineering | outsourcing file | made-up bank (S10) |
| K18 | Internal audit | Checks controls on the supervisor's behalf; asks the five questions | complaint | answers from K8, K9, K7, K5, eval report, monitoring | made-up bank (S10) |
| K19 | Change ticket | Release record that carries the eval report, model card and the outside approval | eval report, model card | approval record | made-up bank (S10) |
| K20 | Model card | One page per use case: purpose, model, prompt version, eval result, limits, fallback | eval report, row | documentation | made-up bank (S10) |
| K21 | Prompt files in git | Versioned instruction files, e.g. `meeting-note/v7` at commit `3c9a1e0` | edits | prompt version id | made-up bank (S10) |
| K22 | advisory-letters service | Feature service for the High suitability letter; saves output PENDING | RM request, gateway draft | PENDING letter, RELEASED letter, event row | made-up bank (S10) |
| K23 | ai-tutor finalization (`checkpointAiTutorSession`) | Enqueues the lesson-note job once at session end | finalized session | `TutorLessonNoteWrite` job | `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-finalization.ts` (X15) |
| K24 | Abandoned-session reaper | Enqueues the same job for abandoned or paused sessions with the same idempotency key | abandoned sessions | `TutorLessonNoteWrite` job | `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-abandoned-reaper.ts` (X16) |
| K25 | Job queue | Runs `TutorLessonNoteWrite` jobs; enqueue is idempotent on `(type, idempotencyKey)` | jobs | handler call | `~/projects/lomem/apps/tunatutor/backend/src/services/jobs/`; handler registered at `apps/tunatutor/backend/src/index.ts:555` |
| K26 | processTutorLessonNoteJob | Note writer: reads session and transcript, builds prompt, calls model, parses, saves note with `writerModel` and `writerPromptVersion` | job payload | `tutor_lesson_notes` row | `~/projects/lomem/apps/tunatutor/backend/src/services/tutor-continuity/lesson-note-writer.ts` (X1-X3) |
| K27 | LLM registry | Holds enabled providers, priority and the active provider; refuses activating an unpriced model | admin settings, DB config | `getActiveProvider()`, `getEnabledProviders()` | `~/projects/lomem/apps/tunatutor/backend/src/services/llm/registry.ts` (X14) |
| K28 | Lomem LLM gateway | Refuses unattributed calls, picks the lead provider, falls back, settles spend once per attempt | usage context, request | provider result, spend events | `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts`, `apps/tunatutor/backend/src/services/llm/index.ts` (X6, X7, X10) |
| K29 | Gemini API | Tunatutor's provider (`gemini-2.5-flash`, `gemini-2.5-flash-lite`) | prompt | text, usage | Google; ids in `apps/tunatutor/backend/src/services/llm/models.ts` (X13) |
| K30 | provider_usage_events | Cost rows, one per billable line per provider attempt; no prompt or output | spend events | cost reports, caps | `~/projects/lomem/packages/shared/prisma/foundation/45-provider-usage.prisma` (X12) |
| K31 | tutor_lesson_notes | One note per session with `writer_model` and `writer_prompt_version`; upserted | note writer | notes for later sessions | `~/projects/lomem/apps/tunatutor/backend/prisma/schema.prisma` (X9) |
| K32 | prompt_templates | DB prompt templates with archived versions and rollback | admin edits | active template | `~/projects/lomem/apps/tunatutor/backend/src/services/prompt-templates.ts` (X17) |
| K33 | Tracing stack as audit trail | Gateway spend logs plus traces that carry prompt and model version per span | gateway and spans | audit log | generic: LiteLLM spend logs, Langfuse (S12) |
| K34 | Governance registry | One place where audit browses rows, model cards and eval reports | rows, cards, reports | browsable registry | generic; Modulos named as a vendor (S10, S12) |

## Flows

### F1 · Meeting-note draft through the governed gateway
- Purpose: produce a model draft while keeping the inventory complete and writing a full audit record.
- Trigger: the relationship manager presses the "draft note" button after a client call.
- Values: made up (S10).

- F1.1 · RM → advisory-notes: press "draft note" for the 12 March call | condition: after a recorded call | data: call id | ref: S10
- F1.2 · advisory-notes → advisory-notes: data-quality check on the transcript | condition: always | data: transcript | ref: S10, C57
- F1.2b · if the transcript is empty or cut off, advisory-notes refuses and no gateway call is made → ends | ref: S10
- F1.3 · advisory-notes → gateway: request authenticated with service credential `advisory-notes` (OAuth client or mTLS), headers `X-Use-Case: meeting-note-draft`, `X-Prompt-Version: meeting-note/v7`, `X-On-Behalf-Of: rm.jmuster` | condition: transcript passed | data: prompt (instructions + transcript) | ref: S10, C28
- F1.4 · gateway → inventory: look up the row for (use case, credential) | condition: always | data: use-case id, credential | ref: S10
- F1.4b · if no row has that use-case id with that credential, gateway → advisory-notes: refused; nothing is sent to the provider → ends | ref: S10, S11 (whether a refusal row is written is not described)
- F1.5 · inventory → gateway: row `meeting-note-draft`, Medium, snapshot `gpt-4o-2024-08-06`, region `eu.api.openai.com`, Modified Abuse Monitoring | condition: row found | data: row | ref: S10, E2
- F1.6 · gateway → OpenAI: model call with the snapshot and region taken from the row, prompt forwarded unchanged | condition: row found | data: prompt, client transcript | ref: S10
- F1.7 · OpenAI → gateway: draft and reported `model: gpt-4o-2024-08-06` | condition: success | data: draft, reported version | ref: S10, C34
- F1.7b · if the reported version differs from the row and the class is Medium or Low, gateway → owner: alert; the call continues → continues at F1.8 | ref: S10
- F1.7c · if the reported version differs from the row and the class is High, gateway → owner: alert, and gateway → caller: refused → ends | ref: S10
- F1.7d · if the provider only echoes the requested name, the gateway cannot see a changed model; only weekly monitoring (F6) can notice it → continues at F1.8 | ref: S10
- F1.8 · gateway → content store: put prompt as sent at `in/c-81f2` and draft at `out/c-81f2` | condition: accepted | data: prompt, draft | ref: S10, E1
- F1.9 · gateway → call table: INSERT call row `c-81f2` at 2025-03-12 15:41:07 | condition: always after F1.8 | data: use case, credential, user, requested and reported model, region, prompt version, pointers | ref: S10, E1
- F1.10 · gateway → advisory-notes: `call_id` `c-81f2` and the draft | condition: success | data: call_id, draft | ref: S10
- F1.11 · advisory-notes → RM: draft shown for editing; the note keeps the `call_id` | condition: always | data: draft | ref: S10
- F1.12 · RM → advisory-notes: save the edited note at 15:52:30 | condition: RM edits | data: final text | ref: S10
- F1.13 · advisory-notes → notes store: store final text `note/44120`; the draft stays untouched in the content store | condition: always | data: final text | ref: S10, M3
- F1.14 · advisory-notes → event table: INSERT event row (`c-81f2`, 15:52:30, edited, `rm.jmuster`, final text `note/44120`) | condition: always | data: event | ref: S10, E1

### F2 · Internal audit answers the five questions
- Purpose: answer an auditor's questions about one past output.
- Trigger: fourteen months after the call, a client complains that a risky product was sold against their wishes.
- Values: made up (S10).

- F2.1 · internal audit → advisory-notes: which call produced note `note/44120` | condition: complaint | data: note id | ref: S10
- F2.2 · advisory-notes → internal audit: `call_id` `c-81f2` stored on the note | condition: always | data: call_id | ref: S10
- F2.3 · internal audit → call table: read call row `c-81f2` | condition: always | data: reported model version `gpt-4o-2024-08-06`, prompt version `meeting-note/v7` | ref: S10 (answers question 1)
- F2.4 · internal audit → git: open `meeting-note/v7` at commit `3c9a1e0` | condition: always | data: instructions | ref: S10 (answers question 1)
- F2.5 · internal audit → content store: read `out/c-81f2` | condition: content not yet deleted | data: draft before edits | ref: S10 (answers question 2)
- F2.5b · if the retention period has ended, the pointer no longer resolves, and a deletion event row explains why → continues at F2.6 | ref: S10
- F2.6 · internal audit → event table: read events for `c-81f2` | condition: always | data: edited by `rm.jmuster`, final text `note/44120` | ref: S10 (answers question 2)
- F2.7 · internal audit → call table + inventory: read region `eu.api.openai.com` and retention option Modified Abuse Monitoring | condition: always | data: region, retention | ref: S10, E6 (answers question 3)
- F2.8 · internal audit → change ticket: read the eval report for `gpt-4o-2024-08-06` + `meeting-note/v7` and the outside approval | condition: always | data: report, approver | ref: S10 (answers question 4)
- F2.9 · internal audit → monitoring records: read March weekly scores and edit rate | condition: always | data: scores, edit rate | ref: S10 (answers question 5)

### F3 · New use case enters the inventory
- Purpose: register and classify a use case before any call is allowed.
- Trigger: a building team wants to call a model for a new business purpose.
- Values: rule made up (S10).

- F3.1 · building team → risk/compliance: propose an inventory row | condition: always | data: owner, data sent, snapshot and retirement date, region and retention option, who acts on the output, allowed credentials | ref: S10
- F3.2 · risk/compliance → risk/compliance: apply the firm rule to the proportionality factors | condition: always | data: client impact, financial impact, whether a person checks the output | ref: S10, C25
- F3.3 · risk/compliance → inventory: class Low | condition: no client data sent and output only helps employees | data: Low controls | ref: S10
- F3.3b · risk/compliance → inventory: class Medium | condition: client data sent, but an employee reads and corrects every output | data: Medium controls (adds region, eval, weekly monitoring) | ref: S10
- F3.3c · risk/compliance → inventory: class High | condition: output reaches a client or decides about a client (credit, suitability, pricing) without a person rewriting it | data: High controls (adds zero retention, named approver, monthly report) | ref: S10
- F3.4 · risk/compliance → inventory: approve and add the row | condition: approved | data: row | ref: S10
- F3.4b · if a credit-scoring use case, the row also carries its EU AI Act tier | ref: S10, C65
- F3.4c · if rejected, no row exists and the gateway refuses every call for that use case | ref: inferred from S10 (rejection path not described)
- F3.5 · third-party risk team → outsourcing file: check provider contract, region, retention, subcontractors, exit plan for the row's class | condition: new provider or new terms | data: provider facts from engineering | ref: S10

### F4 · Release of a prompt or snapshot change
- Purpose: keep the validation evidence true when the prompt or the model changes.
- Trigger: any prompt edit (even one word) or any snapshot change.
- Values: made up (S10).

- F4.1 · building team → git: commit the new prompt file; new prompt version id | condition: prompt edit | data: prompt | ref: S10
- F4.2 · building team → eval runner: run the 300-case eval on the pinned snapshot with the new prompt version | condition: always | data: cases, snapshot, prompt version | ref: S10
- F4.3 · eval runner → anonymiser script: replace names and account numbers with placeholders | condition: always | data: transcripts | ref: S10
- F4.4 · eval runner → gateway → grader: one grader call per draft, under row `meeting-note-eval` and the validation team's credential | condition: grader calibrated (F5) | data: draft, transcript | ref: S10
- F4.5 · eval runner → eval runner: code checks and a human sample | condition: always | data: drafts | ref: S10
- F4.6 · eval runner → change ticket: eval report tied to snapshot and prompt version | condition: score within the 1% bar | data: report | ref: S10, E3
- F4.6b · if the score is above the bar, the release is blocked; the team fixes the prompt → continues at F4.1 | ref: S10 (blocked path inferred from the pass bar)
- F4.7 · building team → change ticket: attach the updated model card | condition: passed | data: model card | ref: S10, E7
- F4.8 · outside reviewer → change ticket: read model card and eval report, record approval | condition: reviewer is outside the building team | data: approval | ref: S10
- F4.8b · if the reviewer does not approve, no release → ends | ref: inferred from S10
- F4.9 · building team → inventory + production: release; the row's snapshot and prompt version are the validated ones | condition: approved | data: release | ref: S10

### F5 · Grader calibration
- Purpose: decide whether a grader model can be trusted before it scores evals and monitoring.
- Trigger: a new grader or a change to the grader's instructions.
- Values: made up (S10).

- F5.1 · people → label set: label 50 cases by hand (does the draft state a risk appetite the client did not say?) | condition: always | data: 50 drafts | ref: S10
- F5.2 · eval runner → grader: ask the same yes/no question on the 50 cases | condition: always | data: drafts | ref: S10
- F5.3 · eval runner → eval runner: count matches with the human labels | condition: always | data: 50 pairs | ref: S10
- F5.4 · grader: is accepted | condition: at least 47 of 50 match | data: none | ref: S10, E4
- F5.4b · if fewer than 47 match, the grader's instructions are rewritten and retested → continues at F5.2 | ref: S10

### F6 · Weekly monitoring
- Purpose: show the feature still works as tested after go-live.
- Trigger: weekly schedule.
- Values: made up (S10).

- F6.1 · monitoring job → content store: read 200 random calls from the week | condition: always | data: prompts, drafts | ref: S10
- F6.2 · monitoring job → gateway → grader: score each draft with the same grader; run the same code checks | condition: always | data: drafts | ref: S10
- F6.3 · monitoring job → event table + notes: diff each stored draft with its final text; compute the edit rate | condition: always | data: drafts, final texts | ref: S10, E5
- F6.4 · monitoring job → monitoring records: store the weekly score and edit rate | condition: invented-content share at most 1% and edit rate at most 30% | data: scores | ref: S10
- F6.4b · if the invented-content share is above 1%, monitoring job → owner: open a review → continues at F6.5 | ref: S10
- F6.4c · if the edit rate is above 30% (first-month baseline 20%), monitoring job → owner: open a review → continues at F6.5 | ref: S10
- F6.5 · owner → advisory-notes: hide the button (fallback); RMs write notes by hand | condition: review open and cause unknown | data: switch | ref: S10, C62
- F6.6 · owner → building team: find the cause (drafts got worse, or the work changed); fix through F4 | condition: always | data: findings | ref: S10
- F6.7 · owner → advisory-notes: show the button again | condition: fix released | data: switch | ref: inferred from S10 ("until the cause is fixed")

### F7 · High-class suitability letter waits for a named approver
- Purpose: stop a high-risk output from reaching a client unchecked.
- Trigger: an RM requests a suitability letter (High class).
- Values: made up (S10).

- F7.1 · RM → advisory-letters: request a suitability letter | condition: always | data: portfolio, client profile | ref: S10
- F7.2 · advisory-letters → gateway: call with credential `advisory-letters` and the suitability use-case id | condition: always | data: prompt | ref: S10, E2
- F7.3 · gateway → provider: call with zero data retention, snapshot from the row | condition: row found | data: prompt | ref: S10
- F7.4 · provider → gateway: draft and reported version | condition: success | data: draft | ref: S10
- F7.4b · if the reported version differs from the row, gateway refuses (High) and alerts the owner → ends | ref: S10
- F7.5 · gateway → content store + call table: store content, INSERT call row; return `call_id` and draft | condition: accepted | data: as F1.8-F1.10 | ref: S10
- F7.6 · advisory-letters → letters store: save the output with status PENDING; nothing is sent | condition: always | data: letter | ref: S10
- F7.7 · named approver → advisory-letters: read and release | condition: approver agrees | data: approver id | ref: S10
- F7.7b · if the approver rejects, the outcome is not described in the inputs | ref: testing (open question)
- F7.8 · advisory-letters → letters store: set status RELEASED | condition: released | data: status | ref: S10
- F7.9 · advisory-letters → event table: INSERT `approved` event row with the approver's id | condition: released | data: event | ref: S10
- F7.10 · advisory-letters → client: send the letter | condition: RELEASED | data: letter | ref: S10

### F8 · Snapshot retirement and exit plan
- Purpose: avoid errors when a provider retires a pinned snapshot.
- Trigger: the retirement date in an inventory row comes within 90 days.
- Values: 90 days made up (S10).

- F8.1 · gateway → owner: warning 90 days before the row's retirement date | condition: date in row | data: row, date | ref: S10
- F8.2 · owner → building team: switch to the exit-plan snapshot or provider | condition: always | data: target model | ref: S10, C45
- F8.3 · building team → eval runner: run the eval on the new snapshot → as F4.2-F4.9 | condition: always | data: cases | ref: S10
- F8.4 · building team → inventory: update the row's snapshot and retirement date | condition: eval passed and approved | data: row | ref: S10
- F8.4b · if no switch happens before the date, calls to that name return an error | ref: S10 (unverified timing claim)

### F9 · Content deletion at the end of retention
- Purpose: delete client data with the client file and keep the audit trail explainable.
- Trigger: the client file's retention period ends.
- Values: none given (S10).

- F9.1 · records process → content store: delete `in/<call_id>` and `out/<call_id>` | condition: client file retention ended | data: content | ref: S10
- F9.2 · records process → event table: INSERT a deletion event row for the `call_id` | condition: always | data: event | ref: S10
- F9.3 · later readers: see a call row whose pointer no longer resolves, explained by the deletion event | condition: always | data: none | ref: S10

### F10 · Lomem lesson-note write (real code)
- Purpose: write a private lesson note at the end of a tutor session, stamped with a model name and prompt version.
- Trigger: a tutor session is finalized, or the reaper finds an abandoned session with no note.
- Values: real (X1-X16).

- F10.1 · ai-tutor finalization → job queue: `enqueueJob({ type: JobType.TutorLessonNoteWrite, idempotencyKey: "lesson-note:<sessionId>", payload })` | condition: session finalized | data: session uuid, user id, language | ref: X15
- F10.1b · if enqueue throws, finalization logs "lesson note enqueue skipped" and continues; no note | ref: X15
- F10.1c · abandoned-session reaper → job queue: enqueues the same job type with the same key for abandoned or paused sessions → continues at F10.2 | ref: X16
- F10.1d · if a job with the same `(type, idempotencyKey)` already exists, the enqueue is idempotent and no second job runs | ref: X16 (comment)
- F10.2 · job queue → note writer: `processTutorLessonNoteJob(payload)` | condition: job runs | data: payload | ref: `apps/tunatutor/backend/src/index.ts:555`, X1
- F10.3 · note writer → registry: `defaultNoteWriterDeps()` reads `getActiveProvider().modelId` into `model` | condition: always | data: configured model id | ref: X3
- F10.3b · if the registry is not initialised, `model` stays `"unknown"` and a debug line is logged | ref: X3
- F10.4 · note writer → database: `getSessionMeta(uuid)` | condition: always | data: session meta | ref: X1
- F10.4b · if no session, return; no model call, no note → ends | ref: X1
- F10.5 · note writer → database: `getTranscript(uuid)` | condition: session found | data: messages | ref: X1
- F10.5b · if the transcript is missing or empty, return; no model call, no note → ends | ref: X1
- F10.6 · note writer → note writer: `buildNoteWriterPrompt` with the last 40 messages (`TRANSCRIPT_WINDOW = 40`) | condition: transcript found | data: prompt | ref: `apps/tunatutor/backend/src/services/tutor-continuity/lesson-note-writer.ts:23`, `:101`
- F10.7 · note writer → Lomem gateway: `callLLM(NOTE_WRITER_SYSTEM_PROMPT, [prompt], 800, { json: true, temperature: 0.3, usageContext })` with `userUsageContext(userId, "lesson_note_writer", sessionUuid)` | condition: always | data: prompt | ref: X1, X3
- F10.8 · Lomem gateway → Lomem gateway: `assertLlmUsageContext` | condition: always | data: usage context | ref: X10
- F10.8b · if the usage context is missing, has no feature, is a system context with no reason, or has a user id that is not a positive integer, throw `MissingUsageContextError` → continues at F10.14b | ref: X10
- F10.9 · Lomem gateway → Gemini: call the lead provider (`resolveLeadProvider`: the caller's model if enabled, else the active provider) | condition: context valid | data: prompt | ref: X18, X6
- F10.10 · Gemini → Lomem gateway: text and usage | condition: lead answers | data: text, usage | ref: X6
- F10.10b · if the lead fails and fallback is on, the gateway tries the next enabled provider; the sticky switch changes the active provider in memory; `writerModel` will still name the lead (derived from reading the code, not observed) → continues at F10.11 | ref: X6, X7
- F10.11 · Lomem gateway → provider_usage_events: spend rows for each attempt (provider key, tokens, cost, latency, error flag), no prompt or output | condition: each attempt | data: usage | ref: X7, X12, S13
- F10.12 · Lomem gateway → note writer: text only (`callLLM` returns `.text`) | condition: success | data: text | ref: X4
- F10.13 · note writer → note writer: `OutputSchema.parse(extractJSON(raw))`; sanitize fields | condition: always | data: parsed note | ref: X1
- F10.13b · if parsing fails, throw → continues at F10.14b | ref: X1
- F10.14 · note writer → database: `upsertLessonNote` with `writerModel: deps.model`, `writerPromptVersion: "v1"`; create on the first write for the session, update (overwrite) on a later one | condition: parsed | data: note, stamps, promises | ref: X1, X8, X9
- F10.14b · on any error above (bad payload, missing session, malformed output, DB error), catch and log "tutor lesson-note write failed (non-fatal)"; no note → ends | ref: X1
- F10.15 · note writer → database: resolve open promises the session addressed | condition: any to resolve | data: promise ids | ref: X1

### F11 · Lomem admin switches the active model (real code)
- Purpose: let an admin change which model answers, without a code release, while refusing an unpriced model.
- Trigger: an admin makes a model active or enables it as a fallback in the admin LLM settings.
- Values: real (X13, X14).

- F11.1 · admin → admin LLM settings: choose `gemini-2.5-flash` or `gemini-2.5-flash-lite` | condition: always | data: model id | ref: X13
- F11.2 · admin route → registry: `assertModelPriced(id)` | condition: the id names a known provider, on `PUT /llm/active-provider` or when a model is enabled | data: model id | ref: X14, `apps/tunatutor/backend/src/routes/admin/index.ts:279`, `:302`
- F11.2b · if any of the model's `:text-input`, `:text-input-cached`, `:text-output` keys has no active price row, throw `ValidationError` → ends | ref: X14
- F11.3 · registry → database: `setActiveProvider(id)` sets the in-memory active id and upserts app setting `llm.activeProvider` | condition: priced, switching the active model | data: model id | ref: `apps/tunatutor/backend/src/services/llm/registry.ts:185-197`, `routes/admin/index.ts:282`
- F11.3b · admin route → registry: enabling or reprioritising a model goes through `updateModelConfig(id, { enabled, priority })` instead | condition: enable or priority edit | data: enabled, priority | ref: `registry.ts:141`, `routes/admin/index.ts:305`
- F11.3c · if the id names no known provider, `setActiveProvider` or `updateModelConfig` throws "Unknown provider" and the route answers `ValidationError` → ends | ref: `registry.ts:186-188`, `:145-147`, `routes/admin/index.ts:281-285`
- F11.4 · next call: the gateway re-reads providers from the registry on every call, so the change takes effect at once | condition: always | data: none | ref: X7
- F11.5 · note: no eval, no review and no inventory row gate this switch; the model behind every feature can change with no release | condition: always | ref: inferred from X7, X13, X14 (contrast with F4)

### F12 · Provider retention for one request (OpenAI terms)
- Purpose: show what OpenAI keeps of one request under each term.
- Trigger: a request reaches OpenAI.
- Values: real terms (S3).

- F12.1 · gateway → OpenAI: request with client data | condition: always | data: prompt | ref: S3
- F12.2 · OpenAI → abuse-monitoring logs: keep a copy for up to 30 days | condition: default terms (Low row) | data: request content | ref: S3, S10
- F12.2b · if Zero Data Retention or Modified Abuse Monitoring (or Private Retention with PSP, or Safety Retention) is approved, content is kept out of the abuse logs → continues at F12.3 | ref: S3, testing fact-check
- F12.3 · OpenAI: API data is not used for training unless the firm opts in | condition: no opt-in | data: none | ref: S3
- F12.4 · OpenAI Europe region: storage and processing in Europe (EEA + Switzerland), not promised in Switzerland; residency does not apply to system data | condition: Europe-region project | data: content | ref: S3, S10

## States

### L1 · Inventory row
- States:
  - NONE: no row; the gateway refuses every call for this use case and credential.
  - PROPOSED: the building team has proposed the row.
  - ACTIVE: risk or compliance approved the row and its class; calls are allowed.
  - RETIREMENT_WARNED: the gateway warned the owner that the row's snapshot retires within 90 days.
  - BROKEN: the snapshot's retirement date passed with no switch; provider calls return an error.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| NONE | building team proposes a use case | none | PROPOSED | row drafted with all columns | S10 |
| PROPOSED | risk or compliance approves | class set by the firm rule | ACTIVE | gateway accepts calls with an allowed credential | S10 |
| PROPOSED | rejected | none | NONE | calls stay refused | inferred (not described) |
| ACTIVE | prompt or snapshot change | eval passed and outside approval | ACTIVE | row updated to the new validated version | S10 |
| ACTIVE | 90 days before retirement date | date in row | RETIREMENT_WARNED | owner alerted | S10 (90 days made up) |
| RETIREMENT_WARNED | switch to exit-plan snapshot or provider | its own eval passed | ACTIVE | row updated | S10 |
| RETIREMENT_WARNED | retirement date passes | no switch | BROKEN | calls to the name return an error | S10 (unverified) |

### L2 · Audit trail of one call (insert-only)
- States:
  - REFUSED: the gateway refused the call (no row, or High with a version mismatch); nothing was sent.
  - RECORDED: call row inserted and prompt and draft in the content store.
  - EDITED: an `edited` event row exists.
  - APPROVED: an `approved` event row exists (High only).
  - CONTENT_DELETED: a deletion event row exists; content-store pointers no longer resolve.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| (start) | call arrives | no row for use case + credential | REFUSED | no provider call; whether a row is written is not described | S10 |
| (start) | provider answers | High and reported version differs | REFUSED | owner alerted | S10 |
| (start) | provider answers | accepted | RECORDED | INSERT call row; put `in/` and `out/` objects | S10 |
| RECORDED | person saves an edited version | feature stored the `call_id` | EDITED | INSERT `edited` event row with final text pointer | S10 |
| RECORDED | named approver releases | class High | APPROVED | INSERT `approved` event row with approver id | S10 |
| RECORDED, EDITED, APPROVED | client file retention ends | none | CONTENT_DELETED | content deleted; INSERT deletion event row | S10 |

### L3 · High-class output
- States:
  - PENDING: saved, not sent to the client.
  - RELEASED: a named approver released it; sent to the client.
  - not described: the approver rejected it; what follows is not described in the inputs (open question).

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| (start) | feature saves model output | class High | PENDING | nothing sent | S10, S11 |
| PENDING | named approver releases | approver is named | RELEASED | status RELEASED; `approved` event row with approver id; letter sent | S10 |
| PENDING | approver rejects | none | not described | not described | testing (open question) |

### L4 · Feature release and live operation
- States:
  - CHANGE_PROPOSED: a prompt edit or snapshot change exists and is not validated.
  - EVAL_FAILED: the eval score is above the pass bar.
  - EVAL_PASSED: the eval report is within the bar and stored.
  - LIVE: released after outside approval.
  - UNDER_REVIEW: monitoring opened a review by the owner.
  - FALLBACK: the button is hidden; people do the work by hand.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| CHANGE_PROPOSED | eval run | score above 1% | EVAL_FAILED | release blocked | S10 (blocked path inferred) |
| CHANGE_PROPOSED | eval run | score within 1% | EVAL_PASSED | report tied to snapshot + prompt version | S10 |
| EVAL_FAILED | prompt fixed | none | CHANGE_PROPOSED | rerun | S10 |
| EVAL_PASSED | outside reviewer approves change ticket | reviewer outside building team | LIVE | model card and report on ticket | S10 |
| LIVE | any prompt edit (even one word) or snapshot change | none | CHANGE_PROPOSED | eval must rerun | S10, S11 |
| LIVE | weekly score above 1% or edit rate above 30% | none | UNDER_REVIEW | owner notified | S10 |
| UNDER_REVIEW | owner hides the button | cause not fixed | FALLBACK | RMs write notes by hand | S10 |
| FALLBACK | fix released through F4 | eval and approval | LIVE | button shown again | inferred from S10 |

### L5 · Grader
- States:
  - UNCALIBRATED: not yet compared with human labels.
  - CALIBRATED: matched at least 47 of 50 human labels; may score evals and monitoring.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| UNCALIBRATED | compare with 50 human labels | at least 47 match | CALIBRATED | grader used | S10 (made up) |
| UNCALIBRATED | compare with 50 human labels | fewer than 47 match | UNCALIBRATED | instructions rewritten and retested | S10 |
| CALIBRATED | grader instructions change | none | UNCALIBRATED | retest | inferred from S10 |

### L6 · One request at OpenAI
- States:
  - SENT: the request reached OpenAI.
  - IN_ABUSE_LOGS: a copy is kept for abuse monitoring.
  - GONE: the abuse-log copy has expired.
  - NOT_LOGGED: content kept out of the abuse logs (system data excepted).

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| SENT | default terms | no approved control | IN_ABUSE_LOGS | copy retained | S3, S10 |
| IN_ABUSE_LOGS | time passes | up to 30 days | GONE | copy removed | S3, S10 |
| SENT | approved ZDR or Modified Abuse Monitoring (or Private Retention with PSP, Safety Retention) | OpenAI approval | NOT_LOGGED | no copy in abuse logs; residency does not cover system data | S3, S10, testing |

### L7 · Lomem lesson note (real code)
- States:
  - NOT_WRITTEN: no note for the session (no session, empty transcript, or an error).
  - WRITTEN: one row for the session, stamped with the active provider id at job start and `"v1"`.
  - OVERWRITTEN: a later write for the same session replaced content, model and prompt version.
  - DELETED: removed by cascade with the user or the session.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| NOT_WRITTEN | job runs | session and transcript found, output parses | WRITTEN | upsert create; `writer_model`, `writer_prompt_version` set | X1, X8 |
| NOT_WRITTEN | job runs | no session, empty transcript, or any error | NOT_WRITTEN | warning or nothing logged | X1 |
| WRITTEN | another write for the same `conversationSessionId` | none | OVERWRITTEN | upsert update; earlier content and stamps lost; no `updatedAt` column | X8, X9 |
| WRITTEN, OVERWRITTEN | user or session deleted | none | DELETED | `onDelete: Cascade`; ADR-037 complete erasure | X9, S14 |

### L8 · Model name over time
- States:
  - PINNED_SNAPSHOT: calls name a dated snapshot; the build does not change.
  - ALIAS: calls name an alias; the provider may move it to a newer build.
  - RETIRED: the snapshot is retired; calls error.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| ALIAS | provider moves the alias | none | ALIAS | a different build answers; eval evidence no longer matches | S10 |
| PINNED_SNAPSHOT | retirement date passes | none | RETIRED | calls to the name return an error | S10 (unverified) |
| ALIAS | team pins a snapshot | eval passes on it | PINNED_SNAPSHOT | evidence stays valid | S10 |

## Worked examples

### E1 · Audit rows for the 12 March call
- Values: made up (S10).
- Inputs: RM `rm.jmuster` presses "draft note" via service `advisory-notes`; use case `meeting-note-draft` (Medium); prompt `meeting-note/v7` (git commit `3c9a1e0`).
- Steps:
  - F1.9 · call row: `call_id` `c-81f2`, time 2025-03-12 15:41:07; use case `meeting-note-draft` (Medium); credential `advisory-notes`; user `rm.jmuster`; model requested `gpt-4o-2024-08-06`, reported `gpt-4o-2024-08-06`; region `eu.api.openai.com`; prompt version `meeting-note/v7` (git commit `3c9a1e0`); prompt sent at `in/c-81f2`, draft at `out/c-81f2`.
  - F1.14 · event row: `c-81f2`, 15:52:30, edited, by `rm.jmuster`, result final text `note/44120`.
- Outcome: the call row answers question 1; the content store and the event row answer question 2. The edit came 11 minutes 23 seconds after the call and is a separate row, so the tables stay insert-only.

### E2 · Three inventory rows
- Values: made up (S10).
- Inputs: the firm rule in C25.
- Steps (F3.3):
  - Code assistant: data sent source code only; allowed credential `dev-tools`; class Low; controls inventory row, audit record, provider contract; provider's default region and 30-day retention allowed.
  - Meeting-note draft: data sent client call transcript; allowed credential `advisory-notes`; class Medium; controls plus Swiss or European processing region (at OpenAI this needs an approved abuse-monitoring control), eval before each release, weekly monitoring.
  - Suitability letter (why a product fits the client), sent to the client: data sent portfolio and client profile; allowed credential `advisory-letters`; class High; controls plus zero data retention at the provider, a named approver per output, monthly monitoring report.
- Outcome: each class carries every control of the class below it; every class writes the audit record.

### E3 · Release eval result
- Values: made up (S10).
- Inputs: 300 past transcripts; bar 1%; grader question about invented risk appetite.
- Steps:
  - F4.4 · the grader flags 1 of the 300 drafts.
  - F4.6 · 1 / 300 = 0.3%, which is under the 1% bar; the report is stored against `gpt-4o-2024-08-06` and `meeting-note/v7`.
- Outcome: the release can proceed to outside review; the report must be rerun on any snapshot or prompt change.

### E4 · Grader calibration
- Values: made up (S10).
- Inputs: 50 hand-labelled cases; bar 47 matches.
- Steps:
  - F5.3 · count matches between grader and human label.
  - F5.4 · 47 or more matches: grader accepted. F5.4b · fewer: instructions rewritten and retested.
- Outcome: "47 of 50" means the grader's answer matches the human label in 47 cases (94%).

### E5 · Edit-rate threshold
- Values: made up (S10).
- Inputs: edit-rate definition "share of notes where the RM changed more than 30% of the characters"; first-month edit rate 20%.
- Steps:
  - F6.3 · weekly edit rate computed from stored drafts and final texts.
  - F6.4c · anything above 30% raises an alert.
- Outcome: a rise from 20% to above 30% means the drafts got worse or the work changed; the owner reviews and may hide the button.

### E6 · Answer to audit question 3
- Values: made-up bank, real OpenAI terms (S3, S10).
- Inputs: Medium row; region Europe (EEA + Switzerland) via `eu.api.openai.com`; Modified Abuse Monitoring.
- Steps:
  - F2.7 · region read from the call row; retention option read from the inventory row.
  - F12.2b · the Europe region requires an approved control, so the transcript was kept out of the abuse logs.
- Outcome: the transcript was processed in OpenAI's Europe region, which may be in Switzerland or in an EEA country; the Medium rule allows either; OpenAI holds no copy. Under the Low row's default terms a copy would sit in the abuse logs for up to 30 days.
- History: an earlier answer said the EU-region transcript sat in the 30-day abuse log; the fact-check found that impossible (testing).

### E7 · Model card for the meeting note
- Values: made up (S10).
- Card:
  - Use case: `meeting-note-draft` (Medium), owner: Head of Advisory Tools.
  - Model: `gpt-4o-2024-08-06` via `eu.api.openai.com`, Modified Abuse Monitoring.
  - Prompt: `meeting-note/v7`.
  - Eval: 300 transcripts, invented risk appetite 0.3% (bar 1%).
  - Limits: Swiss German dialect calls are transcribed less accurately and score worse; the relationship manager must edit every note.
  - Fallback: button hidden, relationship manager writes the note by hand.
- History: an earlier card said "30-day abuse log"; it now says "Modified Abuse Monitoring" (testing, fact-check).

### E8 · The five audit questions and their answers
- Values: made up (S10).
- Steps and outcome:
  - Question 1, which model and instructions: call row, reported model version and prompt version (F2.3, F2.4).
  - Question 2, what the draft said: content store via the call row's pointer; the event row links the final text (F2.5, F2.6).
  - Question 3, where the transcript went: region in the call row; the provider's retention option (Modified Abuse Monitoring) in the inventory row, so no copy remains (F2.7, E6).
  - Question 4, how it was tested and who signed: eval report for that snapshot and prompt version; approval on the change ticket (F2.8).
  - Question 5, whether it still worked: weekly monitoring scores and edit rate for March (F2.9).
- Without governance: git holds the code but not the model; the provider may have moved the alias; a rerun gives a different draft; the draft was never stored; nobody checked the retention terms (S10).

### E9 · Lomem stamps a lesson note (real code)
- Values: real (X1-X3, X13).
- Inputs: a finalized tutor session; registry active provider `gemini-2.5-flash` (the default that seeds a fresh database).
- Steps:
  - F10.3 · `deps.model` = `getActiveProvider().modelId` = `gemini-2.5-flash` (or `"unknown"` without a registry).
  - F10.7 · `callLLM(..., 800, { json: true, temperature: 0.3, usageContext })`.
  - F10.14 · note saved with `writerModel: "gemini-2.5-flash"`, `writerPromptVersion: "v1"`.
- Outcome: the note carries the configured model name, not a provider-reported version.

### E10 · Failing case: Lomem stamp can be wrong or lost (derived from code)
- Values: real code, scenario derived by reading (not observed at run time).
- Steps:
  - F10.3 · the stamp is taken before the call.
  - F10.10b · if the lead provider fails and another enabled provider answers, the note still names the lead.
  - F10.14 · a second write for the same session updates the row, so the earlier content and its stamps are gone.
- Outcome: audit question 1 could get a wrong answer, and question 2 no answer, if Lomem's pattern were used in a bank.

### E11 · Failing case: validating against an alias
- Values: made up (S10).
- Steps: the eval passed on last quarter's model under an alias; the provider moved the alias; production now runs a newer build under the same name.
- Outcome: the eval report no longer describes the running model; pinning a snapshot prevents it.

## Variants and options

- Minimal version:
  - An inventory table (S10, S11).
  - A gateway that holds the keys and refuses unregistered calls (S10, S11).
  - Insert-only call and event tables and an encrypted content store (S10).
  - The provider's region, retention and a one-paragraph exit plan on file (S10).
  - One eval report and model card attached to each change ticket (S10).
  - The smallest version fits in a sprint (S10).
  - The research catalogue's minimal list: an inventory of every AI use case with a risk class; an immutable audit log of prompt version, model version, inputs, outputs and approver; data residency and zero-retention terms with the provider; human sign-off for high-risk uses (S12).
- Mature version:
  - One registry where audit browses rows, model cards and eval reports (S10).
  - Monitoring that opens reviews automatically (S10).
  - A validation team independent of the builders (S10).
  - Periodic provider reviews (S10).
  - The research catalogue's mature list: a risk framework mapped to NIST AI RMF and NIST AI 600-1; documented evals as validation evidence plus ongoing monitoring; independent review; third-party (provider) risk management; EU AI Act classification; an ISO/IEC 42001 management system (S12).

| id | option | when to choose | cost / risk |
|---|---|---|---|
| V1 | Pin a dated snapshot | Always for a validated use case | Must track retirement dates and rerun evals on every switch (S10) |
| V2 | Call an alias | Not for validated use cases | The provider can swap the validated model with no change on the firm's side (S10) |
| V3 | Record the provider-reported version | Whenever the provider returns one (OpenAI `model`, Gemini `modelVersion`) | Some providers only echo the name; then only monitoring catches a change (S10) |
| V4 | Record only the requested or configured name (Lomem) | Cost tracking or personal apps | Wrong if an alias moved or a fallback answered (X3, X6) |
| V5 | Gateway alerts on version mismatch and continues | Medium and Low rows | Unclear whether the draft is still covered by the eval report (testing, final read) |
| V6 | Gateway refuses on version mismatch | High rows | Calls fail until the row or snapshot is fixed (S10) |
| V7 | Store prompt and output in a separate encrypted content store, pointers in the audit tables | Bodies are large client data | Access control and retention to manage; deletion must be an event row (S10) |
| V8 | Keep only usage or cost rows | Cost governance only | Proves a call happened, not what it said (S10, X12) |
| V9 | Overwrite the draft with the edited version (upsert) | Never for audited outputs | Destroys the answer to audit question 2 (S10, X8) |
| V10 | Provider default terms (30-day abuse logs, default region) | Low: no client data | Copies kept for up to 30 days (S3, S10) |
| V11 | Europe (EEA + Switzerland) region with an approved control (Modified Abuse Monitoring or ZDR) | Medium: client data, employee corrects every output | Needs OpenAI approval; may process in an EEA country, not promised in Switzerland; system data excepted (S3, S10) |
| V12 | Zero Data Retention | High | Subject to OpenAI's prior approval (S3, S10) |
| V13 | Code checks | What a program can verify (figures appear in transcript) | Cannot judge meaning (S10) |
| V14 | Grader model | Narrow yes/no questions at scale | Can be wrong; needs calibration (47 of 50) and its own inventory row (S10) |
| V15 | Human reviewers | What neither code nor grader can judge | Slow; scores only a sample (S10) |
| V16 | Run-time approval (PENDING) | High class only | Each output waits for a named approver (S10) |
| V17 | Hide the button (fallback) | Monitoring signal open and cause unknown | People do the work by hand (S10) |
| V18 | Exit plan: second provider or snapshot | Snapshot retirement or provider loss | Needs its own passing eval (S10) |
| V19 | Prompt version as a hand-bumped code constant (Lomem `"v1"`) | Small codebases | Nothing forces a bump when the text changes (X2) |
| V20 | Prompt version as a git-versioned instruction file id (`meeting-note/v7`) | Regulated use cases | Every edit needs a new id, eval and review (S10) |
| V21 | Prompt templates in the database with archived versions and rollback (Lomem) | Admin-editable prompts | Admin edits change behaviour without a release (X17, S13) |

| name | open source or hosted | what it does here | link |
|---|---|---|---|
| LiteLLM (spend logs) | open source | Gateway whose spend logs serve as part of the audit trail | https://github.com/BerriAI/litellm (S12) |
| Langfuse | open source | Tracing stack used as the audit trail | https://github.com/langfuse/langfuse (S12) |
| AWS Bedrock | hosted | Provider regional or zero-retention endpoints | not given in the inputs (S12) |
| Azure (OpenAI service) | hosted | Provider regional or zero-retention endpoints | not given in the inputs (S12) |
| OpenAI API data controls | hosted | Europe (EEA + Switzerland) region, ZDR, Modified Abuse Monitoring | https://developers.openai.com/api/docs/guides/your-data (S3) |
| Modulos | hosted (vendor) | Governance registry; the reference found is a vendor's page | https://docs.modulos.ai/frameworks/owasp-top-10-agentic (S12; the page cited in the research is about OWASP agentic risks) |
| NIST AI RMF | framework (public) | Voluntary risk framework: Govern, Map, Measure, Manage | https://www.nist.gov/itl/ai-risk-management-framework (S4) |
| ISO/IEC 42001 | standard (paid) | AI management-system standard | https://www.iso.org/standard/42001 (S9; returned 403, not read) |

## Facts and numbers

| id | fact | value | source id | verified |
|---|---|---|---|---|
| N1 | Date of FINMA Guidance 08/2024 | 18 December 2024 | S1 | yes |
| N2 | Areas FINMA checked | 7 | S1, S10 | yes (fact-check; S12 says secondary sources) |
| N3 | AI-specific law in Switzerland | none | S1 | yes |
| N4 | OpenAI default abuse-monitoring log retention | up to 30 days | S3 | yes |
| N5 | OpenAI Zero Data Retention | subject to prior approval | S3 | yes |
| N6 | OpenAI training on API data | not used unless the customer opts in | S3 | yes |
| N7 | OpenAI Europe region name | "Europe (EEA + Switzerland)" | S3 | yes |
| N8 | OpenAI Europe endpoint | `eu.api.openai.com` | S3, S10 | yes |
| N9 | Approved controls required for Europe regional processing | ZDR, Modified Abuse Monitoring, Private Retention with PSP, Safety Retention | S3 | yes (fact-check) |
| N10 | Data residency exception | "does not apply to system data" | S3 | yes |
| N11 | EEA members | EU plus Norway, Iceland, Liechtenstein | S10 | yes |
| N12 | NIST AI RMF functions | 4: Govern, Map, Measure, Manage | S4 | yes |
| N13 | NIST AI RMF status | voluntary | S4 | yes |
| N14 | NIST AI 600-1 publication date | 26 July 2024 | S5 | yes |
| N15 | EU AI Act high-risk duties for credit scoring and life/health insurance pricing apply from | 2 December 2027 | S6 | yes |
| N16 | SR 26-2 date | 17 April 2026 | S8 | yes |
| N17 | SR 26-2 replaces | SR 11-7 and SR 21-8 | S8 | yes |
| N18 | SR 11-7 old URL | returns 404 | S12 | yes |
| N19 | SR 26-2 covers generative or agentic AI | unknown | S12 | unverified |
| N20 | Example snapshot name | `gpt-4o-2024-08-06` | S10 | yes (real name; use in the bank is made up) |
| N21 | Example alias | `gpt-4o` | S10 | yes |
| N22 | Snapshot retirement notice | usually months ahead | S10 | unverified |
| N23 | Gateway retirement warning lead time | 90 days | S10 | made up |
| N24 | Running example: time between call and complaint | 14 months | S10 | made up |
| N25 | Audit questions | 5 | S10 | made up |
| N26 | Eval case set | 300 past transcripts | S10 | made up |
| N27 | Eval pass bar | 1% invented risk appetite | S10 | made up |
| N28 | Eval result | 1 of 300 = 0.3% | S10 | made up |
| N29 | Long draft's example eval score | "99% of drafts state no risk preference the client did not express" | S10 | made up |
| N30 | Grader calibration set | 50 hand-labelled cases | S10 | made up |
| N31 | Grader calibration bar | at least 47 of 50 match | S10 | made up |
| N32 | Weekly monitoring sample | 200 random calls | S10 | made up |
| N33 | Monitoring bar | same 1% as release | S10 | made up |
| N34 | Edit definition | more than 30% of characters changed | S10 | made up |
| N35 | First-month edit rate | 20% | S10 | made up |
| N36 | Edit-rate alert threshold | above 30% | S10 | made up |
| N37 | Earlier draft's monitoring threshold (dropped) | 2% | testing | made up |
| N38 | High monitoring report cadence | monthly | S10 | made up |
| N39 | Medium monitoring cadence | weekly | S10 | made up |
| N40 | Example call time | 2025-03-12 15:41:07 | S10 | made up |
| N41 | Example edit time | 15:52:30 (11 minutes after the call) | S10, testing | made up |
| N42 | Example git commit of the prompt | `3c9a1e0` | S10 | made up |
| N43 | Gateway headers | 3: `X-Use-Case`, `X-Prompt-Version`, `X-On-Behalf-Of` | S10 | made up design |
| N44 | Risk classes | 3: High, Medium, Low | S10 | made up rule |
| N45 | Scoring methods for free text | 3: code checks, grader, human reviewers | S10 | yes (as described) |
| N46 | Lomem lesson-note prompt version | `"v1"` | X2 | yes |
| N47 | Lomem note-writer transcript window | last 40 messages | lesson-note-writer.ts:23 | yes |
| N48 | Lomem note-writer max tokens | 800 | lesson-note-writer.ts:24 | yes |
| N49 | Lomem note-writer temperature | 0.3 | X3 | yes |
| N50 | Lomem `writerModel` placeholder without registry | `"unknown"` | X3 | yes |
| N51 | Lomem tunatutor models | `gemini-2.5-flash`, `gemini-2.5-flash-lite` | X13 | yes |
| N52 | Lomem tunatutor default model | `gemini-2.5-flash` | X13 | yes |
| N53 | Lomem price keys required per model | 3: `:text-input`, `:text-input-cached`, `:text-output` | X14 | yes |
| N54 | Lomem usage cost unit | USD micros (millionths of a dollar) | X12 | yes |
| N55 | Lomem `actor_kind` values | `user`, `admin`, `system` | X12 | yes |
| N56 | Lomem lesson-note idempotency key prefix | `lesson-note:` | lesson-note-writer.ts:18 | yes |
| N57 | ADR-037 date | 2026-06-19 | S14 | yes |
| N58 | Readers' scores, round 1 | senior clarity 8, self-contained 6, examples 7; skimmer 7, 6, 7; both failed | testing | yes |
| N59 | Readers' scores, round 2 | senior 8, 7, 9; skimmer 7, 7, 8; both failed | testing | yes |
| N60 | Readers' scores, round 3 | senior 8, 7, 9; skimmer 7, 7, 8; both failed | testing | yes |
| N61 | Source links in the drafts that resolve | 4 (FINMA, OpenAI, NIST AI RMF, EU AI Act summary) | testing | yes (fact-check) |

## Code in Lomem

All excerpts: Lomem main branch as read on 2026-10-15 (commit `8e3f5d5db`). "..." marks elided lines; nothing else is changed.

### X1 · The note writer job: read session and transcript, call the model, stamp and save the note
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/tutor-continuity/lesson-note-writer.ts:185-235` (Lomem main branch as read on 2026-10-15)
- Implements: C72, C71, C57, F10.2-F10.15, L7

```ts
export async function processTutorLessonNoteJob(
  payloadRaw: unknown,
  override: Partial<NoteWriterDeps> = {},
): Promise<void> {
  try {
    const payload = PayloadSchema.parse(payloadRaw);
    const deps: NoteWriterDeps = { ...defaultNoteWriterDeps(), ...override };

    const meta = await deps.getSessionMeta(payload.conversationSessionUuid);
    if (!meta) return;

    const transcript = await deps.getTranscript(payload.conversationSessionUuid);
    if (!transcript || transcript.length === 0) return;

    const openPromises = await deps.loadOpenPromises(payload.userId, payload.language, deps.now());

    const prompt = buildNoteWriterPrompt({
      transcript,
      nativeLanguage: meta.nativeLanguage,
      rolePlay: meta.rolePlay,
      openPromises,
      existingTopicSummary: meta.existingTopicSummary ?? null,
    });
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
}
```

- Notes:
  - Lines 224-225 are the two lines both drafts quote: `writerModel: deps.model` and `writerPromptVersion: LESSON_NOTE_PROMPT_VERSION`.
  - The model name and prompt version travel with the output; this is the first step of an audit record (S10).
  - Only sanitised, parsed fields are saved; the raw model output and the prompt sent are not kept anywhere (old draft reading; consistent with X8, X9).
  - Lines 194 and 197 return early with no model call when the session is missing or the transcript is empty: a data-quality guard (C57).
  - The usage context `userUsageContext(payload.userId, "lesson_note_writer", ...)` attributes the cost to the learner (C68).
  - Every failure is caught and logged as non-fatal (line 233), so a failed note leaves no row and no audit trace beyond a log line.

### X2 · The prompt version is a hand-bumped code constant
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/tutor-continuity/lesson-note-writer.ts:17-24` (Lomem main branch as read on 2026-10-15)
- Implements: C12, V19, F10.6

```ts
/** Idempotency-key prefix for the enqueue call site (Task 7) — `${LESSON_NOTE_KEY_PREFIX}${sessionUuid}`. */
export const LESSON_NOTE_KEY_PREFIX = "lesson-note:";
/** Stamped onto every note as `writerPromptVersion` — bump when the prompt shape changes. */
export const LESSON_NOTE_PROMPT_VERSION = "v1";

/** Only the last N transcript messages are fed to the writer — long sessions are token-bounded (design doc §5). */
const TRANSCRIPT_WINDOW = 40;
const NOTE_WRITER_MAX_TOKENS = 800;
```

- Notes:
  - `LESSON_NOTE_PROMPT_VERSION = "v1"`: the comment says to bump it "when the prompt shape changes"; nothing forces a bump when the text changes.
  - The bank version ties the id to an instruction file in git (`meeting-note/v7`) and to a commit (S10).
  - `TRANSCRIPT_WINDOW = 40` and `NOTE_WRITER_MAX_TOKENS = 800` bound what is sent.

### X3 · The model name is read from the registry before the call, not from the response
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/tutor-continuity/lesson-note-writer.ts:273-284 and 308-318` (Lomem main branch as read on 2026-10-15)
- Implements: C72, C34 (contrast), F10.3, F10.3b, F10.7

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

  return {
...
    saveNote: upsertLessonNote,
    generate: (prompt, usage) =>
      callLLM(NOTE_WRITER_SYSTEM_PROMPT, [{ role: "user", content: prompt }], NOTE_WRITER_MAX_TOKENS, {
        json: true,
        temperature: 0.3,
        usageContext: usage,
      }),
    model,
    now: () => new Date(),
  };
}
```

- Notes:
  - `model` is the active provider's configured id, captured when the dependencies are built.
  - The comment calls `writerModel` "the `writerModel` audit field".
  - `generate` returns a string only; nothing from the provider's response reaches `writerModel`.
  - `temperature: 0.3`: the output is sampled, so a rerun can differ (C3).

### X4 · callLLM returns only the text
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/index.ts:375-386` (Lomem main branch as read on 2026-10-15)
- Implements: C29 (contrast), F10.12

```ts
/**
 * Text-only LLM call. Thin wrapper over {@link callLLMWithMeta} — the historical
 * signature most callers use. Returns just the completion text.
 */
export async function callLLM(
  systemPrompt: string,
  messages: Array<{ role: "user" | "assistant"; content: string }>,
  maxTokens: number,
  options: LLMOptions,
): Promise<string> {
  return (await callLLMWithMeta(systemPrompt, messages, maxTokens, options)).text;
}
```

- Notes:
  - The caller cannot learn which provider or build answered.
  - The bank's gateway returns a `call_id` with the draft so later events can point to the call (S10).

### X5 · The shared result type carries no model version
- File: `~/projects/lomem/packages/shared/src/llm/types.ts:54-70` (Lomem main branch as read on 2026-10-15)
- Implements: C34 (contrast)

```ts
export interface LLMChatResult {
  text: string;
  usage?: LLMUsageDetails;
  /**
   * Diagnostic metadata from the provider's raw response, populated best-effort.
   * Used to investigate empty/blocked completions (e.g. an empty tutor reply):
   * `finishReason` (Gemini candidate.finishReason — STOP / MAX_TOKENS / SAFETY /
   * RECITATION), `blockReason` (promptFeedback.blockReason when the prompt itself
   * is blocked), and the raw `safetyRatings`. Undefined for providers that don't
   * expose them.
   */
  finishReason?: string;
  blockReason?: string;
  safetyRatings?: unknown;
  /** The pictures an image model answered with (`options.image`), in order. */
  images?: Array<{ mimeType: string; data: Uint8Array }>;
}
```

- Notes:
  - Diagnostics from the raw response (`finishReason`, `blockReason`, `safetyRatings`) are already copied here; a `modelVersion` field would be one more such field.
  - A repo search found no use of Gemini's `modelVersion` in `apps/*/backend/src` or `packages/shared/src`.
  - Without it, audit question 1 can only be answered with the requested name.

### X6 · The gateway can answer with a different provider than the lead
- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:228-238` (Lomem main branch as read on 2026-10-15)
- Implements: F10.9, F10.10b, V4

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
  - The lead comes first, then every other provider in priority order as fallback.
  - The note writer stamps the lead's id (X3); if a fallback answered, the stamp is wrong (derived by reading, not observed).
  - A governed gateway would take the model from the inventory row and record the one that answered (S10).

### X7 · Tunatutor wires the gateway to the admin registry, a sticky switch and the cost meter
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/index.ts:268-291` (Lomem main branch as read on 2026-10-15)
- Implements: F10.10b, F10.11, F11.4, P2

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
  - The provider list is re-read from the registry on every call, so an admin change takes effect at once with no release.
  - When a fallback wins, `switchActiveProviderInMemory` changes the active provider in memory (the sticky switch).
  - The meter records provider id, name, usage, latency and error flag per attempt; no prompt and no output.

### X8 · A later write for the same session overwrites the note
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/tutor-continuity/lesson-note-repository.ts:39-61` (Lomem main branch as read on 2026-10-15)
- Implements: C71, C32 (contrast), L7, M3

```ts
export async function upsertLessonNote(input: LessonNoteInput, promises: OpenPromiseInput[]): Promise<number> {
  // Task 6 carry-forward: the note upsert and the promise createMany used to be
  // two separate awaited writes — a crash between them could leave a note with
  // no promises row. Wrapped in a single interactive transaction so both writes
  // (or neither) land. Signature and return value are unchanged.
  return prisma.$transaction(async (tx) => {
    const note = await tx.tutorLessonNote.upsert({
      where: { conversationSessionId: input.conversationSessionId },
      create: {
        conversationSessionId: input.conversationSessionId, userId: input.userId, language: input.language,
        workedOn: input.workedOn ?? undefined, wins: input.wins ?? undefined,
        stumbles: input.stumbles ?? undefined, newItems: input.newItems ?? undefined,
        tutorRemark: input.tutorRemark ?? null, openerUsed: input.openerUsed ?? null,
        writerModel: input.writerModel ?? null, writerPromptVersion: input.writerPromptVersion ?? null,
      },
      update: {
        workedOn: input.workedOn ?? undefined, wins: input.wins ?? undefined,
        stumbles: input.stumbles ?? undefined, newItems: input.newItems ?? undefined,
        tutorRemark: input.tutorRemark ?? null, openerUsed: input.openerUsed ?? null,
        writerModel: input.writerModel ?? null, writerPromptVersion: input.writerPromptVersion ?? null,
      },
      select: { id: true },
    });
```

- Notes:
  - `where: { conversationSessionId }` with `update:` replaces content, `writerModel` and `writerPromptVersion` together; the first note is gone.
  - An audit table would be INSERT only, with each later write as a new row (S10).
  - Tunatutor has no user edit of lesson notes; the overwrite comes from a second write for the same session (testing, fact-check).
  - The fact-check cites `lesson-note-repository.ts:45` for the upsert; the function starts at line 39 and the `tx.tutorLessonNote.upsert` call is at line 45, so both are right.

### X9 · The lesson-note table: one row per session, stamps, cascade delete
- File: `~/projects/lomem/apps/tunatutor/backend/prisma/schema.prisma:1742-1770` (Lomem main branch as read on 2026-10-15)
- Implements: C71, L7

```prisma
/// One row per completed AI-tutor conversation session, holding the internal
/// lesson note the tutor engine wrote for continuity (what was worked on,
/// wins, stumbles, new items) — never shown verbatim to the user.
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

  createdAt DateTime @default(now()) @map("created_at")

  user     User                @relation(fields: [userId], references: [id], onDelete: Cascade)
  session  ConversationSession @relation(fields: [conversationSessionId], references: [id], onDelete: Cascade)
  promises TutorPromise[]

  @@index([userId, language, createdAt(sort: Desc)])
  @@map("tutor_lesson_notes")
}
```

- Notes:
  - `@unique` on `conversationSessionId` is what makes the upsert overwrite.
  - There is `createdAt` but no `updatedAt`, so an overwrite leaves no trace of when it happened.
  - `onDelete: Cascade` removes the note with the user or the session; under ADR-037 that is complete erasure (S14). A bank would record the deletion as an event row (S10).
  - `schemaVersion`, `writerModel`, `writerPromptVersion` are the only provenance columns.

### X10 · Every call must say who it is for, or the shared gateway refuses it
- File: `~/projects/lomem/packages/shared/src/llm/gateway/context.ts:1-6 and 50-66` (Lomem main branch as read on 2026-10-15)
- Implements: C68, C26 (analogue), C28 (analogue), F10.8, F10.8b

```ts
// Who pays for an LLM call (ADR-057 §5).
//
// Every gateway call carries one of these. A call without it is provider money
// that never reaches `provider_usage_events` — invisible to allowances, spend
// guardrails and per-feature cost reports — so the gateway REFUSES it
// (`MissingUsageContextError`) instead of running it unmetered.
...
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
  - Same shape as the bank gateway's refusal: no attribution, no call.
  - `feature` plays the role of the use-case id and `userId` the role of `X-On-Behalf-Of`.
  - It is not bound to a caller credential and has no inventory row behind it; any code can name any feature.
  - A system call with no user must state a `reason`, which keeps the exemption auditable.

### X11 · Tunatutor's usage context says why attribution is required
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/types.ts:4-20 and 38-45` (Lomem main branch as read on 2026-10-15)
- Implements: C68

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
  - The motive is cost visibility (free-tier cap, daily spend guardrails, per-surface cost reports), not regulation; the mechanism is the one governance needs.
  - A system call's spend is still recorded with no user, `actor_kind = 'system'` and the reason as `system_reason`; it is never debited.

### X12 · The usage table records cost, not content
- File: `~/projects/lomem/packages/shared/prisma/foundation/45-provider-usage.prisma:54-100` (Lomem main branch as read on 2026-10-15)
- Implements: C68, V8, M2, F10.11

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
  /// Arbitrary extra event metadata.
  metadataJson      Json?     @map("metadata_json")
  /// When the usage actually occurred.
  occurredAt        DateTime  @default(now()) @map("occurred_at")
  /// FK to the price config row used to compute the cost; null if unpriced.
  priceConfigId     Int?      @map("price_config_id")

  user        User?               @relation(fields: [userId], references: [id], onDelete: Cascade)
  priceConfig ProviderPriceConfig? @relation(fields: [priceConfigId], references: [id], onDelete: SetNull)

  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")
```

- Notes:
  - One row per billable line per provider attempt, so a fallback shows up as rows with another `providerKey`.
  - No prompt, no output, no prompt version: it proves a call happened, not what it said.
  - `actorKind` is `user`, `admin` or `system`; `systemReason` holds the reason for a system row.
  - The table has `updatedAt` and `onDelete: Cascade` on the user, so it is neither insert-only nor kept after erasure.
  - `git grep` over `apps` and `packages` (generated Prisma client excluded) finds no application code that updates usage rows; only the `usage_capability` migrations (`apps/billpod/backend/prisma/migrations/20261007090000_usage_capability/migration.sql:15`, same in mealy) backfill with `UPDATE`, and integration tests `deleteMany` their own rows.
  - Apps sync this foundation file as `apps/<app>/backend/prisma/_shared.45-provider-usage.prisma`.

### X13 · The models a tunatutor admin can choose
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/models.ts:1-11` (Lomem main branch as read on 2026-10-15)
- Implements: C8 (unverified analogue), F11.1, P2

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
  - The active model is chosen in an admin screen and stored in the database, so it can change without a code release.
  - Whether `gemini-2.5-flash` is a stable build or a moving name is the provider's choice (unverified); Gemini reports the build in `modelVersion` (S10, unverified).
  - `apps/tunatutor/CLAUDE.md` line 14 names Gemini (2.5 Flash, 2.5 Flash Lite) as the single LLM provider (S13).

### X14 · Switching to an unpriced model is refused
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/registry.ts:199-212` (Lomem main branch as read on 2026-10-15)
- Implements: F11.2, F11.2b

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
  - A precondition check of the same kind as the inventory row, but for price coverage, not risk.
  - No eval or review gates the switch (F11.5).

### X15 · The note job is enqueued once at session end
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-finalization.ts:96-107` (Lomem main branch as read on 2026-10-15)
- Implements: F10.1, F10.1b

```ts
  // Tutor-continuity private lesson-note writer: enqueue once at session-end,
  // same idempotent-on-uuid shape as the lexicon detect job above. Best-effort
  // — a note-writer detail must never fail finalization.
  try {
    await enqueueJob({
      type: JobType.TutorLessonNoteWrite,
      idempotencyKey: `${LESSON_NOTE_KEY_PREFIX}${sessionId}`,
      payload: { conversationSessionUuid: sessionId, userId, language },
    });
  } catch (err: unknown) {
    curriculumLog("Finalize", `lesson note enqueue skipped: ${getErrorMessage(err)}`);
  }
```

- Notes:
  - The idempotency key `lesson-note:<sessionId>` makes a double enqueue harmless.
  - Enqueue failure is logged and never fails finalization.
  - The excerpt sits inside `checkpointAiTutorSession` (`ai-tutor-finalization.ts:20-198`), the function the reaper comment in X16 names.

### X16 · The abandoned-session reaper enqueues the same job with the same key
- File: `~/projects/lomem/apps/tunatutor/backend/src/session-types/ai-tutor/engine/ai-tutor-abandoned-reaper.ts:15-27 and 84-91` (Lomem main branch as read on 2026-10-15)
- Implements: F10.1c, F10.1d

```ts
// from the DB, so no in-memory engine is required. No double-spend of the LLM judge:
// the enqueue is idempotent (unique `(type, idempotencyKey)`), the query
// already excludes sessions with a detect job, and the pipeline early-returns
// without an LLM call when there is nothing new to judge.
//
// The same gap applies to the tutor-continuity lesson-note writer (Task 7):
// `checkpointAiTutorSession` only enqueues `TutorLessonNoteWrite` when a
// session is explicitly finalized, so an abandoned/paused session would never
// get a note either. The reaper runs a SECOND, independent scan
// (`findAbandonedSessionsNeedingNote`) keyed on the note job's own idempotency
// key — a session can need a note regardless of whether its lexicon detect job
// has already run, so the two scans and enqueue loops are kept separate rather
// than merged into one.
...
export async function enqueueAbandonedSessionJob(
  enqueue: typeof enqueueJob,
  kind: "detect" | "note",
  session: Pick<AbandonedAiTutorSessionRow, "uuid" | "userId" | "targetLanguage">,
): Promise<void> {
  await enqueue({
    type: kind === "detect" ? JobType.LexiconProductionDetect : JobType.TutorLessonNoteWrite,
    idempotencyKey: `${kind === "detect" ? DETECT_KEY_PREFIX : LESSON_NOTE_KEY_PREFIX}${session.uuid}`,
```

- Notes:
  - The enqueue is idempotent on a unique `(type, idempotencyKey)`.
  - Without the reaper, an abandoned or paused session would never get a note.

### X17 · Prompt templates in the database keep archived versions and can roll back
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/prompt-templates.ts:105-131 and 190-193` (Lomem main branch as read on 2026-10-15)
- Implements: C12, V21

```ts
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
...
export async function activatePromptTemplateVersion(
  key: string,
  versionId: number,
): Promise<{ key: string; content: string; updatedAt: Date }> {
```

- Notes:
  - Every content change archives the old version before the upsert; `activatePromptTemplateVersion` rolls back.
  - A template that uses an unregistered `{{variable}}` is refused.
  - Admin edits change behaviour with no release, the same release gap as F11 (prompts block covers this in full).

### X18 · The lead provider: the caller's pinned model if enabled, else the admin-chosen one
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/index.ts:254-266` (Lomem main branch as read on 2026-10-15)
- Implements: F10.9

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
  - A disabled or unknown model id never errors; the call runs on the active model.
  - So even a per-call model choice does not guarantee which model answered.

### X19 · A test pins the refusal of unattributed calls
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/__tests__/usage-context-required.test.ts:1-4` (Lomem main branch as read on 2026-10-15)
- Implements: C68, F10.8b

```ts
// A provider call without a usage context is money we spend and can never see.
// The type system makes it unreachable from TypeScript; this pins the RUNTIME
// backstop — the call must FAIL loudly, never fall through to the provider with
// metering quietly skipped (the old behavior that hid the un-metered surfaces).
```

- Notes:
  - The rule is guarded by a test, not only by types.

### X20 · The shared gateway's stated job
- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:1-14` (Lomem main branch as read on 2026-10-15)
- Implements: C68, K28

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
  - "refuse an unattributed call, pick the provider, fall back to the next one when it fails, and settle spend and errors at ONE point per provider attempt".
  - ADR-057 §5 says every LLM call in tunatutor, Mealy and Billpod goes through this gateway; MyTube still calls a provider directly (S13, S15).

### X21 · ADR-037: deletion is complete erasure
- File: `~/projects/lomem/docs/adr/037-account-erasure-and-admin-deletion.md:14-16` (Lomem main branch as read on 2026-10-15)
- Implements: L7 (DELETED), C33 (contrast)

```md
### 1. Deletion is complete erasure — no leftovers

Deleting a user removes every row that **is** their data or **identifies** them: the `User` row plus everything tied to it. There is no soft delete of the account on this path. After deletion the answer to "does this person exist in the system?" is a flat no.
```

- Notes:
  - Lomem deletes a user's rows, lesson notes and usage rows included; there is no soft delete on this path.
  - A bank instead keeps content for the client file's retention period and records the deletion as an event row (S10).

## Analogy to classic backend

| AI-side item (id) | classic Java/Spring equivalent | holds where | breaks where |
|---|---|---|---|
| Whole block (C14) | The bank's change process plus vendor due diligence plus model validation (S10) | Every release already has a ticket and an approver who did not write it (S10) | The change process assumes nothing changes without a deployment; model validation assumes the model can be inspected and reproduced; neither holds (S10, S11) |
| Inventory (C23) | The list of applications IT already keeps (application register) (S10) | One row per thing, with an owner | The row is a precondition enforced in code by the gateway, not a document; "AI" must be defined broadly (S10) |
| Gateway (C26) | An internal integration service that alone holds a partner's credentials and checks which callers may use it (old draft analogy) | Service credentials (OAuth client, mTLS) and a trusted user claim work as for any internal call (S10) | It also pins the model, records the reported version and stores content (S10) |
| Call and event rows (C30, C31, C32) | An audit trail; SOX or ISO audit trails (S10, S12); an append-only event table such as Spring Data Envers or an outbox table, never updated (old draft analogy) | Insert-only rows, keyed by an id | The output must be stored because a rerun does not reproduce it (S10) |
| Audit content store (C33) | A document archive with the client file's retention period (S10) | Retention and deletion with the client file | The content is client data sent to a third party on every call (S10) |
| Provider file (C43) | The outsourcing file kept for any vendor that handles client data; data-processing agreements; vendor risk management (S10, S12) | Third-party risk team runs it (S10) | The vendor's component can change under an alias, and terms (abuse logs, region) differ per endpoint and approval (S3, S10) |
| Eval report (C53) | Model validation for credit-scoring models; a test report on the change ticket (S10, S12) | Signed report before use | Tests are statistical: "1 bad draft in 300 against a 1% bar", not all assertions green (S10) |
| Pinned snapshot (C9) | An image digest instead of the Docker tag `latest` (S10) | Fixes what runs | The provider retires snapshots on its own dates (S10) |
| Prompt version (C12) | Source code in git with a commit id (S10) | Versioned, reviewable | A plain-language one-word edit changes behaviour and needs the same review as code (S10, S11) |
| Outside reviewer (C60) | Change-advisory board, four-eyes release approval (S12, S10) | Separation of builder and reviewer | The reviewer judges an eval report, not a code diff (S10) |
| PENDING approval (C61) | A payment waiting for a second signature (S10, S11) | Named second person releases | Applies per output, at run time, only for High (S10) |
| Monitoring (C54) | Production health monitoring | Scheduled job and alerts | There is no correct answer after go-live, so a grader and the edit rate stand in (S10) |
| `deps.model` (C72) | A constructor-injected field (old draft analogy) | Injected at construction | The value is the configured name, not the build that answered (X3) |
| Lomem usage context (C68) | A required tenant or billing header checked by a filter | Refuses unattributed calls | Records cost, not content (X12) |

## Pitfalls

| id | mistake | consequence | what to do instead | source |
|---|---|---|---|---|
| M1 | Counting only projects called "AI" | The inventory is incomplete; FINMA saw firms define AI narrowly | Any internal tool with one model call gets a row; the gateway makes the row a precondition | S10 |
| M2 | Logging cost but not content | A usage row proves a call happened, not what it said; audit question 2 has no answer | Store prompt and draft in a content store, pointed to from the call row | S10, X12 |
| M3 | Overwriting the draft | Saving the edited note over the draft destroys the answer to question 2 | Keep the draft; the edit is a new event row with the final text | S10, S11, X8 |
| M4 | Validating against an alias | The eval passed on last quarter's model, and production now runs a newer one under the same name | Pin a snapshot; rerun the eval on any snapshot change | S10, S11 |
| M5 | Assuming the provider keeps nothing | Default terms keep requests for abuse monitoring for up to 30 days | Record region and retention option per risk class; apply for zero retention where needed | S10, S11, S3 |
| M6 | Recording only the requested or configured model name | An alias move or a fallback means the name may not be the build that ran | Record the version the provider reports and alert on a mismatch | S10, X3, X6 |
| M7 | Skipping the eval for a wording change | A one-word prompt edit can change behaviour | Tie the eval report to the prompt version and rerun on any edit | S10 |
| M8 | Reading "Europe (EEA + Switzerland)" as "in Switzerland" | The region does not promise Switzerland | Answer "Switzerland or an EEA country" and check the class allows it | S10, testing |
| M9 | Trusting a grader without calibration | The grader can be wrong | Compare it with 50 human labels (made-up bar 47) before use | S10 |
| M10 | Letting the caller choose the model | A team can bypass the validated snapshot | The gateway takes snapshot and region from the row | S10 |
| M11 | Binding the use-case id to nothing | One team can borrow another team's id | The row lists allowed credentials; the gateway checks them | S10, testing |
| M12 | Self-review of a release | No independent review | Someone outside the building team approves the change ticket | S10 |
| M13 | Using a moving version stamp that nothing forces to change | The stamp says `v1` after the prompt text changed | Tie the prompt version to a git-versioned file and commit | X2, S10 |
| M14 | Treating the provider's region as covering everything | Residency does not apply to system data | Record the exception; ask what system data includes | S3, S10 |
| M15 | Letting an admin screen switch the model with no eval | The model behind every feature changes with no release | Put the snapshot in the inventory row and gate changes through eval and review | X7, X13, X14, S10 |

## Misconceptions

| id | what a newcomer believed | correct statement | evidence |
|---|---|---|---|
| Q1 | NIST AI RMF and the EU AI Act are padding or name-dropping | They ask for the same artefacts: Govern, Map, Measure, Manage map to owners, inventory, evals and monitoring, acting on findings; the EU AI Act makes credit scoring and life/health insurance pricing high-risk from 2 Dec 2027 | testing (all rounds), S10 |
| Q2 | The model gives a different answer each time | The model picks each word with some randomness, so it may not give the same answer twice | testing (round 3), S10 |
| Q3 | The audit record lets you rebuild the output | The output is stored because it cannot be produced again | testing (round 2), S10 |
| Q4 | Low-class use cases write no audit record | Every class, Low included, writes the audit record | testing (round 3), S10 |
| Q5 | Low means weak controls | Low is the lowest set; each higher class adds to it | testing (round 2) |
| Q6 | The "Europe (EEA + Switzerland)" region proves the data left Switzerland | The region may process in Switzerland or in an EEA country and does not promise Switzerland | testing (round 3), S3, S10 |
| Q7 | Audit question 3 has no answer | Processed in OpenAI's Europe region; kept out of abuse logs by Modified Abuse Monitoring, so no copy remains; default terms would keep a copy up to 30 days | testing (round 2), S10 |
| Q8 | An insert-only record cannot hold an edit made 11 minutes after the call | The gateway inserts the call row; the feature service later inserts a separate event row keyed by `call_id` | testing (round 3), S10 |
| Q9 | The gateway check is weak because any team can pass any use-case id | The row binds the use-case id to allowed service credentials | testing (rounds 2, 3), S10 |
| Q10 | The gateway is a library | It is a separate internal service that alone holds the provider keys | testing (round 2), S10 |
| Q11 | A grader model cannot be trusted, or free-text scoring is automatic | Three methods, often combined: code checks, a grader calibrated against human labels, human reviewers | testing (rounds 1, 3), S10 |
| Q12 | The 1% release bar and the 2% monitoring threshold are inconsistent | That was an earlier draft; monitoring uses the same 1% bar as release | testing (round 2), S10 |
| Q13 | Snapshot versus alias does not matter for evidence | Calling a pinned snapshot keeps the eval valid; an alias lets the provider swap the validated model | testing (round 1), S10 |
| Q14 | The reported version is just a nice-to-have | It matters because an alias can change; some providers only echo the name sent | testing (round 2), S10 |
| Q15 | The risk class is just High, Medium or Low | It comes from FINMA's proportionality factors: client impact, financial impact, whether a person checks the output | testing (round 2), S1, S10 |
| Q16 | (forgotten) FINMA's seven areas and "no AI-specific law" | Switzerland has no AI-specific law; existing rules apply; seven areas each map to an artefact | testing (rounds 1, 2), S1 |
| Q17 | Region and retention are just "recorded" | OpenAI: abuse logs up to 30 days by default, ZDR only with prior approval, the EEA + Switzerland region | testing (rounds 1, 3), S3 |
| Q18 | The Lomem cost-attribution snippet is the audit record | Lomem's usage rows are cost records with no content; its note stamp is a first step that records the configured name and is overwritten by an upsert | testing (rounds 1, 3), X8, X12 |
| Q19 | The audit record is only about the model's output | It also captures what a human did with it, as event rows (edited, approved, deleted) | testing (round 3), S10 |
| Q20 | Drift means quality getting worse after go-live | In FINMA's guidance (section 2.4) drift means data drift: the input data changes | testing (fact-check), S1 |
| Q21 | The model card and edit rate are defined where they are first used | Earlier drafts used both before defining them; they are defined in C58 and C55 | testing (round 2) |
| Q22 | The audit questions 3-5 map to controls without help | Readers had to map them themselves in round 1; E8 maps each question to its record | testing (round 1), S10 |

## Open questions

- FINMA's seven areas: the web research says they came from secondary sources because the official PDF did not parse; the fact-check says they were verified against the PDF (S12, testing).
- FINMA outsourcing duties (vetting the vendor, a contract with audit rights, knowing subcontractors, an exit plan) come from FINMA Circular 2018/3, which was not fetched; Guidance 08/2024 only mentions extra tests, controls and contract clauses for outsourcing (testing, unverified).
- That OpenAI's response `model` field and Gemini's `modelVersion` report the exact build is from knowledge of the API references, not a fetched page (testing, unverified).
- "Providers retire snapshots on announced dates, usually months ahead" has no cited source (testing, unverified).
- What OpenAI's "system data" includes, and whether some metadata leaves the EU/CH region, is not answered (testing, final read).
- SR 26-2's coverage of generative or agentic AI is unverified; commentators disagree, and the attachment was not read (S12).
- If the provider reports a different version on a Medium row, the call goes through with an alert; whether the draft is still covered by the eval report, or must be flagged, is not answered (testing, final read).
- Who owns the gateway, and whether putting it in front of every call makes it a single point of failure the bank must also govern, is not covered (testing, final read).
- Whether weekly monitoring re-sends live client transcripts to the provider through the grader, and whether that is allowed, is not covered; presumably the grader's own row `meeting-note-eval` (Medium) governs it (testing, final read; presumption unverified).
- Why the High row's monitoring is monthly while the Medium row's is weekly reads as backwards to readers; no source resolves it (testing, final read).
- Whether approval at High, as opposed to rewriting, is enough to keep the High class, or changes the class, is not settled (testing, final read).
- What happens when an approver rejects a PENDING output, and whether a refused gateway call writes an audit row, is not described (inferred gap).
- How transcripts are anonymised for the eval set, beyond "replace names and account numbers with placeholders", is not said (testing, round 3).
- What counts as abuse beyond the examples malware and spam is not said (testing, round 3).
- How to request Zero Data Retention is not described (testing, round 2).
- The research catalogue's "accountability is unclear when an agent acts" has no engineering answer in this block's drafts (S12); hitl and agents blocks may cover it.
- Lomem: `writerModel` can name a model that did not answer; derived by reading the code (stamp taken from `getActiveProvider()` before the call, gateway fallback, `callLLM` returns only text), not observed at run time (X3, X4, X6).
- Lomem: the code comment calls `writerModel` an "audit field" (X3), but the upsert overwrites it, so it records only the latest write per session (X8).
- Lomem: whether `gemini-2.5-flash` is a stable build or a moving name is the provider's choice and was not checked (X13).
- The research catalogue's request path calls the trace "also the audit log for governance" (S12), but the drafts require content storage that a trace with redacted payloads may not hold; the two sources are not reconciled.

## Sources

| id | title | author or publisher | date | URL | what it supports |
|---|---|---|---|---|---|
| S1 | Guidance 08/2024: Governance and risk management when using artificial intelligence | FINMA | 18 Dec 2024 | https://www.finma.ch/en/~/media/finma/dokumente/dokumentencenter/myfinma/4dokumentation/finma-aufsichtsmitteilungen/20241218-finma-aufsichtsmitteilung-08-2024.pdf | No AI-specific law; technology-neutral rules; seven areas; narrow AI definitions; outputs users changed; materiality factors; documentation contents; data drift (section 2.4) |
| S2 | FINMA press release on Guidance 08/2024 | FINMA | 18 Dec 2024 | https://www.finma.ch/en/news/2024/12/20241218-mm-finma-am-08-24/ | FINMA's AI risk list |
| S3 | Data controls in the OpenAI platform | OpenAI | as read October 2026 | https://developers.openai.com/api/docs/guides/your-data | 30-day abuse logs; ZDR subject to prior approval; no training on API data; Europe (EEA + Switzerland) region; approved controls; system-data exception |
| S4 | NIST AI Risk Management Framework | NIST | not given | https://www.nist.gov/itl/ai-risk-management-framework | Voluntary; Govern, Map, Measure, Manage |
| S5 | Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile (NIST AI 600-1) | NIST | 26 Jul 2024 | https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence | GenAI-specific risks |
| S6 | EU AI Act high-level summary | artificialintelligenceact.eu | not given | https://artificialintelligenceact.eu/high-level-summary/ | Risk tiers; credit scoring and life/health insurance pricing high-risk; 2 Dec 2027; non-EU providers covered |
| S7 | EU AI Act (site) | artificialintelligenceact.eu | not given | https://artificialintelligenceact.eu/ | Named in the research catalogue as a source |
| S8 | SR 26-2 | US Federal Reserve | 17 Apr 2026 | https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm | Replaces SR 11-7 and SR 21-8 |
| S9 | ISO/IEC 42001 | ISO | not given | https://www.iso.org/standard/42001 | Named only; returned 403, not read |
| S10 | Governance lets a regulated firm prove what its AI did (long fact-checked draft) | this learning project | 2026-10 | `personal/Learning/AI-Building-Blocks/sources/sections-long/15-governance.html` | Running example, definitions, inventory, gateway, audit rows, residency, evals, monitoring, model card, analogy, mistakes |
| S11 | Governance (short version tested on newcomer readers) | this learning project | 2026-10 | `personal/Learning/AI-Building-Blocks/sources/sections-tested/15-governance.html` | Tested wording; short forms of the same claims |
| S12 | Web research catalogue, block 15 and the request path | this learning project | 2026-10 | `personal/Learning/AI-Building-Blocks/sources/research-web.md` | Backend analogues, new problems, minimal and mature lists, regulators, tools, trace as audit log, unverified items |
| S13 | Lomem code map, sections 1, 2, 9 and 14 | this learning project | 2026-10 | `personal/Learning/AI-Building-Blocks/sources/research-lomem.md` | Gateway refusal of unattributed calls, usage context, cost ledger, prompt templates, ADR-057 |
| S14 | ADR-037: Account erasure & admin-initiated deletion | Lomem | 2026-06-19 | `~/projects/lomem/docs/adr/037-account-erasure-and-admin-deletion.md` | Deletion is complete erasure; cascade deletes |
| S15 | ADR-057: AI tools, MCP and OAuth provider (§5, the gateway) | Lomem | not given | `~/projects/lomem/docs/adr/057-ai-tools-mcp-and-oauth-provider.md` | One gateway for tunatutor, Mealy and Billpod; a usage context is required (quoted via S13) |
| testing | Testing notes for this section (key points, rounds 1-3, fact-check, final read) | this learning project | 2026-10 | `personal/Learning/AI-Building-Blocks/sources/testing-notes/15-governance-testing.md` | What readers misread, unknown terms, fact-check fixes, questions left |
