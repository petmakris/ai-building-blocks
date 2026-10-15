# One typed tool layer for UI, in-app assistant and MCP: web research

Researched 2026-10-15. Every source in the list at the end was fetched during this session, unless it is marked otherwise. Quotes are verbatim from the fetched page. A number appears here only if a fetched page states it. Where a page did not answer a question, the gap is marked.

## Summary

- **MCP spec, current revision: 2026-07-28.** It replaces 2025-11-25. The revision is stateless (no `initialize` handshake, no `Mcp-Session-Id`) and moves Tasks into an extension. Dynamic Client Registration is deprecated in favour of Client ID Metadata Documents. Tool annotations are formally "hints" that clients "MUST consider … untrusted unless they come from trusted servers". A server may vary `tools/list` "by the authorization presented on the request", so it can filter tools by scope.
- **Tool design guidance converges** on a few points: design capabilities, not endpoint wrappers; use fewer and more distinct tools; namespace them; return concise, high-signal results; write descriptions like onboarding docs; and evaluate tools with realistic multi-call tasks. OpenAI suggests "fewer than 20 functions" per turn as a soft rule. Anthropic's Tool Search raised Opus 4 selection accuracy from 49% to 74% on its MCP evaluation.
- **Products.** Most vendors ship a hosted MCP server as a **separate, agent-shaped surface** built over their existing public API (Stripe, Linear, Notion, Atlassian, Cloudflare, GitHub). Only two verified cases come near "one layer for every front door":
  - **GitHub:** the vendor's own agent, Copilot cloud agent, uses the same GitHub MCP server that external clients use.
  - **Android AppFunctions:** one annotated app function is offered to every on-device agent as an MCP-style tool.
  - No fetched source states that a product's own web UI calls its MCP tools.
- **Arguments against** routing actions through a model: agents "trade latency and cost for better task performance" (Anthropic). Inference is nondeterministic even at temperature 0 (80 distinct completions in 1,000 runs, Thinking Machines). Agents are inconsistent across runs: pass^8 is below 25% on τ-bench retail. Prompt injection through tool results is unsolved: the lethal trifecta, the GitHub MCP exploit, and OWASP LLM01/LLM06. The MCP `Tool` type has no version field, so a description change cannot be detected from the protocol alone.
- **Named patterns.**
  - "Agent-native" (Every; core principle "parity" between UI and agent tools).
  - Thoughtworks Radar puts "Naive API-to-MCP conversion" on **Hold**.
  - Fowler's site (Sadalage and Chandrasekaran): "design capabilities, not endpoints".
  - a16z: MCP servers will be "scenario- and use-case-centric instead of API-centric".
  - Microsoft: Azure API Management turns REST operations into MCP tools, which is the naive conversion Thoughtworks warns against.
  - The closest classic analogy is Cockburn's hexagonal architecture (ports and adapters). Its stated intent is "Allow an application to equally be driven by users, programs, automated test or batch scripts". None of the fetched AI sources names hexagonal architecture.

---

## 1. MCP specification (revision 2026-07-28)

### Version
- The spec landing page builds on `schema/2026-07-28/schema.ts`. The changelog lists changes "since the previous revision, 2025-11-25".
- Major changes in 2026-07-28:
  - Protocol-level sessions are removed. "Servers that need cross-call state use explicit, server-minted handles passed as ordinary tool arguments" (SEP-2567).
  - The `initialize` handshake is removed and every request carries its version and capabilities in `_meta` (SEP-2575).
  - A new `server/discover` method.
  - Tasks move to an extension (`io.modelcontextprotocol/tasks`).
  - Multi Round-Trip Requests (`InputRequiredResult`) replace server-initiated requests.
  - Roots, Sampling and Logging are deprecated.
  - "Deprecate the OAuth 2.0 Dynamic Client Registration Protocol (RFC7591) … in favor of Client ID Metadata Documents."
  - A feature lifecycle policy with "a minimum twelve-month deprecation window".
- Extensions named on the spec page: Tasks, Skills over MCP, and MCP Apps ("Interactive UI elements … rendered inline within conversations").

### Tools (server/tools)
- Tool fields: `name`, `title`, `description`, `icons`, `inputSchema` (JSON Schema, default 2020-12, MUST be a valid object), `outputSchema` (optional), `annotations` (optional) and `_meta`.
- When an `outputSchema` exists, "Servers MUST provide structured results that conform to this schema" and "Clients SHOULD validate structured results against this schema".
- Human in the loop: "For trust & safety and security, there SHOULD always be a human in the loop with the ability to deny tool invocations." Applications SHOULD:
  - "Provide UI that makes clear which tools are being exposed to the AI model"
  - "Insert clear visual indicators when tools are invoked"
  - "Present confirmation prompts to the user for operations"
