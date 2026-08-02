from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import router
from app.domain.errors import ExternalServiceError

app = FastAPI(
    title="MailPilot",
    description="Email orchestrator: reads Gmail, summarizes/classifies with an LLM.",
    version="0.1.0",
)
app.include_router(router)


@app.exception_handler(ExternalServiceError)
def handle_external_service_error(request: Request, exc: ExternalServiceError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})
