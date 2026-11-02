# Execution plan

One commit per step, each leaving the project runnable and tested. No force-push.

| # | Commit | Content | Done when |
|---|---|---|---|
| 0 | `docs: add spec, business rules and plan` | `git init`, `.gitignore` (excludes `.env`, venv, the case PDF), these docs | reviewed and approved |
| 1 | `chore: project scaffold` | `requirements.txt` (anthropic, fastapi, uvicorn, python-dotenv, pytest, httpx), `.env.example`, `emporio/config.py` | `python -c "import emporio"` works |
| 2 | `feat: load CSV data into typed records` | `data.py` | test: 65 products, 50 customers, 20 orders, items attached |
| 3 | `feat: deterministic pricing` | `pricing.py` | tests: A2, A4 numbers, installment tiers at the boundaries |
| 4 | `feat: product search with availability` | `catalog.py` | tests: A1, A5, A6, A13, accent-insensitive query |
| 5 | `feat: order lookup with identification and after-sales windows` | `orders.py` | tests: A8, A9, A10 windows, other customer's order hidden |
| 6 | `feat: complaint registration` | `complaints.py` | tests: protocol sequence, deadline across a weekend, idempotency by `message_id`, foreign order not linked |
| 7 | `feat: tool schemas and dispatch` | `tools.py` | test: dispatch with phone/message_id injected from session, error results |
| 8 | `feat: system prompt with policy manual` | `knowledge/policies.md`, `prompt.py` | manual reviewed line by line against the PDF |
| 9 | `feat: agent loop, sessions and WhatsApp formatting` | `agent.py`, `sessions.py`, `whatsapp_format.py`, `service.py` | tests with a fake client: tool round-trip, max rounds, TTL, sanitizer (A15) |
| 10 | `feat: demo web channel` | `api.py`, `static/index.html` | runs locally; manual smoke test in the browser |
| 11 | `docs: example conversations` | `scripts/run_scenarios.py` runs the acceptance conversations against the live model through `ChatService` and writes `docs/examples/*.md` (4–5: A1/A2, A7+A11, A8+A16, A10, A12) | Haiku 5.5 passes the scenarios (reviewed by hand); transcripts are real runs |
| 12 | `docs: README` | setup, decisions, assumptions, limitations, AI-assistant workflow, WhatsApp adapter design | follows the case's README checklist |
| 13 | `fix: audit against spec` | walk sections 2–10 of the spec and the acceptance table, fix gaps | every scenario traced to a test or an example |

Step 11 needs a real `ANTHROPIC_API_KEY` in `.env`.