- Tools are "model-controlled", but "the protocol itself does not mandate any specific user interaction model".
- Scope-dependent tool lists: `tools/list` "MUST NOT vary per-connection … The set MAY vary by the authorization presented on the request — for example, returning only the tools the caller's granted scopes permit".
- Ordering: "Servers SHOULD return tools in a deterministic order … improves LLM prompt cache hit rates."
- Two error channels:
  - Protocol errors (JSON-RPC).
  - Tool execution errors (`isError: true`) with "actionable feedback that language models can use to self-correct". Clients "SHOULD provide tool execution errors to language models".
- Security considerations:
  - Servers MUST "Validate all tool inputs; Implement proper access controls; Rate limit tool invocations; Sanitize tool outputs".
  - Clients SHOULD "Prompt for user confirmation on sensitive operations; Show tool inputs to the user before calling the server …; Validate tool results before passing to LLM; … Log tool usage for audit purposes".
- Stateful tools (non-normative): "a handle is a name, not a capability. The server should validate the caller's authorization against the handle on every call."

### Tool annotations, and why they are untrusted
- Spec text (tools page): "For trust & safety and security, clients **MUST** consider tool annotations to be untrusted unless they come from trusted servers."
- Spec landing page: "descriptions of tool behavior such as annotations should be considered untrusted, unless obtained from a trusted server" and "Hosts must obtain explicit user consent before invoking any tool".
- `ToolAnnotations` in schema.ts (2026-07-28): "NOTE: all properties in `ToolAnnotations` are **hints**. They are not guaranteed to provide a faithful description of tool behavior (including descriptive properties like `title`). Clients should never make tool use decisions based on `ToolAnnotations` received from untrusted servers."
  - `title`
  - `readOnlyHint`: default false.
  - `destructiveHint`: default true, "meaningful only when `readOnlyHint == false`".
  - `idempotentHint`: default false.
  - `openWorldHint`: default true. Example given: "the world of a web search tool is open, whereas that of a memory tool is not".
- The `Tool` interface has **no version field**. `description` is described as "like a 'hint' to the model". This was checked in schema.ts.

### Authorization (basic/authorization)
- Optional. HTTP transports SHOULD conform. STDIO "SHOULD NOT follow this specification, and instead retrieve credentials from the environment".
- Based on OAuth 2.1 draft-ietf-oauth-v2-1-13, RFC 8414, RFC 7591, RFC 8707, RFC 9728, RFC 9207, the Client ID Metadata Document draft-00, and OIDC Discovery.
- Roles: the MCP server is an OAuth 2.1 resource server and the MCP client is an OAuth 2.1 client.
- Protected Resource Metadata: "MCP servers MUST implement OAuth 2.0 Protected Resource Metadata (RFC9728). MCP clients MUST use [it] for authorization server discovery."
- Client registration:
  - Client ID Metadata Documents: "SHOULD support".
  - Dynamic Client Registration: "MAY support" and "deprecated".
  - Pre-registration.
  - Priority order: pre-registered, then CIMD (if `client_id_metadata_document_supported`), then DCR, then prompt the user.
- Resource Indicators: clients MUST send `resource` (the canonical server URI) in both the authorization and the token request. Servers "MUST validate that access tokens were issued specifically for them".
- Token passthrough: "MCP servers MUST NOT accept or transit any other tokens." From the security considerations page: "The MCP server MUST NOT pass through the token it received from the MCP client."
- Scopes and least privilege:
  - Servers SHOULD send `scope` in `WWW-Authenticate`.
  - `scopes_supported` is "the minimal set of scopes necessary for basic functionality, with additional scopes requested incrementally through the step-up authorization flow".
  - At runtime the server answers 403 `insufficient_scope`, and the client re-authorizes with the union of the old scopes and the new ones.
- Also required: PKCE (S256), and `iss` validation (RFC 9207, new in this revision).
- User consent (security best practices page): MCP proxy servers using a static client ID "MUST implement per-client consent". The consent page "MUST: Clearly identify the requesting MCP client by name; Display the specific third-party API scopes being requested; Show the registered redirect_uri".
- Scope minimization "Common Mistakes": "Publishing all possible scopes in `scopes_supported`; Using wildcard or omnibus scopes; … Silent scope semantic changes without versioning".

---

## 2. Vendor guidance on designing tools for models

