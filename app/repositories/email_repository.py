from typing import Protocol

from app.domain.email import Email


class EmailRepository(Protocol):
    def save(self, email: Email) -> None: ...

    def exists(self, gmail_id: str) -> bool: ...
