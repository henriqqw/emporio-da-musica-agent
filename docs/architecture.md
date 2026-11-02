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
 Agent  (tool-use loop, Anthropic SDK) ── Prompt (persona + rules + policy manual)
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
| LLM provider | Anthropic API, official `anthropic` SDK | 2.3.0 |
| Model | Claude Haiku 5.5 (`claude-haiku-5-5`), effort `low` | — |
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

**Consequences.** Small, auditable surface: three tools with strict schemas. Policy
answers depend on the prompt being followed (covered by the acceptance scenarios).
Revisit RAG if the manual grows to hundreds of pages, a large FAQ base appears, or the
catalog needs semantic search over thousands of products; revisit SQL only for an
internal analytics assistant, never customer-facing.

### ADR-02 No agent framework (LangChain, LlamaIndex, etc.)

**Context.** Three tools, one model, one conversation flow.

**Decision.** Use the provider SDK directly with a manual tool-use loop (~60 lines),
not the SDK's beta tool runner either.

**Consequences.** Every request and tool call is visible in our code, easy to test with
a fake client and to read in a review. We own the loop (limits, error handling,
session-data injection), which is exactly what the case evaluates. No beta dependency.

### ADR-03 Model: Claude Haiku 5.5 at low effort

**Context.** Support chat is high-volume and latency-sensitive; the common industry
pattern is a small, cheap default model.

**Decision.** `claude-haiku-5-5`, effort `low`, chosen by env (`ANTHROPIC_MODEL`).
Deterministic code does the parts where a small model would err (arithmetic, dates,
identification, protocol numbers), and tool results carry pre-decided fields (e.g.
`pix_price: null` when a promotion is active) so the model mostly writes the reply.

**Consequences.** ~15–40x cheaper per message than Opus 5.5. It must pass the
acceptance scenarios; otherwise the prompt is fixed first and `claude-sonnet-5-5` is the
env-only fallback. Haiku 5.5 has no server-side refusal fallback, so a refusal returns a
fixed apology with the human contacts.

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
their own inputs (`strict: true` schemas plus checks in code).

**Consequences.** A prompt injection can at most make the agent ask for an e-mail; it
cannot reach another customer's data. In the demo the phone is typed in the UI, standing
in for the number WhatsApp would provide.

### ADR-06 Channel-agnostic core

**Context.** Real customers use WhatsApp; the evaluator needs something runnable.

**Decision.** The core exposes `ChatService.handle(IncomingMessage) -> OutgoingMessage`.
The demo channel is a FastAPI endpoint plus one static page. Replies already follow
WhatsApp formatting (short text, `*bold*`, `_italic_`, no tables or headings, one question
per message), enforced by the prompt and a small sanitizer.

**Consequences.** A WhatsApp adapter (webhook → `IncomingMessage` → `handle` → send
text) needs no change in the core; it is described in the README, not implemented.

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

**Decision.** Two system blocks: the static one with `cache_control` (cached), and a small
dynamic one after it (current date/time, whether the store is open). The tool list is
fixed and ordered, so the cache prefix never changes.

**Consequences.** Repeated requests read the large prefix from cache (~10% of the input
price). No timestamps or IDs inside the cached block.

### ADR-11 Synchronous code

**Context.** One request at a time per customer; the demo has a handful of users.

**Decision.** Plain synchronous functions and the sync Anthropic client. FastAPI runs sync
endpoints in a thread pool.

**Consequences.** Simpler to read and test. Under real load (many concurrent WhatsApp
webhooks) the agent would move to `AsyncAnthropic` and async endpoints; the module
boundaries stay the same.

### ADR-12 Quality gates

**Decision.**
- **Tests:** pytest. Domain and tools are tested against the real CSVs; the agent loop with
  a fake LLM client; the API with `TestClient`. No test needs an API key or network.
- **LLM behaviour:** `scripts/run_scenarios.py` runs the acceptance conversations against
  the live model; the recorded runs become `docs/examples/`.
- **Lint/format:** ruff (config in `pyproject.toml`).
- **CI:** GitHub Actions runs ruff and pytest on every push.
- **Typing:** type hints everywhere; no mypy gate (cost > benefit at this size).
- **Logging:** standard `logging`; tool names, latency and errors are logged, message
  content and personal data are not (LGPD).
- **Git:** small commits, one concern each, Conventional Commits messages, no force-push.

## 4. Module map

```
emporio/
  config.py           settings from env, store time zone, reference date
  data.py             CSV loading into frozen dataclasses
  pricing.py          promo, PIX, installments (pure)
  catalog.py          product search + availability
  orders.py           identification, status labels, after-sales windows
  complaints.py       ComplaintStore (JSONL), protocol, deadline
  tools.py            tool schemas + dispatch
  prompt.py           system prompt builder
  agent.py            tool-use loop over an injected Anthropic client
  sessions.py         in-memory SessionStore with TTL
  whatsapp_format.py  reply sanitizer
  service.py          ChatService, IncomingMessage, OutgoingMessage
  api.py              FastAPI app (demo channel)
knowledge/policies.md policy manual transcribed from the PDF
static/index.html     demo chat
scripts/run_scenarios.py
tests/
```
