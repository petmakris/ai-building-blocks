---
id: caching
number: 13
title: Caching
summary: Caching avoids paying twice for the same model work, by letting the provider reuse its computation on an identical prompt opening and by storing whole answers to repeated questions, with new risks because a model answer is neither free nor deterministic.
lomem_status: partly
depends_on: [gateway, prompts, context, structured]
related: [observability, tools, rag, memory, guardrails, evals, governance, rollout]
---

# Caching

## Summary

Caching in an LLM application avoids paying twice for the same model work. There are three kinds: provider prompt caching reuses the provider's computation on an exact shared opening of the prompt (the prefix); an exact response cache stores the finished answer under a key and skips the model call on a hit; a semantic cache reuses an answer for a question that only means the same thing, and can return a wrong answer. Prompt caching is new compared with a classic backend, because a classic backend never paid per byte of request, while every LLM call resends and repays the same long opening. The response cache is familiar (Spring `@Cacheable` on Redis or a table), but the cached value is one sample from a non-deterministic model, so validation, eviction by report, version stamps and keeping personal data out of shared rows become part of the design.

## Problem

- P1 · The model keeps no state between calls, so every request resends the tool definitions, the system prompt and the history, and the provider bills those repeated tokens on every call (S10, S12). A classic backend never paid per byte of request, so this waste is new (S10).
- P2 · Long repeated prefixes make calls slow as well as expensive; the research names the new problem as "long, repeated prefixes (system prompt, tool definitions, documents) are paid for on every call, and calls are slow" (S12).
- P3 · Many users ask the same question (Tunatutor: thousands of learners ask about the same common words), and each repeat costs a paid model call (S10). Classic backends had this problem and solved it with a response cache (S10).
- P4 · A model is not a pure function: the same prompt can give a different answer on each call, even at temperature 0, so a cache freezes one sample and serves it, including a bad one, to every user (S10). A classic `@Cacheable` assumes the method returns the same result each time (S10).
- P5 · A shared answer cache can leak one user's data or serve a form that fits only one user (French « je suis allée » for a woman), which a classic cache of pure data rarely risks (S10, S14).
- P6 · A stored answer goes stale when the code changes even if no data changed: a new prompt, output format, model or call parameter changes what a correct answer is (S10).
- P7 · Questions with the same meaning but different text miss an exact cache, and matching them by meaning (semantic cache) can return a fluent wrong answer or another user's data with no error (S10, S12).
- P8 · Provider prompt caching can fail silently: a prefix under the model's minimum length is not cached and no error says so, so the cache must be measured from token counts (S1, S10).

## Concepts

### C1 · Token
- Definition: A token is a piece of a word, about four characters, which is the unit the model reads, writes and is billed in.
- Facts:
  - A token is about four characters of text (S10).
  - The provider bills per token, with one price for input tokens and a higher price for output tokens (S10).
- Relations: C1 is the unit of C2 (pricing), C23 (usage counts) and C24 (cache-read share).

### C2 · Input and output token pricing
- Definition: Input tokens are the tokens sent to the model and output tokens are the tokens the model writes; each has its own price.
- Facts:
  - Output tokens cost more than input tokens (S10).
  - Output tokens are never cached; the answer is always paid at full price (S10).
  - Prompt caching discounts only input tokens (S1, S10).
- Relations: C2 is discounted by C10 (prompt caching) on the input side only; C27 (exact response cache) avoids both input and output cost on a hit.

### C3 · Stateless model call
- Definition: A model keeps no state between calls, so the calling service sends everything the model must see on every request.
- Facts:
  - The model keeps no state between calls (S10, S11).
  - In a chat, the service stores the history and resends all of it on each turn (S10).
  - A model (or LLM) is a hosted service that takes text in and writes text back, run by a provider such as Anthropic or OpenAI, called over HTTP (S10).
  - The text sent to the model is the prompt (S10).
- Relations: C3 causes P1; C3 is why C4 (request parts) repeats on every call.

### C4 · Request parts and their order
- Definition: An LLM request body has three parts in a fixed order: tool definitions, then the system prompt, then the messages.
- Facts:
  - The order is tools, system prompt, messages (S1, S10).
  - Anthropic reads the cached prefix in the order tools, system prompt, messages (S1, S10).
  - Changing a tool definition invalidates everything after it in the prefix (S1, S10).
  - The tools and the system prompt are often thousands of tokens and identical on every call (S10).
  - Testing: readers did not act on the order tools, system, messages while "tool definitions" and "messages" were undefined (testing).
- Relations: C4 is made of C5, C6 and C7; C4 decides what can be in C9 (prefix).

### C5 · Tool definitions
- Definition: Tool definitions are descriptions of functions in the calling service that the model may ask the service to call, sent as JSON schemas in text.
- Facts:
  - An example tool is `lookupOrder(id)` (S10).
  - Tool definitions are JSON schemas sent as text on every call (S10).
  - Tool definitions come first in the request, so they are the start of every cached prefix (S1, S10).
  - Listing tools in a different order on each call, for example from a Java `HashMap`, changes the prefix and drops the hit rate to zero (S10).
  - Testing: "tool definitions" was an unknown term in round 1, and neither round-1 reader carried forward the `HashMap` tool-ordering mistake (testing).
- Relations: C5 is part of C4; C5 instability breaks C11 (exact prefix match); see the `tools` block.

### C6 · System prompt
- Definition: The system prompt is the standing instructions sent with every call.
- Facts:
  - An example system prompt is "You score videos against the user's goal. Reply in this JSON format." (S10).
  - On Anthropic the system prompt can be written as a list of text blocks, one of which can carry a `cache_control` marker (S1, S10).
  - Testing: the round-1 skimmer found "system prompt" glossed only in a parenthesis (testing).
- Relations: C6 is part of C4; C6 is usually the largest stable part of C9; see the `prompts` block.

### C7 · Messages and roles
- Definition: Messages are the conversation so far, each with a role of `user` (what the person or the service says) or `assistant` (what the model said earlier).
- Facts:
  - Each message has a role of `user` or `assistant` (S10).
  - Messages come last in the request order (S1, S10).
  - A per-user message differs on every call, so it should carry no cache marker outside a chat (S10).
  - Testing: "role" and "conversation messages" were unknown terms for both round-1 readers (testing).
- Relations: C7 is part of C4; in a chat, C7 holds C16 (moving marker).

### C8 · Content block
- Definition: A content block is one JSON object inside a message or a system prompt, such as `{"type": "text", "text": "..."}`, and is the object a `cache_control` marker attaches to.
- Facts:
  - A message's content can be written as a list of content blocks (S10).
  - A content block with a marker looks like `{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}` (S10).
  - Testing: "content block" was an unknown term for both round-1 readers (testing).
  - Testing: readers saw a JSON example that marked only the system prompt and used a plain string for message content, and could not say how to cache tools or chat history (testing).
- Relations: C8 carries C13 (marker).

### C9 · Prefix
- Definition: The prefix is the shared opening of a request, from the first token up to a cache marker, that the provider can reuse.
- Facts:
  - The shared opening is called the prefix (S10).
  - Everything up to and including the marked object becomes one cached prefix (S1, S10).
- Relations: C9 is matched by C11; C9 is built by C26 (stable-first ordering); C9 length must reach C20 (minimum).

### C10 · Provider prompt caching
- Definition: Provider prompt caching means the provider keeps its computation over a prefix for a few minutes and reuses it, at a fraction of the input price, when the next request starts with exactly the same tokens.
- Facts:
  - Before the model writes a word, it runs a large computation over every input token (S10).
  - The computation produces a set of internal numbers for each token, and each token's numbers depend on all the tokens before it (S10).
  - That per-token computation is most of the cost of a long prompt (S10).
  - The provider keeps those numbers on its side for a few minutes; the caller never sees or stores them (S10).
  - A hit charges a fraction of the input price and the reply starts sooner (S10).
  - Prompt caching still calls the model and still pays for the output (S10).
  - Testing: "network" and "neural network" were unknown terms; the text glossed them only as "the large computation that is the model" (testing).
  - Testing: readers asked what the provider actually stores; the guide keeps it vague as "internal numbers" per token (testing).
- Relations: C10 solves P1 and P2; C10 is controlled by C13 on Anthropic and is automatic in C22 (OpenAI); C10 is measured by C23.

### C11 · Exact prefix match
- Definition: The prompt cache hits only when the new request starts with exactly the same tokens as the cached prefix, from the first token.
- Facts:
  - If one token near the start differs, nothing after it can be reused, because each token's numbers depend on everything before it (S10).
  - A timestamp, request id or user name near the top of the prompt changes the prefix on every call, so the hit rate is zero (S10).
  - The research's minimal rule is "keep the system prompt and tool definitions byte-stable" (S12).
  - Testing: the round-2 skimmer left out both failure modes of an unstable prefix, a timestamp near the top and tools in an unstable order (testing).
- Relations: C11 is the rule behind C26 (stable-first ordering) and M1, M2.

### C12 · Cache per model
- Definition: A cached prefix is valid only for the model that computed it; the same prefix sent to another model misses.
- Facts:
  - The cache is per model (S10, S11).
  - OpenAI's prompt-caching page states the cache is per model (S2; testing, fact-check).
  - Anthropic's prompt-caching page does not state that the cache is per model; the claim follows from the mechanism (testing, fact-check: unverified for Anthropic).
  - Testing: no round-3 reader mentioned that the cache is per model (testing).
- Relations: C12 limits C10.

### C13 · cache_control marker
- Definition: On Anthropic, `cache_control` is a field added to one JSON object in the request that marks where a cached prefix ends.
- Facts:
  - The marker can sit on a tool definition, a block of the system prompt, or a block of a message (S1, S10).
  - Everything up to and including the marked object becomes one cached prefix (S1, S10).
  - A marker on text that changes on every call pays the write price for text nobody reuses (S10).
  - Testing: a three-marker example with a marker on the per-user message confused both round-3 readers: the senior reader asked whether `input_tokens` is then about 0, and the skimmer read it as paying 1.25x for text nobody reuses (testing).
- Relations: C13 is part of C10 on Anthropic; C13 has C14 (type and TTL) and C15 (up to four).

### C14 · ephemeral type and TTL
- Definition: `"type": "ephemeral"` is the only `cache_control` type and means a 5-minute lifetime; adding `"ttl": "1h"` asks for one hour.
- Facts:
  - `"type": "ephemeral"` is the only type (S1, S10).
  - Ephemeral means a 5-minute lifetime (S1, S10).
  - `"ttl": "1h"` asks for a 1-hour lifetime (S1, S10).
  - The 1-hour lifetime costs 2 times the input price to write (S1, S10).
  - TTL means time to live (S10).
  - Testing: "ephemeral" was an unknown term in round 1 (testing).
  - Testing: readers dropped the 1-hour write price and asked where the field goes (testing).
- Relations: C14 sets C19 (lifetime); C14 changes C17 (write price).

### C15 · Up to four markers
- Definition: An Anthropic request may carry up to four `cache_control` markers, and each one creates its own cached prefix that can be hit on its own.
- Facts:
  - Up to four markers are allowed (S1, S10).
  - Each marker creates its own cached prefix (S1, S10).
  - With one marker after the tools and one after the system prompt, a request with a different system prompt but the same tools still reads the tools from the cache (S10).
  - Whether each of the four markers pays its own 1.25x write on the same tokens is unverified (testing question left).
  - Testing: neither round-3 reader saw that a marker can sit on several kinds of object, each making its own cached prefix; "a marker after the tools still pays off" was opaque to them (testing).
- Relations: C15 extends C13.

### C16 · Moving marker in a chat
- Definition: In a chat, the marker goes on the last block of the newest message and moves to the new last message on every turn, so each turn reads earlier turns from the cache.
- Facts:
  - A chat is the exception to "no marker on the user message", because the history is reused on the next turn (S10).
  - Each turn reads the earlier turns from the cache and writes only the new ones (S10).
  - In a chat with the marker on the newest message, `input_tokens` is close to 0 and `cache_creation_input_tokens` is the size of the newest turn (S10).
  - Testing: no round-3 reader saw that the chat marker moves every turn (testing).
  - Why the previous turn's prefix still hits after the marker moves is not explained in the sources (testing, final-read question; unverified).
- Relations: C16 is a use of C13 on C7.

### C17 · Cache write (creation) price
- Definition: A cache write is the first time a prefix is stored, billed above the normal input price.
- Facts:
  - A write costs 1.25 times the normal input price for the 5-minute lifetime (S1, S10).
  - A write costs 2 times the normal input price for the 1-hour lifetime (S1, S10).
  - The write is paid even if nobody ever reads the entry (S1, S10).
- Relations: C17 is recovered by C18 within C25 (break-even).

### C18 · Cache read price
- Definition: A cache read is a later request reusing a stored prefix, billed at a fraction of the input price.
- Facts:
  - A read costs 0.1 times the input price on most Anthropic models (S1, S10).
  - A read costs 0.05 times on Opus 5.5 and Sonnet 5.5 (S1; testing, fact-check).
  - A read costs 0.025 times on Fable 5.1 and Mythos 5.1 (S1; testing, fact-check).
  - The research catalogue lists reads at 0.1x, or 0.05x on Opus and Sonnet 5.5 (S12).
  - Lomem's seeded Gemini prices put cached input at 0.1 times input: $0.03 against $0.30 per million for gemini-2.5-flash (X10).
- Relations: C18 is part of C25.

### C19 · Lifetime renewal on hit
- Definition: A cached prefix lives 5 minutes (or 1 hour) after its last hit, because every hit renews it.
- Facts:
  - An entry lives 5 minutes, or 1 hour on request (S1, S10).
  - Every hit renews the entry, whichever user's request made the hit (S1, S10).
  - Testing: the round-3 senior reader did not mention renewal on each hit by any user (testing).
- Relations: C19 makes C25 depend on traffic shape.

### C20 · Minimum cacheable length
- Definition: A prefix shorter than a per-model minimum is not cached, and no error says so.
- Facts:
  - The Anthropic minimum is between 512 and 4,096 tokens and is listed per model (S1, S10).
  - A prefix below the minimum is not cached and no error is raised (S1, S10).
  - If `cache_creation_input_tokens` and `cache_read_input_tokens` are both 0, nothing was cached (S1; testing, fact-check).
  - OpenAI's minimum on its newest models (GPT-5.6+) is 1,024 tokens; earlier OpenAI models have a variable minimum (S2; testing, fact-check).
  - Whether the minimum is counted per marker or for the whole prefix is unverified (testing question left).
  - Testing: no round-3 senior reader mentioned the silent minimum (testing).
- Relations: C20 causes P8; C20 is detected by C23.

### C21 · Cache isolation
- Definition: Provider prompt caches are separated per organization and, on Anthropic's own API, per workspace, so no other customer can hit a prefix.
- Facts:
  - An organization is a company's account with the provider (S10).
  - A workspace is a sub-account inside an organization (S10).
  - Caches are separate per organization (S1, S10).
  - Per-workspace isolation applies on Anthropic's own API, and also on AWS and Foundry (S1; testing, fact-check).
  - Bedrock and Google Cloud isolate per organization only (S1; testing, fact-check).
  - A cache you build yourself has no such isolation unless you add it (S10).
  - Testing: readers did not retain isolation, and "workspace" and "organization as a billing unit" were unknown terms (testing).
- Relations: C21 contrasts with C27, C43 which need C32 (tenant scoping).

### C22 · Automatic prompt caching (OpenAI)
- Definition: OpenAI caches prompt prefixes automatically, with no marker in the request.
- Facts:
  - OpenAI caches automatically with no marker (S2, S10).
  - OpenAI's minimum on its newest models is 1,024 tokens (S2, S10).
  - Whether OpenAI charges extra for cache writes is unverified (testing question left).
- Relations: C22 is the alternative to C13.

### C23 · Usage counts
- Definition: Anthropic's response has a `usage` object that splits input into `input_tokens`, `cache_creation_input_tokens` and `cache_read_input_tokens`.
- Facts:
  - `input_tokens` counts the uncached tokens after the last marker (S1, S10).
  - `cache_creation_input_tokens` counts the tokens written to the cache on this call (S1, S10).
  - `cache_read_input_tokens` counts the tokens read from the cache on this call (S1, S10).
  - Log the three counts per call (S10).
  - Gemini reports `promptTokenCount` and `cachedContentTokenCount`, and Lomem treats the cached count as part of the prompt count (X8, X9).
  - Cerebras (OpenAI-compatible) reports `prompt_tokens_details.cached_tokens` (X7).
  - Anthropic's `input_tokens` excludes cached tokens while Gemini's prompt count includes them, so a cross-provider chart must normalise first (X8, X9, S10).
- Relations: C23 measures C10; C23 feeds C24 and the `observability` block.

### C24 · Cache-read share and its ceiling
- Definition: The cache-read share is `cache_read / (cache_read + cache_creation + input)`, the share of input tokens served from the cache.
- Facts:
  - The share is weighted by tokens, not by requests (S10).
  - The share can never reach 1 while an uncached tail exists (S10).
  - The ceiling is `prefix / (prefix + tail)` (S10).
  - A share near the ceiling is healthy (S10).
  - A share stuck at zero means the prefix changes between calls or is under the minimum (S10).
  - Testing: the guide once called the ratio a "hit rate" with no healthy value, and readers were unsure whether a value below 100% meant a broken cache (testing).
  - Testing: the round-2 skimmer worked out about 88% for a perfect hit; the guide's figure is about 87% (testing, E2).
  - Testing: in round 3 the token weighting and the ceiling were in the text but neither reader kept them (testing).
- Relations: C24 is computed from C23; C24 is charted in C51 (dashboard).

### C25 · Break-even and traffic shape
- Definition: Prompt caching saves money when a prefix is reused within its lifetime, and loses money only when calls arrive alone, each more than one lifetime after the last.
- Facts:
  - One reuse within 5 minutes pays for the write: 1.25 + 0.1 = 1.35 against 2 without a cache (S10).
  - Caching loses money only when calls arrive alone, each more than 5 minutes after the last (S10).
  - The 1-hour lifetime pays when the first call is followed by at least two more within the hour (S10).
  - Testing: readers in all three rounds missed or could not follow this caveat, and found the arithmetic dense (testing).
  - Testing: the round-2 skimmer said the 1-hour break-even needed a calculation the text did not show; E5's table answers it (testing).
- Relations: C25 uses C17, C18, C19; worked in E3, E4, E5.

### C26 · Stable-first ordering
- Definition: Stable-first ordering puts content that is the same on every call first and content that varies last, so the stable part can be a cached prefix.
- Facts:
  - Put stable content first and variable content last (S10, S12).
  - Mytube's scoring prompt puts the fixed instructions, rubric and schema first and the user's goal and page items last (X1).
  - Tunatutor passes a fixed system prompt and the variable text as the user message, for example `SENTENCE_SYSTEM_PROMPT` then the sentence (X19).
  - The research's request path orders context assembly stable-first so prompt caching hits (S12).
  - Stable-first ordering is a property of how the prompt string is built, not a provider flag (X1).
- Relations: C26 enables C9 and C10; see the `context` block.

### C27 · Exact response cache
- Definition: An exact response cache stores the finished model answer under a key and, on a hit, makes no model call at all.
- Facts:
  - On a hit the exact cache makes no model call (S10).
  - This is the cache a Java engineer already knows (S10).
  - Prompt caching and the response cache work together: a miss in the response cache calls the model with a prompt ordered for prompt caching (S10).
  - Tunatutor's cache is a Postgres table, `panel_content_cache` (X16, S10).
  - Tunatutor's rows have no time-based expiry; a row stays until its version is out of date or it is evicted (S10, X13).
  - ADR-052: content is "generated once and cached without any user id"; "a hit costs no LLM call" (X33).
  - The research's mature version puts an exact-match cache at the gateway (S12).
- Relations: C27 solves P3; C27 is keyed by C28; C27 is invalidated by C38 and C36.

### C28 · Cache key
- Definition: The cache key is the value a response is stored and looked up under, and must include everything that changes a correct answer.
- Facts:
  - Tunatutor's key is `(kind, targetLanguage, nativeLanguage, cacheKey)`, enforced by a unique constraint (X16, S10).
  - The key must include everything that changes a correct answer, such as the language pair or the tenant (S10).
  - The key or the version must cover everything that changes the answer, call parameters included (S10).
  - Tunatutor's key has no user id (X13, X33).
  - Testing: readers missed that call parameters must be covered by the key or the version (testing).
  - Testing: the round-3 skimmer keyed the cache on "normalised input plus language" and dropped the tenant (testing).
- Relations: C28 is built from C29 and C30; C28 includes C32 in multi-tenant systems; C28 and C38 together define freshness.

### C29 · Normalisation
- Definition: Normalisation turns variants of the same input into one key, for example by trimming, lower-casing and collapsing whitespace.
- Facts:
  - For a word, Tunatutor's cacheKey is the lemma trimmed and lower-cased, so "Bonjour" and " bonjour " share one row (X12).
  - For a sentence, Tunatutor's cacheKey is a SHA-256 hash of the normalised text, so the key has a fixed length (X12, S10).
  - Sentence normalisation is trim, lower-case and collapse whitespace to one space (X12).
  - The original un-normalised lemma is still passed to the prompt, so capitalisation that carries meaning is preserved in generation (X12).
  - The cache-key file warns not to change the normalisation or hashing, or cache reads and writes will miss (X12).
  - Normalising can merge inputs that mean different things: German "Weg" (path) and "weg" (away) share one word key (S10).
  - Normalise only as far as the meaning allows (S10).
- Relations: C29 is part of C28; over-normalising is M10.

### C30 · kind (key component)
- Definition: `kind` is the first part of Tunatutor's cache key and says what is cached.
- Facts:
  - `kind` values include `"word"`, `"sentence"`, `"replies:they_may_ask"` and `"replies:you_can_answer"` (X16, X26).
  - Replies kinds come from `repliesCacheKind`, which returns `replies:<kind>` (X26).
  - The schema comment on `kind` says only `"word" | "sentence"` (X16).
  - Testing: "kind" was an unknown term in round 1 (testing).
- Relations: C30 is part of C28.

### C31 · Upsert
- Definition: An upsert inserts a row, or updates it if the key already exists.
- Facts:
  - Tunatutor writes cache rows with a Prisma `upsert` (X14).
  - Tunatutor's upsert sets `schemaVersion` to the writer's constant with no condition on the stored version (X14).
  - With two concurrent misses the upsert keeps the last answer (S10).
  - Testing: "upsert" was an unknown term in round 3 (testing).
- Relations: C31 is the write step of F4, F5; C31 without a guard causes C40.

### C32 · Tenant
- Definition: A tenant is one customer organisation in a service shared by many.
- Facts:
  - The key of a shared cache must include the tenant where answers differ per tenant (S10).
  - A semantic cache should be scoped per tenant, or per user where permissions differ (S10, S12).
  - Testing: "tenant" was an unknown term in round 2 (testing).
