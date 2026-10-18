"""Bounded explicit-ID team mapping; never guess identities from contact strings."""
import csv
import io
import zipfile
from apps.events.contributions.errors import ProgrammeError

MAX_BYTES = 1_000_000
HEADERS = ("team_id", "member_ids", "alias")


def parse(raw: bytes, *, filename: str):
    if len(raw) > MAX_BYTES:
        raise ProgrammeError("import_too_large", "Keep imports below 1 MB.", status=413)
    try:
        if filename.lower().endswith(".csv"):
            text = raw.decode("utf-8-sig")
            records = list(csv.reader(io.StringIO(text), strict=True))
        elif filename.lower().endswith(".xlsx"):
            # Inspect expansion before a spreadsheet parser allocates XML trees.
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries = archive.infolist()
                if len(entries) > 100 or sum(x.file_size for x in entries) > 4 * MAX_BYTES:
                    raise ValueError()
                if any("vbaProject" in x.filename or "externalLinks/" in x.filename or
                    x.flag_bits & 1 or x.filename.startswith(("/", "\\")) or ".." in x.filename.split("/") for x in entries):
                    raise ValueError()
                # openpyxl uses defusedxml when installed; reject declarations in
                # bounded XML members as a second backstop before loading it.
                for entry in entries:
                    if entry.filename.endswith(".xml"):
                        xml = archive.read(entry)
                        if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                            raise ValueError()
            from openpyxl import load_workbook
            workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=False, keep_links=False)
            try:
                if len(workbook.worksheets) != 1:
                    raise ValueError()
                records = []
                for row in workbook.active.iter_rows():
                    if len(records) > 500 or len(row) > 3 or any(cell.data_type == "f" for cell in row):
                        raise ValueError()
                    records.append([cell.value if cell.value is not None else "" for cell in row])
            finally:
                workbook.close()
        else:
            raise ValueError()
        if not records or tuple(records[0]) != HEADERS or len(records) > 501:
            raise ValueError()
        result, seen = [], set()
        for number, record in enumerate(records[1:], 2):
            if len(record) != 3:
                raise ValueError()
            team_id = int(record[0])
            members = [int(x.strip()) for x in str(record[1]).split(";")]
            alias = str(record[2]).strip()
            if team_id < 1 or team_id in seen or not members or len(members) > 50 or min(members) < 1 or len(set(members)) != len(members):
                raise ValueError()
            if not alias or len(alias) > 100 or any(ord(c) < 32 for c in alias):
                raise ValueError()
            seen.add(team_id)
            result.append({"team_id": team_id, "member_ids": members, "alias": alias})
        return result
    except (ValueError, TypeError, UnicodeError, csv.Error, zipfile.BadZipFile, KeyError) as exc:
        raise ProgrammeError("invalid_import", "Use one sheet with team_id, member_ids (semicolon-separated IDs), and alias; no formulas.", status=400) from exc
