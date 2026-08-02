import os
from datetime import datetime, timezone

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


def get_user_email(service):
    profile = service.users().getProfile(userId="me").execute()
    return profile["emailAddress"]


def list_unread_messages(service, after=None, before=None):
    """List unread messages, optionally within a UTC [after, before) window.

    Gmail's own after:/before: query operators are used as a coarse,
    over-inclusive pre-filter (cheap — narrows what we even fetch), but
    Gmail's date-operator timezone handling is inconsistent, so the real
    boundary check happens in Python against `received_at`, which is
    computed precisely from `internalDate` (epoch ms, unambiguous).
    """
    query = "is:unread"
    if after is not None:
        query += f" after:{after.strftime('%Y/%m/%d')}"
    if before is not None:
        query += f" before:{before.strftime('%Y/%m/%d')}"

    # "me" refers to whichever account authorized via OAuth — there's no
    # user table yet, so this is the only identity the app has.
    # list() only returns message IDs, not content — Gmail keeps listing
    # cheap and makes you fetch each message separately for details.
    message_ids = []
    page_token = None
    while True:
        response = (
            service.users()
            .messages()
            .list(userId="me", q=query, pageToken=page_token)
            .execute()
        )
        message_ids.extend(m["id"] for m in response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    emails = []
    for message_id in message_ids:
        # format="metadata" + metadataHeaders avoids pulling the full
        # MIME body (base64-encoded blob) when we only need two headers.
        detail = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
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

        # internalDate is epoch milliseconds, returned by default
        # regardless of `format` — it's not part of payload/headers.
        received_at = datetime.fromtimestamp(int(detail["internalDate"]) / 1000, tz=timezone.utc)

        if after is not None and received_at < after:
            continue
        if before is not None and received_at >= before:
            continue

        emails.append(
            {
                "gmail_id": message_id,
                "subject": subject,
                "sender": sender,
                "received_at": received_at,
                "label_ids": detail.get("labelIds", []),
            }
        )

    return emails
