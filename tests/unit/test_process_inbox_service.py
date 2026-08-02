from datetime import datetime, timedelta, timezone

from app.domain.email import Category, Classification, GmailMessage
from app.services.process_inbox import DEFAULT_LOOKBACK, ProcessInboxService
from app.workflows.email_pipeline.graph import build_pipeline_graph
from tests.fixtures.fakes import FakeClassifier, FakeEmailRepository, FakeGmailClient, FakeUserRepository


def build_service(messages=None, classifier=None, email_repository=None, user_repository=None):
    gmail = FakeGmailClient(messages=messages or [])
    classifier = classifier or FakeClassifier()
    email_repository = email_repository or FakeEmailRepository()
    user_repository = user_repository or FakeUserRepository()
    graph = build_pipeline_graph(gmail, classifier, email_repository)
    service = ProcessInboxService(gmail=gmail, user_repository=user_repository, pipeline_graph=graph)
    return service, gmail, classifier, email_repository, user_repository


def test_default_window_both_none():
    service, gmail, *_ = build_service()
    before_call = datetime.now(timezone.utc)

    service.run(after=None, before=None)

    after_arg, before_arg = gmail.list_calls[0]
    assert before_arg is None
    assert abs((after_arg - (before_call - DEFAULT_LOOKBACK)).total_seconds()) < 5


def test_window_before_only_derives_after():
    service, gmail, *_ = build_service()
    before = datetime(2026, 1, 10, tzinfo=timezone.utc)

    service.run(after=None, before=before)

    after_arg, before_arg = gmail.list_calls[0]
    assert after_arg == before - DEFAULT_LOOKBACK
    assert before_arg == before


def test_window_after_only_derives_before():
    service, gmail, *_ = build_service()
    after = datetime(2026, 1, 10, tzinfo=timezone.utc)

    service.run(after=after, before=None)

    after_arg, before_arg = gmail.list_calls[0]
    assert after_arg == after
    assert before_arg == after + DEFAULT_LOOKBACK


def test_window_both_given_passed_through_unchanged():
    service, gmail, *_ = build_service()
    after = datetime(2026, 1, 1, tzinfo=timezone.utc)
    before = datetime(2026, 1, 5, tzinfo=timezone.utc)

    service.run(after=after, before=before)

    assert gmail.list_calls[0] == (after, before)


def test_empty_gmail_result():
    service, *_ = build_service(messages=[])

    result = service.run(
        after=datetime(2026, 1, 1, tzinfo=timezone.utc), before=datetime(2026, 1, 2, tzinfo=timezone.utc)
    )

    assert result.processed == 0
    assert result.saved == []
    assert result.relevant == 0
    assert result.ignored == 0


def test_user_resolved_via_get_or_create():
    service, gmail, _, _, user_repository = build_service()

    service.run(
        after=datetime(2026, 1, 1, tzinfo=timezone.utc), before=datetime(2026, 1, 2, tzinfo=timezone.utc)
    )

    assert user_repository.calls == [gmail.get_user_email()]


def test_skip_path_not_counted_as_saved():
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    messages = [GmailMessage(gmail_id="dup", subject="Dup", sender="a@b.com", received_at=now, label_ids=[])]
    email_repository = FakeEmailRepository(existing_gmail_ids=["dup"])
    service, *_ = build_service(messages=messages, email_repository=email_repository)

    result = service.run(after=now - timedelta(days=1), before=now + timedelta(days=1))

    assert result.processed == 1
    assert result.saved == []


def test_pipeline_response_counts_across_paths():
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    messages = [
        GmailMessage(
            gmail_id="promo", subject="Sale!", sender="shop@x.com", received_at=now,
            label_ids=["CATEGORY_PROMOTIONS"],
        ),
        GmailMessage(
            gmail_id="news", subject="Weekly Digest", sender="news@x.com", received_at=now, label_ids=[]
        ),
        GmailMessage(
            gmail_id="lead", subject="Job offer", sender="hr@x.com", received_at=now, label_ids=[]
        ),
    ]
    classifier = FakeClassifier(
        responses={
            "Weekly Digest": Classification(summary="digest", category=Category.NEWSLETTER),
            "Job offer": Classification(summary="maybe", category=Category.JOB_LEAD),
            "Job offer::body": Classification(summary="confirmed", category=Category.JOB_LEAD),
        }
    )
    service, *_ = build_service(messages=messages, classifier=classifier)

    result = service.run(after=now - timedelta(days=1), before=now + timedelta(days=1))

    assert result.processed == 3
    assert len(result.saved) == 3
    assert result.relevant == 1
    assert result.ignored == 2
