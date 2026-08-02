import base64
import os
from datetime import datetime, timezone
from html.parser import HTMLParser

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.domain.email import GmailMessage
from app.domain.errors import ExternalServiceError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _build_service(token_path: str, credentials_path: str):
    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


class GmailClient:
    """Thin wrapper around the Gmail API implementing `GmailPort`.

    OAuth happens once, in `__init__` — callers get a ready-to-use client
    rather than each method re-authenticating.
    """

    def __init__(self, token_path: str = "token.json", credentials_path: str = "credentials.json"):
        try:
            self._service = _build_service(token_path, credentials_path)
        except (GoogleAuthError, FileNotFoundError, OSError) as exc:
            raise ExternalServiceError(f"Gmail authentication failed: {exc}") from exc

    def get_user_email(self) -> str:
        try:
            profile = self._service.users().getProfile(userId="me").execute()
        except HttpError as exc:
            raise ExternalServiceError(f"Gmail getProfile failed: {exc}") from exc
        return profile["emailAddress"]

    def list_unread_messages(
        self, after: datetime | None = None, before: datetime | None = None
    ) -> list[GmailMessage]:
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

        try:
            message_ids = self._list_message_ids(query)
            messages = [self._fetch_message_metadata(mid) for mid in message_ids]
        except HttpError as exc:
            raise ExternalServiceError(f"Gmail message listing failed: {exc}") from exc

        emails = []
        for message in messages:
            if after is not None and message.received_at < after:
                continue
            if before is not None and message.received_at >= before:
                continue
            emails.append(message)

        return emails

    def _list_message_ids(self, query: str) -> list[str]:
        # "me" refers to whichever account authorized via OAuth — there's no
        # user table yet, so this is the only identity the app has.
        # list() only returns message IDs, not content — Gmail keeps listing
        # cheap and makes you fetch each message separately for details.
        message_ids = []
        page_token = None
        while True:
            response = (
                self._service.users()
                .messages()
                .list(userId="me", q=query, pageToken=page_token)
                .execute()
            )
            message_ids.extend(m["id"] for m in response.get("messages", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return message_ids

    def _fetch_message_metadata(self, message_id: str) -> GmailMessage:
        # format="metadata" + metadataHeaders avoids pulling the full
        # MIME body (base64-encoded blob) when we only need two headers.
        detail = (
            self._service.users()
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

        return GmailMessage(
            gmail_id=message_id,
            subject=subject,
            sender=sender,
            received_at=received_at,
            label_ids=detail.get("labelIds", []),
        )

    def get_message_body(self, gmail_id: str, max_chars: int = 500) -> str:
        """Fetch and return the plain-text body of a message, truncated to max_chars.

        Only called for emails that already passed the cheap subject-based
        classification — full-body fetch (format="full") is the expensive path.
        """
        try:
            detail = (
                self._service.users()
                .messages()
                .get(userId="me", id=gmail_id, format="full")
                .execute()
            )
        except HttpError as exc:
            raise ExternalServiceError(f"Gmail message fetch failed: {exc}") from exc

        body_text = self._extract_plain_text(gmail_id, detail.get("payload", {}))
        return body_text[:max_chars]

    def _extract_plain_text(self, message_id: str, payload: dict) -> str:
        plain = self._find_part(message_id, payload, "text/plain")
        if plain:
            return plain

        html = self._find_part(message_id, payload, "text/html")
        if html:
            return _html_to_text(html)

        # Neither text part present — e.g. an image-only email. Nothing to extract.
        return ""

    def _find_part(self, message_id: str, payload: dict, mime_type: str) -> str | None:
        """Recurse into a (possibly multipart) message payload for the first
        part matching mime_type, base64-decoded. Returns None if absent —
        e.g. an image/attachment-only part, which we deliberately skip."""
        body = payload.get("body", {})
        if payload.get("mimeType") == mime_type:
            # Gmail inlines small bodies as body.data, but above a size
            # threshold it omits data and gives an attachmentId instead,
            # requiring a separate fetch to get the actual content.
            data = body.get("data")
            if not data and body.get("attachmentId"):
                data = self._fetch_attachment_data(message_id, body["attachmentId"])
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        for part in payload.get("parts", []) or []:
            result = self._find_part(message_id, part, mime_type)
            if result:
                return result

        return None

    def _fetch_attachment_data(self, message_id: str, attachment_id: str) -> str | None:
        attachment = (
            self._service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        return attachment.get("data")


class _HTMLTextExtractor(HTMLParser):
    """Strips tags/scripts/styles, keeping only visible text — HTML emails
    can run to tens of KB of markup for a couple sentences of content, and
    raw tags would just burn tokens without helping the classifier."""

    def __init__(self):
        super().__init__()
        self._chunks = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._chunks.append(data)

    def get_text(self) -> str:
        return " ".join(" ".join(self._chunks).split())


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()
