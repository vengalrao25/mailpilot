# MailPilot

Email orchestrator: reads Gmail, summarizes/classifies with an LLM, notifies via Telegram.

See [ROADMAP.md](docs/ROADMAP.md) for the version plan.

## Setup

1. Google Cloud Console: create a project, enable Gmail API, configure OAuth consent screen, create an OAuth Client ID (Desktop app), download it as `credentials.json` in the project root.
2. ```bash
   python3.10 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. `python scripts/authenticate.py` — first run opens a browser to log in, later runs reuse `token.json`.
4. Postgres: `docker compose up -d db`, then copy `.env.example` to `.env` and fill in `POSTGRES_*`/`OPENAI_API_KEY`.
5. `alembic upgrade head` to create/update the schema.

Activate the venv (`source .venv/bin/activate`) each time you open a new terminal.

New package installed? Add it to `pyproject.toml` (`dependencies` for runtime, `optional-dependencies.dev` for dev-only), then run `pip freeze > requirements.txt` so the Docker image (which installs from `requirements.txt`) stays in sync.

## Running

- Locally: `uvicorn app.main:app --reload`
- Docker: `docker compose up -d --build`

Routes: `GET /health`, `POST /pipeline/run` (body: optional `after`/`before` ISO datetimes).

## Tests

```bash
pip install -e ".[dev]"
pytest
```

All tests run offline against in-memory fakes (`tests/fixtures/fakes.py`) — no real Gmail/OpenAI calls, no Postgres required. Repository tests use an in-memory SQLite database by default; set `TEST_DATABASE_URL` to point them at a real (disposable) Postgres instead, e.g. to verify FK/constraint behavior that SQLite doesn't enforce.

## Architecture

Hexagonal/ports-and-adapters, one layer per concern:

- `app/domain/` — framework-independent models (`Email`, `Classification`) and port `Protocol`s (`GmailPort`, `ClassifierPort`, repositories). No FastAPI/SQLAlchemy/Gmail/OpenAI/LangGraph imports.
- `app/adapters/` — concrete implementations of the ports (`gmail/client.py`, `llm/classifier.py`, `database/repositories.py`).
- `app/workflows/email_pipeline/` — the LangGraph pipeline. Nodes take their dependencies as constructor arguments (`make_*_node(port)`); they never construct a concrete adapter themselves.
- `app/services/process_inbox.py` — orchestrates fetch → per-email graph run → aggregate; this is what the route calls.
- `app/api/` — routes validate the HTTP request and call the service; `dependencies.py` wires concrete adapters in via FastAPI `Depends`, which tests override with fakes.
- `app/core/` — validated `Settings` and the lazy DB engine/sessionmaker factory. Nothing here (or anywhere else) opens a DB connection just by being imported.