- Relations: C32 is part of C28 and C44; C32 replaces C21 in your own caches.

### C33 · Shared layer and personal layer
- Definition: A shared cache row holds content that fits every user and no personal data, and each user's own data is added to the response after the lookup and never stored in the shared row.
- Facts:
  - A shared row must hold no personal data and must not fit only one user (S10).
  - Lomem's design record says the shared cache is "never personalised" (X33).
  - "I went" in French is "je suis allé" for a man and "je suis allée" for a woman, so a sentence generated for one learner could be served to a learner it does not fit (S10, X33).
  - Every shared Tunatutor prompt writes the neutral « allé(e) » (S10, X33).
  - Only per-learner, uncached prompts use the learner's stored gender (X33).
  - Each learner's saved words and notes are added after the lookup and are never stored in the shared row (S10, X27, X33).
  - The shared bundle and the learner's own state load in parallel in `getSentencePanel` (X27).
  - A word note written in the practice language is dropped before it is cached, because the row is shared by everyone with that language pair (X22).
- Relations: C33 solves P5; see the `memory` and `guardrails` blocks.

### C34 · Non-determinism and temperature
- Definition: The same prompt can give a different answer on each call, so a model call is not a pure function.
- Facts:
  - The same prompt can give a different answer on each call, even at temperature 0 (S10).
  - Temperature is the setting that lowers randomness (S10).
  - A cache freezes one of the answers and serves it to everyone, so a bad answer is repeated to every user (S10).
  - Mytube calls Cerebras at temperature 0 for "deterministic rubric scoring" (X3, X4).
  - Testing: "sample" (one output of a non-deterministic model) was an unknown term in round 2 (testing).
  - Testing: no round-3 reader mentioned that the cache freezes one answer (testing).
- Relations: C34 causes P4; C34 is mitigated by C35 and C36.

### C35 · Validate before storing
- Definition: Validating before storing means parsing the model's JSON and checking required fields and types before the answer is written to the cache.
- Facts:
  - Tunatutor parses the JSON and checks that the required fields exist with the right types, such as `translation` and `breakdown` (S10, X20).
  - A sentence response that fails validation is never stored (S10, X19).
  - An optional field that fails its check is dropped rather than shown half-right (S10, X20).
  - ADR-052: "no data beats wrong data" (S14, `docs/adr/052-help-panel.md:79`; not in the X33 excerpt).
  - On the word path with curated facts, a failed call degrades to empty generated fields, and those empty fields are stored (S10; testing, fact-check; X22, X23).
  - On the word path without curated facts, `validateFullWordBundle` throws on missing arrays or an empty `senses`, and nothing is stored (X24).
  - Tunatutor re-checks some cached rows on read: sentence lines with an unclosed ¿ or ¡ are dropped on the way out (X21).
  - Testing: the senior reader read "validate before storing" as vague (testing).
- Relations: C35 limits C34; see the `structured` block.

### C36 · Eviction by user report
- Definition: Eviction by report lets users flag a bad cached answer so that the row is deleted and regenerated on its next read.
- Facts:
  - Give users a way to report a bad answer that evicts the row (S10).
  - Tunatutor files every report (S10, X28).
  - Tunatutor deletes the cached row once two different signed-in learners report that it is in the wrong language (S10, X28, X29).
  - Other kinds of report are kept for a person to review (S10, X28).
  - Only learners with saved accounts count, because "a new guest is one tap away" (X28, X29).
  - Only reports made after the row was last written count (X28, X29).
  - A report on a sentence deletes the sentence row and its two replies rows (X28).
  - Reports on content other than `sentence` or `word` are filed and never touch the cache (X28, X31).
  - The design reason: "a curious tap must not throw away a correct answer for everyone" (X28).
  - There is no reviewer tool yet (X33).
  - Testing: both round-1 readers missed the eviction path (testing).
- Relations: C36 mitigates C34; C36 is lifecycle L4; see the `hitl` and `evals` blocks.

### C37 · Concurrent misses
- Definition: Concurrent misses are two requests that miss the same key at the same moment, so both call the model and both write.
- Facts:
  - Both requests call the model and both write (S10).
  - The upsert keeps the last answer (S10).
  - The only cost is one extra model call (S10).
  - Add a lock only if a call is expensive enough that duplicates matter (S10).
  - ADR-052 says quick translations are "shared while in flight", one call per text and language pair (X33).
  - Testing: the round-3 skimmer did not mention concurrent misses (testing).
- Relations: C37 is a branch of F4 (F12).

### C38 · Version stamp and lazy invalidation
- Definition: A version stamp is a number from a code constant written into each cache row and compared on read, so a row from older code counts as a miss and regenerates on its next read.
- Facts:
  - A stored answer goes stale when the prompt, output format or model changes, even if no data changed (S10).
  - The version is compared on read, not put in the key, so a new answer overwrites the old row instead of leaving it behind (S10).
  - A row with a lower number counts as a miss and is regenerated on its next read; that is what "lazily" means (S10).
  - No migration job runs and the cost of regeneration spreads over normal traffic (S10).
  - Bump the version in the same commit that changes the prompt, the output schema or the model (S10).
  - Testing: an early analogy said "version in the key", which contradicted the code; readers picked up the contradiction (testing).
  - Testing: "lazily" was explained only implicitly in round 2 (testing).
  - Testing: the round-1 senior reader left the model out of what triggers a bump (testing).
- Relations: C38 solves P6; C38 is implemented by C39; C38 needs a guard against C40.

### C39 · PANEL_BUNDLE_SCHEMA_VERSION
- Definition: `PANEL_BUNDLE_SCHEMA_VERSION` is Tunatutor's code constant for the version stamped into every `panel_content_cache` row.
- Facts:
  - The current value is 6 (X17).
  - A "panel" is the Tunatutor screen that shows a bundle (S10).
  - The constant's comment says to bump it "whenever the WordBundle / SentenceBundle shape changes in a way that older cached rows can't satisfy" (X17).
  - Purely additive, always-optional fields such as `wordFamily` do not need a bump (X17).
  - Version 5 changed every prompt to the neutral « allé(e) », so every older row became a miss (S10, X17).
  - Version 6 added a check that rejects broken lines such as a Spanish ¿ that is never closed, and the bump sent every older row through that check (S10, X17).
  - The constant's comment calls a bump "the one-time sweep" (X17).
  - Lomem stores a model label in each row but does not compare it, so a model change needs a manual bump (S10, X13, X25).
  - Testing: "panel" and `PANEL_BUNDLE_SCHEMA_VERSION` were unknown terms in round 2 (testing).
  - Testing: the round-2 skimmer did not see that version 5 was a prompt change (testing).
- Relations: C39 implements C38; history in L3.

### C40 · Rolling-deploy race
- Definition: During a rolling deploy, an old instance that misses writes a row at the old version, and its upsert can overwrite a row the new code just wrote.
- Facts:
  - A rolling deploy runs old and new code side by side (S10).
  - The new code then regenerates the overwritten row, and rows flip until the last old instance stops (S10).
  - The cost is extra model calls (S10).
  - A write that updates only when the stored version is not higher than its own prevents this (S10).
  - Lomem's upsert has no such guard (S10, X14).
- Relations: C40 is caused by C31 without a guard; see the `rollout` block.

### C41 · Embedding
- Definition: An embedding is a list of numbers that a separate, cheap embedding model computes for a piece of text, such that texts with similar meanings get similar lists.
- Facts:
  - The embedding model is separate and cheap (S10).
  - Lomem has no embeddings and no semantic cache (S10, S13).
  - Testing: "embedding model" was only described as "separate, cheap" in round 2 (testing).
- Relations: C41 is the input of C42; see the `rag` block.

### C42 · Cosine similarity
- Definition: Cosine similarity is a score between two embeddings, in practice between 0 and 1 for text, where 1 means the same meaning.
- Facts:
  - Similarity is usually measured as cosine similarity (S10).
  - For text the score is in practice between 0 and 1 (S10).
  - Testing: readers did not know the similarity scale or distance measure in round 1 (testing).
- Relations: C42 is compared against C44.

### C43 · Semantic cache
- Definition: A semantic cache stores each answer with the embedding of its question and returns a stored answer when a new question's embedding is close enough to a stored one.
- Facts:
  - For a new question, the semantic cache computes the embedding, finds the closest stored one, and returns that answer if the score is above a threshold (S10).
  - A semantic cache can return a fluent wrong answer with no error (S10, S12).
  - A semantic cache shared across users can return another user's data (S10, S12).
  - The research says the semantic-cache risk is the author's own reading, not taken from a fetched source (S12).
  - Use a semantic cache only where a near-miss does little harm, such as FAQ answers with no personal data (S10).
  - Scope it per tenant, or per user where permissions differ (S10, S12).
  - Log each hit with the stored question it matched, so wrong matches can be found and the threshold raised (S10).
  - A semantic cache has no classic equivalent; picture a cache that returns the value of the nearest key when the exact key is missing (S10).
  - Lomem does not use a semantic cache (S10).
  - Testing: no round-3 reader mentioned logging each semantic hit with the question it matched (testing).
- Relations: C43 addresses P7 and causes new risk; C43 uses C41, C42, C44; offered by C45.

### C44 · Similarity threshold
- Definition: The similarity threshold is the minimum score at which a semantic cache treats two questions as the same.
- Facts:
  - 0.9 is the guide's own example threshold, not quoted from LiteLLM (S10; testing, fact-check).
  - To set the threshold, collect a few hundred real question pairs, label each pair as same answer or different answer, and pick the lowest threshold at which no different-answer pair matches (S10).
  - If no threshold separates the pairs while still giving useful hits, do not use a semantic cache for that content (S10).
  - The research's mature version tunes the threshold "by evals" (S12).
- Relations: C44 is calibrated in F14; see the `evals` block.

### C45 · Gateway caching
- Definition: A gateway is a proxy between the service and the provider, and products such as LiteLLM offer exact and semantic caching in it.
- Facts:
  - LiteLLM offers semantic caching with modes `redis-semantic`, `valkey-semantic` and `qdrant-semantic` (S3; testing, fact-check).
  - The research lists "exact and semantic caching" among a mature self-hosted gateway's features (S12).
  - Redis LangCache is a managed semantic cache (S4, S12).
  - GPTCache is an open-source semantic cache (S5, S12).
  - Testing: "gateway", LiteLLM, Redis LangCache and GPTCache were unknown or only hinted at for readers (testing).
- Relations: C45 hosts C27 and C43; see the `gateway` block.

### C46 · Pre-warming
- Definition: Pre-warming fills the cache with the most common questions before users ask them.
- Facts:
  - Pre-warming is part of the mature version (S10).
  - Lomem has a pre-warm script, `scripts/prewarm-panel-cache.ts` (S13, X34).
  - The script seeds the top-N frequency lemmas of a target language, default 50, so the first real request is a hit (X34).
  - Testing: "pre-warming" was an unknown term in round 1, and in round 2 "Lomem has a script for this" pointed at something readers could not see (testing).
- Relations: C46 feeds C27 via F15.

### C47 · Bundle
- Definition: A bundle is Lomem's name for the JSON document the model writes for a word or a sentence, holding the translation, an example and a usage note.
- Facts:
  - A learner types a word or sentence, for example « un tire-bouchon », and gets back a translation, an example and a usage note as a bundle (S10).
  - Testing: "bundle" was only loosely defined in round 1 (testing).
- Relations: C47 is the value stored under C28.

### C48 · Breakdown
- Definition: `breakdown` is a sentence-bundle field with one entry per word of the sentence, giving its part of speech and translation.
- Facts:
  - `breakdown` is a required array in `validateSentenceBundle` (X20).
  - ADR-052 says `breakdown` is "kept for word taps and counts, never drawn as a word grid" (S14).
  - Testing: "breakdown" was an unknown term in round 3 (testing).
- Relations: C48 is checked by C35.

### C49 · Lemma and reading
- Definition: A lemma is the dictionary form of a word, and Tunatutor keys a word row on the normalised lemma and stamps it with the reading (part of speech) it was written for.
- Facts:
  - The word cacheKey is `wordCacheKey(lemma)`, the lemma trimmed and lower-cased (X12).
  - A word row written for another reading of the word, such as the noun « un bonjour » when the word is read as the greeting, counts as a miss (X22).
  - Testing: "lemma" was an unknown term in round 1 (testing).
- Relations: C49 is part of C28.

### C50 · Curated-first word panel
- Definition: When curated dictionary facts exist for a word, Tunatutor asks the model only for the generative fields, grounded on those facts, and stores a generative-only row.
- Facts:
  - Curated facts come from `word_cache` (pos, gender, ipa, senses, examples) (X22, X17).
  - Generated fields are synonyms, antonyms, collocations, wordFamily and notes (X17).
  - When curated facts are absent, the full word prompt runs and a full bundle is stored (X22).
  - The research files this grounding under retrieval, citing ADR-052 line 77 and `panel-content/index.ts` lines 5-11 (S13).
- Relations: C50 is the grounding pattern of the `rag` block; C50 creates the degrade branch of F6.

### C51 · Hit-rate dashboard
- Definition: A hit-rate dashboard charts the cache-read share over time.
- Facts:
  - A mature version adds a hit-rate dashboard (S10).
  - Chart the share of input tokens served from the cache (S10).
- Relations: C51 displays C24; see the `observability` block.

### C52 · Cached-input metering
- Definition: Cached-input metering records cached input tokens as their own cost line, priced below uncached input.
- Facts:
  - Tunatutor writes up to three ledger rows per call: `:text-input` (uncached), `:text-input-cached` and `:text-output` (X9).
  - Thinking tokens are billed as output and join the output row (X9).
  - Tunatutor clamps cached input so it never exceeds input, and computes uncached input as input minus cached (X9).
  - A model cannot be made active or a fallback unless all three price keys have an active `provider_price_config` row (X11).
  - Mytube logs `cacheReadTokens` per `llm_call` event but prices all input tokens at the full input rate (X4, X5, X6).
  - ADR-057 §5: "MyTube, outside this programme, still calls a provider directly (`createLlmClient`)", so the shared meter's three rows (X41) do not cover Mytube (S13; the "so" is derived).
- Relations: C52 uses C23; see the `observability` and `gateway` blocks.

### C53 · Client-side prompt cache (prompt registry)
- Definition: A prompt registry client caches the prompt text locally so fetching a prompt adds no latency.
- Facts:
  - In a mature prompt registry, clients cache the prompt, so fetching it adds no latency (S12, S9).
- Relations: C53 is a different cache from C10; see the `prompts` block.

### C54 · ADR
- Definition: An ADR (architecture decision record) is a design note in `docs/adr/`.
- Facts:
  - ADR-052 covers Tunatutor's help panel and its shared content cache, §3 (S14, X33).
  - Testing: "ADR" was expanded only implicitly as "design record" in round 1 (testing).
- Relations: C54 is the source of X33.

## Components

| id | name | role | inputs | outputs | where it lives |
|---|---|---|---|---|---|
| K1 | Provider prefix cache | Keeps the provider's per-token computation over a prefix for 5 minutes or 1 hour and reuses it on an exact match | request tokens up to a marker (Anthropic) or automatically (OpenAI) | cache hit or write; usage counts | provider side, invisible to the caller (S1, S2) |
| K2 | `cache_control` marker | Marks where an Anthropic cached prefix ends; up to four per request | a tool definition, system block or message content block | one cached prefix per marker | Anthropic Messages API (S1) |
| K3 | Usage object | Reports how input tokens split between uncached, written and read | one model call | `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens` (Anthropic); `cachedContentTokenCount` (Gemini); `prompt_tokens_details.cached_tokens` (OpenAI-compatible) | provider response (S1, X7, X8) |
| K4 | `panel_content_cache` table | Shared exact response cache for word, sentence and replies bundles | upserted bundle, key, version, model label | row `{bundle, model, schemaVersion, updatedAt}` | Postgres, `apps/tunatutor/backend/prisma/schema.prisma:2196-2211` (X16) |
| K5 | Cache-key helpers | Normalise input into a stable key | lemma or sentence text | `wordCacheKey`, `sentenceCacheKey` (SHA-256 hex) | `apps/tunatutor/backend/src/services/panel-content/cache-key.ts` (X12) |
| K6 | Cache repository | Reads with a version check, upserts, deletes | four-part key; bundle; model | row or `null`; `true`/`false` on delete | `apps/tunatutor/backend/src/services/panel-content/repository.ts` (X13, X14, X15) |
| K7 | Schema version constant | Global version stamped on write and compared on read | developer bump | `PANEL_BUNDLE_SCHEMA_VERSION = 6` | `apps/tunatutor/backend/src/services/panel-content/schema-version.ts:52` (X17) |
| K8 | Panel-content service | Get-or-generate for words and sentences: key, look up, call model on miss, validate, store | text or lemma, language pair, deps | `SentenceBundle`, `{bundle, curated}` for words | `apps/tunatutor/backend/src/services/panel-content/index.ts` (X18-X24) |
| K9 | Replies service | Get-or-generate for "They may ask you" / "You can answer" replies; caches only full answers | line text, replies kind, language pair | `RepliesPanelDTO` | `apps/tunatutor/backend/src/services/panel-content/replies.ts` (X26) |
| K10 | Panel-content deps | Wires the repo and an LLM call billed to one learner; sets the neutral model label | `userId` | deps object with `repo`, `callLlm`, `modelId = "panel-content/registry"` | `apps/tunatutor/backend/src/services/panel-content/deps.ts` (X25) |
| K11 | `getSentencePanel` use case | Merges the shared bundle with the learner's personal layer | `userId`, language pair, text | `{ ...bundle, personal }` | `apps/tunatutor/backend/src/use-cases/panels/get-sentence-panel.ts` (X27) |
| K12 | `reportAnswer` use case | Files every report; evicts a shared row after two distinct saved learners report `wrong_language` | report request, user, language pair | `{ rewriteQueued }` | `apps/tunatutor/backend/src/use-cases/panels/report-answer.ts` (X28) |
| K13 | Report route and its deps | `POST /api/panels/report`; supplies `cacheWrittenAt`, `countWrongReporters`, `deleteCache` | HTTP body | report result | `apps/tunatutor/backend/src/routes/panels.ts:757-800` (X29) |
| K14 | `AnswerReport` table | Stores every "Something wrong?" report | report row | rows counted for eviction | Prisma schema (X32) |
| K15 | Pre-warm script | Seeds the cache with the top-N frequency lemmas | `--target`, `--native`, `--n`, `--dry-run` | cache rows; hit/generated/error counts | `apps/tunatutor/backend/scripts/prewarm-panel-cache.ts` (X34) |
| K16 | Tunatutor LLM meter | Writes uncached, cached and output ledger rows per call | provider usage | `:text-input`, `:text-input-cached`, `:text-output` rows | `apps/tunatutor/backend/src/services/llm/index.ts:163-233` (X9) |
| K17 | Provider price config | Prices each of the three token keys; a model without them cannot be activated | seeded rows, admin edits | USD per million tokens | `apps/tunatutor/backend/src/dev/provider-prices.ts`, `services/llm/registry.ts` (X10, X11) |
| K18 | Gemini provider usage mapping | Maps Gemini usage to shared fields | `usageMetadata` | `inputTokens`, `cachedInputTokens`, `thoughtTokens`, `outputTokens` | `packages/shared/src/llm/providers/gemini.ts:187-195` (X8) |
| K19 | Cerebras provider usage mapping | Maps OpenAI-compatible usage to shared fields | `usage` | `inputTokens`, `outputTokens`, `cachedInputTokens` | `packages/shared/src/llm/providers/cerebras.ts:181-188` (X7) |
| K20 | Mytube scoring prompt builder | Builds the scoring prompt stable-first | goal JSON, items JSON | one prompt string | `apps/mytube/web/lib/llm/prompts.ts` (X1, X2) |
| K21 | Mytube LLM adapter | Calls Cerebras at temperature 0; logs `cacheReadTokens` | prompt string | text, token counts, `llm_call` event | `apps/mytube/web/lib/llm/index.ts` (X3, X4, X5) |
| K22 | Mytube pricing | Computes cost from input and output tokens only | token counts | USD | `apps/mytube/web/lib/llm/pricing.ts` (X6) |
| K23 | Line checks | Rejects lines with an unclosed ¿ or ¡ on write and read | a line of text | showable or not | `apps/tunatutor/backend/src/services/panel-content/line-checks.ts` (X40), `index.ts` (X21) |
| K24 | "Something wrong?" sheet | UI where a learner reports an answer | tap, reason, optional note | `POST /api/panels/report` | `apps/tunatutor/frontend/src/components/something-wrong/SomethingWrong.tsx` (X33) |
| K25 | Embedding model | Computes an embedding for a text | text | list of numbers | generic (S10) |
| K26 | Semantic cache store | Stores (question embedding, answer); returns nearest above threshold | embedding | answer or miss | generic; LiteLLM, Redis LangCache, GPTCache (S3, S4, S5) |
| K27 | Gateway with caching | Proxy that can host exact and semantic caching | model requests | cached or forwarded responses | generic; LiteLLM proxy (S3, S12) |
| K28 | Hit-rate dashboard | Charts the cache-read share | logged usage counts | share over time | generic (S10) |

## Flows

### F1 · Anthropic prompt caching across calls
- Purpose: show how a marked prefix is written once and read by later calls.
- Trigger: a service sends a request whose prefix carries a `cache_control` marker.
- Values: made up (S10); the real Mytube calls Cerebras and sends no marker.

- F1.1 · Service → Anthropic API: request for user A with tools, a 6,000-token system prompt ending in a `cache_control` marker, and a 900-token user message | condition: first call | data: tools, system blocks, messages | ref: S1, S10, E1
- F1.2 · Anthropic API → provider prefix cache: look up the exact prefix up to the marker | condition: always | data: prefix tokens, model, organization, workspace | ref: S1
- F1.3 · Provider prefix cache → Anthropic API: miss | condition: no entry with an identical prefix | data: none | ref: S1
- F1.3b · if the prefix is below the model's minimum (512 to 4,096 tokens), nothing is cached and no error is raised; usage shows creation 0 and read 0 → continues at F1.5 | ref: S1, C20
- F1.4 · Anthropic API → provider prefix cache: write the prefix with a 5-minute lifetime (1 hour if `"ttl": "1h"`) | condition: prefix ≥ minimum | data: per-token computation | ref: S1, C14
- F1.5 · Anthropic API → service: answer plus usage `input_tokens: 900, cache_creation_input_tokens: 6000, cache_read_input_tokens: 0` | condition: miss | data: answer, usage | ref: E1
- F1.6 · Service → Anthropic API: request for user B with the same tools and system prompt and a new 900-token user message | condition: within 5 minutes of the last hit or write | data: same prefix, new tail | ref: E1
- F1.7 · Anthropic API → provider prefix cache: lookup hits; the entry's lifetime is renewed | condition: identical prefix, same model, same organization/workspace | data: none | ref: S1, C19
- F1.8 · Anthropic API → service: answer plus usage `input_tokens: 900, cache_creation_input_tokens: 0, cache_read_input_tokens: 6000`; the read is billed at 0.1x on most models | condition: hit | data: answer, usage | ref: E1, C18
- F1.6b · if the next call comes more than 5 minutes (or 1 hour) after the last hit, the entry has expired; the call writes again at 1.25x (or 2x) → continues at F1.5 | ref: S10, C25
- F1.6c · if a token near the top differs (timestamp, request id, user name, tools reordered), no prefix matches; every call writes a new entry and the read share stays 0 → continues at F1.4 | ref: S10, M1, M2
- F1.6d · if the same prefix is sent to another model, it misses on that model → continues at F1.4 | ref: S10, C12 (unverified for Anthropic)
- F1.6e · if a request has the same tools but a different system prompt and a separate marker sits after the tools, the tools prefix is read from the cache and the system prompt is written → continues at F1.8 with a partial read | ref: S10, C15

