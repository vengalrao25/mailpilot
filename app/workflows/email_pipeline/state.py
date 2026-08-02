from datetime import datetime
from typing import TypedDict


class EmailState(TypedDict):
    gmail_id: str
    subject: str
    sender: str
    received_at: datetime
    label_ids: list[str]
    user_id: int
    body: str | None
    summary: str | None
    category: str | None
    status: str  # "pending" -> "skipped" | "saved"
