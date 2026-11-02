# Execution plan

One concern per commit, each with its tests, each leaving the project runnable.
Conventional Commits messages, no force-push. Decisions behind the steps are in
[architecture.md](architecture.md).

| # | Commit | Content | Done when |
|---|---|---|---|
| 0 | `docs: ...` | spec, business rules, plan, architecture | reviewed and approved |
| 1 | `chore: project scaffold and settings` | pinned requirements, `.env.example`, `pyproject.toml`, `config.py` | settings load, incl. time zone |
| 2 | `ci: lint and test workflow` | ruff config, `.github/workflows/ci.yml` | CI green on GitHub |
| 3 | `feat: load CSV data into typed records` | `data.py` | tests: table counts, typed fields, items attached |
| 4 | `feat: deterministic pricing` | `pricing.py` | tests: A2, A4 numbers, installment tiers at the boundaries |
| 5 | `feat: product search with availability` | `catalog.py` | tests: A1, A5, A6, A13, accent-insensitive query |
| 6 | `feat: order lookup with identification and after-sales windows` | `orders.py` | tests: A8, A9, A10 windows, other customer's order hidden |
| 7 | `feat: complaint registration` | `complaints.py` | tests: protocol sequence, deadline across a weekend, idempotency, foreign order not linked |
| 8 | `feat: tool schemas and dispatch` | `tools.py` | tests: session data injected, error results |
| 9 | `docs: transcribe policy manual` | `knowledge/policies.md` | reviewed line by line against the PDF |
| 10 | `feat: system prompt` | `prompt.py` | tests: static block stable (cacheable), dynamic block has date and opening status |
| 11 | `feat: WhatsApp reply formatting` | `whatsapp_format.py` | tests: A15 |
| 12 | `feat: in-memory sessions with TTL` | `sessions.py` | tests: expiry, reset |
| 13 | `feat: agent tool-use loop` | `agent.py` | tests with a fake client: tool round-trip, max rounds, refusal, API error |
| 14 | `feat: channel-agnostic chat service` | `service.py` | tests: session wiring, phone normalization |
| 15 | `feat: demo web channel` | `api.py`, `static/index.html` | `TestClient` tests; manual smoke test in the browser |
| 16 | `docs: example conversations` | `scripts/run_scenarios.py` + `docs/examples/*.md` (A1/A2, A7+A11, A8+A16, A10, A12) | Haiku 5.5 passes the scenarios (reviewed by hand); transcripts are real runs |
| 17 | `docs: README` | setup, decisions, assumptions, limitations, AI-assistant workflow, WhatsApp adapter | follows the case's README checklist |
| 18 | `fix: audit against spec` | walk spec sections 2–10 and the acceptance table, fix gaps | every scenario traced to a test or an example |

Step 16 needs a real `ANTHROPIC_API_KEY` in `.env`.