### Anthropic, "Writing effective tools for agents — with agents" (Ken Aizawa, 2025-09-11)
- "More tools don't always lead to better outcomes." Instead of wrapping each endpoint (`list_users`, `list_events`, `create_event`), build one tool such as `schedule_event` that "finds availability and schedules an event".
- Namespace by service or resource, as in `asana_search` and `jira_search`. Prefix and suffix naming "have non-trivial effects" that vary by model.
- Return high-signal context. Offer a `response_format` enum with concise and detailed values. In the Slack example the concise format used 72 tokens against 206 for detailed.
- "For Claude Code, we restrict tool responses to 25,000 tokens by default."
- Write descriptions as you would onboard a new hire. For example, name a parameter `user_id`, not `user`.
- Evaluate with realistic tasks that may need "dozens" of tool calls and have verifiable outcomes. Keep a held-out test set. Track runtime, number of calls, tokens and tool errors.

### Anthropic, "Introducing advanced tool use on the Claude Developer Platform" (2025-11-24)
- Cost of tool definitions:
  - Five servers with 58 tools take "approximately 55K tokens". By server: GitHub 35 tools (~26K), Slack 11 (~21K), Sentry 5 (~3K), Grafana 5 (~3K), Splunk 2 (~2K). Jira alone takes ~17K.
  - Anthropic reports seeing "134K tokens before optimization".
- **Tool Search Tool** (deferred loading):
  - ~500 tokens up front and ~8.7K in total, against ~77K. The post calls this an "85% reduction in token usage".
  - Selection accuracy on MCP evaluations: "Opus 4 improved from 49% to 74%" and "Opus 4.5 improved from 79.5% to 88.1%".
  - It is recommended when there are "10+ tools" or definitions take ">10K tokens". It brings less benefit for libraries of fewer than 10 tools.
  - The post gives no tool count at which selection collapses. It names wrong tool selection, especially between similar names, as a common failure.
- **Programmatic Tool Calling** (Claude writes code that calls tools in a sandbox):
  - "Average usage dropped from 43,588 to 27,297 tokens, a 37% reduction on complex research tasks".
  - Internal knowledge retrieval improved from 25.6% to 28.5%, and GIA from 46.5% to 51.2%.
  - No latency figure is given beyond removing "19+" inference passes for a 20-call script.
- **Tool Use Examples**: "improved accuracy from 72% to 90% on complex parameter handling".

### Anthropic, "Code execution with MCP" (2025-11-04)
- "Agents scale better by writing code to call tools instead." In the post's example, token use drops from 150,000 to 2,000, which it calls a 98.7% saving.

### Anthropic, "Building effective agents" (2024-12-19)
- "Agentic systems often trade latency and cost for better task performance."
- "we recommend finding the simplest solution possible, and only increasing complexity when needed."
- Invest in the agent-computer interface (ACI). Poka-yoke tools: "Change the arguments so that it is harder to make mistakes". In their example, requiring absolute file paths removed a class of errors.

### OpenAI, function calling guide (developers.openai.com, fetched 2026-10-15)
- "Aim for fewer than 20 functions available at the start of a turn", which the guide calls "just a soft suggestion".
- "We recommend always enabling strict mode." Strict mode requires `additionalProperties: false` and every field listed in `required`.
- Use enums to make invalid states unrepresentable. Don't ask the model for values the code already knows. Merge functions that are always called in sequence. Apply the "intern test".
- Tools can be deferred with `tool_search` (gpt-5.4 and later), and "deferred tools are loaded only when needed".

### Cloudflare, Code Mode
- "Code Mode: the better way to use MCP" (Kenton Varda and Sunil Pai, 2025-09-26). The idea is to turn MCP tools into a TypeScript API and let the model write code against it, because "LLMs have seen a lot of code. They have not seen a lot of 'tool calls'." **The post gives no benchmark numbers.**
- "Code Mode: give agents an entire API in 1,000 tokens" (Matt Carey, 2026-02-20). The Cloudflare API has "over 2,500 endpoints". Two tools, `search()` and `execute()`, cover it in "around 1,000 tokens". "An equivalent MCP server without Code Mode would consume 1.17 million tokens."
  - The page's meta description says "over 2 million". The two figures disagree, and the body gives 1.17 million.

### Research numbers on tool count and selection accuracy
- **RAG-MCP** (Gan and Sun, arXiv 2505.03275, 2025-05-06). Retrieving tools before prompting cut prompt tokens by more than 50% and raised selection accuracy from 13.62% (baseline) to 43.13%.
- **Drew Breunig, "How to Fix Your Context"** (2025-06-26), summarising RAG-MCP and the paper below:
  - With DeepSeek-v3, confusion begins around 30 tools, and above 100 tools the model is "virtually guaranteed to fail".
  - Llama 3.1 8B failed a benchmark with 46 tools and succeeded with 19.
  - The 30/100/46/19 figures are Breunig's reading. The RAG-MCP abstract does not state the 30/100 thresholds.
