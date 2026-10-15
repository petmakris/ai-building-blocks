I've built a catalogue of 16 building blocks, the request path through them, and a ranked reading list. I checked every link below with a live HTTP request, and fetched the main sources to read what they say. Sources that resolved but whose content I didn't read are listed under "Unverified" at the end. Spring AI is listed under every block it covers, because it gives a Spring Boot engineer the most familiar entry point.

## The Fowler / Subramaniam catalogue

"Emerging Patterns in Building GenAI Products", Bharani Subramaniam and Martin Fowler, published 28 Jan to 25 Feb 2025: https://martinfowler.com/articles/gen-ai-patterns/

It defines exactly nine patterns, in this order, quoted from the page:
1. **Direct Prompting**: "Send prompts directly from the user to a Foundation LLM"
2. **Embeddings**: "Transform large data blocks into numeric vectors so that embeddings near each other represent related concepts"
3. **Evals**: "Evaluate the responses of an LLM in the context of a specific task"
4. **Fine Tuning**: "Carry out additional training to a pre-trained LLM to enhance its knowledge base for a particular context"
5. **Guardrails**: "Use separate LLM calls to avoid dangerous input to the LLM or to sanitize its results"
6. **Hybrid Retriever**: "Combine searches using embeddings with other search techniques"
7. **Query Rewriting**: "Use an LLM to create several alternative formulations of a query and search with all the alternatives"
8. **Reranker**: "Rank a set of retrieved document fragments according to their usefulness and send the best of them to the LLM"
9. **Retrieval Augmented Generation (RAG)**: "Retrieve relevant document fragments and include these when prompting the LLM"

- The page calls itself "early days" and says it will be extended, but names no future patterns. No sections have been added since February 2025.
- It is strongest on RAG. It has nothing on gateways, tracing, caching, agents or MCP.
- Agent and context material on the same site sits in Birgitta Böckeler's "Context Engineering for Coding Agents" (5 Feb 2026), in the "Exploring Gen AI" series: https://martinfowler.com/articles/exploring-gen-ai/context-engineering-coding-agents.html

Two other catalogues in the same vein:
- **Eugene Yan, "Patterns for Building LLM-based Systems & Products"** (about Aug 2023): Evals, RAG, Fine-tuning, Caching, Guardrails, Defensive UX, Collect user feedback. https://eugeneyan.com/writing/llm-patterns/
- **Chip Huyen, "Building A Generative AI Platform"** (25 Jul 2024) presents the parts as a build order: enhance context, then guardrails, then router and gateway, then cache, then complex logic and write actions. Observability and orchestration run across all of them. https://huyenchip.com/2024/07/25/genai-platform.html

---

## The blocks

### 1. Model gateway and router
- **Backend analogue:** an API gateway plus an outbound HTTP client with circuit breaker, retry and rate limiter, plus a per-tenant quota service.
- **New problem:**
  - Several providers each have their own API.
  - Cost is charged per token, so one bad loop is a real bill.
  - Providers have outages and 429s.
  - You need to send cheap requests to a small model and hard ones to a large model.
  - API keys spread across services.
- **Minimal:** one client wrapper, provider key in a vault, retry with backoff, token counts logged.
- **Mature:**
  - A self-hosted proxy with one OpenAI-compatible endpoint.
  - Virtual keys per team, with budgets and rate limits.
  - Fallback chains across providers or regions.
  - Spend recorded per key, team or tag.
  - Exact and semantic caching, PII redaction hooks, and an OTel export.
  - A router that classifies requests and picks the model.
- **Tools:**
  - LiteLLM (OSS): https://github.com/BerriAI/litellm and https://docs.litellm.ai/docs/simple_proxy
  - Portkey gateway (OSS and hosted): https://github.com/Portkey-AI/gateway
  - Kong AI Gateway: https://developer.konghq.com/ai-gateway/
  - OpenRouter (hosted): https://openrouter.ai/docs
- **Source:** Chip Huyen, step 3 "model router and gateway", https://huyenchip.com/2024/07/25/genai-platform.html. OWASP LLM10:2025 "Unbounded Consumption" covers the cost and DoS side.

### 2. Prompt management and versioning
- **Backend analogue:** externalised config and feature flags, with versions and environment labels.
- **New problem:**
  - The prompt is now behaviour, and a one-word change can regress quality.
  - Non-engineers (domain experts) need to edit it.
  - You need to know which prompt version produced which trace.
