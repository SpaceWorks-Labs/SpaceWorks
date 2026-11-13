from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from django.db import close_old_connections
import pytest
from apps.events.mentoring import help_workflow
from apps.events.mentoring.models import EventHelpRequest
from apps.events.contributions.errors import ProgrammeError
from tests.events.programme.mentoring.helpers import setup_help, help_payload


@pytest.mark.django_db(transaction=True)
def test_two_mentors_racing_for_one_request_have_one_winner(settings):
    _, event, users, mentors, _, team, _ = setup_help(settings)
    row = help_workflow.create(actor=users[0], event_id=event.pk, payload=help_payload(team.pk)).row

    def claim(index):
        close_old_connections()
        try:
            try:
                return help_workflow.command(actor=mentors[index], event_id=event.pk, help_id=row.pk,
                    payload={"operation_id": uuid4(), "expected_version": row.version}, action="claim").row.state
            except ProgrammeError as exc:
                assert exc.status_code == 409
                return "conflict"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, [0, 1]))
    assert sorted(results) == ["claimed", "conflict"]
    assert EventHelpRequest.objects.filter(state="claimed").count() == 1
