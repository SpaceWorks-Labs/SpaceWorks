"""Server-side reading of an uploaded .xlsx for the Bulk Import column-matching step.

The staff console used to parse the workbook in the browser with SheetJS, whose npm
build carries unpatched advisories (owner decision #123). The panel now uploads the
file here and gets back the same shape SheetJS produced: one object per non-blank row,
keyed by the first row's headers, blank cells as "". The import job itself still parses
the file again server-side, so this endpoint only feeds the preview.

Parsing is defensive: openpyxl in read-only, cached-values mode (formulas are never
evaluated and external links are not loaded), a byte limit before opening, and row and
column caps applied while streaming so a crafted sheet cannot make us read it whole.
"""
import datetime
import io
from decimal import Decimal

from apps.admin_api.bulk_import_parsers import (
    MAX_IMPORT_ROWS,
    MAX_IMPORT_UPLOAD_BYTES,
    BulkImportLimitError,
    is_blank_row,
)

MAX_IMPORT_COLUMNS = 100


def sheet_rows_from_upload(uploaded_file):
    """Return the first worksheet's rows as JSON-safe dicts, or raise ValueError."""
    if not uploaded_file.name.lower().endswith(".xlsx"):
        raise ValueError("Only .xlsx files can be read here.")
    size = getattr(uploaded_file, "size", None)
    if size is not None and size > MAX_IMPORT_UPLOAD_BYTES:
        raise BulkImportLimitError(
            f"Import file must be {MAX_IMPORT_UPLOAD_BYTES} bytes or smaller."
        )
    data = uploaded_file.read(MAX_IMPORT_UPLOAD_BYTES + 1)
    if len(data) > MAX_IMPORT_UPLOAD_BYTES:
        raise BulkImportLimitError(
            f"Import file must be {MAX_IMPORT_UPLOAD_BYTES} bytes or smaller."
        )
    import openpyxl

    try:
        workbook = openpyxl.load_workbook(
            io.BytesIO(data), read_only=True, data_only=True, keep_links=False
        )
    except Exception as exc:
        raise ValueError("XLSX file could not be read.") from exc
    try:
        return _first_sheet_rows(workbook)
    except BulkImportLimitError:
        raise
    except Exception as exc:
        raise ValueError("XLSX file could not be read.") from exc
    finally:
        workbook.close()


def _first_sheet_rows(workbook):
    # Same sheet the browser parser used: the first one in tab order.
    if not workbook.worksheets:
        return []
    sheet = workbook.worksheets[0]
    rows = sheet.iter_rows(values_only=True, max_col=MAX_IMPORT_COLUMNS + 1)
    header_row = next(rows, None)
    if not header_row:
        return []
    if len(header_row) > MAX_IMPORT_COLUMNS and _filled(header_row[MAX_IMPORT_COLUMNS:]):
        raise BulkImportLimitError(
            f"Bulk import is limited to {MAX_IMPORT_COLUMNS} columns."
        )
    headers = [str(value or "").strip() for value in header_row[:MAX_IMPORT_COLUMNS]]
    parsed_rows = []
    for row in rows:
        parsed = {
            header: _json_value(row[index]) if index < len(row) else ""
            for index, header in enumerate(headers)
            if header
        }
        if not parsed or is_blank_row(parsed):
            continue
        parsed_rows.append(parsed)
        if len(parsed_rows) > MAX_IMPORT_ROWS:
            raise BulkImportLimitError(f"Bulk import is limited to {MAX_IMPORT_ROWS} rows.")
    return parsed_rows


def _filled(values):
    return any(str(value or "").strip() for value in values)


def _json_value(value):
    if value is None:
        return ""
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    return str(value)