- **Minimal:** prompts as versioned template files in the repo, rendered with typed variables, with the version hash logged on every call.
- **Mature:**
  - A registry with versions and labels (production or staging).
  - Clients cache the prompt, so fetching it adds no latency.
  - Each version is linked to traces and eval scores.
  - Promotion is gated on an eval run, and rollback means moving a label.
- **Tools:**
  - Langfuse (OSS): https://langfuse.com/docs/prompt-management/overview
  - LangSmith: https://docs.smith.langchain.com/
  - Braintrust: https://www.braintrust.dev/docs
  - promptfoo, for testing prompts in the repo: https://www.promptfoo.dev/docs/intro/
- **Source:** the Langfuse docs above. They confirm versioning, labels, client caching and trace linking. Keeping prompts in git is the default unless non-engineers must edit them.

### 3. Context engineering
- **Backend analogue:** a request assembler or DTO builder that composes a payload from many repositories under a hard size limit. Think of building a response under a strict byte budget.
- **New problem:**
  - The context window is finite and quality degrades as it fills ("context rot").
  - Every token costs money and latency.
  - What the model sees *is* its behaviour.
- **Minimal:** a fixed system prompt, plus the last N turns, plus retrieved snippets, plus tool definitions, all under a token budget.
- **Mature (Anthropic's techniques):**
  - **Compaction:** summarise near the limit and continue in a fresh window.
  - **Clearing old tool results.**
  - **Structured note-taking:** a memory file outside the window.
  - **Sub-agents** that work in clean windows and return condensed summaries.
  - **Just-in-time retrieval:** keep references (paths, queries) and load the data with tools when needed.
  - **Tool search:** load tool definitions on demand.
- **Tools:**
  - Claude API context editing: https://platform.claude.com/docs/en/build-with-claude/context-editing
  - Claude API compaction: https://platform.claude.com/docs/en/build-with-claude/compaction
  - Spring AI Advisors, an interceptor chain around the model call: https://docs.spring.io/spring-ai/reference/api/advisors.html
  - LangGraph: https://docs.langchain.com/oss/python/langgraph/overview
- **Source:** Anthropic, "Effective context engineering for AI agents" (29 Sep 2025), https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

### 4. Structured output and validation
- **Backend analogue:** Jackson deserialisation plus Bean Validation on an inbound DTO, except the "client" is the model.
- **New problem:**
  - Free text can't be parsed reliably.
  - Without constraints, models return malformed or partial JSON.
  - Model output must be treated as untrusted input (OWASP LLM05 "Improper Output Handling").
- **Minimal:** ask for JSON, parse it, validate against a schema, retry once with the error message, fall back if it still fails.
- **Mature:**
  - Provider-side **constrained decoding**: the schema is compiled into a grammar, so the output is guaranteed to parse. Anthropic's version uses `output_config.format`, and `strict: true` does the same for tool inputs.
  - Business validation still runs on top.
  - Limits to know: Anthropic rejects numeric and length constraints and recursive schemas. A refusal or `max_tokens` stop can still break the schema.
- **Tools:**
  - Claude structured outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
  - OpenAI structured outputs: https://developers.openai.com/api/docs/guides/structured-outputs
  - Instructor (OSS): https://github.com/567-labs/instructor
  - Outlines (OSS): https://github.com/dottxt-ai/outlines
  - Spring AI structured output converters, mapping to POJOs: https://docs.spring.io/spring-ai/reference/api/structured-output/converters.html
- **Source:** the Claude structured outputs page above, plus OWASP LLM05:2025 at https://genai.owasp.org/llm-top-10/

### 5. Tool and function calling, and MCP
- **Backend analogue:**
  - A tool is an RPC endpoint whose caller is the model. The JSON schema is its OpenAPI contract.
  - MCP is like LSP or JDBC for LLM apps: a standard protocol so any host can plug into any tool or data server.
- **New problem:**
  - The model decides which endpoint to call and with what arguments.
  - Tool descriptions are effectively prompts.
  - Tool output flows back into the context, which is a token cost and an injection vector.
  - "Excessive agency" (OWASP LLM06).
- **Minimal:** a handful of tools with tight schemas, run in-process, with consent or allow-lists for writes.
- **Mature:**
  - Few, high-level tools that are namespaced, paginated and return readable errors (Anthropic's guidance).
  - MCP servers for shared integrations, with OAuth-based authorization.
  - Tool search when there are many tools.
  - Programmatic tool calling: the model writes code that calls tools in a sandbox, so intermediate data stays out of the context.
  - Every call is audit-logged.
- **MCP spec:** the current version is **2026-07-28**.
  - Runs on JSON-RPC 2.0, with hosts, clients and servers.
  - Servers expose Tools, Resources and Prompts. Clients offer Elicitation.
  - Optional extensions: Tasks (long-running work), Skills over MCP, MCP Apps.
  - The spec says tool annotations are untrusted unless they come from a trusted server.
  - https://modelcontextprotocol.io/specification/latest
- **Tools:**
  - MCP Java SDK: https://github.com/modelcontextprotocol/java-sdk
  - Spring AI tools: https://docs.spring.io/spring-ai/reference/api/tools.html
  - Spring AI MCP: https://docs.spring.io/spring-ai/reference/api/mcp/mcp-overview.html
  - LangChain4j: https://docs.langchain4j.dev/
- **Source:** Anthropic, "Writing effective tools for agents" (11 Sep 2025), https://www.anthropic.com/engineering/writing-tools-for-agents. Also "Introducing advanced tool use" (24 Nov 2025), https://www.anthropic.com/engineering/advanced-tool-use

### 6. Retrieval and RAG
- **Backend analogue:** a search index (Elasticsearch or OpenSearch) fed by an ETL or CDC pipeline. Access-controlled retrieval is row-level security applied to search.
- **New problem:**
  - The model doesn't know your private or recent data, and it hallucinates when it lacks facts.
  - Relevance is now semantic, not keyword.
  - Retrieved text is untrusted input. OWASP LLM08:2025 covers vector and embedding weaknesses.
- **Pipeline:**
  1. **Ingest:** parse, clean, run CDC.
  2. **Chunk:** by structure or semantics, with overlap.
  3. **Embed:** pick a model using the MTEB leaderboard, https://huggingface.co/spaces/mteb/leaderboard.
  4. **Hybrid search:** BM25 plus vectors, with results fused.
  5. **Query rewriting.**
  6. **Rerank:** a cross-encoder over the top K results.
  7. **Access control:** filter by the caller's entitlements *at query time*, through metadata filters, never after generation.
  8. **Cite sources.**
- **Minimal:** pgvector in your existing Postgres, fixed-size chunks, top-K cosine, chunks pasted into the prompt.
- **Mature:**
  - Contextual chunking. Anthropic measured that adding context to each chunk, BM25 and reranking cut retrieval failures from 5.7% to 1.9% (a 67% reduction).
  - Retrieval-specific evals (recall@k).
  - Freshness SLAs and re-embedding on model change.
- **Tools:**
  - pgvector: https://github.com/pgvector/pgvector
  - Qdrant: https://qdrant.tech/documentation/
  - Elastic hybrid search: https://www.elastic.co/docs/solutions/search/hybrid-semantic-text
  - Cohere Rerank: https://docs.cohere.com/docs/rerank-overview
  - Spring AI RAG: https://docs.spring.io/spring-ai/reference/api/retrieval-augmented-generation.html
  - LlamaIndex: https://github.com/run-llama/llama_index
- **Source:** Fowler/Subramaniam, which covers RAG, Embeddings, Hybrid Retriever, Query Rewriting and Reranker. Anthropic "Contextual Retrieval" (19 Sep 2024): https://www.anthropic.com/news/contextual-retrieval

### 7. Memory
- **Backend analogue:**
  - Short-term memory is HTTP session state.
  - Long-term memory is a per-user profile store or CRM record, written by a background job.
- **New problem:**
  - The model is stateless, and each call has to be handed the history.
  - Users expect it to "remember" across sessions.
  - Memory can be poisoned (OWASP Agentic ASI06 "Memory & Context Poisoning"; the name comes from a secondary source).
- **Minimal:** conversation history in a DB keyed by conversation ID, with a sliding window or summary.
- **Mature:**
  - Extracted facts stored in a vector or graph store, with scoping per user or tenant.
  - Time to live and right-to-erasure.
  - An agent-managed memory file through a memory tool.
  - Writes reviewed or validated before reuse.
- **Tools:**
  - Spring AI chat memory: https://docs.spring.io/spring-ai/reference/api/chat-memory.html
  - Claude memory tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
  - Mem0 (OSS): https://github.com/mem0ai/mem0
  - Letta (OSS): https://github.com/letta-ai/letta
  - Zep: https://www.getzep.com/
- **Source:** Anthropic's context engineering post (structured note-taking) and the LangGraph memory concepts page, https://langchain-ai.github.io/langgraph/concepts/memory/

### 8. Agent loop and orchestration patterns
- **Backend analogue:**
  - A **workflow** is a saga or orchestrator: predefined code paths.
  - An **agent** is a while-loop where the model picks the next step from what its tools return.
  - Durable execution (Temporal) is your outbox and saga machinery applied to LLM steps.
- **New problem:** each step is non-deterministic, slow and costly. Long runs need checkpoints, retries that don't repeat side effects, and step budgets.
- **Anthropic's taxonomy** (19 Dec 2024):
  - **The building block is the augmented LLM:** a model with retrieval, tools and memory attached.
  - **Prompt chaining:** sequential steps, with programmatic gates between them.
  - **Routing:** classify the input, then dispatch it to a specialised handler.
  - **Parallelization:** either sectioning (split into independent parts) or voting (run the same task several times).
  - **Orchestrator-workers:** a central LLM splits the task dynamically and gives parts to workers.
  - **Evaluator-optimizer:** generate, critique, loop.
  - **Agents:** tools in a loop, driven by what the environment returns, pausing at checkpoints for a human.
  - **The advice:** start with the simplest option, and add agency only when it measurably helps.
- **Minimal:** a plain-code chain or router, in a service method.
- **Mature:**
  - A graph or agent framework with state checkpoints.
  - Durable execution for long runs.
  - Sub-agents for parallel research.
  - Step, token and time budgets as kill switches.
- **Tools:**
  - LangGraph: https://github.com/langchain-ai/langgraph
  - OpenAI Agents SDK: https://openai.github.io/openai-agents-python/
  - Claude Agent SDK: https://platform.claude.com/docs/en/agent-sdk/overview
  - Google ADK: https://github.com/google/adk-python
  - Temporal for AI: https://temporal.io/solutions/ai
- **Source:** Anthropic, "Building effective agents", https://www.anthropic.com/engineering/building-effective-agents. Also "How we built our multi-agent research system", https://www.anthropic.com/engineering/multi-agent-research-system

### 9. Human in the loop
- **Backend analogue:** a maker-checker or four-eyes approval step, a workflow task queue, or a manual-review state in a state machine.
- **New problem:**
  - Model actions can be wrong with full confidence.
  - Irreversible writes (payments, emails, deletes) need consent.
  - Regulators expect accountable humans.
  - OWASP Agentic ASI09 "Human-Agent Trust Exploitation" (name from a secondary source) adds the risk of rubber-stamping.
- **Minimal:** the agent proposes, a human clicks approve, and only then does code execute the write.
- **Mature:**
  - The graph pauses and resumes, with persisted state.
  - Approval policies are set by risk tier.
  - Edit-before-approve.
  - Reviewer decisions are captured as eval labels.
  - The MCP spec requires the host to get user consent before a tool runs.
- **Tools:**
  - LangGraph interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
  - Temporal signals, via https://temporal.io/solutions/ai
  - OpenAI Agents SDK
  - Claude Code permission modes
- **Source:** Anthropic "Building effective agents" (agents pause for human feedback at checkpoints) and the MCP spec's "User Consent and Control" section.

### 10. Guardrails and LLM security
- **Backend analogue:** input validation plus a WAF plus output encoding plus DLP. Here the "SQL injection" arrives as natural language and can't be escaped.
- **New problem:**
  - Prompt injection, both direct and *indirect* (through retrieved documents, emails or tool output).
  - Jailbreaks, system-prompt leakage, PII leakage, toxic output.
  - Exfiltration. Simon Willison's **"lethal trifecta"** (16 Jun 2025): private data, plus untrusted content, plus an outbound channel, adds up to data theft. https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- **Minimal:**
  - PII redaction on input.
  - An injection or moderation classifier.
  - Model output never executed or rendered unescaped.
  - Least-privilege tools.
  - No markdown image auto-loading, which is a common exfiltration channel.
- **Mature:**
  - Layered input and output rails, including topical rails.
  - Architectural isolation: break the trifecta, and treat tool output as tainted.
  - Per-user scoped credentials for tools.
  - Continuous red-teaming (promptfoo).
- **OWASP Top 10 for LLM Applications, 2025 edition** (current). The ten entries:
  1. LLM01 Prompt Injection
  2. LLM02 Sensitive Information Disclosure
  3. LLM03 Supply Chain
  4. LLM04 Data and Model Poisoning
  5. LLM05 Improper Output Handling
  6. LLM06 Excessive Agency
  7. LLM07 System Prompt Leakage
  8. LLM08 Vector and Embedding Weaknesses
  9. LLM09 Misinformation
  10. LLM10 Unbounded Consumption

  Link: https://genai.owasp.org/llm-top-10/
- **OWASP Top 10 for Agentic Applications 2026** (released 9 Dec 2025): https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
  - The official page only links a download. The ten names below come from a secondary source (https://docs.modulos.ai/frameworks/owasp-top-10-agentic), not from the OWASP text.
  - ASI01 Agent Goal Hijack
  - ASI02 Tool Misuse
  - ASI03 Identity & Privilege Abuse
  - ASI04 Agentic Supply Chain Vulnerabilities
  - ASI05 Unexpected Code Execution
  - ASI06 Memory & Context Poisoning
  - ASI07 Insecure Inter-Agent Communication
  - ASI08 Cascading Failures
  - ASI09 Human-Agent Trust Exploitation
  - ASI10 Rogue Agents
- **Tools:**
  - NVIDIA NeMo Guardrails (OSS): https://github.com/NVIDIA-NeMo/Guardrails
  - Guardrails AI (OSS): https://github.com/guardrails-ai/guardrails
  - Presidio for PII: https://github.com/microsoft/presidio. It now redirects to `github.com/data-privacy-stack/presidio`.
  - Llama Guard 4: https://www.llama.com/docs/model-cards-and-prompt-formats/llama-guard-4/
  - Hosted options:
    - Lakera: https://www.lakera.ai/
    - AWS Bedrock Guardrails: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html
    - Azure AI Content Safety: https://learn.microsoft.com/en-us/azure/ai-services/content-safety/overview
  - LangChain4j guardrails, for Java: https://docs.langchain4j.dev/tutorials/guardrails
- **Source:** the OWASP lists above, plus the OWASP LLM Prompt Injection Prevention Cheat Sheet, https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html

### 11. Evals
- **Backend analogue:** a test suite whose result is a score and a pass rate, not green or red. Regression evals are your regression suite, and online evals are synthetic monitoring or canary analysis.
- **New problem:**
  - Output is non-deterministic and open-ended, so `assertEquals` doesn't work.
  - Every prompt or model change can silently regress something.
- **Minimal:**
  - Read about 30 to 100 real traces by hand.
  - Group the failures into a taxonomy (error analysis).
  - Write binary pass/fail checks: code assertions first, LLM-as-judge only for subjective criteria.
  - Run 50 to 200 cases in CI on every prompt or model change.
- **Mature:**
  - Golden datasets drawn from production traces.
  - **LLM judges validated against human labels**: measure true positive and true negative rates, with one judge per failure mode.
  - Capability evals (low pass rate, a target to climb) versus regression evals (near 100%, a CI gate).
  - **pass@k** (at least one success in k tries) versus **pass^k** (all k succeed). For example, 75% per trial gives about 42% for three in a row.
  - Online evals on sampled production traffic.
  - Error analysis repeated every 2 to 4 weeks.
- **Tools:**
  - promptfoo (OSS, CI-friendly): https://github.com/promptfoo/promptfoo
  - Braintrust: https://www.braintrust.dev/docs
  - LangSmith: https://docs.smith.langchain.com/
  - Langfuse: https://github.com/langfuse/langfuse
  - Arize Phoenix: https://github.com/Arize-ai/phoenix
  - Spring AI evaluation: https://docs.spring.io/spring-ai/reference/api/testing.html
- **Source:**
  - Hamel Husain and Shreya Shankar, "AI Evals: Everything You Need to Know" (updated Sep 2026): https://hamel.dev/blog/posts/evals-faq/
  - Anthropic, "Demystifying evals for AI agents" (9 Jan 2026): https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
  - OpenAI evaluation best practices: https://developers.openai.com/api/docs/guides/evaluation-best-practices
  - Eugene Yan, "LLM evaluators": https://eugeneyan.com/writing/llm-evaluators/

### 12. Observability: traces, cost, latency, drift
- **Backend analogue:** distributed tracing (OTel, Jaeger) plus APM plus a billing meter, with the span payload being prompt and completion.
- **New problem:**
  - You debug by reading what the model saw and said, not stack traces.
  - Every span carries a cost in tokens.
  - Quality drifts as provider models update, user inputs change or the corpus goes stale.
  - Traces contain PII.
- **Minimal:** log the model, prompt version, input and output tokens, latency, cost, trace ID and tool calls for every call. Sample full payloads, with redaction.
- **Mature:**
  - Spans follow the **OpenTelemetry GenAI semantic conventions**: client inference, model and agent spans, token and duration metrics, input and output events, MCP, and provider-specific pages (Anthropic, OpenAI, Bedrock, Azure).
  - The conventions are **status "Development"**, not stable. They moved in 2026 to their own repo.
  - Dashboards per prompt version and model.
  - Online eval scores on traces.
  - User feedback attached to traces.
  - Drift alerts on score distributions.
- **Tools:**
  - Langfuse (OSS): https://github.com/langfuse/langfuse
  - Arize Phoenix (OSS): https://github.com/Arize-ai/phoenix
  - OpenLLMetry (OSS, built on OTel): https://github.com/traceloop/openllmetry
  - Datadog LLM Observability: https://docs.datadoghq.com/llm_observability/
  - Helicone: https://github.com/Helicone/helicone
  - Spring AI observability, built on Micrometer: https://docs.spring.io/spring-ai/reference/observability/index.html
- **Source:** OTel GenAI semantic conventions, https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/README.md. The old `opentelemetry.io/docs/specs/semconv/gen-ai/` pages now just say "Moved".

### 13. Caching
- **Backend analogue:**
  - Prompt caching is like a server-side compiled-statement cache: the provider reuses work on an identical prefix.
  - Exact caching is an HTTP or Redis response cache.
  - Semantic caching is a cache keyed by embedding similarity, which can return a *wrong* hit.
- **New problem:** long, repeated prefixes (system prompt, tool definitions, documents) are paid for on every call, and calls are slow.
- **Prompt caching facts** (Anthropic docs, current):
  - Matching is on exact prefix, in the order tools, then system, then messages.
  - Lifetime is 5 minutes by default, or 1 hour at extra cost.
  - Writes cost 1.25x the input price (5-minute) or 2x (1-hour). Reads cost 0.1x, or 0.05x on Opus and Sonnet 5.5.
  - The minimum cacheable prefix is 512 to 4096 tokens depending on the model.
  - Architectural rule: put the stable content first and the variable content last.
- **Minimal:** turn on provider prompt caching, and keep the system prompt and tool definitions byte-stable.
- **Mature:**
  - Prefix-stable context design.
  - Exact-match cache at the gateway.
  - Semantic cache scoped per tenant or permission, with a similarity threshold tuned by evals.
- **Semantic-cache risk:** serving a hit across users can leak data and can return a confidently wrong answer. This is my reading, not taken from a fetched source.
- **Tools:**
  - Anthropic prompt caching: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
  - OpenAI prompt caching: https://developers.openai.com/api/docs/guides/prompt-caching
  - Redis LangCache (managed semantic cache): https://redis.io/langcache/
  - GPTCache (OSS): https://github.com/zilliztech/GPTCache
  - LiteLLM caching: https://docs.litellm.ai/docs/proxy/caching
- **Source:** the Anthropic prompt caching docs above, plus Chip Huyen step 4.

### 14. Sandboxing for code-executing agents
- **Backend analogue:** running untrusted user code: containers plus seccomp, gVisor or Firecracker microVMs, and egress firewalls.
- **New problem:**
  - Agents write and run code and shell commands, and a prompt-injected agent becomes an attacker inside your network.
  - OWASP Agentic ASI05 "Unexpected Code Execution" (name from a secondary source).
- **Minimal:**
  - An ephemeral container with no credentials.
  - Read-only mounts except a work directory.
  - No network, or an allow-listed proxy.
  - CPU, memory and time limits.
- **Mature:**
  - MicroVM per session.
  - **Both** filesystem and network isolation. Anthropic says either one alone fails: without network isolation, SSH keys leak; without filesystem isolation, the sandbox can be escaped.
  - A domain-allowlist proxy.
  - Credentials injected outside the sandbox.
  - Snapshots for long-running agents.
- **Tools:**
  - E2B (OSS and hosted): https://github.com/e2b-dev/E2B
  - Daytona: https://www.daytona.io/docs
  - Modal Sandboxes: https://modal.com/docs/guide/sandboxes
  - Anthropic sandbox-runtime (OSS, bubblewrap and seatbelt): https://github.com/anthropic-experimental/sandbox-runtime. It now redirects to `github.com/anthropics/sandbox-runtime`.
  - gVisor: https://gvisor.dev/
  - Firecracker: https://firecracker-microvm.github.io/
- **Source:** Anthropic, "Beyond permission prompts: making Claude Code more secure and autonomous" (20 Oct 2025), https://www.anthropic.com/engineering/claude-code-sandboxing

### 15. Governance and model risk in regulated settings
- **Backend analogue:** SOX or ISO audit trails, change-advisory boards, data-processing agreements, vendor risk management, and model validation as banks already do it for statistical models.
- **New problem:**
  - A third-party model you can't inspect changes underneath you.
  - Outputs can't be fully explained.
  - Prompts and outputs carry client data across borders.
  - Accountability is unclear when an agent acts.
- **Minimal:**
  - An inventory of every AI use case, with a risk class.
  - Immutable audit log of prompt version, model version, inputs, outputs and approver.
  - Data residency and zero-retention terms with the provider.
  - Human sign-off for high-risk uses.
- **Mature:**
  - A risk framework mapped to NIST AI RMF and its GenAI profile (NIST AI 600-1).
  - Documented evals as validation evidence, plus ongoing monitoring.
  - Independent review.
  - Third-party (provider) risk management.
  - EU AI Act classification.
  - ISO/IEC 42001 management system.
- **Regulators:**
  - **FINMA Guidance 08/2024** (18 Dec 2024), the relevant one for a Swiss firm. It names these risks: model risk (robustness, correctness, explainability, bias), data risk, IT and cyber risk, third-party dependencies, and legal and reputational risk. https://www.finma.ch/en/news/2024/12/20241218-mm-finma-am-08-24/. The seven assessment areas (governance, inventory and risk classification, data quality, tests and monitoring, documentation, explainability, independent review) come from secondary sources; the official PDF did not parse.
  - **US: SR 26-2** (17 Apr 2026) replaces SR 11-7 and SR 21-8; the old SR 11-7 URL now returns 404. https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm. Whether it covers generative or agentic AI is **unverified**: commentators disagree, and I didn't read the attachment.
- **Tools:**
  - Gateway plus tracing stack as the audit trail (LiteLLM spend logs, Langfuse).
  - Provider regional or zero-retention endpoints, such as Bedrock and Azure.
  - Governance registries: the Modulos reference is a vendor's page.
- **Source:** NIST AI 600-1 GenAI Profile (26 Jul 2024), https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence. Also the NIST AI RMF hub, https://www.nist.gov/itl/ai-risk-management-framework, and the EU AI Act, https://artificialintelligenceact.eu/

### 16. Feedback loop, data flywheel and defensive UX (added: practitioners treat it as standard)
- **Backend analogue:** product analytics plus a dead-letter queue that becomes test fixtures.
- **New problem:** the system improves only if production failures come back into eval sets and prompts.
- **Minimal:** thumbs up or down, plus "edit before send", logged against the trace ID.
- **Mature:**
  - Implicit signals (accepted, edited or retried).
  - Failures triaged into eval datasets.
  - UX that sets expectations: citations, confidence, an easy undo.
- **Source:** Eugene Yan's "Defensive UX" and "Collect user feedback" patterns, https://eugeneyan.com/writing/llm-patterns/

**Fine-tuning** is the remaining Fowler pattern. Practitioners treat it as a late optimisation after RAG and prompting, so it isn't a request-path block.

---

## How they fit together in one request

A user request, following Chip Huyen's ordering, with each step mapped to Spring terms:

1. **Edge and controller.** Normal auth. The tenant and entitlements are resolved here and **carried downstream**, because retrieval and tools must enforce them.
2. **Input guardrails.** This acts as a filter or advisor: PII redaction, an injection or moderation classifier, topical scope. It can short-circuit to a canned reply.
3. **Cache check.** An exact or semantic cache, scoped per tenant. A hit returns immediately.
4. **Router.** A cheap classifier picks the workflow (or agent) and the model tier.
5. **Context assembly.** This is the context engineering step:
   - Fetch the system prompt from the **prompt registry**, and record its version.
   - Load **memory** (session history and user facts).
   - Run **retrieval**: query rewrite, hybrid search with the ACL filter, then rerank.
   - Attach tool definitions (local or **MCP**).
   - Order everything stable-first so **prompt caching** hits, and keep it inside the token budget.
6. **Gateway, then model.** The gateway applies the virtual key, budget and rate limit, then fallback and retry, then sends the call to the provider. Use structured output or strict tool schemas.
7. **Agent or workflow loop.** If the model asks for tools:
   - Validate the arguments.
   - Run the tool with the user's scoped credentials. Code goes to the **sandbox**.
   - Writes go through **human-in-the-loop** approval.
   - Results go back into the context, are compacted if needed, and the model is called again.
   - The loop stops at a step, cost or time budget.
   - Long runs are checkpointed in durable execution: the outbox and saga mindset.
8. **Output handling.** Schema validation, then output guardrails (PII, policy, groundedness or citation check). Escape before rendering, never execute, and never auto-load URLs.
9. **Response, plus memory write-back.** Write memory asynchronously, through a queue.
10. **Across every step:**
    - **Tracing** with OTel GenAI spans per model, tool and agent step, carrying tokens, cost, prompt version and model version. This trace is also the **audit log** for governance.
    - **Online evals** score sampled traces asynchronously.
    - **User feedback** attaches to the trace ID.
    - Failures flow into **offline eval datasets**, which gate the next prompt or model change in **CI**.

---

## Five best sources for a newcomer, ranked

1. **Anthropic, "Building effective agents"** (Dec 2024). It is the shared vocabulary: augmented LLM, the five workflow patterns, and workflow versus agent. https://www.anthropic.com/engineering/building-effective-agents
2. **Chip Huyen, "Building A Generative AI Platform"** (Jul 2024). It is the only one that is a system architecture diagram you can map onto a backend, built up component by component. https://huyenchip.com/2024/07/25/genai-platform.html
3. **Subramaniam and Fowler, "Emerging Patterns in Building GenAI Products"** (Feb 2025). It has the clearest pattern-language treatment of evals, guardrails and the RAG pipeline, in a style you already know. https://martinfowler.com/articles/gen-ai-patterns/
4. **Husain and Shankar, "AI Evals: Everything You Need to Know"** (updated Sep 2026). It covers how to actually test these systems. https://hamel.dev/blog/posts/evals-faq/
5. **Anthropic, "Effective context engineering for AI agents"** (Sep 2025). It covers what goes into the window and why: compaction, memory, sub-agents, just-in-time retrieval. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

Read the OWASP LLM Top 10 2025 (https://genai.owasp.org/llm-top-10/) before shipping anything with tools.

---

## Unverified or caveated
- **OWASP Agentic Top 10 entry names:** taken from a secondary source; the official page only links a download.
- **FINMA's seven assessment areas:** from secondary sources; the official PDF didn't parse.
- **SR 26-2 coverage of generative or agentic AI:** unverified; I didn't read the attachment and commentators disagree.
- **Hamel's CI/CD guidance:** I didn't read that part of the FAQ, because the page was truncated.
- **Links that return 403 to automated requests (not cited above):**
  - ISO 42001: https://www.iso.org/standard/42001
  - Chip Huyen's book *AI Engineering* (O'Reilly): https://www.oreilly.com/library/view/ai-engineering/9781098166298/
- **Link that resolved but I didn't read:** applied-llms.org, "What We've Learned From a Year of Building with LLMs".
- **Not cited:** the OpenSearch vector-search link was broken (it redirects to a 404), and `aigateway.envoyproxy.io` redirects to an unrelated domain.
- **Mine, not from a fetched source:** the backend analogues and the semantic-cache leakage risk.

No files were edited.