- **"Less is More"** (Paramanayakam et al., arXiv 2411.15399, 2024-11-23). The abstract reports up to 70% less execution time and 40% less power from selecting fewer tools. It gives no success-rate number.
- Not verified: a claim that "Haiku 4.5 91% at 10 tools → 87% at 15" (Rodrigues and Vas). It appeared only in a secondary search summary, and the paper was not opened.

---

## 3. Real products: shared layer or separate surface?

| Product | What it is | Date | Shared with the product's own UI? | Verified |
|---|---|---|---|---|
| **Stripe MCP** (`https://mcp.stripe.com`) | Remote MCP server. Generic `stripe_api_search`, `stripe_api_details`, `stripe_api_read` (any GET) and `stripe_api_write` (any POST/PATCH/PUT/DELETE), plus product tools (Treasury `send_money` and others, in preview). Auth by OAuth or "agent API keys". From Dec 2026, full-access and untagged restricted keys are refused. **Human confirmation**: Stripe "requires human confirmation before running certain `stripe_api_write` actions, such as refunds and outbound payments", via a URL; approval expires after 24 h. Admins can turn MCP on or off per live mode and sandbox, and revoke OAuth sessions. | page undated; key migration deadline 2026-11-30 | **Separate surface over the public Stripe API.** The page does not say whether the Dashboard uses it. | yes (docs.stripe.com/mcp, German locale served) |
| **Stripe agent toolkit** (github.com/stripe/agent-toolkit) | SDKs (`@stripe/ai-sdk` for Vercel AI SDK, `@stripe/token-meter`), skills and plugins. Points to the hosted MCP server. | — | Separate. The README does not mention OpenAI Agents SDK, LangChain or CrewAI. | yes |
| **GitHub MCP server** | Remote server (`api.githubcopilot.com/mcp/`) or local binary or Docker image. `--toolsets` and `--tools` reduce context. `--read-only` "takes priority". **Lockdown mode** filters public-repo content from authors without push access, to reduce prompt injection, and the README says it is "**not** an authorization boundary". | — | **The vendor's own agent uses it**: Copilot cloud agent gets the GitHub MCP server configured automatically, with "a specially scoped token that only has read-only access to the current repository". The web UI is not built on it. | yes (README, GitHub Docs) |
| **OpenAI Apps SDK / MCP Apps** | MCP blog: the Apps SDK lets developers "build rich, interactive applications inside ChatGPT using MCP as its backbone". The MCP Apps extension (SEP-1865) "builds on proven work from MCP-UI and OpenAI Apps SDK". It is now an official extension: a tool declares a `ui://` resource and the host renders it in a sandboxed iframe that can itself call `tools/call`. Current OpenAI docs talk of "plugins" and "Build an MCP server for ChatGPT and Codex, with optional UI". | Apps SDK announced at DevDay, Oct 2025 (secondary sources only); MCP Apps post 2025-11-21 | One MCP server serves the model and an embedded UI, but that UI lives inside the AI host, not in the vendor's own app. | MCP blog: yes. openai.com announcement: **no (HTTP 403)** |
| **Cloudflare MCP (Code Mode)** | Two tools over the whole Cloudflare API, generated from the OpenAPI spec and run in a Dynamic Worker isolate with "external fetches disabled by default". | 2026-02-20 | **Generated from the same OpenAPI spec as the public API.** It is a separate surface derived from the same contract. | yes |
| **Atlassian Remote MCP / Atlassian MCP** | Beta launched 2025-05-01, built on Cloudflare's Agents SDK, with Anthropic as the "first official partner". It "respects all your existing permission controls". Rebuilt in Oct 2026: "220+ tools" and "up to 25%" fewer tokens than the previous version (internal benchmark on Claude). OAuth 2.1 with PKCE. Read, write and destructive actions are separated so that clients can require confirmation. Guard DLP policies apply. | 2025-05-01; 2026-10-06 | Separate surface. **The post does not say whether Rovo (Atlassian's own AI) uses the same layer.** | yes |
| **Linear MCP** (`mcp.linear.app/mcp`, plus `/mcp/readonly`) | Centrally hosted server. OAuth 2.1 with DCR, or an API key. Tools for issues, projects and comments. | 2025-05-01 | Separate surface. **The docs do not mention whether it uses the same GraphQL API as the app.** | yes |
| **Notion MCP** (hosted) | Tools "optimized for AI agents—not HTTP calls to the API". `create-pages` and `update-page` were rewritten for agents. "Notion-flavored Markdown" gives more content per token. Notion worked with "the team building the in-app Notion Agent". | 2025-07-15 | Agent-shaped surface built with the in-app agent team. **The post does not say the tools or code are shared** with the in-app agent or the UI. | yes |
| **Shopify** | Storefront MCP at `https://{shop}/api/mcp`. Its catalog and cart tools have been removed and replaced by the UCP endpoint `/api/ucp/mcp`, a Cart MCP and a Checkout MCP. Dev MCP: `@shopify/dev-mcp`. | Dates come only from secondary sources | Separate surfaces per use case. The page does not relate them to the Storefront API. | Storefront page: yes. Dates: no |
| **Android AppFunctions** | "empowers your apps to behave like on device MCP servers". `@AppFunction`-annotated Kotlin functions, with KDoc as the description, become tools for Gemini and other agents. Requires Android 16 / API 36. Experimental. Gemini integration in private preview "as of May 2026". | page updated 2026-09-22 | **The capability is defined once, in-process, next to the app's own repository code** (the example injects `TaskRepository`). This is the nearest verified match to "one typed layer". | yes |
| **Azure API Management** | "Expose one or more of the API operations as tools that MCP clients can call". APIM policies (rate limiting, auth) apply to all tools. Tools only; resources and prompts are not supported. | doc dated 2026-04-28 | One API serves both the app and agents, with a 1:1 mapping from operation to tool. | yes |

