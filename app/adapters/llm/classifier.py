from enum import Enum

import openai
from langsmith.wrappers import wrap_openai
from openai import OpenAI
from pydantic import BaseModel

from app.domain.email import Category, Classification
from app.domain.errors import ExternalServiceError

MODEL = "gpt-5-nano"


class _ResponseCategory(str, Enum):
    """Mirrors `Category` for OpenAI's structured-output schema — kept
    separate so the domain enum never has to satisfy an SDK's schema
    constraints."""

    JOB_LEAD = "job_lead"
    CRITICAL_ALERT = "critical_alert"
    NEWSLETTER = "newsletter"
    PROMOTION = "promotion"
    OTHER = "other"


class _EmailClassification(BaseModel):
    summary: str
    category: _ResponseCategory


class OpenAIClassifier:
    """Implements `ClassifierPort` using OpenAI structured output."""

    def __init__(self, api_key: str, model: str = MODEL):
        self._client = wrap_openai(OpenAI(api_key=api_key))
        self._model = model

    def classify(self, subject: str, sender: str, body: str | None = None) -> Classification:
        user_content = f"Subject: {subject}\nFrom: {sender}"
        if body:
            user_content += f"\nBody: {body}"

        try:
            response = self._client.chat.completions.parse(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You summarize and categorize emails. Give a one-sentence "
                            "summary and pick the single best-fitting category."
                        ),
                    },
                    {
                        "role": "user",
                        "content": user_content,
                    },
                ],
                response_format=_EmailClassification,
            )
        except openai.OpenAIError as exc:
            raise ExternalServiceError(f"OpenAI classification failed: {exc}") from exc

        parsed = response.choices[0].message.parsed
        return Classification(summary=parsed.summary, category=Category(parsed.category.value))
