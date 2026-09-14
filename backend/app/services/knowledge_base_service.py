"""Knowledge base management (expert only): base diagnostics and their exceptions.

Status codes: 404 for a resource in the path that does not exist (or a referenced
family/phase that does not exist), 400 for an incoherent request, 409 for a duplicate.
"""

from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from app.repositories import diagnostics_repository
from app.schemas.knowledge_base import BaseDiagnosticIn, BaseDiagnosticOut, ExceptionIn, ExceptionOut
from app.services.catalog_service import validate_family_phase

# MySQL/MariaDB error code for a UNIQUE constraint violation.
MYSQL_DUPLICATE_ENTRY = 1062

T = TypeVar("T")


def list_diagnostics(connection: Connection) -> list[BaseDiagnosticOut]:
    """Lists all base diagnostics.

    Args:
        connection: Open database connection.

    Returns:
        The diagnostics ordered by id.
    """
    return [BaseDiagnosticOut.model_validate(row) for row in diagnostics_repository.list_base_diagnostics(connection)]


def get_diagnostic(connection: Connection, diagnostic_id: int) -> BaseDiagnosticOut:
    """Fetches one base diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Id of the diagnostic.

    Returns:
        The diagnostic.

    Raises:
        HTTPException: 404 if it does not exist.
    """
    row = diagnostics_repository.get_base_diagnostic(connection, diagnostic_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic not found")
    return BaseDiagnosticOut.model_validate(row)


def create_diagnostic(connection: Connection, data: BaseDiagnosticIn, created_by: int) -> BaseDiagnosticOut:
    """Creates a base diagnostic.

    Args:
        connection: Open database connection.
        data: Validated diagnostic fields.
        created_by: Id of the expert creating it.

    Returns:
        The stored diagnostic, including generated id and timestamps.
    """
    new_id = diagnostics_repository.insert_base_diagnostic(connection, **data.model_dump(), created_by=created_by)
    return get_diagnostic(connection, new_id)


def update_diagnostic(connection: Connection, diagnostic_id: int, data: BaseDiagnosticIn) -> BaseDiagnosticOut:
    """Replaces the fields of a base diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Id of the diagnostic.
        data: New validated fields.

    Returns:
        The updated diagnostic.

    Raises:
        HTTPException: 404 if it does not exist.
    """
    if not diagnostics_repository.update_base_diagnostic(connection, diagnostic_id, **data.model_dump()):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic not found")
    return get_diagnostic(connection, diagnostic_id)


def delete_diagnostic(connection: Connection, diagnostic_id: int) -> None:
    """Deletes a base diagnostic together with its exceptions.

    Args:
        connection: Open database connection.
        diagnostic_id: Id of the diagnostic.

    Raises:
        HTTPException: 404 if it does not exist.
    """
    if not diagnostics_repository.delete_base_diagnostic(connection, diagnostic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic not found")


def list_exceptions(connection: Connection, diagnostic_id: int) -> list[ExceptionOut]:
    """Lists the exceptions of a base diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Id of the diagnostic.

    Returns:
        The exceptions ordered by id.

    Raises:
        HTTPException: 404 if the diagnostic does not exist.
    """
    get_diagnostic(connection, diagnostic_id)
    rows = diagnostics_repository.list_exceptions(connection, diagnostic_id)
    return [ExceptionOut.model_validate(row) for row in rows]


def create_exception(
    connection: Connection, diagnostic_id: int, data: ExceptionIn, created_by: int
) -> ExceptionOut:
    """Creates a context-specific exception for a base diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Id of the diagnostic being overridden.
        data: Validated exception fields.
        created_by: Id of the expert creating it.

    Returns:
        The stored exception.

    Raises:
        HTTPException: 404 if diagnostic, family or phase do not exist; 400 if the
            phase is not part of the family; 409 if the diagnostic already has an
            exception in that phase.
    """
    get_diagnostic(connection, diagnostic_id)
    validate_family_phase(connection, data.family_id, data.cycle_phase_id)
    new_id = _guarded_write(
        connection,
        lambda: diagnostics_repository.insert_exception(
            connection, diagnostic_id, **data.model_dump(), created_by=created_by
        ),
    )
    return ExceptionOut.model_validate(diagnostics_repository.get_exception(connection, new_id))


def update_exception(
    connection: Connection, diagnostic_id: int, exception_id: int, data: ExceptionIn
) -> ExceptionOut:
    """Replaces the fields of an exception belonging to a diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Id of the diagnostic owning the exception.
        exception_id: Id of the exception.
        data: New validated fields.

    Returns:
        The updated exception.

    Raises:
        HTTPException: 404 if the exception is not found under that diagnostic or
            family/phase do not exist; 400 if the phase is not part of the family;
            409 if the diagnostic already has another exception in that phase.
    """
    _get_owned_exception(connection, diagnostic_id, exception_id)
    validate_family_phase(connection, data.family_id, data.cycle_phase_id)
    _guarded_write(
        connection,
        lambda: diagnostics_repository.update_exception(connection, exception_id, **data.model_dump()),
    )
    return ExceptionOut.model_validate(diagnostics_repository.get_exception(connection, exception_id))


def delete_exception(connection: Connection, diagnostic_id: int, exception_id: int) -> None:
    """Deletes an exception belonging to a diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Id of the diagnostic owning the exception.
        exception_id: Id of the exception.

    Raises:
        HTTPException: 404 if the exception is not found under that diagnostic.
    """
    _get_owned_exception(connection, diagnostic_id, exception_id)
    diagnostics_repository.delete_exception(connection, exception_id)


def _get_owned_exception(connection: Connection, diagnostic_id: int, exception_id: int) -> dict[str, Any]:
    """Fetches an exception only if it belongs to the given diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Diagnostic id taken from the URL.
        exception_id: Exception id taken from the URL.

    Returns:
        The exception row.

    Raises:
        HTTPException: 404 if missing or attached to another diagnostic.
    """
    row = diagnostics_repository.get_exception(connection, exception_id)
    if row is None or row["base_diagnostic_id"] != diagnostic_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found for this diagnostic")
    return row


def _guarded_write(connection: Connection, write: Callable[[], T]) -> T:
    """Runs a write inside a savepoint and maps constraint violations to HTTP errors.

    Args:
        connection: Open database connection with an active transaction.
        write: Function performing the write.

    Returns:
        Whatever the write returns.

    Raises:
        HTTPException: 409 for a duplicate, 400 for any other constraint violation.
    """
    try:
        # The savepoint confines the rollback to this write: after a constraint error
        # the request transaction is still usable instead of being left in a failed state.
        with connection.begin_nested():
            return write()
    except IntegrityError as error:
        if error.orig.args[0] == MYSQL_DUPLICATE_ENTRY:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This diagnostic already has an exception for the selected cycle phase",
            ) from error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The request violates a database constraint"
        ) from error
