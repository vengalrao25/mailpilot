"""Inbox-processing orchestration, out of the route.

Resolves the current Gmail user, applies the default date-window rules,
fetches unread mail, and runs each message through the (already-built)
LangGraph pipeline, then aggregates the results. The route only translates
this into an HTTP response.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from langgraph.graph.state import CompiledStateGraph

from app.domain.email import Category
from app.domain.ports import GmailPort
from app.domain.repositories import UserRepository

# If the caller doesn't send `after`, default to the last 24h rather than
# fetching every unread email ever — unbounded fetch means one Gmail call
# (+ possibly one OpenAI call) per unread message, which doesn't scale.
DEFAULT_LOOKBACK = timedelta(days=1)

RELEVANT_CATEGORIES = {Category.JOB_LEAD.value, Category.CRITICAL_ALERT.value}


@dataclass
class EmailResult:
    subject: str
    status: str
    summary: str | None
    category: str | None


@dataclass
class PipelineRunResult:
    results: list[EmailResult] = field(default_factory=list)

    @property
    def processed(self) -> int:
        return len(self.results)

    @property
    def saved(self) -> list[EmailResult]:
        return [r for r in self.results if r.status == "saved"]

    @property
    def relevant(self) -> int:
        return sum(1 for r in self.saved if r.category in RELEVANT_CATEGORIES)

    @property
    def ignored(self) -> int:
        return len(self.saved) - self.relevant


def _resolve_window(
    after: datetime | None, before: datetime | None
) -> tuple[datetime | None, datetime | None]:
    if after is None and before is None:
        after = datetime.now(timezone.utc) - DEFAULT_LOOKBACK
    elif after is None:
        after = before - DEFAULT_LOOKBACK
    elif before is None:
        before = after + DEFAULT_LOOKBACK

    return after, before


class ProcessInboxService:
    def __init__(
        self,
        gmail: GmailPort,
        user_repository: UserRepository,
        pipeline_graph: CompiledStateGraph,
    ):
        self._gmail = gmail
        self._user_repository = user_repository
        self._pipeline_graph = pipeline_graph

    def run(self, after: datetime | None = None, before: datetime | None = None) -> PipelineRunResult:
        user_id = self._user_repository.get_or_create(self._gmail.get_user_email())

        after, before = _resolve_window(after, before)
        emails = self._gmail.list_unread_messages(after=after, before=before)

        result = PipelineRunResult()
        for email in emails:
            final_state = self._pipeline_graph.invoke(
                {
                    "gmail_id": email.gmail_id,
                    "subject": email.subject,
                    "sender": email.sender,
                    "received_at": email.received_at,
                    "label_ids": email.label_ids,
                    "user_id": user_id,
                    "body": None,
                    "summary": None,
                    "category": None,
                    "status": "pending",
                }
            )

            result.results.append(
                EmailResult(
                    subject=email.subject,
                    status=final_state["status"],
                    summary=final_state["summary"],
                    category=final_state["category"],
                )
            )

        return result
