# v2 — Persist what we've seen (Postgres)

**Goal:** fetched emails get saved to Postgres, and re-running the fetch script never inserts the same email twice (idempotency). Still no LLM, no Telegram, no FastAPI.

This is a checklist, not code — write the code yourself for each part; ask for a review once it's written rather than asking for the code directly, that's the point of doing it hands-on.

---

## Part A — Local Postgres (mostly already done)

- [x] `docker-compose.yml` defines a `db` service (Postgres 16) reading `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` from `.env`
- [ ] Run `docker compose up -d db` and confirm the container is healthy (`docker compose ps`)
- [ ] Add `POSTGRES_HOST=localhost` and `POSTGRES_PORT=5432` to `.env` alongside the existing three vars (nothing reads `.env` in Python yet — that's Part B)

## Part B — Dependencies

- [ ] Install `sqlalchemy`, `psycopg2-binary`, `alembic`, `python-dotenv` into the venv
- [ ] Freeze them into `requirements.txt`

## Part C — Domain model (no framework dependency)

- [ ] Create `app/domain/email.py` — a plain dataclass `Email` (no SQLAlchemy import here) with fields like `gmail_id`, `subject`, `sender`, `processed`, `received_at`. This is the shape the rest of the app (LLM step in v3, etc.) works with — it shouldn't know or care that Postgres exists.

## Part D — DB adapter (SQLAlchemy)

- [ ] Create `app/adapters/db/session.py` — builds the SQLAlchemy `engine` and a `SessionLocal` factory, reading host/port/user/password/db from env vars (via `python-dotenv`)
- [ ] Create `app/adapters/db/models.py` — an `EmailORM` table: `id` (PK), `gmail_id` (**unique** — this is what makes idempotency possible), `subject`, `sender`, `processed` (bool, default `False`), `received_at`, `user_id` (just hardcode a constant for now — no user table yet, but per the roadmap's locked-in decision this column exists from day one so it's not a painful migration later)
- [ ] Run `alembic init alembic`, point `alembic/env.py` at your model's `Base.metadata` so autogenerate can see it
- [ ] Generate the first migration (`alembic revision --autogenerate -m "create emails table"`) and inspect the generated file before running it
- [ ] Apply it: `alembic upgrade head`

## Part E — Repository (port + adapter)

This is the hexagonal piece the roadmap calls for: business logic should depend on an interface, not on SQLAlchemy directly.

- [ ] Define the port: `app/repositories/email_repository.py` — an interface (ABC or `Protocol`) with something like `save(email: Email) -> None` and `exists(gmail_id: str) -> bool`
- [ ] Implement it: `app/adapters/db/email_repository_impl.py` — a class that satisfies that interface using the `SessionLocal` + `EmailORM` from Part D

## Part F — Wire it into the fetch flow

- [ ] Update `scripts/fetch_unread.py` so that for each email `list_unread_messages()` returns: check `repository.exists(gmail_id)` first — skip if already stored; otherwise build an `Email` domain object and `repository.save(...)` it

## Part G — Verify it actually works

- [ ] Run the updated script. Confirm rows show up in Postgres (`docker exec -it <container> psql -U <user> -d <db> -c "select * from emails;"`)
- [ ] **Run the script a second time.** Row count should stay the same — proves `exists()` is preventing duplicate inserts instead of re-saving every run.

---

Once Part G passes, v2 is done and we move to **v3**: one LLM call per email for summary + classification.
