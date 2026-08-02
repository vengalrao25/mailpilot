from dataclasses import dataclass
from datetime import datetime


@dataclass
class Email:
    gmail_id: str
    subject: str
    sender: str
    received_at: datetime
    user_id: int
    processed: bool = False
    summary: str | None = None
    category: str | None = None
