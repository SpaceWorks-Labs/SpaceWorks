from io import BytesIO
from uuid import uuid4
import pytest
from openpyxl import load_workbook
from apps.events.mentoring.import_export import encode, export_teams, safe_cell
from apps.events.contributions.errors import ProgrammeError
from tests.events.programme.mentoring.helpers import setup_help


@pytest.mark.parametrize("text", ["=HYPERLINK(\"bad\")", " +1", "@SUM(A1)", "\t=1", "\r-2", "\ufeff=1"])
def test_formula_like_text_is_inert_in_csv_and_xlsx(text):
    assert safe_cell(text).startswith("'")
    rows = [{"team_id": 21, "member_ids": [17, 18], "alias": text}]
    raw, _ = encode(rows, format="csv")
    assert "'" in raw.decode("utf-8-sig")
    raw, _ = encode(rows, format="xlsx")
    book = load_workbook(BytesIO(raw), data_only=False)
    assert book.active["C2"].data_type == "s" and book.active["C2"].value.startswith("'")
    book.close()


@pytest.mark.django_db
def test_export_requires_full_manager_and_tenant_report_permission(settings):
    _, event, _, mentors, _, _, _ = setup_help(settings)
    from rest_framework.exceptions import PermissionDenied
    with pytest.raises(PermissionDenied):
        export_teams(actor=mentors[0], event=event, format="csv")


def test_unknown_export_format_refuses():
    with pytest.raises(ProgrammeError):
        encode([], format="json")


@pytest.mark.django_db(transaction=True)
def test_authorized_export_is_audited_and_does_not_include_contact_details(settings):
    from tests.events.collab_helpers import make_staff
    from apps.audit.models import AuditLog
    space, event, users, _, _, team, _ = setup_help(settings)
    raw, mime = export_teams(actor=make_staff(space), event=event, format="csv")
    text = raw.decode("utf-8-sig")
    assert "team_id,member_ids,alias" in text and str(team.pk) in text
    assert users[0].email not in text and "phone" not in text and "date_of_birth" not in text
    assert AuditLog.objects.filter(action="event.mentor_mappings.exported").exists()
