from io import BytesIO
from uuid import uuid4
import pytest
from openpyxl import Workbook
from django.db import transaction
from apps.events.mentoring.import_parser import parse
from apps.events.mentoring.help_workflow import notice_locked
from apps.events.mentoring.models import EventHelpRequest, EventHelpType, MentorNotificationIntent
from apps.events.contributions.errors import ProgrammeError
from tests.events.programme.mentoring.helpers import setup_help


def test_csv_requires_explicit_ids_and_rejects_contact_matching():
    assert parse(b"team_id,member_ids,alias\n21,17;18,Bench A\n", filename="teams.csv") == [
        {"team_id": 21, "member_ids": [17, 18], "alias": "Bench A"}]
    with pytest.raises(ProgrammeError):
        parse(b"team_id,member_ids,alias\n21,ada@example.test,Bench A\n", filename="teams.csv")


def test_xlsx_uses_same_mapping_and_formulas_are_refused():
    book = Workbook()
    book.active.append(["team_id", "member_ids", "alias"])
    book.active.append([21, "17;18", "Bench A"])
    output = BytesIO(); book.save(output)
    assert parse(output.getvalue(), filename="teams.xlsx")[0]["member_ids"] == [17, 18]
    book.active["A2"] = "=1+20"
    output = BytesIO(); book.save(output)
    with pytest.raises(ProgrammeError):
        parse(output.getvalue(), filename="teams.xlsx")


@pytest.mark.django_db
def test_practice_help_cannot_create_a_production_outbox(settings):
    space, event, users, _, _, team, _ = setup_help(settings)
    from django.utils import timezone
    row = EventHelpRequest.objects.create(event=event, makerspace=space, team=team,
        type=EventHelpType.objects.get(event=event), raised_by=users[0], origin="round", summary="Practice",
        exclusive_until=timezone.now(), practice_run_id=uuid4())
    with transaction.atomic():
        notice_locked(row, event, "created")
    assert not MentorNotificationIntent.objects.exists()
