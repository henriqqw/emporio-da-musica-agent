# Execution plan

One concern per commit, each with its tests, each leaving the project runnable.
Conventional Commits messages, no force-push. Decisions behind the steps are in
[architecture.md](architecture.md).

| # | Commit | Content | Done when | Status |
|---|---|---|---|---|
| 0 | `docs: ...` | spec, business rules, plan, architecture | reviewed and approved | done |
| 1 | `chore: project scaffold and settings` | pinned requirements, `.env.example`, `pyproject.toml`, `config.py` | settings load, incl. time zone | done |
| 2 | `ci: lint and test workflow` | ruff config, `.github/workflows/ci.yml` | CI green on GitHub | done |
| 3 | `feat: load CSV data into typed records` | `data.py` | tests: table counts, typed fields, items attached | done |
| 4 | `feat: deterministic pricing` | `pricing.py` | tests: A2, A4 numbers, installment tiers at the boundaries | done |
| 5 | `feat: product search with availability` | `catalog.py` | tests: A1, A5, A6, A13, accent-insensitive query | done |
| 6 | `feat: order lookup with identification and after-sales windows` | `phone.py`, `orders.py` | tests: A8, A9, A10 windows, other customer's order hidden | done |
| 7 | `feat: complaint registration` | `complaints.py` | tests: protocol sequence, deadline across a weekend, idempotency | done |
| 8 | `feat: tool schemas and dispatch` | `tools.py` | tests: session data injected, error results | done |
| 9 | `docs: transcribe policy manual` | `knowledge/policies.md` | reviewed line by line against the PDF | done |
| 10 | `feat: system prompt` | `store_hours.py`, `prompt.py` | tests: static part stable, dynamic part has date and opening status | done |
| 11 | `feat: WhatsApp reply formatting` | `whatsapp_format.py` | tests: A15 | done |
| 12 | `feat: in-memory sessions with TTL` | `sessions.py` | tests: expiry, reset | done |
| 13 | `feat: agent tool-use loop` | `agent.py` | tests with a fake client: tool round-trip, max rounds, refusal, API error | done |
| 14 | `feat: channel-agnostic chat service` | `service.py` | tests: session wiring, phone normalization | done |
| 15 | `feat: demo web channel` | `api.py`, `static/index.html` | `TestClient` tests; manual check in the browser | done |
| 16 | `feat: validate tool arguments in code` | `tools.py` | tests: wrong types, unknown enum values, out-of-range numbers rejected | done |
| 17 | `refactor: OpenAI-compatible LLM client` (ADR-13) | `config.py`, `prompt.py`, `tools.py`, `agent.py`, `service.py`, fakes, `.env.example`, requirements | all tests green; no `anthropic` import left | done |
| 18 | `docs: example conversations` | `scripts/run_scenarios.py` + `docs/examples/*.md` | scenarios reviewed by hand against spec §10; transcripts are real runs and name the model | done |
| 19 | `docs: README` | setup per provider, decisions, assumptions, limitations, AI-assistant workflow, WhatsApp adapter | follows the case's README checklist | done |
| 20 | `fix: audit against spec` | walk spec sections 2–10 and the acceptance table, fix gaps | every scenario traced to a test or an example | done |

Step 18 needs an API key for any OpenAI-compatible provider in `.env` (a free Gemini
key is enough).

Beyond the plan, the live runs and the audit added fix commits, each traced to what
exposed it: free-tier quota and latency, product alternatives, prompt rules for returns
and complaints, pre-formatted money and dates, combined payment in code (A14) and
categories in stock (A13). The audit's traceability table is in spec section 10.

After the audit, a manual test ("escreva um código de música") led to spec section 10b
(A17): an adversarial eval with code checks and an LLM judge, a calibrated baseline
(17/20), the scope prompt and two rounds of human-review fixes (20/20), then a shorter
README with a 15-minute evaluation path.
