from sqlalchemy.orm import sessionmaker

from app.adapters.database.models import EmailORM, UserORM
from app.adapters.database.session import session_scope
from app.domain.email import Email


class SqlEmailRepository:
    def __init__(self, session_factory: sessionmaker | None = None):
        self._session_factory = session_factory

    def save(self, email: Email) -> None:
        with session_scope(self._session_factory) as session:
            row = session.query(EmailORM).filter_by(gmail_id=email.gmail_id).first()
            if row is None:
                row = EmailORM(gmail_id=email.gmail_id)
                session.add(row)

            row.subject = email.subject
            row.sender = email.sender
            row.received_at = email.received_at
            row.processed = email.processed
            row.summary = email.summary
            row.category = email.category
            row.user_id = email.user_id

            session.commit()

    def exists(self, gmail_id: str) -> bool:
        with session_scope(self._session_factory) as session:
            return (
                session.query(EmailORM).filter_by(gmail_id=gmail_id).first() is not None
            )


class SqlUserRepository:
    def __init__(self, session_factory: sessionmaker | None = None):
        self._session_factory = session_factory

    def get_or_create(self, email: str) -> int:
        with session_scope(self._session_factory) as session:
            user = session.query(UserORM).filter_by(email=email).first()
            if user:
                return user.id

            user = UserORM(email=email)
            session.add(user)
            session.commit()
            session.refresh(user)
            return user.id
