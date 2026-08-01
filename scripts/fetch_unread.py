from app.adapters.gmail_adapter import get_gmail_service, list_unread_messages

if __name__ == "__main__":
    service = get_gmail_service()
    emails = list_unread_messages(service)

    if not emails:
        print("No unread emails.")
    else:
        for email in emails:
            print(f"From: {email['sender']}")
            print(f"Subject: {email['subject']}")
            print("-" * 40)
