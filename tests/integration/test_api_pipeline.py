from datetime import datetime, timezone

from app.domain.email import Category, Classification, GmailMessage
from tests.fixtures.fakes import FakeClassifier, FakeEmailRepository, FakeGmailClient

WINDOW = {"after": "2025-12-31T00:00:00+00:00", "before": "2026-01-02T00:00:00+00:00"}


def test_pipeline_run_defaults_to_empty_result(client_factory):
    client = client_factory()

    response = client.post("/pipeline/run", json={})

    assert response.status_code == 200
    assert response.json() == {"processed": 0, "saved": 0, "relevant": 0, "ignored": 0, "results": []}


def test_pipeline_run_rejects_after_not_before_window(client_factory):
    client = client_factory()

    response = client.post(
        "/pipeline/run", json={"after": "2026-01-05T00:00:00Z", "before": "2026-01-01T00:00:00Z"}
    )

    assert response.status_code == 422


def test_pipeline_run_rejects_invalid_datetime(client_factory):
    client = client_factory()

    response = client.post("/pipeline/run", json={"after": "not-a-date"})

    assert response.status_code == 422


def test_pipeline_run_explicit_window_passed_through(client_factory):
    gmail = FakeGmailClient()
    client = client_factory(gmail=gmail)

    client.post("/pipeline/run", json=WINDOW)

    after_arg, before_arg = gmail.list_calls[0]
    assert after_arg == datetime.fromisoformat(WINDOW["after"])
    assert before_arg == datetime.fromisoformat(WINDOW["before"])


def test_pipeline_run_default_window_applied(client_factory):
    gmail = FakeGmailClient()
    client = client_factory(gmail=gmail)

    client.post("/pipeline/run", json={})

    after_arg, before_arg = gmail.list_calls[0]
    assert before_arg is None
    assert after_arg is not None


def test_pipeline_run_skips_existing_email(client_factory):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    messages = [GmailMessage(gmail_id="dup", subject="Dup", sender="a@b.com", received_at=now, label_ids=[])]
    gmail = FakeGmailClient(messages=messages)
    email_repository = FakeEmailRepository(existing_gmail_ids=["dup"])
    client = client_factory(gmail=gmail, email_repository=email_repository)

    response = client.post("/pipeline/run", json=WINDOW)

    body = response.json()
    assert body["processed"] == 1
    assert body["saved"] == 0
    assert body["results"][0]["status"] == "skipped"


def test_pipeline_run_filters_gmail_promotions(client_factory):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    messages = [
        GmailMessage(
            gmail_id="p1", subject="50% off", sender="shop@x.com", received_at=now,
            label_ids=["CATEGORY_PROMOTIONS"],
        )
    ]
    gmail = FakeGmailClient(messages=messages)
    classifier = FakeClassifier()
    client = client_factory(gmail=gmail, classifier=classifier)

    response = client.post("/pipeline/run", json=WINDOW)

    body = response.json()
    assert body["results"][0]["category"] == "promotion"
    assert classifier.calls == []


def test_pipeline_run_relevant_category_uses_reclassified_result(client_factory):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    subject = "Interview invite"
    messages = [GmailMessage(gmail_id="lead1", subject=subject, sender="hr@x.com", received_at=now, label_ids=[])]
    classifier = FakeClassifier(
        responses={
            subject: Classification(summary="maybe a lead", category=Category.JOB_LEAD),
            f"{subject}::body": Classification(summary="confirmed interview", category=Category.JOB_LEAD),
        }
    )
    gmail = FakeGmailClient(messages=messages, bodies={"lead1": "We'd like to interview you"})
    client = client_factory(gmail=gmail, classifier=classifier)

    response = client.post("/pipeline/run", json=WINDOW)

    body = response.json()
    assert body["results"][0]["summary"] == "confirmed interview"
    assert body["relevant"] == 1
    assert gmail.body_calls == ["lead1"]


def test_pipeline_run_non_relevant_category_saved_directly(client_factory):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    subject = "Weekly newsletter"
    messages = [GmailMessage(gmail_id="n1", subject=subject, sender="news@x.com", received_at=now, label_ids=[])]
    classifier = FakeClassifier(
        responses={subject: Classification(summary="a newsletter", category=Category.NEWSLETTER)}
    )
    gmail = FakeGmailClient(messages=messages)
    client = client_factory(gmail=gmail, classifier=classifier)

    response = client.post("/pipeline/run", json=WINDOW)

    body = response.json()
    assert body["results"][0]["category"] == "newsletter"
    assert body["ignored"] == 1
    assert body["relevant"] == 0
    assert gmail.body_calls == []


def test_pipeline_run_counts_across_categories(client_factory):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    messages = [
        GmailMessage(
            gmail_id="promo", subject="Sale!", sender="shop@x.com", received_at=now,
            label_ids=["CATEGORY_PROMOTIONS"],
        ),
        GmailMessage(gmail_id="news", subject="Digest", sender="n@x.com", received_at=now, label_ids=[]),
        GmailMessage(gmail_id="lead", subject="Job offer", sender="hr@x.com", received_at=now, label_ids=[]),
    ]
    classifier = FakeClassifier(
        responses={
            "Digest": Classification(summary="d", category=Category.NEWSLETTER),
            "Job offer": Classification(summary="maybe", category=Category.JOB_LEAD),
            "Job offer::body": Classification(summary="confirmed", category=Category.JOB_LEAD),
        }
    )
    gmail = FakeGmailClient(messages=messages)
    client = client_factory(gmail=gmail, classifier=classifier)

    response = client.post("/pipeline/run", json=WINDOW)

    body = response.json()
    assert body["processed"] == 3
    assert body["saved"] == 3
    assert body["relevant"] == 1
    assert body["ignored"] == 2


def test_pipeline_run_gmail_failure_returns_502(client_factory):
    gmail = FakeGmailClient(raise_on_list=True)
    client = client_factory(gmail=gmail)

    response = client.post("/pipeline/run", json={})

    assert response.status_code == 502
    assert "detail" in response.json()


def test_pipeline_run_classifier_failure_returns_502(client_factory):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    messages = [GmailMessage(gmail_id="g1", subject="Hi", sender="a@b.com", received_at=now, label_ids=[])]
    gmail = FakeGmailClient(messages=messages)
    classifier = FakeClassifier(raise_error=True)
    client = client_factory(gmail=gmail, classifier=classifier)

    response = client.post("/pipeline/run", json=WINDOW)

    assert response.status_code == 502


def test_dependency_overrides_isolate_from_real_adapters(client_factory):
    """Proves DI: the route never constructs a real GmailClient/OpenAIClassifier
    when the leaf providers are overridden — no credentials.json/token.json/
    OPENAI_API_KEY is ever touched for this request."""
    gmail = FakeGmailClient()
    client = client_factory(gmail=gmail, classifier=FakeClassifier())

    response = client.post("/pipeline/run", json={})

    assert response.status_code == 200
    assert gmail.list_calls
