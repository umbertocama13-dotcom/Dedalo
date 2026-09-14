from fastapi import APIRouter

from app.dependencies import AppAIProvider, AppMatcher, CurrentUser, DbConnection
from app.schemas.diagnosis import DiagnosisRequest, DiagnosisResponse
from app.services import diagnosis_service

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


@router.post("", response_model=DiagnosisResponse)
def diagnose(
    body: DiagnosisRequest,
    _: CurrentUser,
    connection: DbConnection,
    matcher: AppMatcher,
    ai_provider: AppAIProvider,
) -> DiagnosisResponse:
    """Matches a symptom against the knowledge base for a family and cycle phase.

    Always 200 when the request is valid: "no_match" is an expected answer, not an error.
    """
    return diagnosis_service.diagnose(connection, body, matcher, ai_provider)
