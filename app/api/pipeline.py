from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.adapters.db.email_repository_impl import SqlEmailRepository
from app.adapters.db.user_repository_impl import SqlUserRepository
from app.adapters.gmail_adapter import get_gmail_service, get_user_email, list_unread_messages
from app.adapters.llm.openai_classifier import classify_email
from app.domain.email import Email

router = APIRouter()

# Gmail's own inbox categorization — treated as free, obvious noise.
# CATEGORY_UPDATES is deliberately excluded: it can contain real signal
# (interview confirmations, application status) alongside receipts/bills,
# so those still go through the real classifier.
GMAIL_NOISE_LABELS = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL"}

RELEVANT_CATEGORIES = {"job_lead", "critical_alert"}

# If the caller doesn't send `after`, default to the last 24h rather than
# fetching every unread email ever — unbounded fetch means one Gmail call
# (+ possibly one OpenAI call) per unread message, which doesn't scale.
DEFAULT_LOOKBACK = timedelta(days=1)


class PipelineRequest(BaseModel):
    after: datetime | None = None
    before: datetime | None = None


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/pipeline/run")
def run_pipeline(request: PipelineRequest = PipelineRequest()):
    service = get_gmail_service()

    user_repository = SqlUserRepository()
    user_id = user_repository.get_or_create(get_user_email(service))

    after, before = request.after, request.before
    if after is None and before is None:
        after = datetime.now(timezone.utc) - DEFAULT_LOOKBACK
    elif after is None:
        after = before - DEFAULT_LOOKBACK
    elif before is None:
        before = after + DEFAULT_LOOKBACK

    emails = list_unread_messages(service, after=after, before=before)
    email_repository = SqlEmailRepository()

    results = []
    for email in emails:
        if email_repository.exists(email["gmail_id"]):
            results.append({"subject": email["subject"], "status": "skipped"})
            continue

        if GMAIL_NOISE_LABELS & set(email["label_ids"]):
            summary = None
            category = "promotion"
        else:
            classification = classify_email(subject=email["subject"], sender=email["sender"])
            summary = classification.summary
            category = classification.category.value

        email_repository.save(
            Email(
                gmail_id=email["gmail_id"],
                subject=email["subject"],
                sender=email["sender"],
                received_at=email["received_at"],
                user_id=user_id,
                summary=summary,
                category=category,
            )
        )

        results.append(
            {
                "subject": email["subject"],
                "status": "saved",
                "summary": summary,
                "category": category,
            }
        )

    saved = [r for r in results if r["status"] == "saved"]
    relevant = sum(1 for r in saved if r["category"] in RELEVANT_CATEGORIES)

    return {
        "processed": len(results),
        "saved": len(saved),
        "relevant": relevant,
        "ignored": len(saved) - relevant,
        "results": results,
    }
