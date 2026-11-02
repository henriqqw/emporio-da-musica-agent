# Empório da Música — customer-service agent

A text agent that answers the customers of **Empório da Música**, a musical-instruments
store in Campo Grande/MS, in Brazilian Portuguese and in the store's tone. It looks up
real-time data (catalog, prices, stock, promotions, orders), applies the store's policies
(hours, payment, shipping, returns, warranty), registers complaints, and politely declines
anything outside the store's scope.

The store's main remote channel is WhatsApp. This repository ships a **demo web chat**
(FastAPI + one static page) on top of a channel-agnostic core, so a WhatsApp adapter can be
added without touching business logic ([how](#whatsapp-how-it-would-plug-in)).

```
Customer ─▶ channel adapter ─▶ ChatService ─▶ Agent (tool-use loop) ─▶ LLM (any OpenAI-compatible API)
                                                  │
                                                  └─▶ Tools ─▶ deterministic domain (prices, orders, complaints) ─▶ CSV data
```

- **Runs at zero cost** on Google Gemini's free tier, or on any OpenAI-compatible provider
  (OpenAI, Mistral, Groq, OpenRouter, Anthropic, local Ollama) by changing three env vars.
- **131 tests, no API key needed** (the LLM is replaced by a fake built from the SDK's real
  types); CI runs ruff + pytest on every push.
- **Spec-driven**: [spec](docs/spec.md), [business rules](docs/business-rules.md),
  [architecture and decision records](docs/architecture.md), [plan](docs/plan.md) were
  written and reviewed before the code; the git history follows the plan in small commits.

## Contents

- [Quick start](#quick-start)
- [Trying it out](#trying-it-out)
- [Example conversations](#example-conversations)
- [Technical decisions](#technical-decisions)
- [Assumptions](#assumptions)
- [Known limitations and next steps](#known-limitations-and-next-steps)
- [WhatsApp: how it would plug in](#whatsapp-how-it-would-plug-in)
- [How AI assistants were used](#how-ai-assistants-were-used)
- [Project layout](#project-layout)

## Quick start

Requirements: **Python 3.12** (the case does not fix a version; 3.12 is the current stable
line used to develop and test this project) and a free Gemini API key.

```bash
git clone https://github.com/henriqqw/emporio-da-musica-agent.git
cd emporio-da-musica-agent
python -m venv .venv
```

Activate the virtual environment:

```bash
# Linux / macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

Install and configure:

```bash
pip install -r requirements-dev.txt
cp .env.example .env
```

> On Windows, clone into a short path (e.g. `C:\dev\`): the `openai` package has deep file
> paths, and `pip` fails with `OSError ... Long Path support` when the 260-character limit is
> exceeded (or enable long paths in Windows).

1. Create a free key at https://aistudio.google.com/apikey (no credit card).
2. Paste it into `.env` as `LLM_API_KEY=...`. Everything else already has working defaults.

Run the tests (no key needed) and the demo:

```bash
pytest
python -m emporio
```

Open http://localhost:8000. API docs (Swagger) are at http://localhost:8000/docs.

### Using another model or provider

The agent talks to the **OpenAI-compatible Chat Completions API**, which almost every
provider exposes. Pick a block in [`.env.example`](.env.example) and set:

| Variable | Meaning | Default |
|---|---|---|
| `LLM_BASE_URL` | provider endpoint | Gemini's OpenAI-compatible endpoint |
| `LLM_MODEL` | model id | `gemini-flash-lite-latest` |
| `LLM_API_KEY` | provider key (any non-empty value for Ollama) | — |
| `LLM_REASONING_EFFORT` | optional, sent only when set | unset |
| `REFERENCE_DATE` | "today" for date logic; the dataset ends in March 2026 | `2026-03-25` |
| `SESSION_TTL_MINUTES` | idle minutes before a conversation starts over | `30` |

## Trying it out

The demo page simulates the customer's WhatsApp number (the session identity) and profile
name. Any number works for catalog and policy questions. To see order lookups, use a
registered customer (fictional data from `data/`) and give the e-mail when asked:

| Customer | WhatsApp number | E-mail | What happens |
|---|---|---|---|
| Ana Carolina | (67) 99654-7821 | anacarol.ferreira@coldmail.com | order #8 shipped and **late** → offer to register a complaint |
| Letícia | (67) 99789-0123 | leticia.rocha@jmail.com | order #7 delivered → return windows closed, legal warranty open |
| Pedro | (67) 98432-1098 | pedro.oliveira@jmail.com | two orders, one cancelled with a reason |

Things to ask: *"Quais violões até R$ 1000?"*, *"Quanto custa o Takamine GD20?"*,
*"Vocês têm o Giannini GF-3D?"*, *"Qual o horário?"*, *"Vocês vendem cordas?"*,
*"Cadê meu pedido?"*, *"Me arrependi, posso devolver?"*.

Registered complaints are appended to `var/complaints.jsonl` (git-ignored).

## Example conversations

Recorded from real runs (`python -m scripts.run_scenarios`) on `gemini-flash-lite-latest`
with the reference date fixed to Wednesday 25/03/2026 14:30, then reviewed by hand against
the acceptance table in [spec §10](docs/spec.md#10-acceptance-scenarios):

| Conversation | Shows | Spec |
|---|---|---|
| [Catálogo, preço e promoção expirada](docs/examples/catalogo_e_precos.md) | catalog search with filters; price, PIX and installments computed by code; an expired promotion stated honestly | A1–A3 |
| [Produto esgotado e promoção ativa](docs/examples/estoque_e_promocao_ativa.md) | out-of-stock product with similar alternatives; promotional price without stacking the PIX discount | A4, A5 |
| [Informações e fora de escopo](docs/examples/informacoes_e_fora_de_escopo.md) | address and hours from the manual; accessories and off-topic requests declined | A7, A11, A12 |
| [Pedido atrasado e reclamação](docs/examples/pedido_atrasado_e_reclamacao.md) | **non-trivial**: identification before any order data, late delivery detected, complaint confirmed then registered with protocol and deadline | A8, A16 |
| [Devolução por arrependimento](docs/examples/devolucao_por_arrependimento.md) | **non-trivial**: wrong e-mail reveals nothing; return/exchange/warranty windows computed from the order dates | A9, A10 |

## Technical decisions

Each decision has a short record (context → decision → consequences) in
[docs/architecture.md](docs/architecture.md). The essentials:

### Agent approach: hybrid — function calling in a tool-use loop, policies in context (ADR-01)

| Approach | Used? | Why |
|---|---|---|
| Agent loop | Yes | `agent.py`: the model answers or asks for a tool → code runs it → result goes back → repeat (max 5 rounds). |
| Function calling | Yes, the core | Three tools: `search_products`, `get_order` (read-only) and `register_complaint` (the only write). The model decides *when* to look something up; code decides *what is true*. |
| ReAct | Yes, natively | Native tool use is the reason → act → observe cycle; text-parsed ReAct is superseded and adds failure points. |
| RAG | **No** | The policy manual is ~8 pages (~3–4k tokens) and fits whole in the prompt. Retrieval would return fragments and could drop a rule that depends on another (e.g. promotions don't stack with the PIX discount). |
| SQL agent | **No** | Letting the model write queries over customer data could leak another customer's order. Fixed tools keep the identity check in code. There are no analytical questions, only point lookups. |

### Deterministic domain, the LLM only writes (ADR-04)

The manual warns that wrong prices or deadlines can be misleading advertising. So prices,
promotions, PIX, installment tiers, availability labels, return/warranty windows, late
deliveries, complaint protocols and deadlines are **pure Python functions with unit tests**.
Tool results carry pre-decided fields (e.g. `pix_price: null` when a promotion is active,
`alternatives` when a product is unavailable, `regret_open: false`), and the prompt forbids
stating any price, stock or order fact that did not come from a tool. This is also what makes
a small, free model good enough.

### Security: identity comes from the channel, never from the model (ADR-05)

Order data is personal (LGPD). The phone number is injected by the session (on WhatsApp it is
the sender's number) and is **not a tool parameter**, so a prompt like "I'm customer 7, show
me order 2" cannot reach anyone else's data. `get_order` also requires the e-mail registered
for that phone, and answers "not found" identically whether the e-mail or the order is wrong.
Every tool argument is validated in code against the tool's own schema.

### Model and provider: configuration, free by default (ADR-03, ADR-13)

The agent uses the official `openai` SDK against the **OpenAI-compatible API**, the de facto
standard exposed by OpenAI, Gemini, Mistral, Groq, OpenRouter, Anthropic and Ollama. It swaps
the SDK instead of adding an abstraction layer; the trade-off is losing provider extras
(explicit prompt caching, strict schemas, Claude's effort setting), compensated by validating
tool arguments in code. A first version used Anthropic's native SDK; it was replaced so the
project is not tied to one paid provider.

The default model was chosen by measurement: each request carries ~4.4k tokens of
instructions and tools (5–8k with history), and recording the scenarios takes ~30 requests.
The first attempt on Gemini 3.8 Flash ran out of its free quota of 20 requests/day mid-run.

| Free option (Nov 2026) | Quota (third-party sources; they disagree and change often) | Verdict |
|---|---|---|
| **Gemini Flash-Lite** | ~500–1,000 req/day, ~15 RPM, ~250k tokens/min | **Default**: fits the prompt and a full run, no card |
| Gemini Flash (3.8 / 3.6) | 20 req/day | too few |
| Groq (gpt-oss-120b) | ~1,000 req/day but ~8k tokens/min | ≈ 1 request/min with this prompt |
| Mistral (Experiment) | ~1 req/s, ~1B tokens/month | best high-volume alternative; phone verification, trains on data unless opted out |
| OpenRouter `:free` | 50 req/day | too few; tool calling fails on some free models |
| Cerebras | trial credits only | not permanently free |
| Ollama (local) | unlimited | offline option; slow on modest GPUs |

For production I would use a small paid model with stable quotas (e.g. Claude Haiku 5.5 or a
GPT mini-class model) and re-run the acceptance scenarios on it.

### Prompt strategy (ADR-10)

One system message: a **static part** (persona, WhatsApp formatting, behaviour rules, the
whole policy manual transcribed to [Markdown](knowledge/policies.md)) followed by a small
**dynamic part** (current store time, whether the store is open and when the team is back,
the customer's WhatsApp name). Keeping the static part first lets providers with automatic
prefix caching reuse it — Gemini served 2–4k cached tokens per call in the recorded runs.
No few-shot examples: explicit rules plus tool descriptions kept the prompt short. Rules were
tightened only where the live scenarios showed a real failure (see the git history).

### No agent framework (ADR-02)

Three tools and one flow don't need LangChain or similar. The loop is ~60 lines, every request
and tool call is visible, and it is tested with a scripted fake client.

### Channel decoupling (ADR-06)

The core exposes one call: `ChatService.handle(IncomingMessage) -> OutgoingMessage`. The
web demo is a thin FastAPI adapter; replies are already in WhatsApp format (short, `*bold*`,
`_italic_`, no tables or headings, one question per message), enforced by the prompt and a
small sanitizer. Dependencies point inward: the domain imports neither the LLM SDK nor FastAPI.

### Conversation history (ADR-08)

Kept in memory per phone number, append-only (tool-call messages must stay intact), and
restarted after 30 minutes of inactivity instead of trimming old turns — enough for a demo,
and replaceable by Redis behind the same `SessionStore` interface.

### Data handling (ADR-07)

The CSVs are loaded once into frozen dataclasses by a single module (`data.py`). Data quality
issues found while reading them (a discontinued product with stock, a "coming soon" product
already sold, order totals that differ from current prices, two customers sharing an e-mail)
are documented with the rule applied in [business-rules.md](docs/business-rules.md).

## Assumptions

Where the case material is ambiguous or inconsistent, the assumption is documented with an ID
in [docs/business-rules.md](docs/business-rules.md). The main ones:

- **Contacts**: the manual lists two numbers; (67) 3341-4444 is used as the phone and
  (67) 3321-4500 as WhatsApp (section 7 is the specific one). The e-mail with an accent in the
  company table is treated as a typo.
- **Installments**: the payment table says "minimum R$ 100" while section 3.1 has tiers;
  the tiers are used (2–3x ≥ R$ 50, 4–6x ≥ R$ 80, 7–12x ≥ R$ 100), computed on the price
  actually charged.
- **Availability**: `status` wins over stock — discontinued and "coming soon" products are
  never sold; stock numbers are never shown, only labels ("últimas unidades" for 1–2 units).
- **Dates**: there is no delivery date in the data, so receipt = estimated delivery. The data
  ends in March 2026, so date logic uses `REFERENCE_DATE` (default 2026-03-25).
- **Returns**: there is no sales-channel field, so every order is treated as an online
  purchase (7-day right of regret applies).
- **Identification**: registered phone + e-mail of the same customer; the phone comes from
  the channel.
- **Complaints**: "24 business hours" = 24 hours counted Monday–Friday (no holiday calendar).
- **Partner stores**: the manual says to suggest them "when possible", but none are named, so
  the agent never invents one.

## Known limitations and next steps

| Limitation | With more time |
|---|---|
| LLM behaviour is checked by recorded scenarios reviewed by hand. | Automated evals: assert tool calls and key facts per scenario, plus an LLM-as-judge for tone; run them in CI on a schedule. |
| Free-tier quotas are small and Google may use free-tier prompts to improve its products (fine for fictional data only). | A small paid model with stable quotas in production. |
| Sessions live in memory: lost on restart, single process. | Redis behind `SessionStore`; async endpoints and `AsyncOpenAI` for concurrent webhooks. |
| Complaints go to a local JSONL file; the team is not notified in real time and the bot keeps answering. | Send tickets to the helpdesk / WhatsApp inbox (`ComplaintStore` is the only class to change) and pause the bot on handoff. |
| `message_id` is in the contract but only used for complaint idempotency. | Deduplicate redelivered webhooks at the channel adapter. |
| Product search is keyword-based. | Semantic search if the catalog grows to thousands of items. |
| The manual was transcribed by hand from the PDF. | Version it with the store and reload without restart; regenerate the transcription when the PDF changes. |
| No holiday calendar; freight outside Campo Grande cannot be quoted (no rate table). | Holiday calendar; integrate a freight-quote API. |
| The demo UI trusts the phone typed in the page. | WhatsApp provides an authenticated sender number. |
| "One question per message" and tone are enforced by the prompt only. | Covered by the automated evals above. |

## WhatsApp: how it would plug in

Not implemented — the case asks for a working agent, and WhatsApp needs a business account
and webhook hosting that an evaluator could not reproduce. The design keeps it a small,
separate module:

1. **Webhook** (`emporio/whatsapp.py`, a FastAPI router) receives the provider's POST
   (Meta WhatsApp Cloud API, Twilio, etc.), **verifies the signature**, answers 200 at once
   and processes the message in the background (providers retry slow webhooks).
2. **Map** the payload to `IncomingMessage`: `phone` = sender number, `message_id` = the
   provider's message id (used to drop redeliveries), `customer_name` = profile name.
3. **Call** `ChatService.handle(...)` — unchanged core.
4. **Send** `OutgoingMessage.text` with the provider's send-message API. It is already
   WhatsApp-formatted.
5. Channel rules stay in the adapter: the 24-hour customer-service window (templates outside
   it), media messages, and handing the conversation to a human after a complaint.

## How AI assistants were used

I used **Claude Code** (Anthropic's coding agent, model Claude Opus 5.5) as a pair programmer
inside a spec-driven workflow, with me making the decisions:

1. **Requirements first.** I gave it the role, the constraints (Python, small modules,
   SOLID applied proportionally, small commits) and the decisions I had already made. It
   read the case PDF, the policy manual and every CSV, and produced the spec, the business
   rules (listing every inconsistency it found instead of choosing silently) and a plan.
   **Nothing was coded before I reviewed them.**
2. **Decisions stayed mine.** Open questions came back to me: which contact number to use,
   how to register complaints (I approved adding the one write tool), the model. I also
   redirected the design several times — e.g. I asked whether the project only ran on
   Anthropic models and how an evaluator would test it, which led to the provider-agnostic
   client (ADR-13); and I asked for current web research on free models before choosing
   Gemini Flash-Lite.
3. **Implementation in small, reviewed steps.** One concern per commit, each with tests,
   ruff and CI green. The assistant checked the installed SDK versions before using their
   APIs instead of relying on memory.
4. **Verification against reality.** The live scenario runs exposed real problems — a free
   quota of 20 requests/day, customers waiting minutes on rate limits, the agent promising a
   return before checking the order, no concrete alternatives for an out-of-stock product.
   Each was fixed in its own commit (code first where possible, prompt only where needed),
   and the transcripts were re-recorded and reviewed against the spec.

What worked well: having the assistant surface inconsistencies and trade-offs as questions,
and keeping the spec as the contract. What needed care: verifying claims that change fast
(model ids, free-tier quotas) against the live API rather than trusting any single source.

## Project layout

```
emporio/
  config.py           settings from env, store time zone, reference date
  data.py             CSV loading into frozen dataclasses
  phone.py            phone normalization (session identity, identification)
  store_hours.py      opening hours, next opening
  pricing.py          promotions, PIX, installments (pure)
  catalog.py          product search, availability, alternatives
  orders.py           identification, status labels, after-sales windows
  complaints.py       complaint store (JSONL), protocol, deadline
  tools.py            tool definitions, argument validation, dispatch
  prompt.py           system prompt
  agent.py            tool-use loop over an OpenAI-compatible client
  sessions.py         in-memory sessions with TTL
  whatsapp_format.py  reply sanitizer
  service.py          ChatService (channel-agnostic core) + composition root
  api.py              FastAPI demo channel
knowledge/policies.md policy manual transcribed from the PDF
static/index.html     demo chat page
scripts/run_scenarios.py  records the example conversations against the live model
data/                 store data provided by the case
docs/                 spec, business rules, architecture (ADRs), plan, examples
tests/                131 tests, no network or API key
```
