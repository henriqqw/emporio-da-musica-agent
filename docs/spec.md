# Spec: Empório da Música customer-service agent

Source of truth for the implementation. Rules are referenced by ID from
[business-rules.md](business-rules.md). Anything not here is out of scope.

## 1. Goal

A text agent that answers Empório da Música customers in Brazilian Portuguese, in the
store's tone, with correct real-time data (catalog, prices, stock, promotions, orders)
and correct policy answers (hours, payment, shipping, returns, warranty), and that
politely declines anything outside the store's scope.

Production channel: WhatsApp (not implemented). Delivered channel: a demo web chat
(FastAPI + one static HTML file). The core does not know which channel it runs on.

## 2. Intents

| ID | Intent | Example | Source | Rules |
|----|--------|---------|--------|-------|
| I1 | Product search / recommendation | "Quais violões até R$ 1000?" | `search_products` | R-CAT-*, R-PRICE-6 |
| I2 | Price / availability of a product | "Quanto custa o Takamine GD20?" | `search_products` | R-PRICE-*, R-PAY-2, R-CAT-2/3 |
| I3 | Promotion question | "O GD20 ainda está em promoção?" | `search_products` | R-PRICE-2/3/5 |
| I4 | Order status / tracking | "Cadê meu pedido?" | `get_order` | R-ORD-*, R-SHIP-4 |
| I5 | Return / exchange / warranty | "Me arrependi, posso devolver?" | `get_order` + manual | R-RET-*, R-WAR-1 |
| I6 | Store info (address, hours, contacts) | "Qual o endereço?" | manual | R-INFO-* |
| I7 | Payment / installments / shipping policy | "Parcela em quantas vezes?" | manual (+ tool for a specific product) | R-PAY-*, R-SHIP-* |
| I8 | Complaint | "Meu pedido atrasou, que absurdo" | `get_order` + manual | R-TONE-4, R-ORD-4 |
| I9 | Accessories | "Vocês vendem cordas?" | manual | R-CAT-5 |
| I10 | Out of scope | "Me ajuda com a lição de física?" | — | R-CAT-6 |
| I11 | Greeting / small talk / closing | "Oi!" / "Valeu!" | — | R-TONE-2 |
| I12 | Personal data / LGPD | "Quero apagar meus dados" | manual | R-PRIV-1 |

Policy intents are answered from the manual, which is in the system prompt (it is
short; no retrieval needed). Data intents always go through a tool: the prompt forbids
stating a price, stock or order fact that did not come from a tool result in the
current conversation.

## 3. Channel contract

Channel-agnostic types in the core:

```python
@dataclass(frozen=True)
class IncomingMessage:
    channel: str              # "web" | "whatsapp"
    phone: str                # customer's phone = session identity
    text: str
    message_id: str           # unique per message; reserved for deduplication
    customer_name: str | None # e.g. WhatsApp profile name; used only to greet

@dataclass(frozen=True)
class OutgoingMessage:
    text: str                 # WhatsApp-safe text (R-TONE-3)
```

`ChatService.handle(IncomingMessage) -> OutgoingMessage` is the only entry point.

HTTP (demo channel):

- `POST /chat` body `{phone, text, message_id?, customer_name?}` → `{reply}`.
  `message_id` defaults to a UUID if omitted. Validation: phone has 10–13 digits after
  stripping non-digits; text 1–2000 chars. Errors → 422 (FastAPI default).
  LLM/provider failure → 200 with a fixed apology message in pt-BR (the customer never
  sees a stack trace), error logged.
- `GET /` serves `static/index.html`: phone and optional name fields, a message box,
  the conversation, and a "nova conversa" button (new session).
- `POST /chat/reset` body `{phone}` → clears that session (demo convenience).

A WhatsApp adapter (README only) would be one more module: webhook → map payload to
`IncomingMessage` (phone from `from`, name from profile, `message_id` from the message
id) → `ChatService.handle` → send `OutgoingMessage.text` via the provider API.

## 4. Sessions and history

- In-memory dict keyed by normalized phone (digits only, Brazilian `55` prefix removed).
- Stores the full message list exactly as sent to/received from the API (append-only;
  required for tool-use and thinking blocks to stay valid).
- A session expires after `SESSION_TTL_MINUTES` (default 30) of inactivity → a new
  conversation starts. No trimming of old turns inside a session.
- Single process, no persistence; lost on restart (documented limitation).

## 5. Tools

Both read-only, defined with JSON Schema and `strict: true`. Results are compact JSON.
Money values are numbers in BRL rounded to 2 decimals (half-up); the prompt tells the
model to write them as `R$ 1.234,56`.

### 5.1 `search_products`

