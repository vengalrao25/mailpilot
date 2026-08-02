"""Graph node factories.

Every node needs an external dependency (a repository, the Gmail client,
the classifier) to do its job, but nodes must not construct those
themselves — `graph.py` builds each node by calling the matching
`make_*_node()` factory with dependencies it received from the caller
(ultimately, a FastAPI dependency or a test fixture). That's what makes
the graph testable without real Gmail/OpenAI/DB calls.
"""

from app.domain.email import Category, Email
from app.domain.ports import ClassifierPort, GmailPort
from app.domain.repositories import EmailRepository
from app.workflows.email_pipeline.state import EmailState

# Gmail's own inbox categorization — treated as free, obvious noise.
# CATEGORY_UPDATES is deliberately excluded: it can contain real signal
# (interview confirmations, application status) alongside receipts/bills,
# so those still go through the real classifier.
GMAIL_NOISE_LABELS = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL"}

# Categories worth the extra cost of a body fetch + reclassify pass.
RELEVANT_CATEGORIES = {Category.JOB_LEAD, Category.CRITICAL_ALERT}


def make_check_existing_node(email_repository: EmailRepository, force_reprocess: bool = False):
    def check_existing(state: EmailState) -> dict:
        if not force_reprocess and email_repository.exists(state["gmail_id"]):
            return {"status": "skipped"}
        return {"status": "pending"}

    return check_existing


def route_after_check(state: EmailState) -> str:
    return "classify" if state["status"] == "pending" else "__end__"


def make_classify_node(classifier: ClassifierPort):
    def classify(state: EmailState) -> dict:
        if GMAIL_NOISE_LABELS & set(state["label_ids"]):
            return {"summary": None, "category": Category.PROMOTION.value}

        classification = classifier.classify(subject=state["subject"], sender=state["sender"])
        return {"summary": classification.summary, "category": classification.category.value}

    return classify


def route_after_classify(state: EmailState) -> str:
    return "fetch_body" if state["category"] in RELEVANT_CATEGORIES else "save"


def make_fetch_body_node(gmail: GmailPort):
    def fetch_body(state: EmailState) -> dict:
        body = gmail.get_message_body(state["gmail_id"])
        return {"body": body}

    return fetch_body


def make_reclassify_node(classifier: ClassifierPort):
    def reclassify(state: EmailState) -> dict:
        classification = classifier.classify(
            subject=state["subject"], sender=state["sender"], body=state["body"]
        )
        return {"summary": classification.summary, "category": classification.category.value}

    return reclassify


def make_save_node(email_repository: EmailRepository):
    def save(state: EmailState) -> dict:
        email_repository.save(
            Email(
                gmail_id=state["gmail_id"],
                subject=state["subject"],
                sender=state["sender"],
                received_at=state["received_at"],
                user_id=state["user_id"],
                summary=state["summary"],
                category=state["category"],
            )
        )
        return {"status": "saved"}

    return save
