# MailPilot — Build Roadmap

Email orchestrator built with LangGraph + FastAPI. Fetches unread emails, summarizes and classifies them (e.g. job leads, critical alerts), and routes notifications to the right Telegram channel.

Built in small, runnable versions — each version is demoable on its own before moving to the next. Architecture: service/domain/repo, extended with ports & adapters (hexagonal) for external systems (Gmail, LLM, Telegram, DB) so business logic never depends on a specific vendor SDK directly.

## Version roadmap

Order changed from the original plan (see history below the table) — FastAPI moved up much earlier, and LangGraph now comes before Telegram instead of after.

| Version | Goal | What's built | What's NOT built yet |
|---|---|---|---|
| **v1** | Prove we can read email | Split into two sub-steps — see below | No DB, no LLM, no FastAPI, no Telegram |
| &nbsp;&nbsp;v1.1 | Prove OAuth login works | Google Cloud project + OAuth consent + `gmail_adapter.py` with just `get_gmail_service()` — authenticates, no fetching yet. Steps: [V1.1-STEPS.md](steps/V1.1-STEPS.md) | Doesn't fetch emails yet |
| &nbsp;&nbsp;v1.2 | Fetch unread emails | Use the authenticated service from v1.1 to list unread emails (prints subject/sender to console) | Still no DB/LLM/FastAPI/Telegram |
| **v2** | Persist what we've seen | Postgres + SQLAlchemy + Alembic; store fetched emails, mark them processed (idempotency — don't reprocess the same email twice). Steps: [V2-STEPS.md](steps/V2-STEPS.md) | Still no LLM/Telegram |
| **v3** | Summarize + classify | One LLM call (OpenAI `gpt-4o-mini`, structured output via Pydantic) per email → summary + category (`job_opportunity`, `critical_alert`, `newsletter`, `promotion`, `other`) | `summary`/`category` not yet persisted to Postgres — only returned in the API response |
| **v3.5** | Wrap in FastAPI | `Dockerfile` + `app` service in `docker-compose.yml`; `GET /health`, `POST /pipeline/run` (fetch → save → classify). Moved up from the original v6 slot — building the web layer early instead of at the end. | Routes/logic currently live together in one `app/main.py` — needs restructuring into a router as more endpoints get added |
| **v4** | Wire it as a LangGraph | Turn the fetch/save/classify steps into proper graph nodes with `StateGraph`, typed state. Moved up from v5 — built before Telegram this time. | No real conditional routing yet (needs a second branch — Telegram — to route between) |
| **v5** | Notify | Telegram bot + `telegram_adapter.py`; route summary + category to the right channel, as a graph node with a real conditional routing edge (e.g. route by category) | Still manual trigger |
| **v6** | ~~Wrap in FastAPI~~ (done early, see v3.5) | — | — |
| **v7** | Automate the trigger | Gmail `watch()` + Pub/Sub push subscription + `POST /webhooks/gmail` + the 7-day watch-renewal job | — |
| **v8** | Harden | Error handling, retries, logging, deploy notes | — |

## Current status

- [x] v1.1 — Google Cloud project + OAuth setup done (see [V1.1-STEPS.md](steps/V1.1-STEPS.md))
- [x] v1.2 — `list_unread_messages()` in gmail_adapter.py + scripts/fetch_unread.py, verified against live inbox
- [x] v2 — Postgres via Docker Compose, SQLAlchemy models + Alembic migration, hexagonal repository, wired into fetch_unread.py; idempotency verified (see [V2-STEPS.md](steps/V2-STEPS.md))
- [x] v3 — `app/adapters/llm/openai_classifier.py`, tested against real inbox subjects; persistence to Postgres still pending
- [x] v3.5 — FastAPI app (`app/main.py`) + Docker Compose `app` service; `/health` and `/pipeline/run` verified working end-to-end through Docker, including DB connectivity over the internal `db` hostname
- [ ] v4 — LangGraph (in progress)
- [ ] v5
- [ ] v7
- [ ] v8

## Notes / decisions locked in

- **Email source:** Gmail API (OAuth), not IMAP.
- **Trigger:** Gmail push notifications (Pub/Sub webhook) — target for v7. Note: push notifications only signal "something changed," the webhook still has to call `history.list()` to fetch the actual delta. The `watch()` subscription also expires every 7 days and needs a renewal job regardless of push vs. poll.
- **Persistence:** Postgres from the start (v2), via SQLAlchemy + Alembic.
- **LLM:** Switched from the original plan (Claude Haiku 4.5) to **OpenAI `gpt-4o-mini`** — user's choice. Structured output via Pydantic model (`summary: str`, `category: Category` enum). Still one call per email, no two-stage funnel (considered and explicitly rejected — see reasoning below).
- **Classification funnel (rejected):** Considered doing a cheap subject-only pass first, then a second full-body pass only for likely matches, to save tokens. Rejected because: (1) the `snippet` field (short body preview) is already free — it's returned by Gmail's `get()` call by default, no extra API cost, and only ~30-50 tokens; (2) deciding whether an email needs "more checking" would itself require an LLM call, so a two-stage approach could cost *more* tokens than one call with `snippet` included, not less. If a real full-body deep-dive is ever needed, that's a job for v5's LangGraph conditional routing, not v3.
- **Web framework timing:** Originally planned for v6 (after the full pipeline was proven as plain functions), so the web layer wouldn't be debugged at the same time as the underlying logic. User chose to move it up to right after v3 instead — reasoning: build a proper app shape early rather than gluing FastAPI on at the very end. Tradeoff accepted knowingly.
- **Branching:** Originally used `v2-postgres` as a feature branch, merged into `main` after v2 was verified. From v3 onward, everything is built directly on `main` — no more per-version branches for now (until a real BE/FE split happens, if ever).
- **Multi-user:** Not a target for now — single user (you) through v8. But designed v2's schema so it's not painful to add later: `emails` table gets a `user_id` column from the start, and OAuth tokens move from the flat `token.json` file into a per-user DB table instead of staying file-based. No extra work now beyond keeping v2 shaped this way.
