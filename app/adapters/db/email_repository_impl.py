from app.adapters.db.models import EmailORM
from app.adapters.db.session import SessionLocal
from app.domain.email import Email


class SqlEmailRepository:
    def save(self, email: Email) -> None:
        with SessionLocal() as session:
            row = EmailORM(
                gmail_id=email.gmail_id,
                subject=email.subject,
                sender=email.sender,
                received_at=email.received_at,
                processed=email.processed,
                summary=email.summary,
                category=email.category,
                user_id=email.user_id,
            )
            session.add(row)
            session.commit()

    def exists(self, gmail_id: str) -> bool:
        with SessionLocal() as session:
            return (
                session.query(EmailORM).filter_by(gmail_id=gmail_id).first()
                is not None
            )
