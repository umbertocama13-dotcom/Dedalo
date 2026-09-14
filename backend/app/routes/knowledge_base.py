"""Knowledge base endpoints: reading is open to every authenticated user, writing is expert-only."""

from fastapi import APIRouter, status

from app.dependencies import CurrentUser, DbConnection, ExpertUser
from app.schemas.common import MessageResponse
from app.schemas.knowledge_base import BaseDiagnosticIn, BaseDiagnosticOut, ExceptionIn, ExceptionOut
from app.services import knowledge_base_service as kb

router = APIRouter(prefix="/diagnostics", tags=["knowledge base"])


@router.get("", response_model=list[BaseDiagnosticOut])
def list_diagnostics(_: CurrentUser, connection: DbConnection) -> list[BaseDiagnosticOut]:
    """Lists all base diagnostics."""
    return kb.list_diagnostics(connection)


@router.get("/{diagnostic_id}", response_model=BaseDiagnosticOut)
def get_diagnostic(diagnostic_id: int, _: CurrentUser, connection: DbConnection) -> BaseDiagnosticOut:
    """Returns one base diagnostic."""
    return kb.get_diagnostic(connection, diagnostic_id)


@router.post("", response_model=BaseDiagnosticOut, status_code=status.HTTP_201_CREATED)
def create_diagnostic(body: BaseDiagnosticIn, expert: ExpertUser, connection: DbConnection) -> BaseDiagnosticOut:
    """Creates a base diagnostic (expert only)."""
    return kb.create_diagnostic(connection, body, created_by=expert.id)


@router.put("/{diagnostic_id}", response_model=BaseDiagnosticOut)
def update_diagnostic(
    diagnostic_id: int, body: BaseDiagnosticIn, _: ExpertUser, connection: DbConnection
) -> BaseDiagnosticOut:
    """Replaces a base diagnostic (expert only)."""
    return kb.update_diagnostic(connection, diagnostic_id, body)


@router.delete("/{diagnostic_id}", response_model=MessageResponse)
def delete_diagnostic(diagnostic_id: int, _: ExpertUser, connection: DbConnection) -> MessageResponse:
    """Deletes a base diagnostic and its exceptions (expert only)."""
    kb.delete_diagnostic(connection, diagnostic_id)
    return MessageResponse(message="Diagnostic deleted")


@router.get("/{diagnostic_id}/exceptions", response_model=list[ExceptionOut])
def list_exceptions(diagnostic_id: int, _: CurrentUser, connection: DbConnection) -> list[ExceptionOut]:
    """Lists the context-specific exceptions of a diagnostic."""
    return kb.list_exceptions(connection, diagnostic_id)


@router.post("/{diagnostic_id}/exceptions", response_model=ExceptionOut, status_code=status.HTTP_201_CREATED)
def create_exception(
    diagnostic_id: int, body: ExceptionIn, expert: ExpertUser, connection: DbConnection
) -> ExceptionOut:
    """Creates an exception for a diagnostic (expert only)."""
    return kb.create_exception(connection, diagnostic_id, body, created_by=expert.id)


@router.put("/{diagnostic_id}/exceptions/{exception_id}", response_model=ExceptionOut)
def update_exception(
    diagnostic_id: int, exception_id: int, body: ExceptionIn, _: ExpertUser, connection: DbConnection
) -> ExceptionOut:
    """Replaces an exception of a diagnostic (expert only)."""
    return kb.update_exception(connection, diagnostic_id, exception_id, body)


@router.delete("/{diagnostic_id}/exceptions/{exception_id}", response_model=MessageResponse)
def delete_exception(
    diagnostic_id: int, exception_id: int, _: ExpertUser, connection: DbConnection
) -> MessageResponse:
    """Deletes an exception of a diagnostic (expert only)."""
    kb.delete_exception(connection, diagnostic_id, exception_id)
    return MessageResponse(message="Exception deleted")