### F2 · Chat turn with a moving marker
- Purpose: cache a growing chat history turn by turn.
- Trigger: each new user turn in a chat.

- F2.1 · Service → service: append the new user message to the stored history | condition: every turn | data: history | ref: S10
- F2.2 · Service → service: write the newest message's content as a list of content blocks and put `cache_control` on its last block | condition: every turn | data: content blocks | ref: S10, C16
- F2.3 · Service → service: remove the marker from the previous turn's last message (the marker moves) | condition: turn 2 onwards | data: none | ref: S10
- F2.4 · Service → Anthropic API: send tools, system, full history | condition: always | data: request | ref: S10
- F2.5 · Anthropic API → service: earlier turns read from the cache; only the new turn is written; `input_tokens` close to 0 and `cache_creation_input_tokens` equal to the newest turn | condition: earlier prefix still alive | data: usage | ref: S10
- F2.5b · if the earlier turns' entry expired (no call for 5 minutes), the whole history is written again → continues at F2.1 on the next turn | ref: S10, C19 (derived)

### F3 · Verifying that the prompt cache works
- Purpose: prove from token counts that caching happens and is healthy.
- Trigger: every model call; review on a dashboard.

- F3.1 · Service → log: record `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens` per call | condition: every call | data: three counts | ref: S10, C23
- F3.2 · Dashboard → dashboard: compute `read / (read + creation + input)` over a window | condition: periodic | data: share | ref: S10, C24
- F3.3 · Engineer → dashboard: compare the share with the ceiling `prefix / (prefix + tail)` | condition: always | data: ceiling | ref: S10, E2
- F3.4a · if the share is near the ceiling, the cache is healthy → end | ref: S10
- F3.4b · if creation and read are both 0 on every call, nothing is cached: the prefix is under the minimum or no marker is sent → fix at F1.1 | ref: S1, C20
- F3.4c · if creation is above 0 on every call and read stays 0, the prefix changes between calls (timestamp at the top, unstable tool order) → fix ordering (C26) | ref: S10 (derived from F1.6c)

### F4 · Generic exact response cache
- Purpose: answer a repeated question without a model call.
- Trigger: a request whose answer can be shared.
- Ref: S10, S11.

- F4.1 · Service → service: normalise the input and build the key from it plus everything that changes a correct answer (language pair, tenant) | condition: always | data: key | ref: S10, C28, C29
- F4.2 · Service → store: look up the row | condition: always | data: key | ref: S10
- F4.3 · Store → service: row with its version | condition: row exists | data: answer, version | ref: S10
- F4.4 · Service → caller: return the cached answer with no model call | condition: row exists and version is current | data: answer | ref: S10, C38
- F4.3b · if no row exists, or the row's version is older than the code constant → continues at F4.5 | ref: S10
- F4.5 · Service → model: call with the prompt ordered for prompt caching | condition: miss | data: prompt | ref: S10, F1
- F4.6 · Service → service: parse and validate the answer | condition: always after F4.5 | data: JSON | ref: S10, C35
- F4.6b · if validation fails, do not store; return an error (or a degraded answer that is not stored) → end | ref: S10
- F4.7 · Service → store: upsert the answer with the current version | condition: valid | data: key, answer, version | ref: S10, C31
- F4.8 · Service → service: add the user's personal layer to the response, never to the stored row | condition: shared cache | data: personal data | ref: S10, C33
- F4.9 · Service → caller: return the answer | condition: always | data: answer | ref: S10

### F5 · Tunatutor sentence panel (real code)
- Purpose: serve a sentence explanation from the shared cache or generate it once.
- Trigger: `POST /api/panels/sentence {text}`.

- F5.1 · Learner app → panels route: `POST /api/panels/sentence` behind `dailySpendEntryGate`, `entryGate`, `panelLimiter` | condition: always | data: `text`, language pair | ref: X30
- F5.2 · Panels route → `getSentencePanel`: call with `{userId, language, nativeLanguage, text}` and deps built for this learner | condition: always | data: input | ref: X30, X27
- F5.3 · `getSentencePanel` → panel-content service: `getOrGenerateSentence({text, targetLanguage, nativeLanguage})`, in parallel with loading the learner's lemma states and saved phrase | condition: always | data: text, language pair, no user id | ref: X27
- F5.4 · Panel-content service → cache-key helpers: `sentenceCacheKey(text)` = SHA-256 of trimmed, lower-cased, whitespace-collapsed text | condition: always | data: hex key | ref: X19, X12
- F5.5 · Panel-content service → repository: `get({kind: "sentence", targetLanguage, nativeLanguage, cacheKey})` | condition: always | data: four-part key | ref: X19
- F5.6 · Repository → Postgres: `findUnique` on the four-part key, selecting `bundle`, `model`, `schemaVersion` | condition: always | data: key | ref: X13
- F5.7 · Repository → panel-content service: `{bundle, model}` | condition: row exists and `schemaVersion >= 6` | data: bundle | ref: X13
- F5.8 · Panel-content service → `getSentencePanel`: bundle after `sanitizeCachedSentence` (drops lines with an unclosed ¿ or ¡) and `withBundleOpeningMarks`; zero LLM calls | condition: hit | data: SentenceBundle | ref: X19, X21 → continues at F5.15
- F5.7b · if no row exists, or `schemaVersion < 6` (stale), the repository returns `null` → continues at F5.9 | ref: X13
- F5.9 · Panel-content service → LLM gateway: `callLlm(SENTENCE_SYSTEM_PROMPT, [{role: "user", content}], sentenceMaxTokens(text))`, billed to this learner under the help-panel surface | condition: miss | data: fixed system prompt, variable user content | ref: X19, X25
- F5.10 · LLM gateway → Gemini: generate | condition: always | data: request | ref: X25, S13
- F5.11 · LLM gateway → ledger: write `:text-input`, `:text-input-cached`, `:text-output` rows | condition: tokens reported | data: counts | ref: X9, F16
- F5.11b · if the answer did not finish normally (`finishReason` not `STOP`), deps log a warning with the tail of the text, then return the text anyway → continues at F5.12 | ref: X25
- F5.12 · Panel-content service → service: `extractJson(raw)` then `validateSentenceBundle(parsed)` then `withBundleOpeningMarks` | condition: always | data: parsed JSON | ref: X19, X18, X20
- F5.12b · if no JSON object, unparsable JSON, or a required field (`text`, `translation`, `breakdown`, `otherWays`, `grammarCallouts`) is missing, throw `PanelContentGenerationError`; nothing is stored → error to the route, end | ref: X18, X20
- F5.12c · if an optional field (other-way tags, chunks, keyFacts, v6 `level`, `simpler`, `regionTag`) fails its check, it is dropped to its empty value and the bundle continues → continues at F5.13 | ref: X20
- F5.13 · Panel-content service → repository: `put({kind: "sentence", ..., bundle: validated, model: "panel-content/registry"})` | condition: valid | data: bundle, model label | ref: X19, X25
- F5.14 · Repository → Postgres: upsert stamping `schemaVersion: 6`, with no condition on the stored version | condition: always | data: row | ref: X14
- F5.15 · `getSentencePanel` → `getSentencePanel`: build the personal layer and return `{ ...bundle, personal }` | condition: always | data: personal layer never written to the cache | ref: X27
- F5.16 · Panels route → learner app: `SentencePanelDTO` | condition: always | data: JSON | ref: X30

### F6 · Tunatutor word panel with curated facts (real code)
- Purpose: build a word panel from curated dictionary facts plus cached or generated fields.
- Trigger: a word panel request where `resolveCuratedWordFacts` finds the word.

- F6.1 · Panel-content service → cache-key helpers: `wordCacheKey(lemma)` = trimmed, lower-cased lemma | condition: always | data: key | ref: X22, X12
- F6.2 · Panel-content service → word_cache: resolve curated facts, or reuse `preResolvedCurated` from a streaming caller | condition: always | data: lemma, language pair | ref: X22
- F6.3 · Panel-content service → repository: `get({kind: "word", ...})` | condition: always | data: key | ref: X22, X13
- F6.4 · Panel-content service → service: hit when a row exists and its stored reading equals the curated part of speech, or the row stores no reading (legacy row) | condition: curated present | data: `readingPos` | ref: X22
- F6.5 · Panel-content service → service: take the generative fields from the row and run `dropPracticeLanguageNotes`; zero LLM calls | condition: hit | data: fields | ref: X22 → continues at F6.10
- F6.5b · if a note in the practice language was dropped, rewrite the row without it, keeping the row's stored model label → continues at F6.10 | ref: X22
- F6.4b · if no row, a stale row, or a row for another reading (« un bonjour » noun versus the greeting) → continues at F6.6 | ref: X22, X13
- F6.6 · Panel-content service → LLM gateway: `generateGroundedFields`: one narrowed, grounded call with `WORD_GENERATIVE_SYSTEM_PROMPT` and the curated facts in the user prompt | condition: miss | data: prompt | ref: X23
- F6.7 · Panel-content service → service: `extractJson` then `validateGenerativeWordFields` (requires `synonyms`, `antonyms`, `collocations` arrays) | condition: always | data: JSON | ref: X23, X24
- F6.7b · if the LLM call, parsing or validation fails, `generateGroundedFields` catches the error and returns empty generative fields → continues at F6.8 | ref: X23
- F6.8 · Panel-content service → service: `dropPracticeLanguageNotes` before caching, because the row is shared | condition: always | data: fields | ref: X22
- F6.9 · Panel-content service → repository: `put` a generative-only bundle stamped with the reading, with `model: "panel-content/registry"`; this happens even when the fields are empty | condition: always after F6.8 | data: row | ref: X22, X14
- F6.10 · Panel-content service → caller: `{ bundle: assembleWordBundle(curated, fields), curated }` | condition: always | data: word bundle | ref: X22

### F7 · Tunatutor word panel without curated facts (real code)
- Purpose: build a full word bundle from one ungrounded call when no curated facts exist.
- Trigger: a word panel request where `resolveCuratedWordFacts` returns `null`.

- F7.1 · Panel-content service → repository: `get({kind: "word", ...})` | condition: curated absent | data: key | ref: X22
- F7.2 · Panel-content service → service: normalise synonyms and antonyms of the stored bundle and drop a practice-language note | condition: hit | data: bundle | ref: X22
- F7.2b · if a note was dropped, rewrite the row keeping its model label → continues at F7.3 | ref: X22
- F7.3 · Panel-content service → caller: `{ bundle, curated: null }`; zero LLM calls | condition: hit | data: bundle | ref: X22 → end
- F7.1b · if no row or stale → continues at F7.4 | ref: X22, X13
- F7.4 · Panel-content service → LLM gateway: `callLlm(WORD_FULL_SYSTEM_PROMPT, [user], WORD_FULL_MAX_TOKENS)` | condition: miss | data: prompt | ref: X22
- F7.5 · Panel-content service → service: `extractJson` then `validateFullWordBundle` then `dropPracticeLanguageNotes` | condition: always | data: JSON | ref: X22, X24
- F7.5b · if a required field is missing or `senses` is empty, throw `PanelContentGenerationError`; nothing is stored → end | ref: X24
- F7.6 · Panel-content service → repository: `put` the full bundle | condition: valid | data: row | ref: X22
- F7.7 · Panel-content service → caller: `{ bundle, curated: null }` | condition: always | data: bundle | ref: X22

### F8 · Tunatutor replies (real code)
- Purpose: cache the replies to a line only when the answer is complete.
- Trigger: a request for "They may ask you" (`they_may_ask`) or "You can answer" (`you_can_answer`) replies.

- F8.1 · Replies service → service: `cacheKind = "replies:" + kind`; `cacheKey = sentenceCacheKey(text)` | condition: always | data: key | ref: X26
- F8.2 · Replies service → repository: `get` | condition: always | data: key | ref: X26
- F8.3 · Replies service → caller: cached replies with opening marks added | condition: row exists, every line passes `isShowableLine`, and the list is empty or has exactly `MAX_REPLY_LINES[kind]` lines (2 for `they_may_ask`, 3 for `you_can_answer`) | data: replies | ref: X26, X31, X40 → end
- F8.3b · if the row holds a broken line or is short, it counts as a miss → continues at F8.4 | ref: X26
- F8.4 · Replies service → LLM gateway: call with the replies system prompt and the line (attempt 1 of `MAX_ATTEMPTS = 2`) | condition: miss | data: prompt | ref: X26
- F8.5 · Replies service → service: parse, validate, add opening marks | condition: always | data: replies | ref: X26
- F8.6 · Replies service → repository: `put` and return | condition: full answer (the model's own empty list, or exactly the kind's line count) | data: row | ref: X26 → end
- F8.6b · if short, keep the longer answer so far and ask once more → continues at F8.4 (attempt 2) | ref: X26
- F8.7 · Replies service → caller: the longer short answer, not cached, so the next ask tries again | condition: still short after 2 attempts and at least one usable line | data: replies | ref: X26
- F8.7b · if no usable line at all, throw `PanelContentGenerationError`; the replies route answers with no lines | ref: X26, `apps/tunatutor/backend/src/routes/panels.ts:750-752`

### F9 · Report and eviction (real code)
- Purpose: let learners remove a bad shared answer without one tap discarding a good one.
- Trigger: a learner taps "Something wrong?" and sends a reason.

- F9.1 · Learner app → report route: `POST /api/panels/report {surface, reason, content, text, shown, note}` behind `reportLimiter` only (no LLM call, so no spend gates) | condition: always | data: report | ref: X29
- F9.2 · Report route → `reportAnswer`: call with the learner, language pair and report | condition: always | data: report | ref: X29
- F9.3 · `reportAnswer` → service: `cacheKeyFor(content, text)`: `sentenceCacheKey` for `sentence`, `wordCacheKey` for `word`, `null` otherwise | condition: always | data: key | ref: X28
- F9.4 · `reportAnswer` → `AnswerReport` table: `saveReport` always | condition: always | data: row | ref: X28, X32
- F9.4b · if `reason !== "wrong_language"` or the key is `null` (content `answer`) → return `{rewriteQueued: false}`; end | ref: X28
- F9.5 · `reportAnswer` → Postgres: `cacheWrittenAt(ref)` reads the main row's `updatedAt` | condition: wrong_language with a key | data: kind, pair, key | ref: X28, X29
- F9.5b · if no cached row (nothing cached, or already regenerating) → return `{rewriteQueued: false}`; end | ref: X28
- F9.6 · `reportAnswer` → `AnswerReport` table: `countWrongReporters`: distinct `userId` with reason `wrong_language`, `createdAt >= updatedAt`, `user.isAnonymous = false` | condition: row exists | data: count | ref: X29
- F9.6b · if fewer than `REWRITE_REPORT_THRESHOLD = 2` → return `{rewriteQueued: false}`; end | ref: X28
- F9.7 · `reportAnswer` → Postgres: delete the main row and its linked rows (sentence: plus `replies:they_may_ask` and `replies:you_can_answer`; word: the word row only) | condition: 2 or more reporters | data: keys | ref: X28, X15
- F9.8 · Report route → learner app: `{rewriteQueued: true}` | condition: deleted | data: JSON | ref: X28
- F9.9 · Next learner → panel-content service: the next read of the key misses and regenerates | condition: later | data: none | ref: X28 → F5.9 or F6.6

### F10 · Version bump and lazy regeneration
- Purpose: invalidate every old answer after a change to the prompt, schema or model without a migration job.
- Trigger: a developer changes the prompt, the output schema, the model or call parameters.

- F10.1 · Developer → code: change the prompt, schema, model or call parameter and bump `PANEL_BUNDLE_SCHEMA_VERSION` in the same commit | condition: the change makes older rows wrong | data: N → N+1 | ref: S10, X17
- F10.1b · if the change only adds an always-optional field (such as `wordFamily`), no bump is needed; old rows still validate and hit → end | ref: X17
- F10.2 · Deploy → instances: new code reads with version N+1 | condition: deploy | data: none | ref: S10
- F10.3 · Learner → repository: read a row stamped N | condition: next read of that key | data: key | ref: X13
- F10.4 · Repository → service: `null` (stale counts as miss) | condition: `schemaVersion < N+1` | data: none | ref: X13
- F10.5 · Service → model → repository: regenerate, validate, upsert at N+1 | condition: miss | data: new row | ref: F5.9-F5.14
- F10.6 · Rows not read again stay at N, unused, with no expiry | condition: no traffic for that key | data: none | ref: S10

### F11 · Rolling-deploy overwrite
- Purpose: show how an unguarded upsert lets old code overwrite new rows during a deploy.
- Trigger: a rolling deploy that bumps the version while old instances still serve.
- Values: version numbers made up for illustration; mechanism from S10 and X14.

- F11.1 · Deploy → cluster: instance NEW runs version 6 code; instance OLD still runs version 5 code | condition: rolling deploy | data: none | ref: S10
- F11.2 · Learner X → NEW: read key K; the row is at version 5 → miss; NEW calls the model and upserts K at version 6 | condition: stale | data: row v6 | ref: X13, X14
- F11.3 · Learner Y → OLD: read key K; OLD sees version 6 ≥ 5 → hit; OLD serves the newer row | condition: row v6 | data: none | ref: X13 (derived)
- F11.4 · Learner Z → OLD: a miss on K (for example after an eviction); OLD calls the model and upserts K at version 5, overwriting any version-6 row written meanwhile | condition: OLD misses | data: row v5 | ref: S10, X14
- F11.5 · Next read on NEW: the row is at version 5 → miss → regenerate → version 6 | condition: NEW reads | data: row v6 | ref: S10
- F11.6 · Rows flip until the last OLD instance stops; the cost is extra model calls | condition: until deploy completes | data: none | ref: S10
- F11.4b · if the write updates only when the stored version is not higher than the writer's own, OLD's write at F11.4 is skipped → no flip | ref: S10 (Lomem has no such guard, X14)

### F12 · Concurrent misses
- Purpose: show the cost of two simultaneous misses on the same key.
- Trigger: two requests for the same key arrive before either has written.

