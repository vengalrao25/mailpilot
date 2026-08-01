import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"


def get_gmail_service():
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def list_unread_messages(service, max_results=10):
    # "me" refers to whichever account authorized via OAuth — there's no
    # user table yet, so this is the only identity the app has.
    # list() only returns message IDs, not content — Gmail keeps listing
    # cheap and makes you fetch each message separately for details.
    response = (
        service.users()
        .messages()
        .list(userId="me", q="is:unread", maxResults=max_results)
        .execute()
    )

    messages = response.get("messages", [])

    emails = []
    for message in messages:
        # format="metadata" + metadataHeaders avoids pulling the full
        # MIME body (base64-encoded blob) when we only need two headers.
        detail = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message["id"],
                format="metadata",
                metadataHeaders=["Subject", "From"],
            )
            .execute()
        )

        # headers is a flat list of {"name", "value"} dicts, not a dict
        # keyed by name, so we search it rather than index into it.
        headers = detail.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(no subject)")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "(unknown sender)")

        emails.append({"subject": subject, "sender": sender})

    return emails
