import os
from enum import Enum

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

MODEL = "gpt-4o-mini"


class Category(str, Enum):
    JOB_LEAD = "job_lead"
    CRITICAL_ALERT = "critical_alert"
    NEWSLETTER = "newsletter"
    PROMOTION = "promotion"
    OTHER = "other"


class EmailClassification(BaseModel):
    summary: str
    category: Category


def classify_email(subject: str, sender: str) -> EmailClassification:
    response = client.chat.completions.parse(
        model=MODEL,
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
                "content": f"Subject: {subject}\nFrom: {sender}",
            },
        ],
        response_format=EmailClassification,
    )
    return response.choices[0].message.parsed
