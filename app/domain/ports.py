from datetime import datetime
from typing import Protocol

from app.domain.email import Classification, GmailMessage


class GmailPort(Protocol):
    def get_user_email(self) -> str: ...

    def list_unread_messages(
        self, after: datetime | None = None, before: datetime | None = None
    ) -> list[GmailMessage]: ...

    def get_message_body(self, gmail_id: str, max_chars: int = 500) -> str: ...


class ClassifierPort(Protocol):
    def classify(
        self, subject: str, sender: str, body: str | None = None
    ) -> Classification: ...