- F12.1 · Request A → store: miss | condition: no row | data: key | ref: S10
- F12.2 · Request B → store: miss | condition: A has not written yet | data: key | ref: S10
- F12.3 · A and B → model: both call the model | condition: both missed | data: two calls | ref: S10
- F12.4 · A and B → store: both upsert; the last write wins | condition: both valid | data: row | ref: S10
- F12.5 · Cost: one extra model call | ref: S10
- F12.3b · if a call is expensive enough that duplicates matter, add a lock so only one call runs and the other waits for its result (ADR-052's quick translations are "shared while in flight") | ref: S10, X33

### F13 · Semantic cache lookup
- Purpose: reuse an answer for a question with the same meaning.
- Trigger: a question arrives at a service with a semantic cache.
- Values: made up (S10).

- F13.1 · Service → embedding model: compute the embedding of the new question | condition: always | data: text | ref: S10
- F13.2 · Service → semantic cache store: find the closest stored question embedding within the tenant's scope | condition: always | data: embedding, tenant | ref: S10
- F13.3 · Service → caller: return the stored answer | condition: cosine score above the threshold (example 0.9) | data: answer | ref: S10
- F13.4 · Service → log: record the hit with the stored question it matched | condition: hit | data: new question, matched question, score | ref: S10
- F13.2b · if no stored question scores above the threshold → call the model, then store (question embedding, answer) → end | ref: S10
- F13.3b · if the nearest question has a different meaning but scores above the threshold, a fluent wrong answer is returned and no error is raised (E17) | ref: S10
- F13.3c · if the cache is shared across users and the stored answer holds one user's data, the next user sees it (E18) | ref: S10

### F14 · Calibrating a semantic-cache threshold
- Purpose: pick a threshold from data, or decide not to use a semantic cache.
- Trigger: before enabling a semantic cache for a content type.

- F14.1 · Team → data: collect a few hundred real question pairs | ref: S10
- F14.2 · Team → data: label each pair as same answer or different answer | ref: S10
- F14.3 · Team → analysis: pick the lowest threshold at which no different-answer pair matches | ref: S10
- F14.4 · Team → service: enable the cache with that threshold, scoped per tenant (or per user where permissions differ) | condition: the threshold still gives useful hits | ref: S10
- F14.4b · if no threshold separates the pairs while still giving useful hits, do not use a semantic cache for that content → end | ref: S10
- F14.5 · Team → logs: review logged hits with their matched questions and raise the threshold when wrong matches appear | condition: ongoing | ref: S10

### F15 · Pre-warm script (real code)
- Purpose: fill the cache with common words before learners ask.
- Trigger: an operator runs `tsx scripts/prewarm-panel-cache.ts --target <language> --native <language> [--n <number>] [--dry-run]`.

- F15.1 · Script → script: parse flags; `--n` defaults to 50 | condition: always | data: args | ref: X34
- F15.1b · if `--target` or `--native` is missing, print an error and exit 1 → end | ref: X34
- F15.2 · Script → LLM registry: `initLLMRegistry()` | condition: always | data: none | ref: X34
- F15.3 · Script → word_cache: select the top-N lemmas by `frequency_rank` | condition: always | data: language, n | ref: X34
- F15.3b · if no ranked lemmas, print a hint to load the word cache and return → end | ref: X34
- F15.4 · Script → script: for each lemma, skip with a log line in `--dry-run` | condition: dry run | data: none | ref: X34
- F15.5 · Script → repository: `getPanelContent` with `cacheKey: form` (not `wordCacheKey(form)`) | condition: not dry run | data: key | ref: X34
- F15.5b · if a row exists → count a hit and continue with the next lemma | ref: X34
- F15.6 · Script → panel-content service: `getOrGenerateWord({lemma: form, ...}, panelContentDeps)`, which writes the cache | condition: miss | data: lemma | ref: X34, F6, F7
- F15.6b · if it throws, log the error, count it and continue with the next lemma | ref: X34
- F15.7 · Script → stdout: print `hit`, `generated`, `error` counts | condition: end | data: stats | ref: X34

### F16 · Tunatutor metering of cached input (real code)
- Purpose: price cached input on its own line.
- Trigger: a provider call settles with token usage.

- F16.1 · Gemini provider → gateway: `usageOf`: `inputTokens = promptTokenCount`, `cachedInputTokens = cachedContentTokenCount`, `thoughtTokens`, `outputTokens` | condition: response | data: usage | ref: X8
- F16.2 · Meter → meter: `cachedInput = max(0, min(cached, input))`; `uncachedInput = max(0, input - cachedInput)`; `output = output + thoughts` | condition: tokens present | data: counts | ref: X9
- F16.2b · if the call errored or no tokens were reported, write one zero-quantity error row on `:text-input` → end | ref: X9 (lines 146-160)
- F16.3 · Meter → ledger: write a `:text-input` row and settle spend | condition: `uncachedInput > 0` | data: tokens | ref: X9
- F16.4 · Meter → ledger: write a `:text-input-cached` row and settle spend | condition: `cachedInput > 0` | data: tokens | ref: X9
- F16.5 · Meter → ledger: write a `:text-output` row and settle spend | condition: `output > 0` | data: tokens | ref: X9
- F16.6 · Price config → ledger: each key is priced by its `provider_price_config` row (gemini-2.5-flash: $0.30, $0.03, $2.50 per million) | condition: always | data: price | ref: X10

### F17 · Mytube scoring call (real code)
- Purpose: score videos with a stable-first prompt and record cached tokens.
- Trigger: Mytube scores a page of videos for a user's goal.

- F17.1 · Prompt builder → adapter: one prompt string: fixed instructions, rubric and JSON schema first; `GOAL (JSON)` and `ITEMS (JSON …)` last | condition: always | data: prompt | ref: X1
- F17.2 · Adapter → Cerebras: `provider.chat(INSTRUCTIONS, [{role: "user", content: prompt}], DEFAULT_MAX_TOKENS, {temperature: 0})`; no cache marker | condition: always | data: request | ref: X4
- F17.3 · Cerebras provider → adapter: `inputTokens`, `outputTokens`, `cachedInputTokens` from `prompt_tokens_details.cached_tokens` | condition: response | data: usage | ref: X7
- F17.4 · Adapter → activity log: `llm_call` event with `inputTokens`, `outputTokens`, `cacheReadTokens`, `costUsd` | condition: always | data: event | ref: X5
- F17.5 · Adapter → pricing: `cerebrasCostUsd(inputTokens, outputTokens)` prices all input at the full rate; cached tokens are ignored | condition: operator path (`costed`) and success | data: USD | ref: X5, X6
- F17.5b · if the provider is BYOK (the user's own key), the call stays uncosted | ref: X6

### F18 · Where caching sits in the whole request
- Purpose: place the cache in the end-to-end request path from the research.
- Trigger: any user request in an LLM application.

- F18.1 · Edge and controller → input guardrails: auth, tenant resolved and carried downstream | ref: S12
- F18.2 · Input guardrails → cache check: an exact or semantic cache, scoped per tenant | ref: S12
- F18.2b · if the cache hits, return immediately → end | ref: S12
- F18.3 · Cache check → router: choose workflow and model tier | condition: miss | ref: S12
- F18.4 · Router → context assembly: order everything stable-first so prompt caching hits, within the token budget | ref: S12
- F18.5 · Context assembly → gateway → model: send the call | ref: S12
- F18.6 · Chip Huyen's build order puts the cache after enhance context, guardrails, and router/gateway, and before complex logic and write actions | ref: S6, S12

## States

### L1 · Provider prompt-cache entry (Anthropic)
- States:
  - NONE: no entry exists for this exact prefix on this model in this organization/workspace.
  - LIVE: the entry exists and its lifetime (5 minutes or 1 hour since the last write or hit) has not run out.
  - EXPIRED: the lifetime ran out with no hit; equivalent to NONE.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| NONE | request with a marker | prefix ≥ model minimum | LIVE | write billed at 1.25x (5 min) or 2x (1 h); `cache_creation_input_tokens` > 0 | S1, S10 |
| NONE | request with a marker | prefix < model minimum | NONE | nothing cached; creation 0, read 0; no error | S1, S10 |
| LIVE | request with the identical prefix | same model, same organization/workspace, any user | LIVE | read billed at 0.1x on most models; lifetime renewed | S1, S10 |
| LIVE | request whose prefix differs at any token | none | LIVE (unchanged) | the new prefix starts at NONE and is written | S10 |
| LIVE | same prefix sent to another model | none | LIVE (unchanged) | miss on the other model | S10 (unverified for Anthropic) |
| LIVE | no hit for the lifetime | none | EXPIRED | next request writes again | S1, S10 |
| EXPIRED | request with a marker | prefix ≥ minimum | LIVE | write billed again | S1, S10 |

### L2 · panel_content_cache row (Tunatutor)
- States:
  - ABSENT: no row for the four-part key.
  - FRESH: a row stamped with the current `PANEL_BUNDLE_SCHEMA_VERSION`, served on read.
  - FRESH_EMPTY: a word row stamped current that holds empty generative fields after a failed grounded call; served like FRESH.
  - STALE: a row stamped with an older version; read as a miss.
  - CONTENT_MISS: a current row that the read logic still rejects (a word row for another reading; a replies row that is short or holds a broken line).

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| ABSENT | read, model call, valid answer | — | FRESH | upsert at current version; `model = "panel-content/registry"` | X19, X14 |
| ABSENT | read, sentence or full-word answer invalid | — | ABSENT | `PanelContentGenerationError`; nothing stored | X19, X24 |
| ABSENT | read, grounded word call fails | curated facts present | FRESH_EMPTY | empty generative fields stored at current version | X22, X23 |
| ABSENT | replies answer still short after 2 attempts | — | ABSENT | longer short answer shown, not cached | X26 |
| ABSENT | pre-warm script generates the word | script works (see Open questions) | FRESH | same row as an organic one | X34 |
| FRESH | read | — | FRESH | served; sentence lines sanitised on the way out | X19, X21 |
| FRESH | read of a word row holding a practice-language note | — | FRESH | row rewritten without the note; `updatedAt` moves | X22 |
| FRESH | read of a word row | stored reading ≠ curated part of speech | CONTENT_MISS → FRESH | regenerated and overwritten | X22 |
| FRESH | read of a replies row | short or a broken line | CONTENT_MISS → FRESH | regenerated if the new answer is full | X26 |
| FRESH | developer bumps the version and deploys | — | STALE | none until the next read | X17, S10 |
| STALE | read | — | FRESH | regenerated and upserted at the new version | X13, S10 |
| FRESH | second distinct saved learner's `wrong_language` report | both reports after `updatedAt` | ABSENT | row deleted (sentence also deletes its two replies rows) | X28, X29 |
| FRESH | `unclear` or `other` report, or a guest's report | — | FRESH | report filed only | X28, X29 |
| FRESH (new version) | old instance upserts during a rolling deploy | no version guard | STALE | new code regenerates on next read | S10, X14 |
| FRESH_EMPTY | read | — | FRESH_EMPTY | served with curated facts; no timer refreshes it | X22, X13 |
| FRESH_EMPTY | version bump, or two `wrong_language` reports | — | STALE or ABSENT | regenerated on next read | X17, X28 |

### L3 · Schema version (code constant)
- States:
  - vN: the constant's value in the deployed code.
  - vN+1: the value after a bump.
- History of real values (X17):
  - v2: curated-first word panel; v1 word rows were ungrounded and leaked dropped fields.
  - v3: sentence breakdowns ignore non-contextual dictionary metadata; v2 sentence rows held bad overrides.
  - v4: sentence breakdowns no longer apply dictionary gloss overrides at all.
  - v5: Ask's one answer layout and the unknown-speaker-gender rule (« allé(e) »); every older sentence and word row regenerated.
  - v6: answers that fit the learner (level, simpler line, region tags) and a sweep of broken lines (every ¿ / ¡ closed, checked on write and read); every older sentence, word and replies row is a miss.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| vN | prompt, output schema, model or call-parameter change that makes older rows wrong | bump in the same commit | vN+1 | every row < N+1 becomes STALE (L2) | S10, X17 |
| vN | purely additive, always-optional field | — | vN | old rows still validate and hit | X17 |
| vN | admin switches the active model in the registry | no code change | vN | rows keep being served; the model label is not compared | X25, X13, S10 |

### L4 · Report and eviction for one cached bundle (Tunatutor)
- States:
  - CLEAN: no counting `wrong_language` reports since the row was last written.
  - ONE_REPORT: one distinct saved learner reported `wrong_language` after the last write.
  - EVICTED: the row was deleted; the next read regenerates it, which resets to CLEAN.

| from | trigger | guard | to | effect | ref |
|---|---|---|---|---|---|
| CLEAN | `wrong_language` report from a saved learner | report after `updatedAt` | ONE_REPORT | report filed; `rewriteQueued: false` | X28, X29 |
| CLEAN or ONE_REPORT | `unclear` or `other` report | — | unchanged | report filed only | X28 |
| CLEAN or ONE_REPORT | report from a guest (`isAnonymous`) | — | unchanged | report filed; not counted | X29 |
| ONE_REPORT | `wrong_language` report from the same learner | — | ONE_REPORT | counted once (`distinct userId`) | X29 |
| ONE_REPORT | `wrong_language` report from a different saved learner | after `updatedAt` | EVICTED | main row and linked rows deleted; `rewriteQueued: true` | X28 |
| EVICTED | next read | — | CLEAN | row regenerated; `updatedAt` moves, so older reports stop counting | X28, X29 |
| ONE_REPORT | row rewritten (regenerated or note dropped) | — | CLEAN | older reports predate `updatedAt` | X29, X22 (derived) |

## Worked examples

### E1 · Usage counts for two users on one cached prefix
- Values: made up (S10). Setting: a Mytube-like app on Anthropic (the real Mytube calls Cerebras and sends no marker), no tools, one marker after a 6,000-token system prompt, two users whose goal and items are 900 tokens each.
- Inputs: system prompt 6,000 tokens with `cache_control`; user A tail 900 tokens; user B tail 900 tokens, within 5 minutes.
- Steps:
  - F1.1-F1.5 · user A misses: `"input_tokens": 900, "cache_creation_input_tokens": 6000, "cache_read_input_tokens": 0`.
  - F1.6-F1.8 · user B hits: `"input_tokens": 900, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 6000`.
- Outcome: `input_tokens` counts the uncached 900 tokens after the marker on both calls; the 6,000-token prefix is written once and read once.

### E2 · Cache-read share ceiling
- Values: made up (S10), from E1.
- Inputs: prefix 6,000 tokens; tail 900 tokens.
- Steps:
  - F3.2 · user B's share = 6,000 / (6,000 + 0 + 900) = 6,000 / 6,900.
  - F3.3 · ceiling = prefix / (prefix + tail) = 6,000 / 6,900 ≈ 86.96%, about 87%.
- Outcome: a share near 87% is healthy for this app; it can never reach 100% while the 900-token tail is uncached.

### E3 · One reuse pays for the write
- Values: made up units (S10). Unit = the prefix sent once at full input price.
- Inputs: two calls within 5 minutes.
- Steps:
  - No cache: 1 + 1 = 2.
  - With cache (F1.4 then F1.8): write 1.25 + read 0.1 = 1.35.
- Outcome: 1.35 against 2, so a single reuse already pays for the write.

### E4 · Daily cost at scale
- Values: made up (S10); the $3 per million input price is made up and was not checked against a price list.
- Inputs: 6,000-token prefix; $3 per million input tokens; 10,000 calls a day that never pause for 5 minutes.
- Steps:
  - No cache: 6,000 × 10,000 = 60,000,000 tokens × $3 / 1,000,000 = $180 a day.
  - With cache: reads at 0.1x ≈ $18 a day (the few writes add little).
- Outcome: about $18 against $180 a day for the prefix.

### E5 · When the 1-hour lifetime pays
- Values: made up units (S10). Unit = the prefix sent once at full input price. Sparse traffic: each call more than 5 minutes after the last, counted within one hour.

| Calls in the hour | No cache | 5-minute cache (every call writes) | 1-hour cache |
|---|---|---|---|
| 1 | 1 | 1.25 | 2 |
| 2 | 2 | 2.5 | 2.1 |
| 3 | 3 | 3.75 | 2.2 |

- Steps:
  - 5-minute cache: every call is a write at 1.25 (F1.6b).
  - 1-hour cache: one write at 2, then reads at 0.1 each.
- Outcome: the 1-hour lifetime pays when the first call is followed by at least two more within the hour (2.2 against 3); with sparse traffic the 5-minute cache always costs more than no cache.

### E6 · Made-up request with two markers
- Values: made up (S10, S11).
- Inputs:
```json
{
  "model": "...",
  "tools": [
    { "name": "lookupVideo", "description": "...", "input_schema": { ... } },
    { "name": "lookupChannel", "description": "...", "input_schema": { ... },
      "cache_control": { "type": "ephemeral" } }
  ],
  "system": [
    { "type": "text",
      "text": "<6,000 tokens of fixed instructions, rubric and output format>",
      "cache_control": { "type": "ephemeral" } }
  ],
  "messages": [
    { "role": "user", "content": "<this user's goal and items>" }
  ]
}
```
- Steps:
  - Marker 1 on the last tool creates a cached prefix of the tools (C15).
  - Marker 2 on the system block creates a cached prefix of tools plus system prompt (C15).
  - The user message carries no marker because it differs on every call (C13).
  - F1.6e · a request with a different system prompt but the same tools still reads the tools from the cache.
- Outcome: two independently reusable prefixes; no write is paid for the per-user text.

### E7 · Chat content block with a marker
- Values: made up (S10).
- Inputs: the newest message's content as a list of blocks: `{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}`.
- Steps: F2.2 puts the marker on this block; F2.3 removes it from the previous message.
- Outcome: each turn reads earlier turns from the cache and writes only the new turn; `input_tokens` ≈ 0.

### E8 · Running example: Lomem's two apps
- Values: real (S10, X1, X19).
- Inputs: Mytube asks a model to score YouTube videos against a user's goal; each scoring prompt starts with a long fixed block of instructions, a scoring rubric and an output format, and only the last lines change (X1). Tunatutor is a language-learning app; a learner types a word or sentence, for example « un tire-bouchon », and gets back a translation, an example and a usage note as a JSON bundle (S10).
- Steps: Mytube shows the first kind of waste, the same opening resent on every call (F17); Tunatutor shows the second kind, the same question asked by many users (F5).
- Outcome: Mytube needs prompt caching (C10); Tunatutor needs an exact response cache (C27).

### E9 · Case variants share one word row
- Values: real (X12).
- Inputs: "Bonjour", "bonjour", " bonjour ".
- Steps: F6.1 `wordCacheKey` trims and lower-cases each to "bonjour".
- Outcome: one cache row instead of three misses and three paid generations; the prompt still receives the original "Bonjour".

### E10 · Over-normalisation merges meanings
- Values: real language fact used by the guide (S10).
- Inputs: German "Weg" (path) and "weg" (away).
- Steps: F4.1 lower-cases both to "weg".
- Outcome: both share one word key, so one of them gets the other's answer.

### E11 · Gendered form in a shared row
- Values: real (S10, X33).
- Inputs: "I went" in French.
- Steps: a learner-specific prompt would write « je suis allé » for a man or « je suis allée » for a woman; the shared prompt writes « allé(e) » (X33).
- Outcome: one shared row fits every learner; only per-learner, uncached prompts use the learner's stored gender.

### E12 · Version 5 and version 6 bumps
- Values: real (X17, S10).
- Inputs: `PANEL_BUNDLE_SCHEMA_VERSION` went to 5, then to 6.
- Steps:
  - v5: every prompt switched to the neutral « allé(e) »; F10.1 bump; every older sentence and word row became STALE (L2).
  - v6: a check rejects lines such as a Spanish ¿ that is never closed; F10.1 bump; every older sentence, word and replies row became STALE and was swept through the check on its next read.
- Outcome: one constant change re-validated the whole cache lazily, with no migration job.

### E13 · Word row for another reading
- Values: real (X22).
- Inputs: a word row written for the noun « un bonjour »; the word is now read as the greeting.
- Steps: F6.4 compares the stored reading with the curated part of speech; they differ → F6.4b.
- Outcome: the row is regenerated, not served.

### E14 · Two-learner eviction
- Values: made-up learners; rule from real code (X28, X29).
- Inputs: a cached sentence row with `updatedAt` T; a guest reports `wrong_language` after T; saved learner A reports `wrong_language` after T; saved learner A reports again; saved learner B reports `unclear`; saved learner C reports `wrong_language` after T.
- Steps:
  - Guest: F9.4 files; F9.6 count = 0 (guests excluded).
  - A: F9.6 count = 1 → F9.6b, `rewriteQueued: false`.
  - A again: count stays 1 (`distinct userId`).
  - B `unclear`: F9.4b, filed only.
  - C: count = 2 → F9.7 deletes the sentence row and its two replies rows.
- Outcome: `rewriteQueued: true`; the next read regenerates the row and older reports no longer count.

### E15 · Failed grounded word call is cached empty
- Values: real behaviour (X22, X23); the timeout is a made-up trigger.
- Inputs: a word with curated facts; the Gemini call times out.
- Steps: F6.6 → F6.7b empty fields → F6.9 stored at version 6.
- Outcome: this learner and later learners see curated facts with empty generative fields until a version bump or two `wrong_language` reports evict the row.

### E16 · Rolling deploy flip
- Values: made up (S10 mechanism, X14).
- Inputs: OLD at version 5 and NEW at version 6 running together.
- Steps: F11.2 NEW writes v6; F11.4 OLD writes v5 over it; F11.5 NEW regenerates v6.
- Outcome: extra model calls until OLD stops; a conditional write (F11.4b) prevents it.

### E17 · Semantic cache returns a wrong answer
- Values: made up (S10).
- Inputs: a bank's support assistant has cached the answer to "How do I cancel a card payment?"; the next question is "How do I cancel a card?".
- Steps: F13.1-F13.3; the two embeddings score above the threshold → F13.3b.
- Outcome: the customer gets the steps for disputing a payment and never learns how to block a lost card; no error is raised and the answer reads well.

### E18 · Semantic cache leaks a balance
- Values: made up (S10).
- Inputs: the cached answer to "What is my current balance?" contains one customer's balance; the cache is shared across users.
- Steps: the next customer asks the same question → F13.3c.
- Outcome: the next customer sees someone else's balance.

### E19 · Gemini cached-input price in Lomem
- Values: prices real (X10); token counts made up.
- Inputs: gemini-2.5-flash prices: input $0.30, cached input $0.03, output $2.50 per million tokens; a call with 10,000 prompt tokens of which 8,000 cached and 500 output tokens (made up).
- Steps: F16.2 cachedInput = 8,000; uncachedInput = 2,000; F16.3-F16.5 rows: 2,000 × $0.30/M = $0.0006; 8,000 × $0.03/M = $0.00024; 500 × $2.50/M = $0.00125.
- Outcome: total $0.00209, against $0.00425 if all 10,000 input tokens were priced at the full rate (made-up arithmetic on real prices).

### E20 · Mytube's cached tokens are logged but not priced
- Values: prices real defaults (X6); token counts made up.
- Inputs: Cerebras defaults $0.25 input and $0.69 output per million; a call with 100,000 input tokens of which 80,000 cached (made up) and 4,000 output tokens (made up).
- Steps: F17.4 logs `cacheReadTokens: 80000`; F17.5 cost = 100,000 × $0.25/M + 4,000 × $0.69/M = $0.025 + $0.00276 = $0.02776.
- Outcome: the logged cost treats the 80,000 cached tokens at the full input rate; any provider discount is not reflected (unverified whether Cerebras discounts cached tokens).

## Variants and options

- Minimal version:
  - Order every prompt with fixed content first (S10).
  - Add a `cache_control` marker at the end of the fixed part (S10).
  - Log the three input token counts per call (S10).
  - The research phrases the minimal step as "turn on provider prompt caching, and keep the system prompt and tool definitions byte-stable" (S12).
  - For questions many users ask with no personal content, add an exact cache table or Redis entry (S10).
  - Key the exact cache on the normalised input plus the language or tenant (S10).
  - Validate before storing (S10).
  - Put a version number in each row and compare it on read (S10).
- Mature version:
  - A hit-rate dashboard (S10).
  - The 1-hour lifetime where traffic is sparse (S10).
  - Pre-warming the most common questions (S10).
  - A report button that evicts a bad answer (S10).
  - A measured, tenant-scoped semantic cache only where it pays (S10).
  - Prefix-stable context design (S12).
  - An exact-match cache at the gateway (S12).
  - A semantic cache scoped per tenant or permission, with a similarity threshold tuned by evals (S12).
  - A conditional write that never lowers a row's version (S10).

| id | option | when to choose | cost / risk |
|---|---|---|---|
| V1 | Provider prompt caching, 5-minute lifetime | Busy traffic where a prefix is reused within 5 minutes | Writes at 1.25x; loses money when every call arrives alone (S10) |
| V2 | Provider prompt caching, 1-hour lifetime | Sparse traffic where at least three calls land within an hour | Writes at 2x; loses money for one or two calls an hour (S10, E5) |
| V3 | Automatic prompt caching (OpenAI) | Using OpenAI | No marker to manage; minimum 1,024 tokens on newest models; write charges unverified (S2, S10) |
| V4 | One marker after the system prompt | One large stable system prompt, per-user tail | Simplest; system-prompt change invalidates it (S10) |
| V5 | Several markers (tools, system, history) | Tools stable but system prompt varies, or a chat | Up to four; per-marker write cost unverified (S10) |
| V6 | Exact response cache in Postgres | Shared answers that must persist and be queried (Tunatutor) | A DB round-trip per lookup; rows have no expiry (X16, S10) |
| V7 | Exact response cache in Redis | Shared answers where speed matters | Same validation and versioning needs (S10) |
| V8 | Version compared on read | Prompt, schema or model changes over time | Lazy regeneration cost spreads over traffic; needs a deploy guard (S10) |
| V9 | Version in the key | (Rejected by the guide) | Old rows are left behind instead of overwritten (S10) |
| V10 | Time-based expiry (TTL) on response rows | Not used by Tunatutor | Not covered by the inputs beyond "rows have no time-based expiry" (S10) |
| V11 | Lock (single-flight) on a miss | A call expensive enough that duplicates matter | Extra complexity; otherwise one extra call per concurrent miss (S10) |
| V12 | Conditional upsert (update only if stored version ≤ own) | Several instances and rolling deploys | Slightly more complex write; prevents row flips (S10) |
| V13 | Report-driven eviction with a distinct-user threshold | Shared cache where one tap must not discard a good answer | Bad answers persist until enough reports (X28) |
| V14 | Semantic cache | Low-harm content with no personal data (FAQ) | Fluent wrong answers and data leaks with no error; needs per-tenant scope and a measured threshold (S10) |
| V15 | Pre-warming | Known head of frequent questions | Upfront model spend for questions nobody may ask (S10, X34) |
| V16 | Store degraded results | When a failure must not block the screen (Tunatutor curated word path) | The degraded row is served until a bump or eviction (X22, X23) |

| name | open source or hosted | what it does here | link |
|---|---|---|---|
| Anthropic prompt caching | hosted (provider feature) | Marker-based prefix caching with 5-minute or 1-hour lifetime | https://platform.claude.com/docs/en/build-with-claude/prompt-caching |
| OpenAI prompt caching | hosted (provider feature) | Automatic prefix caching, no marker | https://developers.openai.com/api/docs/guides/prompt-caching |
| LiteLLM proxy caching | open source | Gateway with exact and semantic caching (`redis-semantic`, `valkey-semantic`, `qdrant-semantic`) | https://docs.litellm.ai/docs/proxy/caching |
| Redis LangCache | hosted (managed) | Managed semantic cache | https://redis.io/langcache/ |
| GPTCache | open source (Zilliz) | Semantic cache library | https://github.com/zilliztech/GPTCache |
| Langfuse prompt management | open source | Prompt registry whose clients cache prompts locally | https://langfuse.com/docs/prompt-management/overview |
| Spring `@Cacheable` with Redis or a table | open source | Classic exact response cache analogue | (no link in the inputs) |

## Facts and numbers

| id | fact | value | source id | verified |
|---|---|---|---|---|
| N1 | Characters per token, roughly | about 4 | S10 | yes |
| N2 | Anthropic cache write price, 5-minute lifetime | 1.25x input price | S1 | yes |
| N3 | Anthropic cache write price, 1-hour lifetime | 2x input price | S1 | yes |
| N4 | Anthropic cache read price, most models | 0.1x input price | S1 | yes |
| N5 | Anthropic cache read price, Opus 5.5 and Sonnet 5.5 | 0.05x input price | S1 | yes (fact-check) |
| N6 | Anthropic cache read price, Fable 5.1 and Mythos 5.1 | 0.025x input price | S1 | yes (fact-check) |
| N7 | Default cache lifetime (`ephemeral`) | 5 minutes | S1 | yes |
| N8 | Optional cache lifetime | 1 hour (`"ttl": "1h"`) | S1 | yes |
| N9 | Maximum `cache_control` markers per request | 4 | S1 | yes |
| N10 | Anthropic minimum cacheable prefix | 512 to 4,096 tokens, per model | S1 | yes |
| N11 | OpenAI minimum cacheable prefix, newest models (GPT-5.6+) | 1,024 tokens | S2 | yes (fact-check) |
| N12 | Date of the Anthropic facts | as of October 2026 | S10 | yes |
| N13 | Example prefix size | 6,000 tokens | S10 | made up |
| N14 | Example uncached tail | 900 tokens | S10 | made up |
| N15 | Cache-read share ceiling in the example | 6,000 / 6,900 ≈ 86.96% (about 87%) | S10 | yes (arithmetic) |
| N16 | Cost of two calls in 5 minutes, no cache vs cache | 2 vs 1.35 | S10 | yes (arithmetic) |
| N17 | Example input price | $3 per million tokens | S10 | unverified (made up) |
| N18 | Example traffic | 10,000 calls a day | S10 | made up |
| N19 | Example daily prefix cost, no cache vs cache | $180 vs about $18 | S10 | yes (arithmetic) |
| N20 | 1-hour cache, 1 / 2 / 3 calls in the hour | 2 / 2.1 / 2.2 (no cache 1 / 2 / 3; 5-minute 1.25 / 2.5 / 3.75) | S10 | yes (arithmetic) |
| N21 | Semantic-cache example threshold | 0.9 | S10 | unverified (guide's own example) |
| N22 | Cosine similarity range for text, in practice | 0 to 1 | S10 | yes |
| N23 | Threshold calibration sample | a few hundred real question pairs | S10 | yes |
| N24 | Tunatutor `PANEL_BUNDLE_SCHEMA_VERSION` | 6 | X17, X33 | yes |
| N25 | Tunatutor eviction threshold `REWRITE_REPORT_THRESHOLD` | 2 distinct saved learners | X28 | yes |
| N26 | Tunatutor replies attempts `MAX_ATTEMPTS` | 2 | X26 | yes |
| N27 | `MAX_REPLY_LINES` | `they_may_ask`: 2, `you_can_answer`: 3 | X31 | yes |
| N28 | `REPLIES_MAX_TOKENS` | 500 | X26 | yes |
| N29 | Pre-warm default `--n` | 50 lemmas | X34 | yes |
| N30 | Sentence cache key | SHA-256 hex of normalised text | X12 | yes |
| N31 | `panel_content_cache.schemaVersion` column default | 1 | X16 | yes |
| N32 | Gemini 2.5 Flash prices seeded in Tunatutor | input $0.30, cached input $0.03, output $2.50 per million | X10 | yes (code, read 2026-10-03 from Google's page per the comment) |
| N33 | Gemini 2.5 Flash Lite prices seeded in Tunatutor | input $0.10, cached input $0.01 per million | X10 | yes (code) |
| N34 | Mytube Cerebras default prices | input $0.25, output $0.69 per million (env-overridable) | X6 | yes (code) |
| N35 | Mytube default model | `gpt-oss-120b` | X3 | yes |
| N36 | Mytube default max tokens | 8192 | X3 | yes |
| N37 | Mytube temperature | 0 | X4 | yes |
| N38 | Tunatutor selectable models | `gemini-2.5-flash`, `gemini-2.5-flash-lite` | X39 | yes |
| N39 | Gemini provider default timeout | 120 s (120_000 ms) | X36 | yes |
| N40 | Gemini provider default retry attempts | 3 | X36 | yes |
| N41 | Level-chat call budgets | `RATER_CALL` 2,000 ms; `TUTOR_CALL` 4,000 ms | X37 | yes |
| N42 | `JUDGE_CALL` 15 s listed by the research | not found in code | S13 | unverified |
| N43 | Billpod capture tool limit | 30 calls per 60,000 ms per person | X38 | yes |
| N44 | Eval worker pools | `CONCURRENCY = 3` (judge gate); default 4, max 8 (fidelity eval) | S13 | unverified (not re-read) |
| N45 | Guide Lomem quote date | 2026-10-14 | S10 | yes |
| N46 | Lomem commit read for this file | `8e3f5d5db`, committed 2026-10-14 23:14 | X (all) | yes |
| N47 | Chip Huyen article date | 25 Jul 2024 | S6 | yes |
| N48 | Eugene Yan article date | about Aug 2023 | S7 | yes |
| N49 | Fowler/Subramaniam catalogue dates | 28 Jan to 25 Feb 2025 | S8 | yes |
| N50 | Testing scores round 1 (clarity / self-contained / examples) | senior 8/7/8 fail; skimmer 7/6/8 fail | testing | yes |
| N51 | Testing scores round 2 | senior 8/8/8 fail; skimmer 7/8/9 fail | testing | yes |
| N52 | Testing scores round 3 | senior 8/8/9 pass; skimmer 7/8/8 fail | testing | yes |
| N53 | ADR-052 date | 2026-07-27 | S14 | yes |
| N54 | Testing misreads in rounds 1 and 2 that were wrong explanations rather than omissions | none, apart from the round-1 analogy confusion (Q3) | testing | yes |

## Code in Lomem

All excerpts: Lomem main branch as read on 2026-10-15 (commit `8e3f5d5db`). "..." marks elided lines; nothing else is changed.

### X1 · Mytube puts the variable input last so the fixed part is a cacheable prefix
- File: `~/projects/lomem/apps/mytube/web/lib/llm/prompts.ts:312-320`
- Implements: C26, C9, F17.1
```ts
    // VARIABLE INPUT LAST: the static instructions + rubric + schema above are
    // identical across every score call (all users), so they form the cacheable
    // prefix. The GOAL varies per user and the ITEMS per page, so both come last.
    "GOAL (JSON):",
    goalJson,
    "",
    "ITEMS (JSON — each has the video review + channel review). Return exactly one",
    "object per item below, echoing its video id:",
    itemsJson,
```
- Notes:
  - The static instructions, rubric and schema sit above these lines and are identical across every score call for all users.
  - The goal varies per user and the items per page, so both come last.
  - Mytube sends no `cache_control` marker; its provider is Cerebras (X3, X4).

### X2 · Mytube prompt file header still names the claude CLI
- File: `~/projects/lomem/apps/mytube/web/lib/llm/prompts.ts:1-10`
- Implements: context for X1
```ts
// ===========================================================================
// MyTube — LLM prompt builders.
//
// Each exported function returns a single prompt STRING that is passed to the
// local `claude` CLI in non-interactive mode (`claude -p "<prompt>"
// --output-format json`). Every prompt:
//   - embeds the relevant inputs as compact JSON,
//   - specifies the EXACT JSON output schema the model must return,
//   - instructs the model to emit STRICT JSON only (no prose, no code fences),
//   - tells the model to echo input ids so the caller can correlate results.
```
- Notes:
  - The header says prompts go to the local `claude` CLI; the adapter (X3) calls Cerebras. See Open questions.

### X3 · Mytube adapter: Cerebras transport, temperature 0, fixed system message
- File: `~/projects/lomem/apps/mytube/web/lib/llm/index.ts:1-20,66-75`
- Implements: C34, F17.2
```ts
// ===========================================================================
// MyTube — LLM domain adapter (operator + BYOK).
//
// Rebuilt on the shared CerebrasProvider (@repo/shared/llm). The five domain
// methods (reviewVideos / reviewChannels / scoreVideos / generateGoal /
// discussScore) keep ALL their MyTube domain logic — BATCH_SIZE=25, env-driven
// fan-out concurrency, the per-chunk projections, the 2-attempt JSON-parse
// retry, the app-local stripFences, and the llm_call instrumentation. Only the
// per-call TRANSPORT changed: instead of shelling out to a CLI, each call goes
// straight through CerebrasProvider.chat(systemPrompt, [{user}], maxTokens,
// {temperature:0}).
//
// WHY chat() directly (not the LlmClient.callJson facade): the facade hardcodes
// temperature 0.2 and uses a fence-only parser; deterministic rubric scoring
// needs temperature 0 + MyTube's stricter stripFences (outermost-bracket slice).
// So the five methods bypass the facade and own their parse path. The two retry
// layers are intentionally SEPARATE: CerebrasProvider owns transport (429/≥500)
// retries; this adapter owns the domain 2-attempt JSON-parse retry.
//
// Cost: recomputed app-side from result.usage via pricing.ts — but ONLY for the
...
// --- Configuration ---------------------------------------------------------

/** System message — STRICT JSON, no prose (matches the old transport's). */
const INSTRUCTIONS =
  "You are a precise evaluation engine. Do exactly what the user's message asks. " +
  "When it asks for JSON, return STRICT JSON only — no prose, no markdown code fences.";

/** Operator model + reply cap. MyTube imposed no cap; 8192 fits a 25-item batch. */
const DEFAULT_MODEL = process.env.CEREBRAS_MODEL ?? "gpt-oss-120b";
const DEFAULT_MAX_TOKENS = Number(process.env.CEREBRAS_MAX_TOKENS) || 8192;
```
- Notes:
  - `INSTRUCTIONS` is a short fixed system message; the whole scoring prompt is the user message.
  - The adapter bypasses the shared facade to get temperature 0 for "deterministic rubric scoring"; temperature 0 still does not make output deterministic (S10).

### X4 · Mytube records cached tokens from each call
- File: `~/projects/lomem/apps/mytube/web/lib/llm/index.ts:117-149`
- Implements: C23, F17.2, F17.3
```ts
/** A raw text call plus the usage we reattach cost from. */
interface RawCall {
  text: string;
  inputTokens?: number;
  outputTokens?: number;
  cacheReadTokens?: number;
}

/**
 * Build a domain LlmProvider bound to a specific Cerebras transport instance.
 * Prompts/parsers/batching/instrumentation are shared; only the provider
 * (operator vs per-request BYOK) and `costed` flag differ.
 */
function makeProvider(provider: CerebrasProvider, opts: { costed: boolean }): LlmProvider {
  // The recorded model name for the llm_call event: operator = the operator
  // model; BYOK = the per-request model carried on the provider instance.
  const model = provider.modelId;

  /** One raw chat round-trip at temperature 0 — the transport seam. */
  async function callRawText(prompt: string): Promise<RawCall> {
    const result = await provider.chat(
      INSTRUCTIONS,
      [{ role: "user", content: prompt }],
      DEFAULT_MAX_TOKENS,
      { temperature: 0 },
    );
    return {
      text: result.text,
      inputTokens: result.usage?.inputTokens,
      outputTokens: result.usage?.outputTokens,
      cacheReadTokens: result.usage?.cachedInputTokens,
    };
  }
```
- Notes:
  - `cacheReadTokens` is taken from the provider's `cachedInputTokens`.

### X5 · Mytube logs cached tokens but costs only input and output
- File: `~/projects/lomem/apps/mytube/web/lib/llm/index.ts:265-293`
- Implements: C52, F17.4, F17.5
```ts
function emitLlmCall(
  stage: string,
  model: string,
  raw: RawCall | undefined,
  startedAt: number,
  errMessage: string | null,
  costed: boolean,
): void {
  try {
    const ok = errMessage == null;
    const costUsd =
      costed && ok ? cerebrasCostUsd(raw?.inputTokens, raw?.outputTokens) : undefined;
    emit({
      type: "llm_call",
      level: ok ? "info" : "error",
      stage,
      model,
      durationMs: Date.now() - startedAt,
      inputTokens: raw?.inputTokens,
      outputTokens: raw?.outputTokens,
      cacheReadTokens: raw?.cacheReadTokens,
      costUsd,
      status: ok ? "ok" : "error",
      message: ok ? undefined : errMessage,
    });
  } catch {
    /* instrumentation must never affect the call path */
  }
}
```
- Notes:
  - `cacheReadTokens` goes into the `llm_call` event.
  - `costUsd` comes from `cerebrasCostUsd(inputTokens, outputTokens)`, which ignores cached tokens.

### X6 · Mytube pricing prices every input token at the full rate
- File: `~/projects/lomem/apps/mytube/web/lib/llm/pricing.ts:1-21`
- Implements: C52, F17.5
```ts
// lib/llm/pricing.ts — operator Cerebras token pricing.
//
// Rates are $/1M tokens, overridable via env (CEREBRAS_PRICE_IN_PER_M /
// CEREBRAS_PRICE_OUT_PER_M; defaults 0.25 / 0.69). ONLY the operator metered
// Cerebras path prices calls — BYOK stays uncosted (the user pays their own
// provider), so this is intentionally Cerebras-specific and model-agnostic.

const IN_PER_M = Number(process.env.CEREBRAS_PRICE_IN_PER_M) || 0.25;
const OUT_PER_M = Number(process.env.CEREBRAS_PRICE_OUT_PER_M) || 0.69;

/** USD cost for a Cerebras call from its token counts. Returns undefined when
 *  there are no tokens (e.g. a failed call) so the llm_call event stays cost-null. */
export function cerebrasCostUsd(
  inputTokens: number | undefined,
  outputTokens: number | undefined,
): number | undefined {
  const inn = inputTokens ?? 0;
  const out = outputTokens ?? 0;
  if (inn === 0 && out === 0) return undefined;
  return (inn / 1_000_000) * IN_PER_M + (out / 1_000_000) * OUT_PER_M;
}
```
- Notes:
  - Defaults are $0.25 input and $0.69 output per million, overridable by env.
  - BYOK calls stay uncosted.

### X7 · The Cerebras provider reads the OpenAI-style cached-token field
- File: `~/projects/lomem/packages/shared/src/llm/providers/cerebras.ts:181-188`
- Implements: C23, K19, F17.3
```ts
    return {
      text,
      usage: {
        inputTokens: optNum(usage?.prompt_tokens),
        outputTokens: optNum(usage?.completion_tokens),
        cachedInputTokens: optNum(usage?.prompt_tokens_details?.cached_tokens),
      },
    };
```
- Notes:
  - The field is `prompt_tokens_details.cached_tokens`, the OpenAI-compatible shape.
  - Each provider adapter maps its own field into one shared `cachedInputTokens`.

### X8 · Gemini's usage has a cached-content count inside the prompt count
- File: `~/projects/lomem/packages/shared/src/llm/providers/gemini.ts:187-195`
- Implements: C23, K18, F16.1
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
```
- Notes:
  - `inputTokens` is `promptTokenCount`; the meter (X9) subtracts the cached count from it, so Lomem treats the cached count as part of the prompt count.

### X9 · Tunatutor meters uncached input, cached input and output as separate ledger rows
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/index.ts:146-212`
- Implements: C52, F16.2-F16.4
```ts
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
```
- Notes:
  - Cached input is clamped to never exceed input; uncached = input − cached.
  - Thinking tokens join the output row (lines 213-233, same pattern).
  - These rows are the data needed to chart a cache-read share for Gemini.

### X10 · Tunatutor's seeded prices put cached input at a tenth of input
- File: `~/projects/lomem/apps/tunatutor/backend/src/dev/provider-prices.ts:1-44`
- Implements: C18, C52, F16.6
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
```
- Notes:
  - gemini-2.5-flash: $0.30 input, $0.03 cached input, $2.50 output per million.
  - This file was not quoted by the research; it is the price data behind the `:text-input-cached` key the research names.

### X11 · A model without all three price keys cannot be activated
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/registry.ts:199-204`
- Implements: C52
```ts
/**
 * Refuses a model whose calls would be priced at $0: every one of its
 * `:text-input`, `:text-input-cached` and `:text-output` keys needs an active
 * `provider_price_config` row (ADR-057 §5, price coverage). The admin LLM
 * settings call it before making a model active or enabling it as a fallback.
 */
```
- Notes:
  - The research cited this comment under `gateway.ts`; it lives in `registry.ts`.

### X12 · The cache key is normalised so variants share one row
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/cache-key.ts:1-31`
- Implements: C28, C29, F5.4, F6.1
```ts
/**
 * Panel-content cache-key helpers.
 *
 * Extracted from the panel-content service so that other producers (e.g. an
 * admin "regenerate" path) can derive the SAME keys the service reads/writes.
 * Behavior here is byte-for-byte identical to the original in-service helpers —
 * DO NOT change the normalization or hashing, or cache reads/writes will miss.
 */
import { createHash } from "node:crypto";

/** Normalize a sentence for stable cache-key generation. */
export function normalizeSentence(text: string): string {
  return text.trim().toLowerCase().replace(/\s+/g, " ");
}

/** Derive a stable sha256 cache key from a sentence. */
export function sentenceCacheKey(text: string): string {
  return createHash("sha256").update(normalizeSentence(text)).digest("hex");
}

/**
 * Normalize a lemma into a stable cache key. Matches how the lexicon stores
 * lemmas (`trim().toLowerCase()`), so case/whitespace variants of the same word
 * ("Bonjour", "bonjour", " bonjour ") share ONE cache row instead of each
 * missing the cache and firing a duplicate paid LLM generation. The original
 * (un-normalized) lemma is still passed to the LLM prompt so capitalization
 * that carries meaning (proper nouns, German nouns) is preserved in generation.
 */
export function wordCacheKey(lemma: string): string {
  return lemma.trim().toLowerCase();
}
```
- Notes:
  - Lines 12-14 are the excerpt quoted in the long draft.
  - Lower-casing merges German "Weg" and "weg" into one row.
  - Only the key is normalised; the prompt sees the original casing.
  - The sentence key is a hash, so it has a fixed length.

### X13 · The read treats an older version as a miss
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/repository.ts:17-44`
- Implements: C38, F5.6, F5.7, F5.7b, L2
```ts
/**
 * Look up a cached panel bundle.
 *
 * Returns null if not found, OR if the stored row predates the current bundle
 * schema (`schemaVersion < PANEL_BUNDLE_SCHEMA_VERSION`). Treating a stale-version
 * row as a MISS makes the caller regenerate it against the current bundle shape.
 */
export async function getPanelContent(
  prisma: PrismaClient,
  key: PanelContentCacheKey,
): Promise<PanelContentCacheRow | null> {
  const row = await prisma.panelContentCache.findUnique({
    where: {
      kind_targetLanguage_nativeLanguage_cacheKey: {
        kind: key.kind,
        targetLanguage: key.targetLanguage,
        nativeLanguage: key.nativeLanguage,
        cacheKey: key.cacheKey,
      },
    },
    select: { bundle: true, model: true, schemaVersion: true },
  });
  if (!row) return null;
  // Staleness guard: a row written under an older bundle schema is a cache miss,
  // so it regenerates at the current version instead of serving an outdated shape.
  if (row.schemaVersion < PANEL_BUNDLE_SCHEMA_VERSION) return null;
  return { bundle: row.bundle, model: row.model };
}
```
- Notes:
  - Lines 39-43 are the excerpt quoted in both drafts; the tested version elides the two comment lines 40-41.
  - The key has four parts; none is a user id.
  - Stale and absent both return `null` to the caller.
  - `model` is read but never compared.

### X14 · The write is an unconditional upsert with no version guard
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/repository.ts:46-77`
- Implements: C31, C40, F5.14, F11.4
```ts
/**
 * Upsert a cached panel bundle.
 */
export async function putPanelContent(
  prisma: PrismaClient,
  params: PanelContentCacheKey & { bundle: unknown; model?: string },
): Promise<void> {
  await prisma.panelContentCache.upsert({
    where: {
      kind_targetLanguage_nativeLanguage_cacheKey: {
        kind: params.kind,
        targetLanguage: params.targetLanguage,
        nativeLanguage: params.nativeLanguage,
        cacheKey: params.cacheKey,
      },
    },
    update: {
      bundle: params.bundle as Parameters<typeof prisma.panelContentCache.upsert>[0]["update"]["bundle"],
      schemaVersion: PANEL_BUNDLE_SCHEMA_VERSION,
      model: params.model ?? null,
    },
    create: {
      kind: params.kind,
      targetLanguage: params.targetLanguage,
      nativeLanguage: params.nativeLanguage,
      cacheKey: params.cacheKey,
      bundle: params.bundle as Parameters<typeof prisma.panelContentCache.upsert>[0]["create"]["bundle"],
      schemaVersion: PANEL_BUNDLE_SCHEMA_VERSION,
      model: params.model ?? null,
    },
  });
}
```
- Notes:
  - The writer stamps its own compiled-in version; an old instance stamps the old number.
  - `update` has no condition such as "only if the stored version is not higher": this is the rolling-deploy race.
  - Last writer wins on concurrent misses.

### X15 · Delete removes one row and reports whether it existed
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/repository.ts:79-110`
- Implements: F9.7
```ts
/**
 * Delete a cached panel bundle so the next view rebuilds it curated-first.
 *
 * Returns `true` when a row was removed, `false` when nothing matched (Prisma
 * P2025 "record not found") — the caller decides whether a miss is an error.
 */
export async function deletePanelContent(
  prisma: PrismaClient,
  key: PanelContentCacheKey,
): Promise<boolean> {
  try {
    await prisma.panelContentCache.delete({
      where: {
        kind_targetLanguage_nativeLanguage_cacheKey: {
          kind: key.kind,
          targetLanguage: key.targetLanguage,
          nativeLanguage: key.nativeLanguage,
          cacheKey: key.cacheKey,
        },
      },
    });
    return true;
  } catch (err) {
    if (
      err instanceof Prisma.PrismaClientKnownRequestError &&
      err.code === "P2025"
    ) {
      return false;
    }
    throw err;
  }
}
```
- Notes:
  - A missing row (Prisma P2025) returns `false` instead of throwing.

### X16 · The table enforces the four-part key and carries the version
- File: `~/projects/lomem/apps/tunatutor/backend/prisma/schema.prisma:2196-2211`
- Implements: K4, C28, C38
```prisma
model PanelContentCache {
  id             Int      @id @default(autoincrement())
  kind           String // "word" | "sentence"
  targetLanguage String   @map("target_language")
  nativeLanguage String   @map("native_language")
  cacheKey       String   @map("cache_key") // lemma (word) | sha256(normalized sentence) (sentence)
  bundle         Json     @db.JsonB // panel bundle JSON
  schemaVersion  Int      @default(1) @map("schema_version")
  model          String? // LLM model id that generated it
  createdAt      DateTime @default(now()) @map("created_at")
  updatedAt      DateTime @updatedAt @map("updated_at")

  @@unique([kind, targetLanguage, nativeLanguage, cacheKey])
  @@index([targetLanguage, kind])
  @@map("panel_content_cache")
}
```
- Notes:
  - The `kind` comment is out of date: replies kinds `replies:<kind>` also live here.
  - The `model` comment says "model id"; the code writes `"panel-content/registry"`.
  - `updatedAt` is what the report logic uses as "when the row was written".
  - There is no expiry column.

### X17 · The version constant documents every bump and why
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/schema-version.ts:1-52`
- Implements: C39, L3, F10
```ts
/**
 * Schema version for the panel-content cache bundles.
 *
 * Every row written to `panel_content_cache` is stamped with this version. On
 * read, a row whose stored `schemaVersion` is LESS than this constant is treated
 * as a cache MISS (the lookup returns null) so it regenerates against the current
 * bundle shape. This is the staleness guard for the cache: bump this number
 * whenever the WordBundle / SentenceBundle shape changes in a way that older
 * cached rows can't satisfy.
 *
 * NOTE: purely additive, always-optional changes (e.g. the additive `wordFamily`
 * field, which legacy rows simply omit) do NOT require a bump — those rows still
 * validate and serve a hit. Only bump for changes that make older rows wrong.
 *
 * v2 — curated-first: the word panel is now assembled from curated word_cache
 * facts (pos / gender / ipa / senses / examples) plus LLM-generated fields
 * grounded on those facts. Word cache rows now store the GENERATIVE-ONLY fields
 * (synonyms / antonyms / collocations / wordFamily / notes); the `etymology` and
 * `falseFriend` fields were dropped entirely. Every v1 word row is UNGROUNDED
 * (generated without the curated facts) and would leak the dropped fields, so v1
 * rows are treated as misses and rebuilt. The staleness guard in repository.ts
 * enforces this automatically.
 *
 * v3 — sentence breakdowns ignore non-contextual dictionary metadata
 * (abbreviations, letter names, alternative forms, etc.) when applying curated
 * token gloss overrides. v2 sentence rows may already have stored those bad
 * overrides, so they must be regenerated.
 *
 * v4 — sentence breakdowns no longer apply dictionary token gloss overrides at
 * all. v3 sentence rows may still contain cache-rewritten content-word glosses,
 * so they must be regenerated from the LLM-authored bundle.
 *
 * v5 — Ask's one answer layout: sentence bundles carry meaning `chunks`,
 * `keyFacts` and a `register` tag on at most two `otherWays`; word bundles
 * carry the noun's `article` and, for the calm Word page, one glossed `usage`
 * and `example` plus the chips' `glosses` and noun `chipArticles` (optional: a
 * row without them falls back to the first collocation / example, unglossed,
 * and bare chips). Every prompt now follows the unknown-speaker-
 * gender rule ("allé(e)", never a male default), so older rows — sentence AND
 * word — are regenerated.
 *
 * v6 — answers that fit the learner, and a sweep of broken lines: sentence
 * bundles carry the line's `level`, a `simpler` line for one above A2, a
 * `regionTag` for a line said in one region only, a `region` on each other
 * way and a `use` note on each chunk; other ways and replies must be phrases
 * people really say, with every ¿ / ¡ closed (checked on write AND read);
 * a word's note is the one thing an A2 learner gets wrong. Bumping the version
 * is the one-time sweep: every older row — sentence, word and replies — is a
 * miss and regenerates on its next read, so the lines cached before the check
 * are never served again.
 */
export const PANEL_BUNDLE_SCHEMA_VERSION = 6;
```
- Notes:
  - The rule in the comment is "bump when the bundle shape changes"; v5 was also a prompt change and v6 a validation sweep.
  - A bump is used as a deliberate one-time sweep of the whole cache.
  - Additive optional fields do not need a bump.

### X18 · Service header and JSON extraction
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/index.ts:1-13,148-166`
- Implements: C27, C35, F5.12b
```ts
/**
 * Panel-content service: getOrGenerateWord / getOrGenerateSentence.
 *
 * CURATED-FIRST (ADR panel refactor). The word panel is assembled from curated
 * word_cache facts (pos / gender / ipa / senses / examples) plus a small set of
 * LLM-generated fields (synonyms / antonyms / collocations / wordFamily / notes)
 * that are GROUNDED on those facts. When the word is in the curated cache we ask
 * the LLM for the generative fields ONLY and store a generative-only cache row;
 * when it isn't, we fall back to the full LLM word prompt and store a full bundle.
 *
 * Generate-once + cache: a cache HIT returns a panel with ZERO LLM calls. A cache
 * MISS calls the LLM exactly once, validates, stores, and returns.
 */
...
/** Extract the first JSON object from an LLM response string. */
function extractJson(raw: string): unknown {
  const trimmed = raw.trim();
  const start = trimmed.indexOf("{");
  const end = trimmed.lastIndexOf("}");
  if (start === -1 || end === -1) {
    throw new PanelContentGenerationError(
      `LLM response did not contain a JSON object. Raw: ${rawForError(trimmed)}`,
    );
  }
  try {
    return JSON.parse(trimmed.slice(start, end + 1)) as unknown;
  } catch {
    // internal sentinel — caught immediately below
    throw new PanelContentGenerationError(
      `LLM response JSON could not be parsed. Raw: ${rawForError(trimmed)}`,
    );
  }
}
```
- Notes:
  - "a cache HIT returns a panel with ZERO LLM calls. A cache MISS calls the LLM exactly once, validates, stores, and returns."
  - `extractJson` throws `PanelContentGenerationError` when there is no JSON object or it does not parse.

### X19 · The sentence path: hit returns with zero calls, miss calls once, validates, stores
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/index.ts:859-910`
- Implements: F5.4-F5.14, C26, C35
```ts
export interface GetOrGenerateSentenceInput {
  text: string;
  targetLanguage: string;
  nativeLanguage: string;
}

/**
 * Return the cached SentenceBundle for a sentence+language pair, or generate it via LLM.
 *
 * The cache key is sha256(normalize(text)) so that whitespace/case variants share an entry.
 *
 * Cache hit: zero LLM calls.
 * Cache miss: one LLM call → validate → store → return.
 *
 * On LLM / parse / validation failure: throws PanelContentGenerationError.
 */
export async function getOrGenerateSentence(
  input: GetOrGenerateSentenceInput,
  deps: PanelContentServiceDeps,
): Promise<SentenceBundle> {
  const { text, targetLanguage, nativeLanguage } = input;
  const { repo, callLlm, modelId, languageNameFor } = deps;

  const cacheKey = sentenceCacheKey(text);

  // 1. Cache hit — already model-authored at generation time.
  const cached = await repo.get({ kind: "sentence", targetLanguage, nativeLanguage, cacheKey });
  if (cached !== null) {
    return withBundleOpeningMarks(sanitizeCachedSentence(cached.bundle as SentenceBundle), targetLanguage);
  }

  // 2. Cache miss — generate via LLM
  const targetName = languageNameFor(targetLanguage);
  const nativeName = languageNameFor(nativeLanguage);
  const userContent = buildSentenceUserPrompt(text, targetName, nativeName, varietyPromptClause(targetLanguage));

  const raw = await callLlm(
    SENTENCE_SYSTEM_PROMPT,
    [{ role: "user", content: userContent }],
    sentenceMaxTokens(text),
  );

  // 3. Parse + validate
  const parsed = extractJson(raw);
  const validated = withBundleOpeningMarks(validateSentenceBundle(parsed), targetLanguage);

  // 4. Store the model-authored sentence explanation as-is. Sentence meanings
  // are contextual; dictionary cache glosses must not rewrite them.
  await repo.put({ kind: "sentence", targetLanguage, nativeLanguage, cacheKey, bundle: validated, model: modelId });

  return validated;
}
```
- Notes:
  - The fixed `SENTENCE_SYSTEM_PROMPT` goes first and the variable user content last.
  - `extractJson` and `validateSentenceBundle` throw before `repo.put`, so a bad sentence answer is never stored.
  - A hit is re-checked on the way out (`sanitizeCachedSentence`).
  - No user id reaches this function.

### X20 · Validation throws on missing required fields and drops bad optional ones
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/index.ts:528-561`
- Implements: C35, F5.12, F5.12b, F5.12c
```ts
/**
 * Validate that a parsed JSON value matches the required SentenceBundle shape,
 * and clean the v5 fields (other-way tags, chunks, key facts): a field that
 * doesn't validate is dropped to its empty value, never shown half-right.
 */
export function validateSentenceBundle(obj: unknown): SentenceBundle {
  if (
    typeof obj !== "object" ||
    obj === null ||
    typeof (obj as Record<string, unknown>)["text"] !== "string" ||
    typeof (obj as Record<string, unknown>)["translation"] !== "string" ||
    !Array.isArray((obj as Record<string, unknown>)["breakdown"]) ||
    !Array.isArray((obj as Record<string, unknown>)["otherWays"]) ||
    !Array.isArray((obj as Record<string, unknown>)["grammarCallouts"])
  ) {
    throw new PanelContentGenerationError(
      "LLM response did not match SentenceBundle schema (missing required fields)",
    );
  }
  const record = obj as Record<string, unknown>;
  // The model's raw v6 fields never pass through unchecked: they are re-added
  // below only when they validate.
  const { level: _level, simpler: _simpler, regionTag: _regionTag, ...bundle } = obj as SentenceBundle;
  return {
    ...bundle,
    otherWays: normalizeOtherWays(record["otherWays"]),
    chunks: normalizeChunks(record["chunks"], bundle.text),
    keyFacts: normalizeKeyFacts(record["keyFacts"]),
    // v6 fields: present only when the model gave a usable value.
    ...withValue("level", normalizeLevel(record["level"])),
    ...withValue("simpler", normalizeSimpler(record["simpler"], bundle.text)),
    ...withValue("regionTag", normalizeRegionTag(record["regionTag"])),
  };
}
```
- Notes:
  - Required: `text`, `translation`, `breakdown`, `otherWays`, `grammarCallouts`.
  - Optional v5 and v6 fields are normalised or dropped, never shown half-right.

### X21 · A cached sentence is checked again on the way out
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/index.ts:455-467`
- Implements: F5.8, K23
```ts
/**
 * A cached sentence bundle, checked again on the way out: a line cached
 * before a check existed (an unclosed «¿…») is dropped at read time too, so
 * no learner is served it while the row waits to be regenerated.
 */
export function sanitizeCachedSentence(bundle: SentenceBundle): SentenceBundle {
  const out: SentenceBundle = { ...bundle, otherWays: (bundle.otherWays ?? []).filter((w) => isShowableLine(w.text)) };
  if (out.simpler && !isShowableLine(out.simpler.text)) out.simpler = null;
  if (out.regionTag?.alternative && !isShowableLine(out.regionTag.alternative.text)) {
    out.regionTag = { ...out.regionTag, alternative: null };
  }
  return out;
}
```
- Notes:
  - A line cached before a check existed is dropped at read time, so no learner sees it while the row waits to be regenerated.

### X22 · The word path: curated-first, reading check, note drop, store even when empty
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/index.ts:692-822`
- Implements: F6, F7, C49, C50, C33, L2
```ts
/**
 * Return the word panel bundle for a lemma+language pair, curated-first.
 *
 * Curated present:
 *   - cache HIT → generative fields from the cached row; ZERO LLM. A row
 *     stamped for another reading of the word (`readingPos`) counts as a MISS.
 *   - cache MISS → one LLM call (narrowed, grounded) → generative-only row stored.
 *   - LLM fail → empty generative fields (never throws).
 *   Bundle = curated factual fields + generative fields.
 * Curated absent:
 *   - cache HIT → the stored full bundle.
 *   - cache MISS → full LLM word prompt → full bundle stored.
 *
 * Returns `{ bundle, curated }`. The `curated` slot lets a streaming caller emit
 * the instant factual frame before the generative fields resolve.
 *
 * A streaming caller that already resolved the curated facts for its first (instant)
 * frame can pass them as `preResolvedCurated` (including an explicit `null` miss) to
 * skip the duplicate lookup here. Omit the param entirely to resolve internally.
 */
export async function getOrGenerateWord(
  input: GetOrGenerateWordInput,
  deps: PanelContentServiceDeps,
  preResolvedCurated?: CuratedWordFacts | null,
): Promise<GetOrGenerateWordResult> {
  const { lemma, targetLanguage, nativeLanguage } = input;
  const { repo, callLlm, modelId, languageNameFor, resolveCuratedWordFacts } = deps;

  // Cache key is normalized (case/whitespace-insensitive) so variants share one row.
  const cacheKey = wordCacheKey(lemma);

  // Reuse the caller's already-resolved curated facts when provided (streaming path
  // resolves them once for frame 1); otherwise resolve here. `undefined` = not passed.
  const curated =
    preResolvedCurated !== undefined
      ? preResolvedCurated
      : await resolveCuratedWordFacts({
          language: targetLanguage,
          nativeLanguage,
          lemma,
        });

  const cached = await repo.get({ kind: "word", targetLanguage, nativeLanguage, cacheKey });

  // ── Curated present: assemble curated facts + generative fields ──────────
  if (curated !== null) {
    let fields: WordGenerativeFields;
    // A row written for another reading of the word (the noun « un bonjour »
    // when the word is now read as the greeting) is regenerated, not served.
    const cachedReading = cached !== null ? storedReadingPos(cached.bundle) : undefined;
    const forThisReading = cachedReading === undefined || cachedReading === (curated.pos ?? null);
    if (cached !== null && forThisReading) {
      // HIT — take generative fields from the cached row (generative-only or legacy full).
      const stored = generativeFieldsFromStored(cached.bundle);
      fields = await dropPracticeLanguageNotes(stored, input, deps.resolveWordRanks);
      if (fields !== stored) {
        // A row written before the note check held a practice-language note:
        // store it without, so the next learner never gets it either.
        await repo.put({
          kind: "word",
          targetLanguage,
          nativeLanguage,
          cacheKey,
          bundle: generativeBundleForStorage(fields, cachedReading),
          ...(cached.model ? { model: cached.model } : {}),
        });
      }
    } else {
      // MISS (or a row for another reading) — narrowed, grounded LLM call. On
      // any failure, degrade to empty fields.
      const generated = await generateGroundedFields(lemma, targetLanguage, nativeLanguage, curated, {
        callLlm,
        languageNameFor,
      });
      // A note in the practice language is dropped BEFORE it is cached (the
      // cache is shared by everyone with this language pair).
      fields = await dropPracticeLanguageNotes(generated, input, deps.resolveWordRanks);
      // Store a generative-only bundle so future hits are LLM-free, stamped
      // with the reading it was written for.
      await repo.put({
        kind: "word",
        targetLanguage,
        nativeLanguage,
        cacheKey,
        bundle: generativeBundleForStorage(fields, curated.pos ?? null),
        model: modelId,
      });
    }
    return { bundle: assembleWordBundle(curated, fields), curated };
  }

  // ── Curated absent: full LLM bundle (today's behavior, minus dropped fields) ──
  if (cached !== null) {
    const raw = cached.bundle as WordBundle;
    // Synonyms / antonyms are read clean (a row stored before the clean-up).
    const stored: WordBundle = {
      ...raw,
      synonyms: normalizeWordRefs(raw.synonyms),
      antonyms: normalizeWordRefs(raw.antonyms),
    };
    const bundle = await dropPracticeLanguageNotes(stored, input, deps.resolveWordRanks);
    if (bundle !== stored) {
      await repo.put({
        kind: "word",
        targetLanguage,
        nativeLanguage,
        cacheKey,
        bundle,
        ...(cached.model ? { model: cached.model } : {}),
      });
    }
    return { bundle, curated: null };
  }

  const targetName = languageNameFor(targetLanguage);
  const nativeName = languageNameFor(nativeLanguage);
  const userContent = buildWordUserPrompt(lemma, targetName, nativeName, varietyPromptClause(targetLanguage));

  const raw = await callLlm(
    WORD_FULL_SYSTEM_PROMPT,
    [{ role: "user", content: userContent }],
    WORD_FULL_MAX_TOKENS,
  );

  const parsed = extractJson(raw);
  const bundle = await dropPracticeLanguageNotes(validateFullWordBundle(parsed), input, deps.resolveWordRanks);

  await repo.put({ kind: "word", targetLanguage, nativeLanguage, cacheKey, bundle, model: modelId });

  return { bundle, curated: null };
}
```
- Notes:
  - A row for another reading counts as a miss (lines 739-743).
  - A practice-language note is dropped before caching, because the row is shared (lines 766-768).
  - On the curated path the row is written even when `generateGroundedFields` returned empty fields (lines 771-778).
  - A rewrite on the hit path keeps the row's stored model label (lines 750-757, 794-801).

### X23 · A failed grounded call degrades to empty fields
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/index.ts:824-857`
- Implements: F6.6, F6.7b, C35
```ts
/**
 * Narrowed, grounded generative-field generation. Returns EMPTY generative fields
 * on any LLM / parse / validation failure — a cold generative call must never
 * break the word panel (the curated facts still render).
 */
async function generateGroundedFields(
  lemma: string,
  targetLanguage: string,
  nativeLanguage: string,
  curated: CuratedWordFacts,
  deps: Pick<PanelContentServiceDeps, "callLlm" | "languageNameFor">,
): Promise<WordGenerativeFields> {
  try {
    const targetName = deps.languageNameFor(targetLanguage);
    const nativeName = deps.languageNameFor(nativeLanguage);
    const userContent = buildGenerativeWordUserPrompt(
      lemma,
      targetName,
      nativeName,
      curated,
      varietyPromptClause(targetLanguage),
    );
    const raw = await deps.callLlm(
      WORD_GENERATIVE_SYSTEM_PROMPT,
      [{ role: "user", content: userContent }],
      WORD_GENERATIVE_MAX_TOKENS,
    );
    const parsed = extractJson(raw);
    return validateGenerativeWordFields(parsed);
  } catch {
    // internal control-flow: any failure degrades to empty generative fields.
    return emptyGenerativeFields();
  }
}
```
- Notes:
  - This is the one path where a failed answer is cached (as empty fields), unlike sentences.

### X24 · Word validators for the generative-only and full shapes
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/index.ts:303-319,340-364`
- Implements: F6.7, F7.5, F7.5b
```ts
/**
 * Validate a parsed JSON value as the GENERATIVE-ONLY word shape.
 * Requires the generative arrays are arrays; filters wordFamily to strings.
 * No etymology/falseFriend, no "senses length >= 1" requirement.
 */
export function validateGenerativeWordFields(obj: unknown): WordGenerativeFields {
  if (
    typeof obj !== "object" ||
    obj === null ||
    !Array.isArray((obj as Record<string, unknown>)["synonyms"]) ||
    !Array.isArray((obj as Record<string, unknown>)["antonyms"]) ||
    !Array.isArray((obj as Record<string, unknown>)["collocations"])
  ) {
    throw new PanelContentGenerationError(
      "LLM response did not match the generative word-fields schema (missing required array fields)",
    );
  }
...
/**
 * Validate that a parsed JSON value matches the required (full) WordBundle shape.
 * Used only on the curated-absent fallback path. etymology/falseFriend dropped.
 */
function validateFullWordBundle(obj: unknown): WordBundle {
  if (
    typeof obj !== "object" ||
    obj === null ||
    typeof (obj as Record<string, unknown>)["lemma"] !== "string" ||
    !Array.isArray((obj as Record<string, unknown>)["senses"]) ||
    !Array.isArray((obj as Record<string, unknown>)["examples"]) ||
    !Array.isArray((obj as Record<string, unknown>)["synonyms"]) ||
    !Array.isArray((obj as Record<string, unknown>)["antonyms"]) ||
    !Array.isArray((obj as Record<string, unknown>)["collocations"])
  ) {
    throw new PanelContentGenerationError(
      "LLM response did not match WordBundle schema (missing required array fields or lemma)",
    );
  }
  // A word panel with zero glosses is useless on the curated-absent path — reject.
  if (((obj as Record<string, unknown>)["senses"] as unknown[]).length < 1) {
    throw new PanelContentGenerationError(
      "LLM response had an empty senses array (a word panel needs at least one gloss)",
    );
  }
```
- Notes:
  - The full shape rejects an empty `senses` array: "a word panel needs at least one gloss".

### X25 · Deps per learner and the neutral model label
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/deps.ts:34-90`
- Implements: K10, F5.9, F5.11b, C39
```ts
// Panel content generation is a single cheap classification/structured call.
// callLLM routes to the registry's active provider (Gemini primary per ADR-057),
// not a fixed model — so we tag cache rows with a neutral, honest source label
// rather than a specific model id that would be wrong in almost every deployment.
const PANEL_MODEL_ID = "panel-content/registry";

// Cast once at the boundary — the repo functions accept narrow duck-typed
// Prisma shapes, and prisma is exported as PrismaClient.
const prismaClient = prisma as unknown as PrismaClient;

/**
 * Panel-content service deps: real cache repo + real LLM, generate-once.
 * Built PER LEARNER so every generated panel is billed to the learner it is
 * for (`callLlm` refuses an un-attributed call).
 */
export function panelContentDepsFor(userId: number): PanelContentServiceDeps {
  return {
    repo: {
      get: (params: { kind: string; targetLanguage: string; nativeLanguage: string; cacheKey: string }) =>
        getPanelContent(prismaClient, params),
      put: (params: { kind: string; targetLanguage: string; nativeLanguage: string; cacheKey: string; bundle: unknown; model?: string }) =>
        putPanelContent(prismaClient, params),
    },
    callLlm: async (
      systemPrompt: string,
      messages: Array<{ role: "user" | "assistant"; content: string }>,
      maxTokens: number,
    ) => {
      const result = await callLLMWithMeta(systemPrompt, messages, maxTokens, {
        usageContext: userUsageContext(userId, HELP_PANEL_SURFACE),
      });
      // A panel answer that did not end normally (cut off at the token cap,
      // blocked) is the usual cause of "JSON could not be parsed": log why.
      if (result.finishReason && result.finishReason !== "STOP") {
        logger.warn(
          {
            finishReason: result.finishReason,
            blockReason: result.blockReason,
            maxTokens,
            outputTokens: result.usage?.outputTokens,
            chars: result.text.length,
            tail: result.text.slice(-600),
          },
          "panel content LLM answer did not finish normally",
        );
      }
      return result.text;
    },
    modelId: PANEL_MODEL_ID,
    languageNameFor,
    // Curated word facts from the word_cache (pos / gloss / examples); null = miss.
    resolveCuratedWordFacts: (input: { language: string; nativeLanguage: string; lemma: string }) =>
      resolveCuratedWordFacts(input, { wordCachePrisma, lookupByForm, getLemmaDetail }),
    // A word note the model wrote in the practice language is dropped, never cached.
    resolveWordRanks: resolveWordRanksFromWordCache,
  };
}
```
- Notes:
  - The generating call is billed to the learner whose request missed; later hits are free.
  - Rows are tagged `"panel-content/registry"`, not a model id, so a model switch in the admin registry changes neither the key nor the stored label.
  - An answer that did not finish normally is logged with its tail.

### X26 · Replies are cached only when complete
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/replies.ts:13-19,33-38,183-255`
- Implements: F8, C30
```ts
 * Generate once + cache, like the sentence bundle: the row is keyed by the
 * normalized line and the language pair, in `panel_content_cache` under
 * `replies:<kind>`. The cache is SHARED by every learner, so the prompt carries
 * the unknown-speaker-gender rule and never a learner's own gender. A line that
 * needs no reply (a goodbye, a thank-you that ends it) is an empty list — also
 * cached — never a made-up exchange. A short answer (two replies where three
 * belong) is asked once more and never cached, so no learner is stuck with it.
...
/** The cache row kind for one replies kind. */
export function repliesCacheKind(kind: RepliesKind): string {
  return `replies:${kind}`;
}

const REPLIES_MAX_TOKENS = 500;
...
const MAX_ATTEMPTS = 2;

/**
 * A full answer: the model's own "needs no reply" (an empty list), or every
 * line the kind shows (one exchange; three replies). Anything in between is
 * short — shown if nothing better comes, never cached.
 */
function isFull(replies: RepliesPanelDTO, kind: RepliesKind, modelSaidNone: boolean): boolean {
  if (replies.lines.length === 0) return modelSaidNone;
  return replies.lines.length === MAX_REPLY_LINES[kind];
}

/**
 * The replies for one line and language pair: from the cache (zero LLM), or
 * an LLM call → validate → store → return. A short answer (1–2 of three
 * replies) is asked once more; if it is still short, the longer one is shown
 * and nothing is cached, so the next ask tries again. A short row cached
 * before this rule is a miss too. Throws PanelContentGenerationError when no
 * answer can be used (nothing is cached then).
 */
export async function getOrGenerateReplies(
  input: GetOrGenerateRepliesInput,
  deps: Pick<PanelContentServiceDeps, "repo" | "callLlm" | "modelId" | "languageNameFor">,
): Promise<RepliesPanelDTO> {
  const { text, kind, targetLanguage, nativeLanguage } = input;
  const { repo, callLlm, modelId, languageNameFor } = deps;
  const cacheKind = repliesCacheKind(kind);
  const cacheKey = sentenceCacheKey(text);

  const cached = await repo.get({ kind: cacheKind, targetLanguage, nativeLanguage, cacheKey });
  if (cached !== null) {
    const bundle = cached.bundle as RepliesPanelDTO;
    // An empty list is the model's own "needs no reply"; a short row is a miss.
    // A row cached before the line check is checked again on the way out: a
    // broken line in it makes it a miss, so it regenerates instead of serving it.
    const intact = bundle.lines.every((l) => isShowableLine(l.phrase));
    if (intact && (bundle.lines.length === 0 || bundle.lines.length === MAX_REPLY_LINES[kind])) {
      return withLineMarks(bundle, targetLanguage);
    }
  }

  let best: RepliesPanelDTO | null = null;
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    const raw = await callLlm(
      repliesSystemPrompt(kind),
      [
        {
          role: "user",
          content: buildRepliesUserPrompt(
            text.trim(),
            languageNameFor(targetLanguage),
            languageNameFor(nativeLanguage),
            varietyPromptClause(targetLanguage),
          ),
        },
      ],
      REPLIES_MAX_TOKENS,
    );
    const parsed = parseJsonObject(raw);
    const replies = withLineMarks(validateReplies(parsed, kind, text), targetLanguage);
    if (isFull(replies, kind, rawLinesOf(parsed).length === 0)) {
      await repo.put({ kind: cacheKind, targetLanguage, nativeLanguage, cacheKey, bundle: replies, model: modelId });
      return replies;
    }
    if (best === null || replies.lines.length > best.lines.length) best = replies;
  }
  // Lines that were all unusable are a failed answer, unlike the model's own
  // empty list ("needs no reply").
  if (best === null || best.lines.length === 0) {
    throw new PanelContentGenerationError("Replies answer had lines, none usable");
  }
  return best;
}
```
- Notes:
  - A cache row can be judged a miss by its content (short, or a broken line), not only by its version.
  - A short answer is shown but not cached, so the next ask retries.
  - An empty list is the model's own "needs no reply" and is cached.

### X27 · Personal data is merged after the shared lookup and never cached
- File: `~/projects/lomem/apps/tunatutor/backend/src/use-cases/panels/get-sentence-panel.ts:80-92,216-217`
- Implements: C33, F5.3, F5.15
```ts
export async function getSentencePanel(
  input: GetSentencePanelInput,
  deps: SentencePanelDeps,
): Promise<SentencePanelDTO> {
  const { userId, language, nativeLanguage, text } = input;

  const [bundle, allStates, phraseEntry] = await Promise.all([
    deps.getOrGenerateSentence({ text, targetLanguage: language, nativeLanguage }),
    deps.getKnownLemmaStates(userId, language),
    // Saved-phrase personal layer: non-null only when this exact text is a
    // saved lexicon phrase — powers the Sentence panel's meters + honest stats.
    deps.getPhraseEntry(userId, language, text),
  ]);
...
  return { ...bundle, personal };
}
```
- Notes:
  - The shared bundle and the learner's own state load in parallel.
  - `personal` is added to the response only; `getOrGenerateSentence` never receives a user id.

### X28 · Two different saved learners must report before a shared answer is deleted
- File: `~/projects/lomem/apps/tunatutor/backend/src/use-cases/panels/report-answer.ts:1-19,55-98`
- Implements: C36, F9, L4
```ts
/**
 * "Something wrong?" — a learner reports an answer (Ask, a tutor correction, a
 * drill's feedback). ADR-052 §3.
 *
 * The answer cache is SHARED by every learner, so one report never changes it:
 * a curious tap must not throw away a correct answer for everyone. The report
 * is always kept (a reviewer reads it). Only when two DIFFERENT learners with
 * saved accounts (never guests — a new guest is one tap away) say "the
 * practice language is wrong" about the same cached bundle — both after that
 * bundle was written — is the bundle deleted, so its next read writes it
 * again. "Didn't understand" and "Other" never touch the cache (the learner is
 * shown a simpler version on screen instead).
 */
import type { AnswerReportRequest, AnswerReportResponse } from "@tunatutor/shared";
import { sentenceCacheKey, wordCacheKey } from "../../services/panel-content/cache-key.js";
import { repliesCacheKind } from "../../services/panel-content/replies.js";

/** Distinct learners' "wrong" reports that send a shared bundle to be rewritten. */
const REWRITE_REPORT_THRESHOLD = 2;
...
/** The cache rows a report on `content` points at (the line's replies go with it). */
function cacheKindsFor(content: AnswerReportRequest["content"]): string[] {
  if (content === "sentence") return ["sentence", repliesCacheKind("they_may_ask"), repliesCacheKind("you_can_answer")];
  if (content === "word") return ["word"];
  return [];
}

function cacheKeyFor(content: AnswerReportRequest["content"], text: string): string | null {
  if (content === "sentence") return sentenceCacheKey(text);
  if (content === "word") return wordCacheKey(text);
  return null;
}

export async function reportAnswer(input: ReportAnswerInput, deps: ReportAnswerDeps): Promise<AnswerReportResponse> {
  const { userId, targetLanguage, nativeLanguage, report } = input;
  const cacheKey = cacheKeyFor(report.content, report.text);
  await deps.saveReport({
    userId,
    surface: report.surface,
    reason: report.reason,
    content: report.content,
    targetLanguage,
    nativeLanguage,
    text: report.text.trim(),
    shown: report.shown?.trim() || null,
    note: report.note?.trim() || null,
    cacheKey,
  });

  if (report.reason !== "wrong_language" || cacheKey === null) return { rewriteQueued: false };
  const [mainKind, ...linked] = cacheKindsFor(report.content);
  if (!mainKind) return { rewriteQueued: false };
  const ref: CacheRef = { kind: mainKind, targetLanguage, nativeLanguage, cacheKey };
  const writtenAt = await deps.cacheWrittenAt(ref);
  // Nothing cached (or already regenerating): nothing to rewrite.
  if (writtenAt === null) return { rewriteQueued: false };
  const reporters = await deps.countWrongReporters(
    { content: report.content, targetLanguage, nativeLanguage, cacheKey },
    writtenAt,
  );
  if (reporters < REWRITE_REPORT_THRESHOLD) return { rewriteQueued: false };
  for (const kind of [mainKind, ...linked]) await deps.deleteCache({ ...ref, kind });
  return { rewriteQueued: true };
}
```
- Notes:
  - The report is always saved first; eviction is the exception.
  - Reports count only after the row's last write.
  - A sentence report deletes the sentence row and its two replies rows.

### X29 · The report route counts only saved accounts and reads the row's updatedAt
- File: `~/projects/lomem/apps/tunatutor/backend/src/routes/panels.ts:757-800`
- Implements: F9.1, F9.5, F9.6, L4
```ts
  // ===========================================================================
  // POST /api/panels/report — "Something wrong?" on an answer (Ask, a tutor
  // correction, a drill). Always filed; two learners' "wrong" reports on the
  // same cached bundle send it to be rewritten (use-cases/panels/report-answer).
  // No LLM call, so no spend gates.
  // ===========================================================================
  t.post("/report", { schema: PostAnswerReportSchema, preHandler: [reportLimiter] }, async (request) => {
    const userId = request.user.sub;
    const { language, nativeLanguage } = await resolvePair(userId, request.body);
    const { surface, reason, content, text, shown, note } = request.body;
    return reportAnswer(
      { userId, targetLanguage: language, nativeLanguage, report: { surface, reason, content, text, shown, note } },
      {
        saveReport: async (row) => {
          await prismaClient.answerReport.create({ data: row });
        },
        cacheWrittenAt: async (ref) => {
          const row = await prismaClient.panelContentCache.findUnique({
            where: { kind_targetLanguage_nativeLanguage_cacheKey: ref },
            select: { updatedAt: true },
          });
          return row?.updatedAt ?? null;
        },
        countWrongReporters: async (ref, since) => {
          // Only saved accounts count: a guest is one tap away from a fresh
          // identity, so guests could otherwise rewrite a shared answer alone.
          const rows = await prismaClient.answerReport.findMany({
            where: {
              ...ref,
              reason: "wrong_language",
              createdAt: { gte: since },
              user: { isAnonymous: false },
            },
            distinct: ["userId"],
            select: { userId: true },
          });
          return rows.length;
        },
        deleteCache: async (ref) => {
          await deletePanelContent(prismaClient, ref);
        },
      },
    );
  });
```
- Notes:
  - `distinct: ["userId"]` makes it two different learners, not two reports.
  - `isAnonymous: false` keeps guests from evicting alone.
  - The route has only a rate limiter, because it makes no LLM call.

### X30 · The sentence route and its gates
- File: `~/projects/lomem/apps/tunatutor/backend/src/routes/panels.ts:465-477`
- Implements: F5.1, F5.2
```ts
  // ===========================================================================
  // POST /api/panels/sentence — SentencePanelDTO
  // ===========================================================================
  t.post(
    "/sentence",
    { schema: PostSentencePanelSchema, preHandler: [dailySpendEntryGate, entryGate, panelLimiter] },
    async (request) => {
      const userId = request.user.sub;
      const { text } = request.body;
      const { language, nativeLanguage } = await resolvePair(userId, request.body);
      return getSentencePanel({ userId, language, nativeLanguage, text }, sentencePanelDepsFor(userId));
    },
  );
```
- Notes:
  - A cache hit still passes the daily spend gate, entry gate and rate limiter, because they run before the lookup.

### X31 · Report request types and reply line limits
- File: `~/projects/lomem/packages/tunatutor-shared/src/panels.ts:360-366,382-415`
- Implements: F8.3, F9.3, C36
```ts
export type RepliesKind = "they_may_ask" | "you_can_answer";

/** Lines per kind at most: one exchange (them, then you), or three replies. */
export const MAX_REPLY_LINES: Readonly<Record<RepliesKind, number>> = {
  they_may_ask: 2,
  you_can_answer: 3,
};
...
// ─── "Something wrong?" — one report sheet for Ask, tutor corrections, drills ───

/**
 * Why a learner reported an answer: the practice language in it is wrong or
 * odd; they didn't understand it (they get a simpler version — the shared
 * answer stays); something else.
 */
export type AnswerReportReason = "wrong_language" | "unclear" | "other";

/** Where the report came from. */
export type AnswerReportSurface = "ask" | "tutor" | "drill";

/**
 * The shared-cache content a report points at. `sentence` / `word` name the
 * cached bundle for `text`; `answer` is anything not in the shared cache (a
 * free answer, a tutor correction, a drill's feedback) — filed for review only.
 */
export type AnswerReportContent = "sentence" | "word" | "answer";

export interface AnswerReportRequest {
  surface: AnswerReportSurface;
  reason: AnswerReportReason;
  content: AnswerReportContent;
  /** The practice-language line (or word) the report is about. */
  text: string;
  /** What was shown for it (a meaning, a correction), when the screen has one. */
  shown?: string | null;
  note?: string | null;
}

export interface AnswerReportResponse {
  /** The shared answer was sent to be rewritten (2+ "wrong" reports from different learners). */
  rewriteQueued: boolean;
}
```
- Notes:
  - Reasons are `wrong_language`, `unclear`, `other`; the UI labels are "The {language} is wrong or odd", "I didn't understand it", "Something else" (X33).
  - Content `answer` is "anything not in the shared cache", filed for review only.

### X32 · Every report is stored in AnswerReport
- File: `~/projects/lomem/apps/tunatutor/backend/prisma/schema.prisma:2159-2184`
- Implements: K14, F9.4
```prisma
/// A learner's "Something wrong?" report on an answer (Ask, a tutor correction,
/// a drill's feedback) — ADR-052. One report never changes the shared answer:
/// two "wrong_language" reports from different learners on the same cached
/// bundle (newer than the bundle) delete it so it regenerates.
model AnswerReport {
  id             Int      @id @default(autoincrement())
  userId         Int      @map("user_id")
  /// Where it was reported: ask | tutor | drill.
  surface        String
  /// wrong_language | unclear | other.
  reason         String
  /// What it points at: sentence | word (a shared cache bundle) | answer (anything else).
  content        String
  targetLanguage String   @map("target_language")
  nativeLanguage String   @map("native_language")
  /// The practice-language line or word reported.
  text           String
  /// What the screen showed for it (a meaning, a correction), when known.
  shown          String?
  /// The learner's optional note.
  note           String?
  /// The shared-cache key of `text` for sentence / word content; null for `answer`.
  cacheKey       String?  @map("cache_key")
  createdAt      DateTime @default(now()) @map("created_at")

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
```
- Notes:
  - Reports are cascade-deleted with the user.

### X33 · ADR-052 states the design rules for the shared cache
- File: `~/projects/lomem/docs/adr/052-help-panel.md:67,73-75,81-83`
- Implements: C27, C33, C36, C37, C38
```text
**The LLM never decides where a text goes.** It runs only to generate content: the free-question stream (`ask` lane) and a cache miss in the shared content cache (§3). A translation shows the quick translation first (`services/quickTranslate`: one call per text and language pair, shared while in flight, reused when Enter follows the typing preview), then the sentence bundle fills in the rest.
...
Word and sentence content, "They may ask you" / "You can answer" replies, help translations and quick translations are the same for every learner who asks the same thing in the same language pair, so they are generated once and cached **without any user id**. The panel-content service (`services/panel-content/`) keys its cache by `(kind, targetLanguage, nativeLanguage, cacheKey)`: a hit costs no LLM call; a miss calls the LLM once, validates, and stores. `PANEL_BUNDLE_SCHEMA_VERSION` (a single global number, currently `6`) invalidates rows lazily: a row written under an older number regenerates on its next read — which is also how a new check sweeps the whole cache once.

On top sits a **personal layer**, assembled per request from the learner's own lexicon row (saved or not, receptive / productive state, notes, what they said with it) — `use-cases/panels/get-word-panel.ts` and `get-sentence-panel.ts` merge the two. The shared layer never holds a user id; the personal layer is never cached in it.
...
**Reports — "Something wrong?"** Under every answer outside a chat sits one quiet link that opens one sheet (`components/something-wrong/SomethingWrong.tsx`, the same component tutor corrections and drill feedback import): "The Spanish is wrong or odd" · "I didn't understand it" (the screen then shows a simpler version — Ask asks the line again as a question, "Explain … in simple words") · "Something else", an optional note, Send. `POST /api/panels/report` (`use-cases/panels/report-answer.ts`) always files it (`AnswerReport`, cascade-deleted with the user, purged with its language, exported with the account). Because the cache is shared, one report never changes it: only when **two different learners** say the practice language of the same cached bundle is wrong — both after the bundle was written — is it deleted (a sentence with its two replies rows), so its next read writes it again. "Didn't understand" and "Something else" never touch the cache. A reviewer reads the reports; there is no reviewer tool yet.

**No male default.** Every prompt that writes a line the learner would say carries the unknown-speaker rule (`services/speaker-gender-rule.ts`): when a form depends on the speaker's gender, write the variable ending in parentheses ("allé(e)") or add a one-line note in the native language ("A woman says je suis allée."). Anything in a shared cache always uses that rule and is **never personalised** — otherwise one learner's « allée » would be served to another. Only per-learner, uncached prompts (the tutor's reply suggestions, ADR-016) use the learner's stored gender when there is one. The rule names no language (ADR-007).
```
- Notes:
  - "without any user id", "a hit costs no LLM call", "invalidates rows lazily" and "sweeps the whole cache once" are the ADR's own words.
  - Shared content is shaped to fit every learner (« allé(e) »); personal shaping happens only in uncached prompts.
  - Quick translations are "shared while in flight", a single-flight pattern.

### X34 · The pre-warm script fills the cache before users ask
- File: `~/projects/lomem/apps/tunatutor/backend/scripts/prewarm-panel-cache.ts:1-21,47-52,125-189`
- Implements: C46, F15
```ts
/**
 * prewarm-panel-cache.ts — Seed the PanelContentCache for the top-N frequency
 * lemmas of a target language so the first real user request is a cache hit.
 *
 * Usage:
 *   tsx scripts/prewarm-panel-cache.ts \
 *     --target <language>   e.g. "french"
 *     --native <language>   e.g. "english"
 *     [--n <number>]        default 50
 *     [--dry-run]           log without writing to the cache
 *
 * Environment variables (same as the backend):
 *   DATABASE_URL              — app DB (panelContentCache lives here)
 *   WORD_CACHE_DATABASE_URL   — word cache DB (may differ in staging/prod)
 *
 * Generation routes through callLLM → the LLM registry's active provider (Gemini
 * per ADR-057), not a specific Anthropic model. The provider's own key (e.g.
 * GEMINI_API_KEY) must be present, exactly as the backend requires it.
 *
 * Cache hit = 0 LLM calls. Re-running is safe and idempotent.
 */
...
// ─── Model config (mirrors panels.ts) ─────────────────────────────────────────

// Neutral, honest label: generation goes through callLLM → the registry's active
// provider, so the stamped model id must NOT name a specific Anthropic model.
// Matches the production route's label in routes/panels.ts.
const PANEL_MODEL_ID = "panel-content/registry";
...
  // ── Build deps (same wiring as panels.ts panelContentDeps) ────────────────

  const prismaClient = prismaDefault as unknown as PrismaClient;

  const panelContentDeps = {
    repo: {
      get: (params: { kind: string; targetLanguage: string; nativeLanguage: string; cacheKey: string }) =>
        getPanelContent(prismaClient, params),
      put: (params: {
        kind: string;
        targetLanguage: string;
        nativeLanguage: string;
        cacheKey: string;
        bundle: unknown;
        model?: string;
      }) => putPanelContent(prismaClient, params),
    },
    callLlm: (
      systemPrompt: string,
      messages: Array<{ role: "user" | "assistant"; content: string }>,
      maxTokens: number,
    ) => callLLM(systemPrompt, messages, maxTokens),
    modelId: PANEL_MODEL_ID,
    languageNameFor,
  };

  // ── Process lemmas ────────────────────────────────────────────────────────

  const stats = { hit: 0, generated: 0, error: 0 };

  for (let i = 0; i < lemmaRows.length; i++) {
    const { form, frequency_rank } = lemmaRows[i];
    const prefix = `[prewarm-panel-cache] [${i + 1}/${lemmaRows.length}] rank=${frequency_rank ?? "?"} lemma="${form}"`;

    if (dryRun) {
      console.log(`${prefix} → DRY RUN skip`);
      continue;
    }

    try {
      // Check cache first — avoids counting hits as generated
      const existing = await getPanelContent(prismaClient, {
        kind: "word",
        targetLanguage,
        nativeLanguage,
        cacheKey: form,
      });

      if (existing !== null) {
        console.log(`${prefix} → cache hit (skipped LLM)`);
        stats.hit++;
        continue;
      }

      // Cache miss — call getOrGenerateWord (writes to cache)
      await getOrGenerateWord({ lemma: form, targetLanguage, nativeLanguage }, panelContentDeps);
      console.log(`${prefix} → generated + cached`);
      stats.generated++;
    } catch (err) {
      const msg = getErrorMessage(err);
      console.error(`${prefix} → ERROR: ${msg}`);
      stats.error++;
      // Resilient: continue to the next lemma
    }
  }
```
- Notes:
  - Pre-warming is a script run by hand, not a scheduled job.
  - It reuses `getOrGenerateWord`, so pre-warmed rows look like organic ones.
  - Its pre-check passes `cacheKey: form`, not `wordCacheKey(form)`.
  - Its deps call `callLLM` with three arguments and no usage context, and have no `resolveCuratedWordFacts` or `resolveWordRanks`. See Open questions.

### X35 · Streaming falls back to another provider only before the first token
- File: `~/projects/lomem/packages/shared/src/llm/gateway/gateway.ts:428-434,491-493`
- Implements: latency trick filed next to caching by the research (S13 §11c); not a cache
```ts
  /**
   * The one streaming loop: try each candidate that implements the stream,
   * forward its events, settle once per attempt — on `done`, on failure, or
   * when the caller gives up (its signal fires, or it stops reading) — and
   * fall back only while nothing has reached the consumer and the caller has
   * not aborted.
   */
...
        lastError = err;
        // Text already reached the consumer: another provider cannot continue it.
        if (yielded) throw err;
```
- Notes:
  - Once text has reached the consumer, another provider cannot continue it, so the error is thrown.

### X36 · Gemini timeout, retries and thinking off
- File: `~/projects/lomem/packages/shared/src/llm/providers/gemini.ts:308-310,343-347,364-372`
- Implements: latency trick filed next to caching by the research (S13 §11d); not a cache
```ts
    this.timeoutMs = options?.timeoutMs ?? 120_000;
    this.retry = {
      maxAttempts: options?.retry?.maxAttempts ?? 3,
...
    // Gemini 2.5 models have "thinking" enabled by default, which consumes
    // output tokens from the maxOutputTokens budget. For structured JSON output
    // (our primary use case), thinking wastes tokens and causes truncation, so
    // it is off unless the caller asks for it.
    const thinking = options?.thinking ?? (this.modelId.includes("2.5") ? "off" : undefined);
...
  /**
   * POST with the key in `x-goog-api-key`, the call's time budget, and
   * retries on the policy's statuses (and, if the policy says so, on network
   * failures) with a linear backoff that yields to Retry-After. The budget
   * spans every attempt and wait: a retry whose wait would outlast it is not
   * made, and the failure is thrown instead. Returns the OK response with its
   * deadline still armed, so the caller can read the body under the same
   * budget.
   */
```
- Notes:
  - Default timeout is 120 s and default retry attempts 3.
  - One time budget spans every attempt and wait; retries yield to Retry-After.
  - Thinking is off by default on 2.5 models because for structured JSON it "wastes tokens and causes truncation".

### X37 · Per-call budgets in the level chat
- File: `~/projects/lomem/apps/tunatutor/backend/src/use-cases/level-chat/prompts.ts:32-33`
- Implements: latency trick (S13 §11d); not a cache
```ts
export const RATER_CALL = { temperature: 0.1, timeoutMs: 2000, maxTokens: 500 } as const;
export const TUTOR_CALL = { temperature: 0.6, timeoutMs: 4000, maxTokens: 700 } as const;
```
- Notes:
  - The research also listed `JUDGE_CALL` 15 s at lines 34-36; no such constant exists on main.

### X38 · Billpod's per-person limit for the capture tool
- File: `~/projects/lomem/apps/billpod/backend/src/ai/tools/capture.ts:23-24`
- Implements: concurrency and rate limit (S13 §11e); not a cache
```ts
/** capture_invoice calls per person per window: the REST upload's limit (routes/billpod/captures.ts). */
export const CAPTURE_TOOL_LIMIT = { max: 30, windowMs: 60_000 };
```
- Notes:
  - 30 calls per 60-second window per person.

### X39 · Tunatutor's selectable models each need three price rows
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/models.ts:1-11`
- Implements: C52
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
  - A switch between these models in the admin registry does not bump `PANEL_BUNDLE_SCHEMA_VERSION`.

### X40 · A showable line is non-empty and closes its ¿ / ¡
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/panel-content/line-checks.ts:33-37`
- Implements: K23, F8.3, E12
```ts
/** A line a learner may be shown: non-empty and well-formed. */
export function isShowableLine(text: string | null | undefined): boolean {
  const trimmed = text?.trim() ?? "";
  return trimmed.length > 0 && !hasUnclosedMark(trimmed);
}
```
- Notes:
  - This is the v6 check that the version bump swept through every older row.

### X41 · The shared meter writes the same three rows for other apps
- File: `~/projects/lomem/packages/shared/src/llm/gateway/provider-usage-meter.ts:46-59`
- Implements: C52
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
```
- Notes:
  - A key with no price row is written at $0 with `isEstimated`, so tokens are never dropped.

### X42 · callLLM requires an options argument
- File: `~/projects/lomem/apps/tunatutor/backend/src/services/llm/index.ts:1-7,375-386`
- Implements: context for the pre-warm open question (X34)
```ts
// tunatutor's LLM entry points, on the shared gateway (`@repo/shared/llm`,
// ADR-057 §5). The gateway owns the refusal of unattributed calls, the
// provider fallback loop and the one settle point; this file supplies tunatutor's
// ports: the admin-configured registry and its sticky switch, the ledger +
// allowance settle below, the admin SSE error stream and the postmortem
// mirror. `callLLM` / `callLLMWithMeta` / `callLLMWithTools` keep their
// signatures for every existing caller.
...
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
  - The gateway "owns the refusal of unattributed calls"; the pre-warm script passes no options.
  - `apps/tunatutor/backend/tsconfig.json` includes only `src`, so the script is not type-checked with the backend.

## Analogy to classic backend

| AI-side item (id) | classic Java/Spring equivalent | holds where | breaks where |
|---|---|---|---|
| Provider prompt caching (C10) | A database's execution-plan cache for prepared statements; the research calls it a server-side compiled-statement cache (S10, S12) | The server reuses work for identical text, and one changed character defeats it (S10) | A plan cache is free and invisible; a prompt cache is chosen with a marker, billed (writes cost more than a plain call, reads less) and visible in token counts (S10). It matches a prefix in a fixed order, per model, per organization/workspace, with a short lifetime renewed on each hit (S10) |
| Exact response cache (C27) | Spring `@Cacheable` backed by Redis or a table; an HTTP or Redis response cache (S10, S12) | Store the result under a key; a hit skips the work (S10) | `@Cacheable` assumes the method returns the same result each time; a model call does not, so the cache freezes one sample, including a wrong one (S10) |
| Cache key (C28) | `@Cacheable` key from method arguments | Normalised arguments form the key | Here the key or version must also cover things outside the arguments: prompt text, output schema, model, call parameters (S10) |
| Version stamp (C38) | A version column checked on read (S10) | A row from older code is treated as stale | It is compared against a code constant on read, not used for optimistic locking like JPA `@Version` (derived) |
| Lazy invalidation (C38) | Cache eviction on deploy, or a migration job | Old entries stop being served | No job runs; each stale row regenerates on its next read, spreading model cost over traffic (S10) |
| Tunatutor rows (C27) | Spring cache entries usually with a TTL | Both store results | Tunatutor rows have no time-based expiry; they live until a version bump or eviction (S10) |
| Semantic cache (C43) | No classic equivalent; picture a cache that returns the value of the nearest key when the exact key is missing (S10) | — | A wrong `@Cacheable` hit is a visible bug; a wrong semantic hit is a fluent answer with no error (S10) |
| Concurrent misses (C37) | Cache stampede / single-flight lock | Both duplicate work on a cold key | Each duplicate is a paid model call; the guide accepts one extra call unless calls are expensive (S10) |
| Cache isolation (C21) | Per-tenant cache namespaces | Provider separates organizations and workspaces | Your own cache has no isolation unless you add a tenant to the key (S10) |
| Personal layer merge (C33) | Composing a shared DTO with per-user data after a cached call | Shared part cached, user part fresh | A model can bake user-specific forms into text (« allée »), so the prompt itself must be made neutral (S10, X33) |

## Pitfalls

| id | mistake | consequence | what to do instead | source |
|---|---|---|---|---|
| M1 | A timestamp, request id or user name near the top of the prompt | The prefix changes on every call; hit rate is zero; every call pays a 1.25x write | Put variable content last, or leave it out | S10 |
| M2 | Tools listed in a different order on each call, for example from a `HashMap` | The prefix changes; hit rate is zero | Use a fixed tool order (derived: `LinkedHashMap` or a sorted list) | S10 |
| M3 | A marker on text that changes on every call | Each call pays the write price for nothing | Mark only the end of the stable part; in a chat, move the marker to the newest message | S10 |
| M4 | Assuming the cache works | A prefix under the minimum is silently not cached | Log `cache_read_input_tokens`, `cache_creation_input_tokens`, `input_tokens`; chart the share | S10 |
| M5 | Reading a share below 100% as a broken cache | Wasted debugging | Compare against the ceiling `prefix / (prefix + tail)` | S10, testing |
| M6 | Mixing provider usage semantics | Wrong share or cost charts | Normalise: Anthropic `input_tokens` excludes cached tokens; Gemini's prompt count includes them | X8, X9, S10 |
| M7 | Logging cached tokens but pricing them at the full rate | Cost reports overstate spend (if the provider discounts cached tokens) | Price cached input on its own line, as Tunatutor does | X5, X6, X9 |
| M8 | A shared response cache stores answers that contain one user's data | The next user sees it | Keep personal data out; merge the personal layer after the lookup | S10, X27 |
| M9 | A shared row holds a form that fits only one user | A man is served « je suis allée » | Make shared prompts neutral (« allé(e) ») | S10, X33 |
| M10 | Normalising too far | "Weg" and "weg" share one answer | Normalise only as far as the meaning allows | S10 |
| M11 | The key misses the tenant or language pair | One tenant's answer is served to another | Put every answer-changing input in the key | S10 |
| M12 | The version is not bumped when the prompt or the model changes | Old answers are still served after a deploy | Bump in the same commit; cover call parameters too | S10 |
| M13 | Storing a model label that cannot change | A model switch is invisible to the cache | Bump by hand, or store and compare the real model id and call parameters | X25, S10 |
| M14 | An unconditional upsert during rolling deploys | Old instances overwrite new rows; extra model calls | Update only when the stored version is not higher than the writer's | S10, X14 |
| M15 | Caching a degraded result with no expiry | Empty fields served until the next bump | Do not store degraded results, or give them a short expiry (derived) | X22, X23 |
| M16 | No eviction path for a bad answer | One bad sample reaches every user | Add a report button that evicts; require distinct reporters for a shared cache | S10, X28 |
| M17 | Semantic cache with a guessed threshold, shared across users | Fluent wrong answers and data leaks with no error | Scope per tenant, set the threshold from labelled pairs, log hits with the matched question, or do not use it | S10 |
| M18 | Expecting temperature 0 to make the model deterministic | The cache freezes an unvalidated sample | Validate before storing | S10 |
| M19 | Putting the version in the key | Old rows are left behind instead of overwritten | Compare the version on read | S10, testing |
| M20 | Caching tiny prompts | Below the minimum nothing is cached | Check the model's minimum (512 to 4,096 tokens on Anthropic) | S1, S10 |

## Misconceptions

| id | what a newcomer believed | correct statement | evidence |
|---|---|---|---|
| Q1 | The response cache needs no eviction path | Users must be able to report a bad answer so that it is evicted; Tunatutor deletes a row after two distinct saved learners report `wrong_language` | testing round 1; X28 |
| Q2 | Rows need a "schema/prompt version" only | A model change must also bump the version, or the key must cover the model; call parameters too | testing rounds 1-2; S10 |
| Q3 | The prompt cache is invisible and cannot be managed | It is chosen with a marker, billed, and visible in the token counts | testing round 1 (the old analogy was wrong); S10 |
| Q4 | Prompt caching always saves money | It loses money when calls arrive alone, each more than 5 minutes apart; one reuse within 5 minutes pays for the write (1.35 vs 2) | testing rounds 1-3; S10 |
| Q5 | The order of tools, system and messages does not matter | The prefix is read in that order; changing a tool definition invalidates everything after it | testing rounds 1-2; S1 |
| Q6 | The 1-hour lifetime costs the same as the 5-minute one | A 1-hour write costs 2x input; it pays when the first call is followed by at least two more within the hour; ask for it with `"ttl": "1h"` in `cache_control` | testing rounds 1-2; S1, S10 |
| Q7 | Any customer could hit my prefix, or my own cache is isolated like the provider's | The provider isolates per organization (and workspace on Anthropic's own API); your own cache has no isolation unless you add it | testing rounds 1-3; S1, S10 |
| Q8 | "Validate before storing" is a vague rule | Parse the JSON, check required fields and types, store nothing on failure, drop a bad optional field | testing round 1; X20 |
| Q9 | A cache-read share below 100% means the cache is broken | The share is token-weighted and peaks at `prefix / (prefix + tail)`, about 87% in the example | testing rounds 2-3; S10 |
| Q10 | The version belongs in the key | The version is compared on read, so a new answer overwrites the old row | testing round 2; X13, S10 |
| Q11 | Only the system prompt can be cached | A marker can sit on a tool definition, a system block or a message content block; in a chat it sits on the newest message and moves every turn | testing rounds 2-3; S1, S10 |
| Q12 | Version 5 was only a shape change | Version 5 changed every prompt to the neutral « allé(e) » | testing round 2; X17 |
| Q13 | "Reports its language as wrong" is ambiguous | The reason means "the practice language in this answer is wrong or odd" | testing round 2; X31 |
| Q14 | A marker on the per-user message is fine | It pays 1.25x for text nobody reuses; only in a chat does the newest message carry the marker | testing round 3; S10 |
| Q15 | The key is normalised input plus language | It must also include the tenant where answers differ per tenant | testing round 3; S10 |
| Q16 | Temperature 0 makes the cached answer the one true answer | Output is not deterministic even at temperature 0; the cache freezes one sample for every user | testing round 3; S10 |
| Q17 | Concurrent misses corrupt the cache | Both call the model and the upsert keeps the last answer; the cost is one extra call | testing round 3; S10 |
| Q18 | A semantic hit needs no audit trail | Log each hit with the stored question it matched | testing rounds 2-3; S10 |
| Q19 | There is one cached prefix per request | Up to four markers, each its own prefix, hit on its own | testing round 3; S1 |
| Q20 | A too-short prefix raises an error | It is silently not cached; creation and read are both 0 | testing round 3; S1 |
| Q21 | A cache entry lives a fixed 5 minutes | Every hit renews it, whichever user made the hit | testing round 3; S1 |
| Q22 | The cache works across models | The cache is per model | testing round 3; S2, S10 |
| Q23 | Lomem's Mytube benefits from prompt caching because its comment says so | Mytube calls Cerebras with no marker, and whether Cerebras caches the prefix is unverified | testing (fact-check); X1, X4 |
| Q24 | The semantic-cache leakage risk is a quoted finding | It is the research author's own reading, not from a fetched source | S12 |
| Q25 | A failed answer is never stored in Tunatutor | True for sentences and the full word path; on the curated word path a failed call stores empty generative fields | testing (fact-check); X22, X23 |

## Open questions

- Anthropic's prompt-caching page does not state that the cache is per model; OpenAI's page does; the guide keeps the claim because it follows from the mechanism (unverified for Anthropic).
- The $3 per million input-token price in E4 is made up and was not checked against a price list; the arithmetic was checked.
- The 0.9 threshold is the guide's own example, not quoted from LiteLLM.
- The semantic-cache leakage and wrong-hit risk is the research author's reading, not from a fetched source.
- In a chat, why the previous turn's prefix still counts as a hit after the marker moves is not explained by the sources read (unverified).
- Whether each of up to four markers is charged its own 1.25x write on overlapping tokens is unverified.
- Whether the minimum prefix length is counted per marker or for the whole prefix is unverified.
- Whether OpenAI's automatic caching charges extra for writes is unverified.
- Whether Mytube benefits from caching on Cerebras is unverified: `prompts.ts` calls the fixed part "the cacheable prefix", but Mytube sends no marker and `cerebrasCostUsd` prices all input at the full rate.
- Code versus comment: `apps/mytube/web/lib/llm/prompts.ts:1-10` says prompts go to the local `claude` CLI; `index.ts` and `client.ts` use Cerebras.
- Code versus comment: `apps/mytube/web/lib/llm/client.ts:4-5` says "the five scoring methods in provider.ts call CerebrasProvider.chat() DIRECTLY"; there is no `provider.ts` in `apps/mytube/web/lib/llm/`; the calls are in `index.ts`.
- Whether Gemini's implicit caching ever triggers for Tunatutor's short panel prompts is unverified; the meter handles `cachedContentTokenCount`, but no explicit `cachedContents` API use was found.
- Code versus comment: `schema.prisma:2204` says `model` is the "LLM model id that generated it"; the code writes the constant `"panel-content/registry"`. The long draft's "Lomem stores the model name in each row" is inaccurate in detail; the label could not detect a model change even if compared.
- Code versus comment: `schema.prisma:2198` says `kind` is `"word" | "sentence"`; replies kinds `replies:<kind>` also live in the table.
- Code versus comment: `schema-version.ts` says to bump when the bundle shape changes; v5 was also a prompt change and v6 a validation sweep, so the documented rule is narrower than the practice.
- Code versus comment: `replies.ts:197` says "A short answer (1–2 of three replies)"; `MAX_REPLY_LINES.they_may_ask` is 2, so "three" fits only `you_can_answer`.
- Degraded word rows: on the curated word path a failed grounded call stores empty generative fields at the current version; nothing regenerates them except a version bump or two `wrong_language` reports, and "the language is wrong" does not describe an empty answer. Possibly unintended.
- `putPanelContent` updates `schemaVersion` unconditionally, so the rolling-deploy race described in S10 is live in Lomem.
- The pre-warm script may not work on main (not run): its pre-check uses `cacheKey: form` instead of `wordCacheKey(form)`, so a capitalised lemma counts as a miss; its deps have no `resolveCuratedWordFacts` or `resolveWordRanks`, which `getOrGenerateWord` calls when `preResolvedCurated` is not passed; and it calls `callLLM` with three arguments while `callLLM` requires an `options` argument and the gateway refuses unattributed calls (X42). Each of these would likely make every lemma fail and be counted as an error (unverified).
- Code versus comment: `prewarm-panel-cache.ts:51` says the label "Matches the production route's label in routes/panels.ts"; the production label is defined in `services/panel-content/deps.ts:38`.
- Research reference drift: the research placed the price-coverage comment in `packages/shared/src/llm/gateway/gateway.ts`; it is in `apps/tunatutor/backend/src/services/llm/registry.ts:199-204`.
- Research reference drift: the research listed `JUDGE_CALL` 15 s at `level-chat/prompts.ts:34-36`; no such constant exists on main.
- The eval worker pools (`CONCURRENCY = 3`, default 4 max 8) and the ADR-032 judge-call ceiling were not re-read for this file.
- Per-workspace isolation on AWS and Foundry, and per-organization-only isolation on Bedrock and Google Cloud, come from the fact-check and were not re-read here.
- The newest-model read prices (0.05x, 0.025x) come from the fact-check of Anthropic's docs as of October 2026 and were not re-read here.
- Not covered by the research: time-based expiry policies for response caches, cache sizing and eviction by memory (LRU), caching of tool results inside agent loops, and caching of embeddings in RAG.
- Not covered by the research: whether Tunatutor's help translations and quick translations (named in ADR-052 §3 as cached) use `panel_content_cache` or another store.

## Sources

| id | title | author or publisher | date | URL | what it supports |
|---|---|---|---|---|---|
| S1 | Prompt caching | Anthropic | as read October 2026 | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | Markers, prefix order, lifetimes, write and read prices, minimums, isolation, usage fields |
| S2 | Prompt caching | OpenAI | as read October 2026 | https://developers.openai.com/api/docs/guides/prompt-caching | Automatic caching, 1,024-token minimum on newest models, cache per model |
| S3 | Caching (LiteLLM proxy) | LiteLLM / BerriAI | as read October 2026 | https://docs.litellm.ai/docs/proxy/caching | Gateway caching including semantic modes |
| S4 | Redis LangCache | Redis | not given | https://redis.io/langcache/ | Managed semantic cache (named; content not read) |
| S5 | GPTCache | Zilliz | not given | https://github.com/zilliztech/GPTCache | Open-source semantic cache (named; content not read) |
| S6 | Building A Generative AI Platform | Chip Huyen | 25 Jul 2024 | https://huyenchip.com/2024/07/25/genai-platform.html | Cache as step 4 of the build order; place in the request path |
| S7 | Patterns for Building LLM-based Systems & Products | Eugene Yan | about Aug 2023 | https://eugeneyan.com/writing/llm-patterns/ | Caching as one of the core patterns |
| S8 | Emerging Patterns in Building GenAI Products | Bharani Subramaniam and Martin Fowler | 28 Jan to 25 Feb 2025 | https://martinfowler.com/articles/gen-ai-patterns/ | Has nothing on caching |
| S9 | Prompt management overview | Langfuse | not given | https://langfuse.com/docs/prompt-management/overview | Prompt clients cache prompts so fetching adds no latency |
| S10 | Caching cuts the cost of repeated text and repeated questions (long fact-checked draft) | this learning project | Lomem quoted as of 2026-10-14 | `personal/Learning/AI-Building-Blocks/sources/sections-long/13-caching.html` | The guide's explanations, running example, worked arithmetic, made-up examples, pitfalls, analogy |
| S11 | Caching (short version tested on newcomer readers) | this learning project | 2026-10-14 | `personal/Learning/AI-Building-Blocks/sources/sections-tested/13-caching.html` | Tested wording; repository excerpt without comment lines |
| S12 | Web research catalogue, block 13 and the request path | this learning project | 2026-10 | `personal/Learning/AI-Building-Blocks/sources/research-web.md` | Backend analogues, new problem, minimal and mature versions, tools, request path |
| S13 | Lomem code map, sections 9, 11 and 14 | this learning project | 2026-10 | `personal/Learning/AI-Building-Blocks/sources/research-lomem.md` | Where caching lives in Lomem; latency tricks filed next to it |
| S14 | ADR-052: Ask — the Help Panel | Lomem | 2026-07-27 | `~/projects/lomem/docs/adr/052-help-panel.md` | Two-layer content cache, "never personalised", lazy sweep, report rule |
| testing | Testing notes for this section (rounds 1-3, fact-check, final read) | this learning project | 2026-10 | `personal/Learning/AI-Building-Blocks/sources/testing-notes/13-caching-testing.md` | What readers misread, unknown terms, fact-check fixes, questions left |
