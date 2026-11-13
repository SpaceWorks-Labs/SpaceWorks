from datetime import timedelta
from uuid import uuid4
import pytest
from django.utils import timezone
from apps.events.mentoring import help_workflow, help_expiry
from apps.events.mentoring.models import EventHelpAction
from apps.events.contributions.errors import ProgrammeError
from tests.events.programme.mentoring.helpers import setup_help, help_payload


def claim(event, mentors, row):
    return help_workflow.command(actor=mentors[0], event_id=event.pk, help_id=row.pk,
        payload={"operation_id": uuid4(), "expected_version": row.version}, action="claim").row


@pytest.mark.django_db(transaction=True)
def test_expired_claim_releases_once_and_old_tab_cannot_renew(settings):
    _, event, users, mentors, _, team, _ = setup_help(settings)
    row = help_workflow.create(actor=users[0], event_id=event.pk, payload=help_payload(team.pk)).row
    row = claim(event, mentors, row)
    old_uuid, generation = row.claim_uuid, row.claim_generation
    row.claim_expires_at = timezone.now() - timedelta(seconds=1)
    row.save(update_fields=["claim_expires_at"])
    with pytest.raises(ProgrammeError) as error:
        help_workflow.command(actor=mentors[0], event_id=event.pk, help_id=row.pk,
            payload={"operation_id": uuid4(), "expected_version": row.version,
                     "claim_uuid": old_uuid, "claim_generation": generation}, action="renew")
    assert error.value.detail["code"] == "lease_lost"
    assert help_expiry.expire(event_id=event.pk) == 1
    assert help_expiry.expire(event_id=event.pk) == 0
    row.refresh_from_db()
    assert row.state == "open" and row.claimed_by_id is None and row.claim_uuid is None
    assert EventHelpAction.objects.filter(request=row, kind="lease_expired").count() == 1
    row = claim(event, mentors, row)
    assert row.claim_generation == generation + 1 and row.claim_uuid != old_uuid


@pytest.mark.django_db(transaction=True)
def test_renew_preserves_generation_and_terminal_expiry_never_reopens(settings):
    _, event, users, mentors, _, team, _ = setup_help(settings)
    row = claim(event, mentors, help_workflow.create(actor=users[0], event_id=event.pk, payload=help_payload(team.pk)).row)
    old_expiry, generation = row.claim_expires_at, row.claim_generation
    result = help_workflow.command(actor=mentors[0], event_id=event.pk, help_id=row.pk,
        payload={"operation_id": uuid4(), "expected_version": row.version,
                 "claim_uuid": row.claim_uuid, "claim_generation": generation}, action="renew")
    assert result.row.claim_generation == generation and result.row.claim_expires_at >= old_expiry
    row = result.row
    row.expires_at = timezone.now() - timedelta(seconds=1)
    row.save(update_fields=["expires_at"])
    help_expiry.expire(event_id=event.pk)
    row.refresh_from_db()
    assert row.state == "expired" and row.claimed_by_id is None
    with pytest.raises(ProgrammeError):
        help_workflow.command(actor=users[0], event_id=event.pk, help_id=row.pk,
            payload={"operation_id": uuid4(), "expected_version": row.version, "reason": "Try again"}, action="reopen", member_surface=True)


@pytest.mark.django_db(transaction=True)
def test_expiry_racing_an_old_heartbeat_cannot_revive_the_claim(settings):
    from concurrent.futures import ThreadPoolExecutor
    from django.db import close_old_connections
    _, event, users, mentors, _, team, _ = setup_help(settings)
    row = claim(event, mentors, help_workflow.create(actor=users[0], event_id=event.pk, payload=help_payload(team.pk)).row)
    row.claim_expires_at = timezone.now() - timedelta(seconds=1)
    row.save(update_fields=["claim_expires_at"])
    def attempt(index):
        close_old_connections()
        try:
            if index == 0:
                return help_expiry.expire(event_id=event.pk)
            try:
                help_workflow.command(actor=mentors[0], event_id=event.pk, help_id=row.pk,
                    payload={"operation_id": uuid4(), "expected_version": row.version,
                        "claim_uuid": row.claim_uuid, "claim_generation": row.claim_generation}, action="renew")
            except ProgrammeError as error:
                return str(error.detail["code"])
            return "renewed"
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, (0, 1)))
    assert outcomes[0] == 1 and outcomes[1] in ("stale_version", "lease_lost")
    row.refresh_from_db()
    assert row.state == "open" and row.claimed_by_id is None
