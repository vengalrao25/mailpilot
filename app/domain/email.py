from dataclasses import dataclass
from datetime import datetime


@dataclass
class Email:
    gmail_id: str
    subject: str
    sender: str
    received_at: datetime
    processed: bool = False
