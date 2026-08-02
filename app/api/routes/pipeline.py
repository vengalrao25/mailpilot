from fastapi import APIRouter, Depends

from app.api.dependencies import get_process_inbox_service
from app.api.schemas.pipeline import PipelineEmailResult, PipelineRunRequest, PipelineRunResponse
from app.services.process_inbox import ProcessInboxService

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/run", response_model=PipelineRunResponse)
def run_pipeline(
    request: PipelineRunRequest = PipelineRunRequest(),
    service: ProcessInboxService = Depends(get_process_inbox_service),
) -> PipelineRunResponse:
    result = service.run(after=request.after, before=request.before)

    return PipelineRunResponse(
        processed=result.processed,
        saved=len(result.saved),
        relevant=result.relevant,
        ignored=result.ignored,
        results=[
            PipelineEmailResult(
                subject=r.subject, status=r.status, summary=r.summary, category=r.category
            )
            for r in result.results
        ],
    )
