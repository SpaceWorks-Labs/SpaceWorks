"""Explicit-ID, bounded team exports. Never export contact or DOB sources."""
import csv
import io
from apps.accounts.rbac import Action, can
from apps.events import event_authority
from apps.events.contributions.errors import ProgrammeError
from apps.events.contributions.ports import ports, required_hook
from apps.events.contributions.subjects import require_owner, subject_for
from .import_parser import HEADERS


def safe_cell(value):
    text = "".join(c for c in str(value) if ord(c) >= 32 or c in "\t\r\n")
    # Excel may discard whitespace/control prefixes before formula detection.
    significant = text.lstrip(" \t\r\n\ufeff\u200b")
    if significant.startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def encode(rows, *, format):
    values = [HEADERS, *[(row["team_id"], ";".join(map(str, row["member_ids"])), row["alias"]) for row in rows]]
    if format == "csv":
        target = io.StringIO(newline="")
        writer = csv.writer(target, lineterminator="\r\n")
        writer.writerows([[safe_cell(value) for value in row] for row in values])
        return target.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"
    if format == "xlsx":
        from openpyxl import Workbook
        from openpyxl.cell import WriteOnlyCell
        book = Workbook(write_only=True)
        sheet = book.create_sheet("Team mappings")
        for row in values:
            cells = []
            for value in row:
                cell = WriteOnlyCell(sheet, value=safe_cell(value))
                cell.data_type = "s"
                cells.append(cell)
            sheet.append(cells)
        target = io.BytesIO()
        book.save(target)
        book.close()
        return target.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    raise ProgrammeError("invalid_format", "Choose CSV or XLSX.", status=400)


def export_teams(*, actor, event, format, practice_run_id=None):
    from apps.makerspaces.guards import require_feature, require_module
    event_authority.require(actor, event, None)
    if not can(actor, Action.VIEW_AUDIT, event.makerspace_id):
        raise ProgrammeError("report_permission_required", "Private report permission is required.", status=403)
    require_module(event.makerspace, "events")
    require_feature(event.makerspace, "events.mentoring")
    ports().require_event_feature(event_id=event.pk, feature="events.mentoring")
    ids = ports().teams.ids(event_id=event.pk, practice_run_id=practice_run_id)
    if len(ids) > 500:
        raise ProgrammeError("export_too_large", "Export at most 500 teams at a time.", status=413)
    rows = []
    for pk in ids:
        ports().teams.require_practice(event_id=event.pk, team_id=pk, practice_run_id=practice_run_id)
        rows.append({"team_id": pk, "member_ids": ports().teams.member_ids(event_id=event.pk, team_id=pk),
            "alias": ports().teams.alias(event_id=event.pk, team_id=pk)})
    result = encode(rows, format=format)
    from django.db import transaction
    from apps.audit.services import record
    from apps.tenant_migration.gate_runtime import boundary_tenant_write
    with boundary_tenant_write(event.makerspace_id), transaction.atomic():
        with ports().fences(tenant_ids=(event.makerspace_id,), account_ids=(actor.pk,)):
            event_authority.require(actor, event, None)
            if not can(actor, Action.VIEW_AUDIT, event.makerspace_id):
                raise ProgrammeError("report_permission_required", "Private report permission is required.", status=403)
            record(actor, "event.mentor_mappings.exported", makerspace=event.makerspace, target=event,
                meta={"event_id": event.pk, "format": format, "team_count": len(rows),
                      "practice": practice_run_id is not None})
    return result


def export_role_owner(*, actor, row):
    subject = require_owner(actor.pk, subject_for(row))
    # P includes owner-only DOB/frozen-date sources. Organizers use the separate
    # age-only form projection; never route them to this archive adapter.
    result = required_hook(ports().forms, "export_owner")(subject=subject, actor_id=actor.pk)
    from django.db import transaction
    from apps.audit.services import record
    from apps.tenant_migration.gate_runtime import boundary_tenant_write
    with boundary_tenant_write(row.makerspace_id), transaction.atomic():
        with ports().fences(tenant_ids=(row.makerspace_id,), account_ids=(actor.pk,)):
            require_owner(actor.pk, subject)
            record(actor, "event.role.owner_exported", makerspace=row.makerspace, target=row,
                   meta={"event_id": row.event_id})
    return result
