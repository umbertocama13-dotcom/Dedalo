"""CSV export and parsing of the knowledge base, without database access.

The format targets Excel with Italian regional settings: semicolon separator and
UTF-8 with BOM (without the BOM, Excel shows accented letters as garbage).
Parsing is tolerant with what Excel produces on other systems: comma separator
and Windows-1252 encoding are accepted too.

Error messages are in Italian because the expert reads them directly.
"""

import csv
import io
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.schemas.knowledge_base import MAX_COMPONENT_LENGTH, MAX_SYMPTOM_LENGTH, MAX_TEXT_LENGTH

CSV_COLUMNS = (
    "id",
    "family_name",
    "phase_number",
    "phase_name",
    "symptom_description",
    "affected_component",
    "probable_cause",
    "recommended_solution",
)
# phase_name is exported for readability only: on import the phase is identified by its number.
REQUIRED_COLUMNS = tuple(column for column in CSV_COLUMNS if column != "phase_name")
TEXT_LIMITS = {
    "symptom_description": MAX_SYMPTOM_LENGTH,
    "affected_component": MAX_COMPONENT_LENGTH,
    "probable_cause": MAX_TEXT_LENGTH,
    "recommended_solution": MAX_TEXT_LENGTH,
}
MAX_ROWS = 5000

# Excel runs a cell starting with these characters as a formula (CSV injection).
# Exported cells get a leading apostrophe, which the parser removes again, so an
# export -> Excel -> import round trip never changes the data.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class CsvRow:
    """A valid data row, not yet resolved against the database."""

    line: int
    id: int | None
    family_name: str | None
    phase_number: int | None
    symptom_description: str
    affected_component: str
    probable_cause: str
    recommended_solution: str


@dataclass(frozen=True)
class CsvError:
    """A problem found in the file, located by line and column."""

    line: int
    column: str | None
    message: str


@dataclass
class ParsedCsv:
    """Valid rows and errors found while reading a file."""

    rows: list[CsvRow] = field(default_factory=list)
    errors: list[CsvError] = field(default_factory=list)


def export_diagnostics_csv(rows: Iterable[Mapping[str, Any]]) -> bytes:
    """Writes diagnostics in the import/export CSV format.

    Args:
        rows: Diagnostic rows with at least the keys of CSV_COLUMNS; None becomes an empty cell.

    Returns:
        The file content: UTF-8 with BOM, semicolon separated, one header line.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow([_protect_formula("" if row.get(column) is None else str(row[column])) for column in CSV_COLUMNS])
    return buffer.getvalue().encode("utf-8-sig")


def parse_diagnostics_csv(data: bytes, max_rows: int = MAX_ROWS) -> ParsedCsv:
    """Reads and validates a diagnostics CSV file, without touching the database.

    Checks done here: encoding, header, number formats, required texts, lengths,
    phase without family, repeated ids. Checks that need the database (family and
    phase names, existing ids) are done by the import service.

    Args:
        data: Raw file content.
        max_rows: Maximum number of data rows accepted.

    Returns:
        The valid rows and every error found, in file order.
    """
    text = _decode(data)
    if not text.strip():
        return ParsedCsv(errors=[CsvError(line=1, column=None, message="Il file è vuoto.")])

    first_line = text.splitlines()[0]
    delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    header = [name.strip().lower() for name in next(reader)]

    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        message = (
            f"Intestazione non valida: mancano le colonne {', '.join(missing)}. "
            "Scarica il modello CSV per vedere l'intestazione corretta."
        )
        return ParsedCsv(errors=[CsvError(line=1, column=None, message=message)])

    positions = {column: header.index(column) for column in REQUIRED_COLUMNS}
    parsed = ParsedCsv()
    first_line_of_ids: dict[int, int] = {}
    data_rows = 0
    # reader.line_num counts physical lines, so a cell spanning several lines is still
    # reported at the line where its row starts.
    next_row_line = reader.line_num + 1

    for values in reader:
        line = next_row_line
        next_row_line = reader.line_num + 1
        # Excel often exports empty trailing rows such as ";;;;;;;".
        if not any(value.strip() for value in values):
            continue
        data_rows += 1
        if data_rows > max_rows:
            parsed.errors.append(
                CsvError(line=line, column=None, message=f"Troppe righe: il massimo per un file è {max_rows}.")
            )
            break

        cells = {
            column: _unprotect_formula(values[index].strip()) if index < len(values) else ""
            for column, index in positions.items()
        }
        row_errors = _validate_cells(cells, line, first_line_of_ids)
        if row_errors:
            parsed.errors.extend(row_errors)
            continue
        parsed.rows.append(
            CsvRow(
                line=line,
                id=int(cells["id"]) if cells["id"] else None,
                family_name=cells["family_name"] or None,
                phase_number=int(cells["phase_number"]) if cells["phase_number"] else None,
                symptom_description=cells["symptom_description"],
                affected_component=cells["affected_component"],
                probable_cause=cells["probable_cause"],
                recommended_solution=cells["recommended_solution"],
            )
        )

    if data_rows == 0:
        parsed.errors.append(CsvError(line=2, column=None, message="Il file non contiene righe di dati."))
    return parsed


def _validate_cells(cells: dict[str, str], line: int, first_line_of_ids: dict[int, int]) -> list[CsvError]:
    """Validates the cells of one row.

    Args:
        cells: Trimmed cell values by column name.
        line: Line where the row starts.
        first_line_of_ids: Ids already seen in the file with their line; updated in place.

    Returns:
        The errors of the row; empty if the row is valid.
    """
    errors = []
    for column in ("id", "phase_number"):
        if cells[column] and not _is_positive_int(cells[column]):
            errors.append(CsvError(line, column, f"«{cells[column]}» non è un numero intero positivo."))

    if cells["phase_number"] and not cells["family_name"]:
        errors.append(
            CsvError(line, "family_name", "manca la famiglia: una fase appartiene sempre a una famiglia.")
        )

    for column, limit in TEXT_LIMITS.items():
        if not cells[column]:
            errors.append(CsvError(line, column, "campo obbligatorio vuoto."))
        elif len(cells[column]) > limit:
            errors.append(
                CsvError(line, column, f"testo troppo lungo ({len(cells[column])} caratteri, massimo {limit}).")
            )

    if cells["id"] and _is_positive_int(cells["id"]):
        diagnostic_id = int(cells["id"])
        if diagnostic_id in first_line_of_ids:
            errors.append(
                CsvError(line, "id", f"id {diagnostic_id} ripetuto: compare già alla riga {first_line_of_ids[diagnostic_id]}.")
            )
        else:
            first_line_of_ids[diagnostic_id] = line
    return errors


def _decode(data: bytes) -> str:
    """Decodes the file as UTF-8 (with or without BOM), falling back to Windows-1252.

    Args:
        data: Raw file content.

    Returns:
        The decoded text.
    """
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Excel on Windows saves "CSV (delimitato dal separatore)" in Windows-1252.
        # A few byte values are undefined there: replace them instead of failing.
        return data.decode("cp1252", errors="replace")


def _is_positive_int(value: str) -> bool:
    """Tells whether a cell holds a whole number greater than zero, e.g. "12" but not "12.0"."""
    return value.isdigit() and int(value) > 0


def _protect_formula(value: str) -> str:
    """Prefixes an apostrophe to a cell that Excel would run as a formula."""
    return f"'{value}" if value.startswith(_FORMULA_PREFIXES) else value


def _unprotect_formula(value: str) -> str:
    """Removes the apostrophe added by _protect_formula."""
    return value[1:] if value.startswith("'") and value[1:].startswith(_FORMULA_PREFIXES) else value
