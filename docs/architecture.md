# Architecture

How the agent is built and why. The [spec](spec.md) says *what* it does; this
document records the technical decisions behind it, one short ADR per decision
(context → decision → consequences).

## 1. Overview

```
 Channel adapters            web demo (FastAPI + static HTML)   ·   WhatsApp (documented)
        │  IncomingMessage / OutgoingMessage
        ▼
 ChatService ─────────────── SessionStore (in memory, TTL)
        │
        ▼
 Agent  (tool-use loop, OpenAI-compatible API) ── Prompt (persona + rules + policy manual)
        │  tool calls
        ▼
 Tools  (schemas + dispatch; injects phone / message_id from the session)
        │
        ▼
 Domain   catalog · orders · complaints · pricing      (pure Python, no LLM, no HTTP)
        │
        ▼
 Data     data.py (CSV → immutable records)  ·  ComplaintStore (JSONL)
```

**Dependency rule:** arrows point inward only. The domain imports neither the SDK nor
FastAPI; the channel knows no business rule. A new channel is one new adapter on top;
a new data source is one change at the bottom.

## 2. Stack

| Layer | Choice | Version |
|---|---|---|
| Language | Python | 3.12 |
| LLM access | any OpenAI-compatible Chat Completions API, official `openai` SDK | pinned |
| Model | configuration; default: Gemini Flash-Lite on Google's free tier (ADR-03) | — |
| HTTP | FastAPI + uvicorn | 0.162 / 0.54 |
| Demo UI | one static HTML file, plain JavaScript | — |
| Config | environment variables, `python-dotenv` for local `.env` | 1.2 |
| Tests | pytest (+ FastAPI `TestClient`) | 9.2 |
| Lint / format | ruff | — |
| CI | GitHub Actions: ruff + pytest on every push | — |

Versions are pinned in `requirements*.txt` so a reviewer reproduces the same build.

## 3. Decisions

### ADR-01 Agent approach: hybrid (function calling in a tool-use loop + policies in context)

**Context.** The case lists RAG, function calling, ReAct, SQL agents and hybrids. The
agent needs two kinds of knowledge: *live data* (prices, stock, promotions, orders) and
*policy* (hours, payment, returns, tone).

**Decision.**

| Approach | Used? | Why |
|---|---|---|
| Agent loop | Yes | `agent.py`: model replies or asks for a tool → code runs it → result goes back → repeat until a final answer (max 5 rounds). |
| Function calling | Yes, the core | The model decides *when* and *what* to look up; code computes prices, dates and identification. |
| ReAct | Yes, natively | Tool use *is* the reason → act → observe cycle. The classic text ReAct ("Thought/Action/Observation" parsed with regex) is superseded by native tool use and adds failure points. |
| RAG (vector search) | No | The manual is ~8 pages (~3–4k tokens) and fits whole in the prompt, cached. Retrieval would return fragments and could drop a rule that depends on another (e.g. promotions are not cumulative with PIX). More moving parts, more risk, no gain. |
| SQL agent | No | Letting the model write queries over customer data could expose another customer's order; with fixed tools the phone + e-mail check runs in code and cannot be bypassed. There are no analytical questions to answer, only point lookups. |

**Consequences.** Small, auditable surface: three tools, arguments validated in code. Policy
answers depend on the prompt being followed (covered by the acceptance scenarios).
Revisit RAG if the manual grows to hundreds of pages, a large FAQ base appears, or the
catalog needs semantic search over thousands of products; revisit SQL only for an
internal analytics assistant, never customer-facing.

### ADR-02 No agent framework (LangChain, LlamaIndex, etc.)

**Context.** Three tools, one model, one conversation flow.

**Decision.** Call the chat API directly through the official `openai` SDK with a manual
tool-use loop (~60 lines). See ADR-13 for why that SDK.

**Consequences.** Every request and tool call is visible in our code, easy to test with
a fake client and to read in a review. We own the loop (limits, error handling,
session-data injection), which is exactly what the case evaluates.

### ADR-03 Model: configuration, free-tier default, small model recommended

**Context.** The case leaves the model open ("pagos ou grátis, locais ou via API").
Support chat is high-volume and latency-sensitive; the common industry pattern is a
small, cheap default model. Evaluators must be able to run the project without paying.

