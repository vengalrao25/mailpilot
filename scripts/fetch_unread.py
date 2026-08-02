from app.adapters.database.repositories import SqlEmailRepository, SqlUserRepository
from app.adapters.gmail.client import GmailClient
from app.core.config import get_settings
from app.core.database import get_sessionmaker
from app.domain.email import Email

if __name__ == "__main__":
    settings = get_settings()
    gmail = GmailClient(
        token_path=settings.gmail_token_path, credentials_path=settings.gmail_credentials_path
    )
    session_factory = get_sessionmaker(settings)
    email_repository = SqlEmailRepository(session_factory=session_factory)
    user_repository = SqlUserRepository(session_factory=session_factory)

    user_id = user_repository.get_or_create(gmail.get_user_email())
    emails = gmail.list_unread_messages()

    if not emails:
        print("No unread emails.")

    for email in emails:
        if email_repository.exists(email.gmail_id):
            print(f"Skipping (already saved): {email.subject}")
            continue

        email_repository.save(
            Email(
                gmail_id=email.gmail_id,
                subject=email.subject,
                sender=email.sender,
                received_at=email.received_at,
                user_id=user_id,
            )
        )
        print(f"Saved: {email.subject}")