Input (all optional, at least one of `query`/`category`/`max_price` is expected):

| Field | Type | Meaning |
|---|---|---|
| `query` | string | free text: brand, model, type ("takamine gd20", "7 cordas", "elétrico") |
| `category` | enum of the 9 category names | category filter |
| `min_price`, `max_price` | number | filter on the card price (R-PRICE-6) |
| `include_unavailable` | boolean, default false | also return esgotado / descontinuado / em breve |

Matching: accent- and case-insensitive; every query token must appear in
name + category name + description + spec values. If that returns nothing, fall back
to products matching any token, ranked by number of matched tokens. When the query
names a specific product, unavailable matches are always returned so the agent can say
"esgotado"/"descontinuado" and suggest alternatives (R-CAT-3).

Ordering: best match first, then card price ascending. Limit 8; the result includes
`total_found` so the agent can ask the customer to narrow down.

Output per product:

```json
{
  "id": 95, "name": "Takamine GD20 Dreadnought Natural", "category": "Violões",
  "description": "...", "specs": {"top": "...", "electronics": "no"},
  "availability": "disponível",
  "table_price": 2199.0,
  "promotion": null,                       // or {"name": "...", "discount_percent": 18, "price": 1967.18}
  "expired_promotions": ["Oferta Especial (12%)"],
  "pix_price": 2089.05,                    // null when a promotion is active (R-PRICE-4)
  "card": {"price": 2199.0, "max_installments": 12, "installment_value": 183.25}
}
```

Pricing lives in a pure module (`pricing.py`): `promo_price`, `pix_price`,
`max_installments`. No LLM arithmetic.

### 5.2 `get_order`

Input: `email` (string, required), `order_id` (integer, optional).
The phone is **not** an input: the tool handler receives it from the session.

Behaviour:
1. Normalize phone and e-mail (lowercase, trimmed). Find the customer with that exact
   pair. Not found → `{"error": "not_identified"}`; the agent says it could not find a
   registration with this number and e-mail, without saying which one is wrong.
2. `order_id` given and not owned by that customer → same `not_identified`-style
   answer `{"error": "order_not_found"}` (no leaking that the order exists).
3. Without `order_id` → the customer's orders, most recent first (max 5).

Output per order:

```json
{
  "order_id": 7, "date": "2026-02-03", "status": "delivered",
  "status_label": "entregue", "total": 159.9, "payment_method": "cartão de crédito 3x",
  "items": [{"name": "Shelby SU-21S Soprano Sunburst", "quantity": 1}],
  "tracking_code": "BRKR1122334BR", "estimated_delivery": "2026-02-17",
  "delivery_late": false, "notes": null,
  "after_sales": {                          // only for delivered orders
    "received_on": "2026-02-17",
    "regret_until": "2026-02-24", "regret_open": false,
    "preference_exchange_until": "2026-02-24", "preference_exchange_open": false,
    "defect_exchange_until": "2026-03-05", "defect_exchange_open": false,
    "legal_warranty_until": "2026-05-18", "legal_warranty_open": true
  }
}
```

The customer's first name is included so the agent can greet them.
Once identified in a session, the agent may call `get_order` again with the same e-mail
without asking again (the e-mail stays in history; the check still runs every call).

## 6. Prompt strategy

- **Static system block** (cached with `cache_control`): persona and tone (R-TONE-*),
  WhatsApp format rules, behaviour rules (always use tools for data, never invent,
  identification flow, out-of-scope handling, accessories redirect, one question per
  message), and the full manual as Markdown (`knowledge/policies.md`, transcribed once
  from the PDF and reviewed by hand, with our assumptions marked inline).
- **Dynamic system block** (after the cache breakpoint): current date/time in
  America/Campo_Grande based on `REFERENCE_DATE`, whether the store is open now, the
  customer's channel name if any.
- Few-shot examples are not used; rules + tool descriptions are enough and keep the
  prompt short.

## 7. Agent loop

Anthropic Python SDK, manual tool-use loop (`while stop_reason == "tool_use"`), max 5
tool rounds per customer message, then a fallback apology. Tool exceptions are returned
as `tool_result` with `is_error: true`. Model and effort come from env
(`ANTHROPIC_MODEL`, default `claude-opus-5-5`; `ANTHROPIC_EFFORT`, default `low`).
The final text goes through `whatsapp_format.sanitize()` (converts `**x**` → `*x*`,
drops `#` headings and Markdown links/tables) as a safety net; the prompt is the first
line of defence.

## 8. Configuration (env)

