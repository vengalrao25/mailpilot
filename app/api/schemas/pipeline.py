from datetime import datetime

from pydantic import BaseModel, model_validator
from typing_extensions import Self


class PipelineRunRequest(BaseModel):
    after: datetime | None = None
    before: datetime | None = None

    @model_validator(mode="after")
    def check_window_order(self) -> Self:
        if self.after is not None and self.before is not None and self.after >= self.before:
            raise ValueError("`after` must be earlier than `before`")
        return self


class PipelineEmailResult(BaseModel):
    subject: str
    status: str
    summary: str | None
    category: str | None


class PipelineRunResponse(BaseModel):
    processed: int
    saved: int
    relevant: int
    ignored: int
    results: list[PipelineEmailResult]