**Finding:** no fetched source shows a product whose **own web UI** calls the same tool layer that its in-app assistant and external MCP clients use. Some sources come close:
- GitHub's first-party agent uses the same MCP server as external clients.
- Cloudflare derives its MCP surface from the same OpenAPI contract as its public API.
- Android AppFunctions defines a capability once beside the app's domain code.
- Notion built its tools together with the in-app agent team.

The "agent-native" guide (section 5) states the parity principle as a design goal, not a product case.

---

## 4. Arguments and evidence for and against

### Cost and latency of routing actions through a model
- Anthropic: "Agentic systems often trade latency and cost for better task performance." It advises the simplest solution first.
- Tool definitions alone can take 55K–134K tokens before any work starts (Anthropic advanced tool use). Each extra inference pass costs "hundreds of milliseconds to seconds" (same post).
- Mitigations with published numbers:
  - Tool Search: 85% fewer tokens.
  - Programmatic tool calling: 37% fewer.
  - Code execution with MCP: 150K to 2K tokens.
  - Cloudflare Code Mode: about 1K against 1.17M tokens.
- Thoughtworks (Hold): granular APIs "chained together by an AI, can lead to excessive token usage, context pollution, and poor agent performance".

### Non-determinism
- Thinking Machines (Horace He, 2025-09-10): Qwen3-235B at temperature 0, 1,000 runs, gave "80 unique completions". The cause is the lack of batch invariance in kernels, not floating-point concurrency alone. Batch-invariant kernels made all 1,000 identical, at 26 s → 42 s for 1,000 requests on Qwen3-8B.
- τ-bench (Yao et al., 2024-06-17): gpt-4o-class agents succeed on "<50% of the tasks", and "pass^8 is below 25% in the retail domain".

### Tool selection errors
- See the section 2 numbers: Tool Search 49% → 74% (Opus 4); RAG-MCP 13.62% → 43.13%; OpenAI's soft limit of 20.
- Sadalage and Chandrasekaran (martinfowler.com, 2026-08-27): "Five to ten well described business capabilities will outperform 50 thin API wrappers almost every time".
- MCP spec: servers may filter `tools/list` by the caller's scopes, so fewer tools are visible per user.

### Prompt injection through tool results
- **OWASP LLM01:2025 Prompt Injection.** Indirect injection "occur[s] when an LLM accepts input from external sources, such as websites or files". Its mitigations:
  - constrain model behaviour
  - validate output formats with deterministic code
  - filtering
  - least privilege, "handle privileged functions in code rather than through the model"
  - human approval for high-risk actions
  - segregate external content
  - adversarial testing
- **OWASP LLM06:2025 Excessive Agency.** Root causes are excessive functionality, excessive permissions and excessive autonomy. Mitigations:
  - minimise extensions
  - avoid open-ended extensions (granular tools rather than a shell)
  - minimise permissions
  - execute in the user's context with limited OAuth scopes
  - require user approval
  - **complete mediation**: "enforce authorization in downstream systems instead of relying on the LLM"
