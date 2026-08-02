"""In-memory fakes for the domain ports — let nodes/services/routes be
tested without real Gmail, OpenAI, or Postgres calls."""

from datetime import datetime, timezone
from typing import Iterable

from app.domain.email import Category, Classification, Email, GmailMessage
from app.domain.errors import ExternalServiceError


class FakeGmailClient:
    def __init__(
        self,
        messages: Iterable[GmailMessage] | None = None,
        user_email: str = "user@example.com",
        bodies: dict[str, str] | None = None,
        raise_on_list: bool = False,
        raise_on_body: bool = False,
    ):
        self._messages = list(messages or [])
        self._user_email = user_email
        self._bodies = bodies or {}
        self._raise_on_list = raise_on_list
        self._raise_on_body = raise_on_body
        self.list_calls: list[tuple[datetime | None, datetime | None]] = []
        self.body_calls: list[str] = []

    def get_user_email(self) -> str:
        return self._user_email

    def list_unread_messages(
        self, after: datetime | None = None, before: datetime | None = None
    ) -> list[GmailMessage]:
        self.list_calls.append((after, before))
        if self._raise_on_list:
            raise ExternalServiceError("simulated Gmail list failure")

        result = []
        for message in self._messages:
            if after is not None and message.received_at < after:
                continue
            if before is not None and message.received_at >= before:
                continue
            result.append(message)
        return result

    def get_message_body(self, gmail_id: str, max_chars: int = 500) -> str:
        self.body_calls.append(gmail_id)
        if self._raise_on_body:
            raise ExternalServiceError("simulated Gmail body-fetch failure")
        return self._bodies.get(gmail_id, "")[:max_chars]


class FakeClassifier:
    """Programmed by subject: `responses[subject]` is used for the
    subject-only pass, `responses[subject + "::body"]` for the reclassify
    pass (when a body is present)."""

    def __init__(
        self,
        responses: dict[str, Classification] | None = None,
        default: Classification | None = None,
        raise_error: bool = False,
    ):
        self._responses = responses or {}
        self._default = default or Classification(summary="default summary", category=Category.OTHER)
        self._raise_error = raise_error
        self.calls: list[tuple[str, str, str | None]] = []

    def classify(self, subject: str, sender: str, body: str | None = None) -> Classification:
        self.calls.append((subject, sender, body))
        if self._raise_error:
            raise ExternalServiceError("simulated OpenAI failure")

        key = f"{subject}::body" if body else subject
        return self._responses.get(key, self._responses.get(subject, self._default))


class FakeEmailRepository:
    def __init__(self, existing_gmail_ids: Iterable[str] | None = None):
        self._saved: dict[str, Email] = {}
        for gmail_id in existing_gmail_ids or []:
            self._saved[gmail_id] = Email(
                gmail_id=gmail_id,
                subject="(preexisting)",
                sender="(preexisting)",
                received_at=datetime.now(timezone.utc),
                user_id=0,
            )

    def save(self, email: Email) -> None:
        self._saved[email.gmail_id] = email

    def exists(self, gmail_id: str) -> bool:
        return gmail_id in self._saved

    def all(self) -> list[Email]:
        return list(self._saved.values())


class FakeUserRepository:
    def __init__(self):
        self._users: dict[str, int] = {}
        self._next_id = 1
        self.calls: list[str] = []

    def get_or_create(self, email: str) -> int:
        self.calls.append(email)
        if email not in self._users:
            self._users[email] = self._next_id
            self._next_id += 1
        return self._users[email]
