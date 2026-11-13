from datetime import timedelta
from uuid import uuid4
import pytest
from django.db import transaction
from django.utils import timezone
from apps.events.contracts.providers import LockedContext
from apps.events.mentoring import notifications, round_triggers, diagnostics, help_workflow
from apps.events.mentoring.models import (MentorNotificationIntent, EventHelpRequest, MentorRound, MentorProfile)
from tests.events.programme.mentoring.helpers import setup_help, help_payload


@pytest.mark.django_db(transaction=True)
def test_provider_failure_retries_but_revoked_mentors_are_rechecked(settings):
    _, event, users, _, roles, team, adapter = setup_help(settings)
    row = help_workflow.create(actor=users[0], event_id=event.pk, payload=help_payload(team.pk)).row
    intent = MentorNotificationIntent.objects.get(request=row, kind="created")
    attempts = []
    def fail(**kwargs):
        assert "summary" not in kwargs["payload"]
        assert "Private wiring" not in str(kwargs)
        attempts.append(kwargs["idempotency_key"])
        raise OSError("provider unavailable")
    adapter.deliver_help = fail
    assert notifications.deliver_one(intent.pk) is False
    intent.refresh_from_db()
    assert intent.delivered_at is None and intent.claim_uuid is None and intent.attempts == 1
    for role in roles:
        role.state = "revoked"
        role.save(update_fields=["state"])
    intent.available_at = timezone.now() - timedelta(seconds=1)
    intent.save(update_fields=["available_at"])
    assert notifications.deliver_one(intent.pk) is True
    assert len(attempts) == 1
    assert notifications.deliver_one(intent.pk) is False


@pytest.mark.django_db(transaction=True)
def test_round_trigger_deduplicates_and_practice_has_no_outbox(settings):
    space, event, users, _, _, team, _ = setup_help(settings)
    rule = {"key": "pcb-followup", "question_id": "help", "op": "eq", "value": True, "type_key": "pcb"}
    locks = LockedContext(event_id=event.pk, tenant_ids=(space.pk,), account_ids=(users[0].pk,))
    round = MentorRound.objects.create(event=event, makerspace=space, index=1, key="progress", label="Progress",
        opens_at=event.starts_at, closes_at=event.ends_at, help_trigger_rules=[rule])
    with transaction.atomic():
        for _ in range(2):
            round_triggers.fire_locked(actor=users[0], event=event, round=round, team_id=team.pk, answers={"help": True}, locks=locks)
    assert EventHelpRequest.objects.filter(origin="round", practice_run_id__isnull=True).count() == 1
    assert MentorNotificationIntent.objects.count() == 1
    round.practice_run_id = uuid4()
    round.save(update_fields=["practice_run_id"])
    with transaction.atomic():
        round_triggers.fire_locked(actor=users[0], event=event, round=round, team_id=team.pk, answers={"help": True}, locks=locks)
    assert EventHelpRequest.objects.filter(practice_run_id=round.practice_run_id).count() == 1
    assert MentorNotificationIntent.objects.count() == 1


def test_generosity_does_not_invent_normalization_for_small_or_constant_samples():
    assert diagnostics.generosity({1: [4], 2: [5, 5]})[0]["z_score"] is None
    assert all(row["z_score"] is None for row in diagnostics.generosity({1: [4] * 3, 2: [4] * 3}))
    rows = diagnostics.generosity({1: [1] * 3, 2: [5] * 3})
    assert rows[0]["z_score"] < 0 < rows[1]["z_score"]