- **Lethal trifecta** (Simon Willison, 2025-06-16): "Access to your private data", "Exposure to untrusted content" and "The ability to externally communicate". "We still don't know how to 100% reliably prevent this." MCP "encourages users to mix and match tools from different sources."
- **GitHub MCP exploit** (Invariant Labs, 2025-05-26):
  - A malicious issue in a public repo led Claude 4 Opus with the official GitHub MCP server to leak private-repo data into a public PR.
  - The user had set tool calls to "Always Allow".
  - Invariant calls it architectural, not a server bug. GitHub later added lockdown mode, which is "not an authorization boundary".
- **Tool poisoning and rug pulls** (Invariant Labs, 2025-04-01): "malicious instructions are embedded within MCP tool descriptions that are invisible to users but visible to AI models". In a rug pull, "a malicious server can change the tool description after the client has already approved it". The mitigation is to pin the server version and its tools, with "a hash or checksum".
- **Design patterns** (Beurer-Kellner et al., arXiv 2506.08837, 2025-06; list taken from Willison's 2025-06-13 summary): Action-Selector, Plan-Then-Execute, LLM Map-Reduce, Dual LLM, Code-Then-Execute, Context-Minimization.
- The MCP spec says clients SHOULD "Validate tool results before passing to LLM" and that servers MUST "Sanitize tool outputs".

### Confirmation for destructive tools
- MCP: there SHOULD be a human in the loop who can deny calls, and clients SHOULD prompt "for user confirmation on sensitive operations". `destructiveHint` defaults to true, but annotations are untrusted from untrusted servers.
- Stripe enforces confirmation **on the server**: refunds and outbound payments need a human approval URL, and the approval expires in 24 h.
- Atlassian separates read, write and destructive actions "so clients can require confirmation".

### Scopes and least privilege
- MCP: minimal `scopes_supported`, plus step-up through `insufficient_scope` challenges. The "Common Mistakes" list includes omnibus scopes.
- Examples:
  - GitHub: `--read-only`, toolsets, and a read-only repo-scoped token for Copilot cloud agent.
  - Linear: `/mcp/readonly` endpoint.
  - Stripe: agent API keys "only with the permissions that the client needs".
  - Atlassian: "will never grant access a user didn't already have".

### Versioning tool descriptions as an API contract
- The MCP `Tool` type has no version field; `listChanged` notifications announce changes. The protocol has a twelve-month deprecation policy for **itself**, but nothing per tool.
- "Silent scope semantic changes without versioning" is a listed MCP common mistake.
- Invariant recommends pinning tool descriptions by hash.
- **No fetched vendor source treats tool descriptions as a versioned contract with semver.** That treatment remains a proposal.

### Evaluating tool choice
- Anthropic: realistic tasks with verifiable outcomes, a held-out set, and tracking of calls, tokens and errors.
- OpenAI: "Test accuracy with different function counts".
- Benchmarks:
  - BFCL ("evaluates the LLM's ability to call functions (aka tools) accurately"). V4 adds agentic evaluation; last updated 2026-04-12.
  - τ-bench, with pass^k for consistency.

---

## 5. Named patterns and classic analogies

- **"Agent-native architectures"** (Every, Dan Shipper and Claude; no date on the page). Parity: "Whatever the user can do through the UI, the agent should be able to achieve through tools." Granularity: "Tools should be atomic primitives." Further principles are composability, emergent capability, and improvement over time. "Agents and users should work in the same data space, not separate sandboxes."
  - Note the tension: Every favours atomic primitives, while Anthropic, Thoughtworks and Sadalage favour fewer, higher-level capability tools.
- **Thoughtworks Technology Radar, "Naive API-to-MCP conversion": Hold** (2025-11-05). "We recommend architecting a dedicated, secure MCP server specifically tailored for agentic workflows, built on top of your existing APIs." The blip is no longer on the current edition.
- **martinfowler.com, "Making Your Data Ready for Agentic AI"** (Pramod Sadalage and Prem Chandrasekaran, 2026-08-27).
  - "design capabilities, not endpoints".
  - Each capability carries a description, inputs, permissions, an owner, preconditions and a reversibility class.
  - "Resources (read-only) are safe, Prompts shape behavior, and Tools change state."
  - The article does not mention hexagonal architecture.
- **a16z, "A Deep Dive Into MCP and the Future of AI Tooling"** (Yoko Li, 2025-03-20). "MCP server design will be scenario- and use-case-centric instead of API-centric"; "APIs alone are no longer enough, but can be great starting points".
- **Microsoft.** Azure API Management maps REST API operations to MCP tools under gateway policies. This is the operation-equals-tool mapping. No fetched Microsoft reference architecture names a pattern.
- **Anthropic.** ACI (agent-computer interface) and poka-yoke tools in "Building effective agents". Code Mode and programmatic tool calling are the "tools as a code API" variant.
- **Classic analogy: hexagonal architecture / ports and adapters** (Alistair Cockburn, 2005-09-04). Intent: "Allow an application to equally be driven by users, programs, automated test or batch scripts, and to be developed and tested in isolation from its eventual run-time devices and databases."
  - The tool layer reads as a driving port.
  - The UI, the in-app assistant and the MCP server read as driving adapters.
  - **This mapping is this report's inference. No fetched AI source states it.**
- **Not researched, no source fetched:** API-first, the command pattern and CQRS commands. Their fit as analogies (a tool call as a serializable command with a schema, and authorization at the handler) is offered without a citation.

---

## Sources

| # | Title | Publisher | Date | URL | Verified |
|---|---|---|---|---|---|
| 1 | Specification (landing, 2026-07-28) | Model Context Protocol | 2026-07-28 | https://modelcontextprotocol.io/specification/latest | yes |
| 2 | Key Changes (changelog) | Model Context Protocol | 2026-07-28 | https://modelcontextprotocol.io/specification/2026-07-28/changelog | yes |
| 3 | Tools | Model Context Protocol | 2026-07-28 | https://modelcontextprotocol.io/specification/2026-07-28/server/tools | yes |
| 4 | schema.ts (ToolAnnotations, Tool) | modelcontextprotocol GitHub | 2026-07-28 | https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/2026-07-28/schema.ts | yes |
| 5 | Authorization | Model Context Protocol | 2026-07-28 | https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization | yes |
| 6 | Client Registration | Model Context Protocol | 2026-07-28 | https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/client-registration | yes |
| 7 | Authorization Security Considerations | Model Context Protocol | 2026-07-28 | https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/security-considerations | yes |
| 8 | Security Best Practices | Model Context Protocol | undated | https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices | yes |
| 9 | MCP Apps (extension overview) | Model Context Protocol | undated | https://modelcontextprotocol.io/extensions/apps/overview | yes |
| 10 | MCP Apps: Extending servers with interactive user interfaces | MCP blog | 2025-11-21 | https://blog.modelcontextprotocol.io/posts/2025-11-21-mcp-apps/ | yes |
| 11 | Writing effective tools for agents — with agents | Anthropic | 2025-09-11 | https://www.anthropic.com/engineering/writing-tools-for-agents | yes |
| 12 | Introducing advanced tool use on the Claude Developer Platform | Anthropic | 2025-11-24 | https://www.anthropic.com/engineering/advanced-tool-use | yes |
| 13 | Code execution with MCP | Anthropic | 2025-11-04 | https://www.anthropic.com/engineering/code-execution-with-mcp | yes |
| 14 | Building effective agents | Anthropic | 2024-12-19 | https://www.anthropic.com/engineering/building-effective-agents | yes |
| 15 | Function calling guide | OpenAI | undated (fetched 2026-10-15) | https://developers.openai.com/api/docs/guides/function-calling | yes |
| 16 | Building an MCP server (Apps/plugins docs) | OpenAI | undated | https://developers.openai.com/apps-sdk/concepts/mcp-server | yes (does not name "Apps SDK") |
| 17 | Introducing apps in ChatGPT and the new Apps SDK | OpenAI | Oct 2025 (secondary) | https://openai.com/index/introducing-apps-in-chatgpt/ | **no (HTTP 403)** |
| 18 | Code Mode: the better way to use MCP | Cloudflare | 2025-09-26 | https://blog.cloudflare.com/code-mode/ | yes |
| 19 | Code Mode: give agents an entire API in 1,000 tokens | Cloudflare | 2026-02-20 | https://blog.cloudflare.com/code-mode-mcp/ | yes |
| 20 | RAG-MCP: Mitigating Prompt Bloat in LLM Tool Selection | arXiv 2505.03275 | 2025-05-06 | https://arxiv.org/abs/2505.03275 | yes (abstract) |
| 21 | Less is More: Optimizing Function Calling for LLM Execution on Edge Devices | arXiv 2411.15399 | 2024-11-23 | https://arxiv.org/abs/2411.15399 | yes (abstract) |
| 22 | How to Fix Your Context | dbreunig.com | 2025-06-26 | https://www.dbreunig.com/2025/06/26/how-to-fix-your-context.html | yes |
| 23 | Model Context Protocol (MCP) | Stripe Docs | undated | https://docs.stripe.com/mcp | yes |
| 24 | stripe/agent-toolkit | Stripe (GitHub) | undated | https://github.com/stripe/agent-toolkit | yes |
| 25 | github/github-mcp-server README | GitHub | undated | https://github.com/github/github-mcp-server | yes |
| 26 | MCP and GitHub Copilot cloud agent | GitHub Docs | undated | https://docs.github.com/en/copilot/concepts/agents/coding-agent/mcp-and-coding-agent | yes |
| 27 | Introducing Atlassian's Remote MCP Server | Atlassian | 2025-05-01 | https://www.atlassian.com/blog/announcements/remote-mcp-server | yes |
| 28 | Atlassian MCP brings more of your work within reach of any AI agent | Atlassian | 2026-10-06 | https://www.atlassian.com/blog/company-news/team26-europe-atlassian-mcp | yes |
| 29 | Rovo MCP (product page) | Atlassian | undated | https://www.atlassian.com/platform/rovo-mcp | yes (little content) |
| 30 | MCP server (docs) | Linear | undated | https://linear.app/docs/mcp | yes |
| 31 | Linear MCP server (changelog) | Linear | 2025-05-01 | https://linear.app/changelog/2025-05-01-mcp | yes |
| 32 | Notion MCP (docs) | Notion | undated | https://developers.notion.com/docs/mcp | yes |
| 33 | Notion's hosted MCP server: an inside look | Notion | 2025-07-15 | https://www.notion.com/blog/notions-hosted-mcp-server-an-inside-look | yes |
| 34 | Storefront MCP server | Shopify | undated | https://shopify.dev/docs/apps/build/storefront-mcp/servers/storefront | yes |
| 35 | AppFunctions | Android Developers | updated 2026-09-22 | https://developer.android.com/ai/appfunctions | yes |
| 36 | Expose REST API as MCP server | Microsoft Learn | 2026-04-28 | https://learn.microsoft.com/en-us/azure/api-management/export-rest-mcp-server | yes |
| 37 | LLM01:2025 Prompt Injection | OWASP GenAI | 2025 list | https://genai.owasp.org/llmrisk/llm01-prompt-injection/ | yes |
| 38 | LLM06:2025 Excessive Agency | OWASP GenAI | 2025 list | https://genai.owasp.org/llmrisk/llm062025-excessive-agency/ | yes |
| 39 | The lethal trifecta for AI agents | Simon Willison | 2025-06-16 | https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/ | yes |
| 40 | Design Patterns for Securing LLM Agents against Prompt Injections (summary) | Simon Willison | 2025-06-13 | https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/ | yes |
| 41 | Design Patterns for Securing LLM Agents against Prompt Injections | arXiv 2506.08837 | 2025-06-10 | https://arxiv.org/abs/2506.08837 | yes (abstract) |
| 42 | MCP Security Notification: Tool Poisoning Attacks | Invariant Labs | 2025-04-01 | https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks | yes |
| 43 | GitHub MCP Exploited: Accessing private repositories via MCP | Invariant Labs | 2025-05-26 | https://invariantlabs.ai/blog/mcp-github-vulnerability | yes |
| 44 | Defeating Nondeterminism in LLM Inference | Thinking Machines Lab | 2025-09-10 | https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/ | yes |
| 45 | τ-bench | arXiv 2406.12045 | 2024-06-17 | https://arxiv.org/abs/2406.12045 | yes (abstract) |
| 46 | Berkeley Function Calling Leaderboard | UC Berkeley Gorilla | updated 2026-04-12 | https://gorilla.cs.berkeley.edu/leaderboard.html | yes |
| 47 | Naive API-to-MCP conversion (Hold) | Thoughtworks Technology Radar | 2025-11-05 | https://www.thoughtworks.com/radar/techniques/naive-api-to-mcp-conversion | yes |
| 48 | Making Your Data Ready for Agentic AI | martinfowler.com | 2026-08-27 | https://martinfowler.com/articles/making-data-ready-for-agentic-ai.html | yes |
| 49 | A Deep Dive Into MCP and the Future of AI Tooling | a16z | 2025-03-20 | https://a16z.com/a-deep-dive-into-mcp-and-the-future-of-ai-tooling/ | yes |
| 50 | Agent-native Architectures | Every | undated | https://every.to/guides/agent-native | yes |
| 51 | Hexagonal architecture | Alistair Cockburn | 2005-09-04 | https://alistair.cockburn.us/hexagonal-architecture/ | yes |

Search results that were seen but not opened, and are not relied on: the Rodrigues and Vas tool-count paper (Haiku 4.5 91%/87%), the MCPTox attack success rates, Shopify launch dates, and the OpenAI DevDay write-ups.
