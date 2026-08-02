from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Category(str, Enum):
    JOB_LEAD = "job_lead"
    CRITICAL_ALERT = "critical_alert"
    NEWSLETTER = "newsletter"
    PROMOTION = "promotion"
    OTHER = "other"


@dataclass
class Classification:
    summary: str
    category: Category


@dataclass
class GmailMessage:
    gmail_id: str
    subject: str
    sender: str
    received_at: datetime
    label_ids: list[str]


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
