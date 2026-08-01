# MailPilot — Build Roadmap

Email orchestrator built with LangGraph + FastAPI. Fetches unread emails, summarizes and classifies them (e.g. job leads, critical alerts), and routes notifications to the right Telegram channel.

Built in small, runnable versions — each version is demoable on its own before moving to the next. Architecture: service/domain/repo, extended with ports & adapters (hexagonal) for external systems (Gmail, LLM, Telegram, DB) so business logic never depends on a specific vendor SDK directly.

## Version roadmap

| Version | Goal | What's built | What's NOT built yet |
|---|---|---|---|
| **v1** | Prove we can read email | Split into two sub-steps — see below | No DB, no LLM, no FastAPI, no Telegram |
| &nbsp;&nbsp;v1.1 | Prove OAuth login works | Google Cloud project + OAuth consent + `gmail_adapter.py` with just `get_gmail_service()` — authenticates, no fetching yet. Steps: [V1.1-STEPS.md](V1.1-STEPS.md) | Doesn't fetch emails yet |
| &nbsp;&nbsp;v1.2 | Fetch unread emails | Use the authenticated service from v1.1 to list unread emails (prints subject/sender to console) | Still no DB/LLM/FastAPI/Telegram |
| **v2** | Persist what we've seen | Postgres + SQLAlchemy + Alembic; store fetched emails, mark them processed (idempotency — don't reprocess the same email twice) | Still no LLM/Telegram |
| **v3** | Summarize + classify | One LLM call (Haiku 4.5, structured output) per email → summary + category. No LangGraph yet — just a plain function, so the LLM logic is visible in isolation | No routing, no Telegram, no graph |
| **v4** | Notify | Telegram bot + `telegram_adapter.py`; route summary + category to the right channel | Still manual trigger, still no real graph orchestration |
| **v5** | Wire it as a LangGraph | Turn the v3/v4 functions into proper graph nodes with `StateGraph`, typed state, conditional routing edge | Still manual trigger |
| **v6** | Wrap in FastAPI | `POST /pipeline/run` endpoint invokes the graph; `/health` | Still no webhook, still manually triggered |
| **v7** | Automate the trigger | Gmail `watch()` + Pub/Sub push subscription + `POST /webhooks/gmail` + the 7-day watch-renewal job | — |
| **v8** | Harden | Error handling, retries, logging, deploy notes | — |

## Current status

- [x] v1.1 — Google Cloud project + OAuth setup done (see [V1.1-STEPS.md](V1.1-STEPS.md))
- [x] v1.2 — `list_unread_messages()` in gmail_adapter.py + scripts/fetch_unread.py, verified against live inbox
- [ ] v2
- [ ] v3
- [ ] v4
- [ ] v5
- [ ] v6
- [ ] v7
- [ ] v8

## Notes / decisions locked in

- **Email source:** Gmail API (OAuth), not IMAP.
- **Trigger:** Gmail push notifications (Pub/Sub webhook) — target for v7. Note: push notifications only signal "something changed," the webhook still has to call `history.list()` to fetch the actual delta. The `watch()` subscription also expires every 7 days and needs a renewal job regardless of push vs. poll.
- **Persistence:** Postgres from the start (v2), via SQLAlchemy + Alembic.
- **LLM:** Claude Haiku 4.5 for summarization + classification (cheap, fast, sufficient for this task). Combine summarize + classify into one structured-output call per email rather than two separate calls.
- **Multi-user:** Not a target for now — single user (you) through v8. But design v2's schema so it's not painful to add later: `emails` table gets a `user_id` column from the start, and OAuth tokens move from the flat `token.json` file into a per-user DB table instead of staying file-based. No extra work now beyond keeping v2 shaped this way.