| Var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — (required) | provider credentials |
| `ANTHROPIC_MODEL` | `claude-opus-5-5` | model id |
| `ANTHROPIC_EFFORT` | `low` | reasoning effort |
| `REFERENCE_DATE` | real date | "today" for date logic (R-DATE-1) |
| `SESSION_TTL_MINUTES` | `30` | session inactivity timeout |
| `DATA_DIR` | `./data` | CSV location |

## 9. Layout

```
emporio/
  config.py           settings from env
  data.py             CSV loading into typed records (one place that knows file names)
  pricing.py          pure: promo, PIX, installments
  catalog.py          product search + availability
  orders.py           identification, status labels, after-sales windows
  tools.py            tool schemas + dispatch (thin; calls catalog/orders)
  prompt.py           system prompt builder
  agent.py            LLM loop (depends on an injected Anthropic client)
  sessions.py         in-memory session store with TTL
  whatsapp_format.py  reply sanitizer
  service.py          ChatService + IncomingMessage/OutgoingMessage
  api.py              FastAPI app (demo channel)
knowledge/policies.md
static/index.html
tests/
docs/ (spec, business rules, plan, examples/)
```

Dependencies point inward: `api → service → agent → tools → catalog/orders → pricing/data`.
Nothing below `service` imports FastAPI; nothing below `agent` imports the SDK.

## 10. Acceptance scenarios

Reference date 2026-03-25. "Must" items are checked by unit tests where deterministic
(tools, pricing, windows, formatting) and by the recorded example conversations for
LLM behaviour.

| # | Customer says | Must |
|---|---|---|
| A1 | "Quais violões até R$ 1000?" | calls `search_products(category=Violões, max_price=1000)`; lists a few sellable ones with price; excludes Giannini GF-3D (esgotado) and Shelby SN-7C (descontinuado); offers to narrow down (12 match). |
| A2 | "Quanto custa o Takamine GD20?" | R$ 2.199,00; PIX R$ 2.089,05; até 12x de R$ 183,25; disponível. |
| A3 | "O GD20 tá na promoção ainda?" | says the "Oferta Especial" is no longer active and gives the current price (R-PRICE-5). |
| A4 | "Quanto tá o Crafter HT-100?" | from R$ 2.399,00 to R$ 1.967,18 (18% off, "Desconto Exclusivo"); does **not** offer the extra PIX 5%. |
| A5 | "Tem o Giannini GF-3D?" | esgotado; suggests sellable dreadnought/aço alternatives. |
| A6 | "Quero o Shelby SN-7C" | descontinuado; suggests other 7-string guitars. |
| A7 | "Qual o endereço e horário?" | Rua 14 de Maio, 3200, Centro, CG/MS; Seg–Sex 9h–18h, Sáb 9h–13h, Dom/feriados fechado. |
| A8 | "Onde está meu pedido?" (phone of customer 2) | asks for the registered e-mail before any order data; with `anacarol.ferreira@coldmail.com` → order #8 enviado, tracking BRJL5544332BR, previsão 28/02 already passed → apologises, flags the delay, points to the team. |
| A9 | Same as A8 but wrong e-mail | does not reveal any order data; says it couldn't find the registration and how to get help. |
| A10 | "Me arrependi da compra, posso devolver?" (customer 14, order #7) | identifies; arrependimento window (until 24/02) closed; defect exchange (until 05/03) closed; legal warranty until 18/05 open → explains options honestly. |
| A11 | "Vocês vendem cordas de violão?" | only instruments; polite redirect; no invented partner store. |
| A12 | "Me ajuda com uma receita de bolo?" | politely declines, says what it can help with. |
| A13 | "Vocês têm saxofone?" | category has no products → says so; does not invent. |
| A14 | "Dá pra pagar metade no PIX e metade no cartão um ukulele de R$ 359?" | combination only above R$ 2.000. |
| A15 | Any reply | WhatsApp format: no headings/tables/`**`, ≤ 1 question. |

## 11. Out of scope

Placing/cancelling orders, opening returns, freight quotes outside Campo Grande,
payment links, human handoff integration, persistence, authentication of the demo UI,
WhatsApp integration (documented only), multi-language.

## 12. Open questions (need your decision)

- **Q1** Phone conflict (R-INFO-2): OK with phone 3341-4444 / WhatsApp 3321-4500?
- **Q2** Complaints (R-TONE-4): with read-only tools the agent cannot "register and
  forward". Proposal: keep two tools; the agent acknowledges with empathy, says the
  team will follow up within 24 business hours, and gives the human contacts — the
  limitation is stated in the README. Alternative: a third tool `escalate_to_human`
  that appends to a local JSONL log (small, but breaks "read-only").
- **Q3** Model: default `claude-opus-5-5` at low effort, overridable by env (e.g.
  `claude-haiku-5-5` for cost/latency). OK?
