"""Centralized, validated environment configuration.

Reading env vars is deferred to `get_settings()` (cached) so importing this
module — or anything that imports it — never touches the environment or
fails at import time. Settings are only constructed, and only validated,
the first time a caller actually asks for them.
"""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class MissingSettingError(RuntimeError):
    def __init__(self, missing: list[str]):
        super().__init__(
            f"Missing required environment variable(s): {', '.join(missing)}"
        )
        self.missing = missing


@dataclass(frozen=True)
class Settings:
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: str
    openai_api_key: str
    force_reprocess: bool
    langchain_api_key: str | None = None
    langchain_project: str | None = None
    gmail_token_path: str = "token.json"
    gmail_credentials_path: str = "credentials.json"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


_REQUIRED = (
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "OPENAI_API_KEY",
)


def _load_settings_from_env() -> Settings:
    missing = [key for key in _REQUIRED if not os.environ.get(key)]
    if missing:
        raise MissingSettingError(missing)

    return Settings(
        postgres_user=os.environ["POSTGRES_USER"],
        postgres_password=os.environ["POSTGRES_PASSWORD"],
        postgres_db=os.environ["POSTGRES_DB"],
        postgres_host=os.environ["POSTGRES_HOST"],
        postgres_port=os.environ["POSTGRES_PORT"],
        openai_api_key=os.environ["OPENAI_API_KEY"],
        force_reprocess=os.environ.get("FORCE_REPROCESS", "false").lower() == "true",
        langchain_api_key=os.environ.get("LANGCHAIN_API_KEY"),
        langchain_project=os.environ.get("LANGCHAIN_PROJECT"),
        gmail_token_path=os.environ.get("GMAIL_TOKEN_PATH", "token.json"),
        gmail_credentials_path=os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json"),
    )


@lru_cache
def get_settings() -> Settings:
    return _load_settings_from_env()