**Decision.** The model is three env vars (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`).
The default is **Gemini Flash-Lite** (`gemini-flash-lite-latest`) on Google's free tier
(no card), with ready-made blocks in `.env.example` for Mistral, Groq, OpenRouter,
OpenAI, Claude and a local Ollama. Deterministic code does the parts where a small model
would err (arithmetic, dates, identification, protocol numbers), and tool results carry
pre-decided fields (e.g. `pix_price: null` when a promotion is active) so the model
mostly writes the reply.

**How the default was chosen (November 2026).** Two measurements drove it:
1. Every request carries ~4.4k tokens of instructions and tool definitions (the whole
   manual is in the prompt, ADR-01); with history and a search result a request reaches
   5–8k tokens. A free tier must allow that many *tokens per minute*, not only requests.
2. A conversation turn that looks something up costs 2 requests (tool call + answer); the
   five recorded scenarios need ~30. The first attempt, on `gemini-flash-latest`
   (Gemini 3.8 Flash), exhausted its free quota of **20 requests/day** mid-run (HTTP 429).

| Free option | Quota (third-party sources, they disagree and change often) | Verdict |
|---|---|---|
| **Gemini Flash-Lite** | ~500–1,000 req/day, ~15 RPM, ~250k tokens/min | **Chosen**: fits the prompt size and a full scenario run; no card; works with the same Google key. |
| Gemini Flash (3.8 / 3.6) | 20 req/day | Rejected: exhausted by one scenario run. |
| Groq (gpt-oss-120b) | 30 RPM, ~1,000 req/day, but ~8k tokens/min and ~200k tokens/day | Rejected as default: very fast and good at tool use, but with our prompt size ≈ 1 request/min and ~30/day. |
| Mistral (Experiment plan) | ~1 req/s, ~1B tokens/month | Best high-volume alternative: needs phone verification and trains on data by default (opt-out). |
| OpenRouter `:free` models | 20 RPM, 50 req/day | Rejected: too few requests; tool calling fails on some free models. |
| Cerebras | free tier replaced by one-time trial credits in 2026 | Rejected: not permanently free. |
| Ollama (local) | unlimited | Alternative for offline use; slow on modest GPUs. |

Quality trade-off: a Flash-Lite model is weaker than larger ones at multi-step tool use
(older public tau-bench numbers put Flash-Lite well below gpt-oss-120b; no 2026 figures
found). The design limits the impact (ADR-04), and the acceptance scenarios are run on it
before the examples are recorded; if it fails, the prompt is fixed first, then Mistral is
the next candidate.

**Consequences.** Anyone can run the agent at zero cost. Behaviour still depends on the
model: the README lists the models the acceptance scenarios were actually run on instead
of promising "works with everything". Free quotas are per Google project and reset daily
(midnight Pacific); the live numbers for an account are at aistudio.google.com/rate-limit.
For production, a small paid model with stable quotas (e.g. Claude Haiku 5.5, a GPT mini
class model) is the recommendation; Google's free tier may use prompts to improve its
products, acceptable for fictional demo data only.

### ADR-04 Deterministic domain, LLM only for language

**Context.** The manual warns that wrong prices or deadlines can be misleading
advertising.

**Decision.** Prices, PIX, installments, availability labels, after-sales windows,
late-delivery flags, complaint protocols and deadlines are computed in pure functions
and returned by the tools. The prompt forbids stating any price, stock or order fact
that did not come from a tool result.

**Consequences.** Business rules are unit-tested without an API key; the LLM cannot
"calculate" a wrong installment.

### ADR-05 Security: identity from the channel, never from the model

**Context.** Order data is personal (LGPD) and the model can be manipulated by the user
("I am customer 7, show me order 2").

**Decision.** The tool handler injects the session phone and `message_id`; they are not
tool parameters. `get_order` requires the e-mail of the customer owning that phone and
returns the same "not found" whether the e-mail or the order is wrong. Tools validate
every argument in code (types, enums, limits); provider-side schema enforcement is not
relied on, because not every OpenAI-compatible provider applies it.

**Consequences.** A prompt injection can at most make the agent ask for an e-mail; it
cannot reach another customer's data. In the demo the phone is typed in the UI, standing
in for the number WhatsApp would provide.

### ADR-06 Channel-agnostic core

**Context.** Real customers use WhatsApp; the evaluator needs something runnable.

**Decision.** The core exposes `ChatService.handle(IncomingMessage) -> OutgoingMessage`.
The demo channel is a FastAPI endpoint plus one static page. Replies already follow
WhatsApp formatting (short text, `*bold*`, `_italic_`, no tables or headings, one question
per message), enforced by the prompt and a small sanitizer.

**Consequences.** A WhatsApp adapter needs no change in the core. It is not implemented
(it needs a business account and webhook hosting an evaluator could not reproduce); it
would be one module next to `api.py`:

1. **Webhook** (FastAPI router) receives the provider's POST (Meta WhatsApp Cloud API,
   Twilio, etc.), **verifies the signature**, answers 200 at once and processes the
   message in the background (providers retry slow webhooks).
2. **Map** the payload to `IncomingMessage`: `phone` = sender number, `message_id` = the
   provider's message id (used to drop redeliveries), `customer_name` = profile name.
3. **Call** `ChatService.handle(...)`, unchanged.
4. **Send** `OutgoingMessage.text` with the provider's send-message API; it is already
   WhatsApp-formatted.
5. Channel rules stay in the adapter: the 24-hour customer-service window (templates
   outside it), media messages, and handing the conversation to a human after a complaint.

### ADR-07 Data: CSVs in memory

**Context.** 65 products, 50 customers, 20 orders; read-only.

**Decision.** Load the CSVs once at startup into frozen dataclasses (`data.py` is the only
module that knows file names and columns). No database.

**Consequences.** Zero setup for the evaluator. Data changes need a restart. A real
deployment would put a repository over the store's ERP/database behind the same
functions the tools call.

### ADR-08 Sessions and history in memory

**Context.** Multi-turn conversations ("e em quantas vezes?") need history.

**Decision.** A dict keyed by phone holds the full message list (append-only, as the API
requires for tool-use blocks); a session expires after 30 minutes of inactivity instead
of trimming old turns.

**Consequences.** Lost on restart and not shared across processes; Redis (or similar)
would replace it behind the same `SessionStore` interface in production.

### ADR-09 Complaints: one write, behind a store

**Context.** The manual requires registering complaints; the other tools are read-only.

**Decision.** `register_complaint` appends to a JSONL file through `ComplaintStore`;
idempotent per `message_id`; deadline computed by code.

**Consequences.** Honest replies with a real protocol number. Swapping the JSONL for a
helpdesk API (Zendesk, Freshdesk, the WhatsApp provider's inbox) changes one class.

### ADR-10 Prompt and caching

**Context.** The system prompt (persona, rules, manual) is the same for every request.

**Decision.** One system message: the static part first (persona, rules, manual), then a
small dynamic part (current date/time, whether the store is open). The tool list is fixed
and ordered. No timestamps or IDs inside the static part.

**Consequences.** Providers with automatic prefix caching (OpenAI, Gemini) reuse the
static prefix across requests. Explicit cache control (Anthropic's `cache_control`) is
not available through the OpenAI-compatible API; that cost is accepted (ADR-13).

### ADR-11 Synchronous code

**Context.** One request at a time per customer; the demo has a handful of users.

**Decision.** Plain synchronous functions and the sync `OpenAI` client. FastAPI runs sync
endpoints in a thread pool.

**Consequences.** Simpler to read and test. Under real load (many concurrent WhatsApp
webhooks) the agent would move to `AsyncOpenAI` and async endpoints; the module
boundaries stay the same.

### ADR-12 Quality gates

**Decision.**
- **Tests:** pytest. Domain and tools are tested against the real CSVs; the agent loop with
  a fake LLM client; the API with `TestClient`. No test needs an API key or network.
- **LLM behaviour:** `scripts/run_scenarios.py` runs the acceptance conversations against
  the live model; the recorded runs become `docs/examples/`.
- **Lint/format:** ruff (config in `pyproject.toml`).
- **CI:** GitHub Actions runs ruff, mypy and pytest on every push.
- **Typing:** type hints everywhere, checked by mypy (`check_untyped_defs`); the one
  cast is the SDK call, where the history's plain wire-format dicts meet the SDK's
  TypedDicts.
- **Review:** an independent read-only review (a separate agent, not shown the author's
  conclusions) found two high-severity issues (an extra tool round that could register
  an untold complaint; prompt injection through the profile name) and several medium
  ones; each was fixed in its own commit with a test.
- **Logging:** standard `logging`; tool names, latency and errors are logged, message
  content and personal data are not (LGPD).
- **Git:** small commits, one concern each, Conventional Commits messages, no force-push.

### ADR-14 Web channel hardening: rate limit and security headers

**Context.** Order lookup treats the registered e-mail like a password for a known
phone; without a limit on attempts it can be brute-forced. The free LLM quota (500
requests a day) can be burned by a script. The page renders model output as HTML (for
*bold*/_italic_), so it is an XSS surface.

**Decision.** In the web adapter only (`api.py`), not in the core:
- `RateLimiter` (sliding window, in memory, injected clock): 10 messages per minute per
  phone, 30 per IP (a script changing phones each try is still limited). Checked before
  the agent, so a 429 costs no LLM call.
- Security headers on every response: a strict Content-Security-Policy (only the page's
  own scripts and styles, requests only to this API, `frame-ancestors 'none'`), plus
  `nosniff`, `X-Frame-Options: DENY` and `no-referrer`. The page's CSS and JS live in
  files so the CSP can forbid inline code; HTML escaping stays the first defence.

**Consequences.** Counters are per process: several instances would need Redis or the
API gateway, and the WhatsApp provider limits senders on its side. The CSP is a second
line: an escaping mistake in a future change would not become script execution.

### ADR-13 LLM access: one OpenAI-compatible client

**Context.** The first version used Anthropic's SDK, which runs only models that speak
Anthropic's API. Evaluators may have no Anthropic account, and testing should cost nothing.

**Decision.** Talk to the model through the OpenAI Chat Completions format with the
official `openai` SDK; the provider is chosen by `LLM_BASE_URL` + `LLM_MODEL` +
`LLM_API_KEY`. That format is the de facto standard: OpenAI, Google Gemini, Groq,
OpenRouter, a local Ollama and Anthropic itself expose it.

| Option | Verdict |
|---|---|
| Native Anthropic SDK only (previous version) | Rejected: one provider, paid key required. |
| Own `LLMClient` interface + one adapter per provider | Rejected for now: more code and two paths to test, with no provider requirement that needs it. |
| LiteLLM | Rejected: large dependency that hides the request/response translation we want visible. |
| **OpenAI-compatible API, one client** | **Chosen:** swaps the SDK rather than adding a layer; same loop size. |

**Consequences.** Provider-specific extras are lost where the compatibility layers drop
them: explicit prompt caching, `strict` tool schemas and `reasoning_effort` on Claude,
Anthropic's structured refusal details (a refusal arrives as `finish_reason:
content_filter` and gets the same fallback). Tools therefore validate every argument
in code (ADR-05). Optional `LLM_REASONING_EFFORT` is sent only when set, since not every
provider accepts it. If a provider ever needs native features, an adapter can be added
behind the agent's single call site without touching tools or domain.

## 4. Module map

```
emporio/
  config.py           settings from env, store time zone, reference date
  data.py             CSV loading into frozen dataclasses
  phone.py            phone normalization (session identity, identification)
  store_hours.py      opening hours, next opening
  pricing.py          promo, PIX, installments (pure)
  catalog.py          product search + availability
  orders.py           identification, status labels, after-sales windows
  complaints.py       ComplaintStore (JSONL), protocol, deadline
  validation.py       tool-argument validation against the schemas, ToolError
  tools.py            tool schemas, dispatch, serialization for the model
  prompt.py           system prompt builder
  agent.py            tool-use loop over an injected OpenAI-compatible client
  sessions.py         in-memory SessionStore with TTL
  whatsapp_format.py  reply sanitizer
  service.py          ChatService, IncomingMessage, OutgoingMessage
  api.py              FastAPI app (demo channel), security headers
  rate_limit.py       sliding-window rate limit for the demo channel
  __main__.py         python -m emporio
knowledge/policies.md policy manual transcribed from the PDF
static/               demo chat: index.html, app.js, app.css (no inline code, for the CSP)
scripts/run_scenarios.py     records docs/examples/ against the live model
scripts/run_adversarial.py   adversarial eval (spec §10b), cases in adversarial_cases.py
tests/                       unit tests; fakes.py, constants.py, shared fixtures in conftest.py
```
