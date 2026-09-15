"""Knowledge base endpoints: reading is open to every authenticated user; writing, export and import are expert-only."""

from typing import Annotated

from fastapi import APIRouter, Query, Response, UploadFile, status

from app.dependencies import CurrentUser, DbConnection, ExpertUser
from app.schemas.common import MessageResponse
from app.schemas.knowledge_base import DiagnosticIn, DiagnosticOut, ImportReport
from app.services import import_service
from app.services import knowledge_base_service as kb

router = APIRouter(prefix="/diagnostics", tags=["knowledge base"])

CSV_RESPONSES = {200: {"content": {"text/csv": {}}, "description": "CSV file, UTF-8 with BOM, semicolon separated"}}


@router.get("", response_model=list[DiagnosticOut])
def list_diagnostics(
    _: CurrentUser,
    connection: DbConnection,
    family_id: Annotated[int | None, Query(gt=0)] = None,
    cycle_phase_id: Annotated[int | None, Query(gt=0)] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> list[DiagnosticOut]:
    """Lists diagnostics, optionally filtered by family, phase and text."""
    return kb.list_diagnostics(connection, family_id, cycle_phase_id, search)


# The fixed paths below are declared before "/{diagnostic_id}": routes are matched in
# order, and "export" would otherwise be taken as a (non-numeric) diagnostic id.


@router.get("/export", response_class=Response, responses=CSV_RESPONSES)
def export_diagnostics(_: ExpertUser, connection: DbConnection) -> Response:
    """Downloads every diagnostic as CSV (expert only)."""
    return _csv_response(kb.export_csv(connection), "dedalo_diagnostics.csv")


@router.get("/import-template", response_class=Response, responses=CSV_RESPONSES)
def download_import_template(_: ExpertUser, connection: DbConnection) -> Response:
    """Downloads a CSV template with example rows (expert only)."""
    return _csv_response(kb.template_csv(connection), "dedalo_template.csv")


@router.post("/import", response_model=ImportReport)
def import_diagnostics(
    expert: ExpertUser, connection: DbConnection, file: UploadFile, dry_run: bool = True
) -> ImportReport:
    """Imports diagnostics from a CSV file (expert only).

    With dry_run=true (the default) nothing is written and the report shows what would
    change. With dry_run=false the file is written only if it has no errors (otherwise 400).
    """
    # One byte more than the limit is enough to know the file is too large without reading all of it.
    data = file.file.read(import_service.MAX_FILE_BYTES + 1)
    return import_service.import_diagnostics_csv(connection, data, created_by=expert.id, dry_run=dry_run)


@router.get("/{diagnostic_id}", response_model=DiagnosticOut)
def get_diagnostic(diagnostic_id: int, _: CurrentUser, connection: DbConnection) -> DiagnosticOut:
    """Returns one diagnostic."""
    return kb.get_diagnostic(connection, diagnostic_id)


@router.post("", response_model=DiagnosticOut, status_code=status.HTTP_201_CREATED)
def create_diagnostic(body: DiagnosticIn, expert: ExpertUser, connection: DbConnection) -> DiagnosticOut:
    """Creates a diagnostic (expert only)."""
    return kb.create_diagnostic(connection, body, created_by=expert.id)


@router.put("/{diagnostic_id}", response_model=DiagnosticOut)
def update_diagnostic(diagnostic_id: int, body: DiagnosticIn, _: ExpertUser, connection: DbConnection) -> DiagnosticOut:
    """Replaces a diagnostic (expert only)."""
    return kb.update_diagnostic(connection, diagnostic_id, body)


@router.delete("/{diagnostic_id}", response_model=MessageResponse)
def delete_diagnostic(diagnostic_id: int, _: ExpertUser, connection: DbConnection) -> MessageResponse:
    """Deletes a diagnostic (expert only)."""
    kb.delete_diagnostic(connection, diagnostic_id)
    return MessageResponse(message="Diagnostic deleted")


def _csv_response(content: bytes, filename: str) -> Response:
    """Wraps CSV bytes in a download response.

    Args:
        content: File content.
        filename: Name proposed to the browser.

    Returns:
        A response that makes the browser save the file.
    """
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
