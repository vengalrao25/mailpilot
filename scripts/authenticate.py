from app.adapters.gmail_adapter import get_gmail_service

if __name__ == "__main__":
    service = get_gmail_service()
    if service:
        print("Authenticated successfully")
