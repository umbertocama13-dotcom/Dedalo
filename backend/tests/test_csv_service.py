"""Unit tests for CSV export and parsing, without a database."""

import pytest

from app.services.csv_service import CSV_COLUMNS, CsvError, export_diagnostics_csv, parse_diagnostics_csv

HEADER = ";".join(CSV_COLUMNS)
VALID_ROW = "12;Cella di saldatura robotizzata;1;Ingresso pallet;Il pallet non arriva;Sensore;Sensore sporco.;Pulire il sensore."


def csv_bytes(*lines: str, encoding: str = "utf-8") -> bytes:
    return "\r\n".join(lines).encode(encoding)


def row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": 12,
        "family_name": "Cella di saldatura robotizzata",
        "phase_number": 1,
        "phase_name": "Ingresso pallet",
        "symptom_description": "Il pallet non arriva",
        "affected_component": "Sensore",
        "probable_cause": "Sensore sporco.",
        "recommended_solution": "Pulire il sensore.",
    }
    return {**base, **overrides}


def only_error(data: bytes) -> CsvError:
    parsed = parse_diagnostics_csv(data)
    assert parsed.rows == []
    [error] = parsed.errors
    return error


# --- Export ------------------------------------------------------------------------


def test_export_is_excel_friendly() -> None:
    content = export_diagnostics_csv([row()])

    assert content.startswith(b"\xef\xbb\xbf")
    lines = content.decode("utf-8-sig").split("\r\n")
    assert lines[0] == HEADER
    assert lines[1] == VALID_ROW


def test_export_writes_none_as_empty_cells() -> None:
    content = export_diagnostics_csv([row(family_name=None, phase_number=None, phase_name=None)])

    assert content.decode("utf-8-sig").split("\r\n")[1].startswith("12;;;;Il pallet")


def test_export_then_parse_gives_back_the_same_values() -> None:
    tricky = row(
        symptom_description='Il nastro; "quello pallet"\nsi ferma',
        probable_cause="=SOMMA(A1:A2) non è una formula",
        recommended_solution="-10 °C sotto il setpoint",
    )

    parsed = parse_diagnostics_csv(export_diagnostics_csv([tricky, row(id=13)]))

    assert parsed.errors == []
    first = parsed.rows[0]
    assert (first.id, first.family_name, first.phase_number) == (12, "Cella di saldatura robotizzata", 1)
    assert first.symptom_description == tricky["symptom_description"]
    assert first.probable_cause == tricky["probable_cause"]
    assert first.recommended_solution == tricky["recommended_solution"]
    # Header on line 1, first row on lines 2-3 (the symptom holds a newline), second row on line 4.
    assert parsed.rows[1].line == 4


def test_export_neutralizes_cells_that_excel_would_run_as_formulas() -> None:
    content = export_diagnostics_csv([row(probable_cause="=HYPERLINK(\"http://evil\")", affected_component="@cmd")])

    text = content.decode("utf-8-sig")
    assert "'=HYPERLINK" in text
    assert "'@cmd" in text


# --- Parsing: accepted variants -----------------------------------------------------


@pytest.mark.parametrize(
    "data",
    [
        csv_bytes(HEADER, VALID_ROW),
        b"\xef\xbb\xbf" + csv_bytes(HEADER, VALID_ROW),
        csv_bytes(HEADER.replace(";", ","), VALID_ROW.replace(";", ",")),
        csv_bytes(HEADER.upper().replace(";", " ; "), VALID_ROW),
    ],
    ids=["utf8", "utf8-bom", "comma-separator", "header-case-and-spaces"],
)
def test_accepted_file_variants(data: bytes) -> None:
    parsed = parse_diagnostics_csv(data)

    assert parsed.errors == []
    [parsed_row] = parsed.rows
    assert (parsed_row.id, parsed_row.phase_number, parsed_row.recommended_solution) == (12, 1, "Pulire il sensore.")


def test_windows_1252_accents_are_decoded() -> None:
    data = csv_bytes(HEADER, ";;;;La macchina è ferma;Motore;Perché sì;Più olio", encoding="cp1252")

    [parsed_row] = parse_diagnostics_csv(data).rows

    assert parsed_row.symptom_description == "La macchina è ferma"
    assert parsed_row.recommended_solution == "Più olio"


