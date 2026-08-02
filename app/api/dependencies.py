"""FastAPI dependency providers.

Every external dependency (DB session factory, Gmail client, classifier,
compiled graph) is resolved here via `Depends`, never constructed inside a
route or a workflow node. Tests swap any of these out with
`app.dependency_overrides[...]`.
"""

from langgraph.graph.state import CompiledStateGraph

from fastapi import Depends

from app.adapters.database.repositories import SqlEmailRepository, SqlUserRepository
from app.adapters.gmail.client import GmailClient
from app.adapters.llm.classifier import OpenAIClassifier
from app.core.config import Settings, get_settings
from app.core.database import get_sessionmaker
from app.domain.ports import ClassifierPort, GmailPort
from app.domain.repositories import EmailRepository, UserRepository
from app.services.process_inbox import ProcessInboxService
from app.workflows.email_pipeline.graph import build_pipeline_graph


def get_email_repository(settings: Settings = Depends(get_settings)) -> EmailRepository:
    return SqlEmailRepository(session_factory=get_sessionmaker(settings))


def get_user_repository(settings: Settings = Depends(get_settings)) -> UserRepository:
    return SqlUserRepository(session_factory=get_sessionmaker(settings))


def get_gmail_client(settings: Settings = Depends(get_settings)) -> GmailPort:
    return GmailClient(
        token_path=settings.gmail_token_path,
        credentials_path=settings.gmail_credentials_path,
    )


def get_classifier(settings: Settings = Depends(get_settings)) -> ClassifierPort:
    return OpenAIClassifier(api_key=settings.openai_api_key)


def get_pipeline_graph(
    settings: Settings = Depends(get_settings),
    gmail: GmailPort = Depends(get_gmail_client),
    classifier: ClassifierPort = Depends(get_classifier),
    email_repository: EmailRepository = Depends(get_email_repository),
) -> CompiledStateGraph:
    return build_pipeline_graph(
        gmail=gmail,
        classifier=classifier,
        email_repository=email_repository,
        force_reprocess=settings.force_reprocess,
    )


def get_process_inbox_service(
    gmail: GmailPort = Depends(get_gmail_client),
    user_repository: UserRepository = Depends(get_user_repository),
    pipeline_graph: CompiledStateGraph = Depends(get_pipeline_graph),
) -> ProcessInboxService:
    return ProcessInboxService(
        gmail=gmail,
        user_repository=user_repository,
        pipeline_graph=pipeline_graph,
    )
