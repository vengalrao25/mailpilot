from datetime import datetime, timezone

from app.adapters.database.models import EmailORM
from app.adapters.database.repositories import SqlEmailRepository, SqlUserRepository
from app.domain.email import Email


def test_email_repository_save_and_exists(db_session_factory):
    email_repo = SqlEmailRepository(session_factory=db_session_factory)
    user_id = SqlUserRepository(session_factory=db_session_factory).get_or_create("a@b.com")
    assert email_repo.exists("abc") is False

    email_repo.save(
        Email(
            gmail_id="abc",
            subject="Hi",
            sender="a@b.com",
            received_at=datetime.now(timezone.utc),
            user_id=user_id,
            summary="s",
            category="other",
        )
    )

    assert email_repo.exists("abc") is True


def test_email_repository_save_is_an_upsert(db_session_factory):
    repo = SqlEmailRepository(session_factory=db_session_factory)
    user_id = SqlUserRepository(session_factory=db_session_factory).get_or_create("a@b.com")
    email = Email(
        gmail_id="abc", subject="v1", sender="a@b.com", received_at=datetime.now(timezone.utc),
        user_id=user_id,
    )
    repo.save(email)

    email.subject = "v2"
    email.category = "job_lead"
    repo.save(email)

    with db_session_factory() as session:
        rows = session.query(EmailORM).filter_by(gmail_id="abc").all()

    assert len(rows) == 1
    assert rows[0].subject == "v2"
    assert rows[0].category == "job_lead"


def test_user_repository_get_or_create_is_idempotent(db_session_factory):
    repo = SqlUserRepository(session_factory=db_session_factory)

    first_id = repo.get_or_create("user@example.com")
    second_id = repo.get_or_create("user@example.com")

    assert first_id == second_id


def test_user_repository_creates_distinct_users(db_session_factory):
    repo = SqlUserRepository(session_factory=db_session_factory)

    id_a = repo.get_or_create("a@example.com")
    id_b = repo.get_or_create("b@example.com")

    assert id_a != id_b
