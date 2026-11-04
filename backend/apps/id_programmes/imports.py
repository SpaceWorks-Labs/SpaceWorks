"""CSV import into a programme (SPEC §5.2; #128 C-13), or a public Google Sheet (L13).

Step 1 (preview): headers, the first 20 rows and an automatic column mapping. Step 2
(commit): the confirmed mapping, optionally approving, optionally as a dry run.
Imported rows are `source=import` pending entries bound to an emailed invite: nothing
links to an existing account and no account is created until the person accepts by
signing in with that verified email. The file itself is never stored; a sheet is
fetched as CSV under `membership.id_programmes_import_sheets` and parsed the same way.
"""
import csv
import hashlib
import io

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from .cards import add, decide, email_digest
from .models import IdProgrammeCard, IdProgrammeImport

MAX_BYTES, MAX_ROWS, MAX_COLUMNS, MAX_CELL, PREVIEW_ROWS = 2 * 1024 * 1024, 2000, 40, 500, 20
ALIASES = {"name": ("name", "full name", "full_name", "student name", "person"),
           "email": ("email", "e-mail", "email address", "mail")}


def parse(raw):
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not raw or len(raw) > MAX_BYTES:
        raise ValidationError({"file": "Upload a CSV file up to 2 MB."})
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows or not rows[0]:
        raise ValidationError({"file": "The file has no header row."})
    headers = [cell.strip()[:MAX_CELL] for cell in rows[0]]
    if len(headers) > MAX_COLUMNS:
        raise ValidationError({"file": f"Use at most {MAX_COLUMNS} columns."})
    body = [row for row in rows[1:] if any(cell.strip() for cell in row)]
    if len(body) > MAX_ROWS:
        raise ValidationError({"file": f"Import at most {MAX_ROWS} rows at a time."})
    for row in body:
        if any(len(cell) > MAX_CELL for cell in row):
            raise ValidationError({"file": f"A cell is longer than {MAX_CELL} characters."})
    return headers, body, hashlib.sha256(raw).hexdigest()


def auto_map(programme, headers):
    lowered = {header.lower(): index for index, header in enumerate(headers)}
    mapping = {}
    for field, aliases in ALIASES.items():
        mapping[field] = next((lowered[alias] for alias in aliases if alias in lowered), None)
    for question in programme.form_schema or ():
        for candidate in (question["key"].lower(), question["label"].lower()):
            if candidate in lowered:
                mapping[f"field:{question['key']}"] = lowered[candidate]
                break
    return mapping


def _row_values(row, mapping):
    def cell(index):
        return row[index].strip() if isinstance(index, int) and 0 <= index < len(row) else ""

    answers = {key[len("field:"):]: cell(index) for key, index in mapping.items() if key.startswith("field:")}
    return cell(mapping.get("name")), cell(mapping.get("email")).lower(), answers


def plan(programme, body, mapping):
    """-> (rows to create, skipped [{row, reason}]). Row numbers count from 2 (after the header)."""
    existing = set(IdProgrammeCard.objects.filter(programme=programme).values_list("email_digest", flat=True))
    seen, create, skipped = set(), [], []
    for number, row in enumerate(body, start=2):
        name, email, answers = _row_values(row, mapping)
        digest = email_digest(email)
        if not name:
            skipped.append({"row": number, "reason": "no_name"})
        elif "@" not in email or len(email) > 254:
            skipped.append({"row": number, "reason": "bad_email"})
        elif digest in seen:
            skipped.append({"row": number, "reason": "duplicate_in_file"})
        elif digest in existing:
            skipped.append({"row": number, "reason": "already_in_programme"})
        else:
            seen.add(digest)
            create.append((name, email, answers))
    return create, skipped


def read(programme, values):
    """-> (CSV bytes or text, the fetched sheet or None) for a validated preview/commit request."""
    from apps.admin_api import import_sources
    sheet = import_sources.read_source(values, programme.makerspace, import_sources.PROGRAMME_SHEETS,
                                       max_bytes=MAX_BYTES, max_rows=MAX_ROWS)
    return (sheet.content if sheet else values["content"]), sheet


def preview(programme, raw):
    headers, body, _digest = parse(raw)
    mapping = auto_map(programme, headers)
    create, skipped = plan(programme, body, mapping)
    return {"headers": headers, "rows": body[:PREVIEW_ROWS], "mapping": mapping, "rows_total": len(body),
            "to_create": len(create), "skipped": skipped}


@transaction.atomic
def commit(actor, programme, raw, mapping, *, approve=False, dry_run=False, source="file"):
    headers, body, source_digest = parse(raw)
    if not isinstance(mapping, dict) or mapping.get("name") is None or mapping.get("email") is None:
        raise ValidationError({"mapping": "Map a name column and an email column."})
    create, skipped = plan(programme, body, mapping)
    result = {"rows_total": len(body), "created": 0 if dry_run else len(create), "would_create": len(create),
              "skipped": skipped, "dry_run": dry_run}
    if dry_run:
        return result
    cards = [add(actor, programme, name=name, email=email, answers=answers, source=IdProgrammeCard.Source.IMPORT)
             for name, email, answers in create]
    if approve and cards:
        decide(actor, programme, "approve", [card.pk for card in cards])
    run = IdProgrammeImport.objects.create(programme=programme, created_by=actor, source_sha256=source_digest,
                                           rows_total=len(body), created=len(cards), skipped=len(skipped),
                                           mapping={key: value for key, value in mapping.items()
                                                    if isinstance(value, int)})
    audit.record(actor, "id_programme.cards_imported", makerspace=programme.makerspace, target=programme,
                 meta={"programme_id": programme.pk, "import_id": run.pk, "count": len(cards), "source": source})
    from .invites import send_invites
    transaction.on_commit(lambda: send_invites([card.pk for card in cards]), robust=True)
    return result