def test_generic_row_has_no_id_family_or_phase() -> None:
    [parsed_row] = parse_diagnostics_csv(csv_bytes(HEADER, ";;;;Sintomo;Componente;Causa;Soluzione")).rows

    assert (parsed_row.id, parsed_row.family_name, parsed_row.phase_number) == (None, None, None)
    assert parsed_row.line == 2


def test_blank_rows_are_skipped_and_lines_stay_correct() -> None:
    parsed = parse_diagnostics_csv(csv_bytes(HEADER, ";;;;;;;", VALID_ROW, "", ";;;;;;;"))

    assert parsed.errors == []
    assert [parsed_row.line for parsed_row in parsed.rows] == [3]


def test_extra_columns_and_missing_phase_name_are_tolerated() -> None:
    header = "note;id;family_name;phase_number;symptom_description;affected_component;probable_cause;recommended_solution"
    data = csv_bytes(header, "da rivedere;;;;Sintomo;Componente;Causa;Soluzione")

    [parsed_row] = parse_diagnostics_csv(data).rows

    assert parsed_row.symptom_description == "Sintomo"


# --- Parsing: errors ---------------------------------------------------------------


def test_empty_file() -> None:
    assert only_error(b"").message == "Il file è vuoto."


def test_header_without_data_rows() -> None:
    error = only_error(csv_bytes(HEADER, ";;;;;;;"))

    assert (error.line, error.message) == (2, "Il file non contiene righe di dati.")


def test_missing_columns_are_listed() -> None:
    error = only_error(csv_bytes("id;symptom_description", "1;Sintomo"))

    assert error.line == 1
    assert "family_name" in error.message
    assert "recommended_solution" in error.message


@pytest.mark.parametrize(
    ("line", "column", "message_part"),
    [
        (VALID_ROW.replace("12;", "abc;", 1), "id", "«abc» non è un numero intero positivo"),
        (VALID_ROW.replace("12;", "0;", 1), "id", "«0»"),
        (VALID_ROW.replace("12;", "12.0;", 1), "id", "«12.0»"),
        (VALID_ROW.replace(";1;", ";-1;", 1), "phase_number", "«-1»"),
        (";;2;;Sintomo;Componente;Causa;Soluzione", "family_name", "manca la famiglia"),
        (VALID_ROW.replace("Sensore sporco.", ""), "probable_cause", "campo obbligatorio vuoto"),
        (VALID_ROW.replace("Il pallet non arriva", "x" * 501), "symptom_description", "501 caratteri, massimo 500"),
    ],
    ids=["id-not-a-number", "id-zero", "id-decimal", "negative-phase", "phase-without-family", "empty-cause", "symptom-too-long"],
)
def test_row_errors_name_line_and_column(line: str, column: str, message_part: str) -> None:
    error = only_error(csv_bytes(HEADER, line))

    assert (error.line, error.column) == (2, column)
    assert message_part in error.message


def test_every_error_of_a_row_is_reported() -> None:
    errors = parse_diagnostics_csv(csv_bytes(HEADER, "x;;;;;;;")).errors

    assert {error.column for error in errors} == {
        "id",
        "symptom_description",
        "affected_component",
        "probable_cause",
        "recommended_solution",
    }


def test_repeated_id_points_to_its_first_line() -> None:
    parsed = parse_diagnostics_csv(csv_bytes(HEADER, VALID_ROW, VALID_ROW))

    assert len(parsed.rows) == 1
    [error] = parsed.errors
    assert (error.line, error.column) == (3, "id")
    assert "riga 2" in error.message


def test_errors_in_one_row_do_not_hide_valid_rows() -> None:
    parsed = parse_diagnostics_csv(csv_bytes(HEADER, "x;;;;S;C;P;R", VALID_ROW))

    assert [parsed_row.line for parsed_row in parsed.rows] == [3]
    assert [error.line for error in parsed.errors] == [2]


def test_too_many_rows_stops_parsing() -> None:
    data = csv_bytes(HEADER, *[";;;;Sintomo;Componente;Causa;Soluzione"] * 4)

    parsed = parse_diagnostics_csv(data, max_rows=3)

    assert len(parsed.rows) == 3
    [error] = parsed.errors
    assert (error.line, error.message) == (5, "Troppe righe: il massimo per un file è 3.")
