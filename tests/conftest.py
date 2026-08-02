import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main
from app.adapters.database.models import Base
from app.api.dependencies import (
    get_classifier,
    get_email_repository,
    get_gmail_client,
    get_settings,
    get_user_repository,
)
from app.core.config import Settings
from tests.fixtures.fakes import FakeClassifier, FakeEmailRepository, FakeGmailClient, FakeUserRepository


def make_fake_settings(**overrides) -> Settings:
    base = dict(
        postgres_user="test",
        postgres_password="test",
        postgres_db="test",
        postgres_host="localhost",
        postgres_port="5432",
        openai_api_key="test-key",
        force_reprocess=False,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture()
def db_session_factory():
    """A disposable database for repository tests.

    Defaults to an isolated in-memory SQLite database — fast, and never
    touches the real development Postgres instance. Set TEST_DATABASE_URL
    to point this at a real (disposable) Postgres instead, e.g. for
    verifying against Postgres-specific behavior.
    """
    test_db_url = os.environ.get("TEST_DATABASE_URL")
    if test_db_url:
        engine = create_engine(test_db_url)
    else:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    try:
        yield factory
    finally:
        if not test_db_url:
            Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client_factory():
    """Builds a TestClient for app.main.app with every external dependency
    overridden by an in-memory fake — proves the route/service/graph never
    hardcode a concrete Gmail/OpenAI/DB implementation."""
    fastapi_app = app.main.app

    def _factory(
        gmail: FakeGmailClient | None = None,
        classifier: FakeClassifier | None = None,
        email_repository: FakeEmailRepository | None = None,
        user_repository: FakeUserRepository | None = None,
        settings: Settings | None = None,
    ) -> TestClient:
        fastapi_app.dependency_overrides[get_settings] = lambda: settings or make_fake_settings()
        fastapi_app.dependency_overrides[get_gmail_client] = lambda: gmail or FakeGmailClient()
        fastapi_app.dependency_overrides[get_classifier] = lambda: classifier or FakeClassifier()
        fastapi_app.dependency_overrides[get_email_repository] = (
            lambda: email_repository or FakeEmailRepository()
        )
        fastapi_app.dependency_overrides[get_user_repository] = (
            lambda: user_repository or FakeUserRepository()
        )
        return TestClient(fastapi_app)

    yield _factory
    fastapi_app.dependency_overrides.clear()
