from datetime import datetime, timezone

from app.domain.email import Category, Classification
from app.workflows.email_pipeline.graph import build_pipeline_graph
from tests.fixtures.fakes import FakeClassifier, FakeEmailRepository, FakeGmailClient


def make_state(gmail_id="g1", subject="Hi", sender="a@b.com", label_ids=None):
    return {
        "gmail_id": gmail_id,
        "subject": subject,
        "sender": sender,
        "received_at": datetime.now(timezone.utc),
        "label_ids": label_ids or [],
        "user_id": 1,
        "body": None,
        "summary": None,
        "category": None,
        "status": "pending",
    }


def test_skips_existing_email():
    email_repository = FakeEmailRepository(existing_gmail_ids=["g1"])
    classifier = FakeClassifier()
    graph = build_pipeline_graph(FakeGmailClient(), classifier, email_repository)

    result = graph.invoke(make_state(gmail_id="g1"))

    assert result["status"] == "skipped"
    assert classifier.calls == []


def test_force_reprocess_reclassifies_existing_email():
    email_repository = FakeEmailRepository(existing_gmail_ids=["g1"])
    classifier = FakeClassifier()
    graph = build_pipeline_graph(FakeGmailClient(), classifier, email_repository, force_reprocess=True)

    result = graph.invoke(make_state(gmail_id="g1", subject="Newsletter"))

    assert result["status"] == "saved"
    assert classifier.calls


def test_promotion_label_skips_classifier_and_saves_directly():
    email_repository = FakeEmailRepository()
    classifier = FakeClassifier()
    graph = build_pipeline_graph(FakeGmailClient(), classifier, email_repository)

    result = graph.invoke(make_state(label_ids=["CATEGORY_PROMOTIONS"]))

    assert result["status"] == "saved"
    assert result["category"] == "promotion"
    assert result["summary"] is None
    assert classifier.calls == []
    assert email_repository.exists("g1")


def test_social_label_also_treated_as_noise():
    graph = build_pipeline_graph(FakeGmailClient(), FakeClassifier(), FakeEmailRepository())

    result = graph.invoke(make_state(label_ids=["CATEGORY_SOCIAL"]))

    assert result["category"] == "promotion"


def test_category_updates_label_still_goes_through_classifier():
    """CATEGORY_UPDATES is deliberately not in the noise set — it can
    contain real signal (interview confirmations) alongside receipts."""
    classifier = FakeClassifier(default=Classification(summary="s", category=Category.OTHER))
    graph = build_pipeline_graph(FakeGmailClient(), classifier, FakeEmailRepository())

    graph.invoke(make_state(label_ids=["CATEGORY_UPDATES"]))

    assert classifier.calls


def test_relevant_category_triggers_body_fetch_and_reclassify():
    subject = "Job offer"
    classifier = FakeClassifier(
        responses={
            subject: Classification(summary="looks like a lead", category=Category.JOB_LEAD),
            f"{subject}::body": Classification(
                summary="confirmed job lead", category=Category.JOB_LEAD
            ),
        }
    )
    gmail = FakeGmailClient(bodies={"g1": "Full email body text"})
    email_repository = FakeEmailRepository()
    graph = build_pipeline_graph(gmail, classifier, email_repository)

    result = graph.invoke(make_state(subject=subject))

    assert gmail.body_calls == ["g1"]
    assert len(classifier.calls) == 2
    assert classifier.calls[1][2] == "Full email body text"
    assert result["status"] == "saved"
    assert result["summary"] == "confirmed job lead"
    assert result["category"] == "job_lead"


def test_critical_alert_is_also_relevant():
    subject = "Server down"
    classifier = FakeClassifier(
        responses={subject: Classification(summary="uh oh", category=Category.CRITICAL_ALERT)}
    )
    gmail = FakeGmailClient(bodies={"g1": "prod is on fire"})
    graph = build_pipeline_graph(gmail, classifier, FakeEmailRepository())

    graph.invoke(make_state(subject=subject))

    assert gmail.body_calls == ["g1"]


def test_non_relevant_category_saves_directly_without_body_fetch():
    subject = "Weekly newsletter"
    classifier = FakeClassifier(
        responses={subject: Classification(summary="a newsletter", category=Category.NEWSLETTER)}
    )
    gmail = FakeGmailClient()
    graph = build_pipeline_graph(gmail, classifier, FakeEmailRepository())

    result = graph.invoke(make_state(subject=subject))

    assert gmail.body_calls == []
    assert len(classifier.calls) == 1
    assert result["status"] == "saved"
    assert result["category"] == "newsletter"


def test_saved_email_persisted_in_repository():
    email_repository = FakeEmailRepository()
    graph = build_pipeline_graph(FakeGmailClient(), FakeClassifier(), email_repository)

    graph.invoke(make_state(gmail_id="g42"))

    assert email_repository.exists("g42")
