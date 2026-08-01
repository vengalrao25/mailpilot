from app.adapters.db.email_repository_impl import SqlEmailRepository
from app.adapters.gmail_adapter import get_gmail_service, list_unread_messages
from app.domain.email import Email

if __name__ == "__main__":
    service = get_gmail_service()
    emails = list_unread_messages(service)
    repository = SqlEmailRepository()

    if not emails:
        print("No unread emails.")

    for email in emails:
        if repository.exists(email["gmail_id"]):
            print(f"Skipping (already saved): {email['subject']}")
            continue

        repository.save(
            Email(
                gmail_id=email["gmail_id"],
                subject=email["subject"],
                sender=email["sender"],
                received_at=email["received_at"],
            )
        )
        print(f"Saved: {email['subject']}")
