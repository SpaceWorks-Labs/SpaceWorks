"""Actual source discovery advances past scheduled rows and suppresses stale dues."""
from datetime import timedelta
from types import SimpleNamespace
import pytest
from django.utils import timezone
from apps.operations.models_reminders import ReminderSchedule
from apps.event_reimbursements.reminders import discover_awards, discover_claims, resolve, award_identity, claim_identity
from apps.event_reimbursements.models import GrantAward
from apps.event_reimbursements import award_workflow, claim_workflow
from .helpers import requested, submitted, decision_data
from .conftest import cmd

pytestmark = pytest.mark.django_db(transaction=True)


def schedule(world, source, subject):
    return ReminderSchedule.objects.create(makerspace=world.space, source=source, subject=subject.subject,
        kind=subject.kind, offset_seconds=subject.offsets[-1], due_at=subject.due_at,
        remind_at=subject.due_at + timedelta(seconds=subject.offsets[-1]))


def test_offer_extension_suppresses_old_schedule(world):
    grant = requested(world)
    value = cmd(grant.version, outcome="award", amount_minor=10000, currency="INR", reason_code="need_based",
        expected_award_version=None, expected_pool_version=world.pool.version)
    award_workflow.decide(request=world.finance, event_id=world.event.pk, request_id=grant.pk, data=value)
    award = GrantAward.objects.get(request=grant)
    subjects = list(discover_awards(world.space, timezone.now(), 1, timezone.get_current_timezone()))
    old = schedule(world, "event_reimbursements.award_accept", subjects[0])
    assert not list(discover_awards(world.space, timezone.now(), 1, timezone.get_current_timezone()))
    grant.refresh_from_db(); world.pool.refresh_from_db()
    award_workflow.decide(request=world.finance, event_id=world.event.pk, request_id=grant.pk,
        data=cmd(grant.version, outcome="award", amount_minor=10000, currency="INR", reason_code="need_based",
            expected_award_version=award.version, expected_pool_version=world.pool.version,
            accept_by=award.accept_by - timedelta(hours=1)))
    award.refresh_from_db()
    assert award_identity(award) != old.subject
    assert resolve(world.space, old, timezone.now(), award=True) is None
    assert list(discover_awards(world.space, timezone.now(), 1, timezone.get_current_timezone()))


def test_claim_extension_is_new_identity_and_submitted_claim_is_suppressed(world, monkeypatch):
    claim, _, line_id = submitted(world, monkeypatch)
    assert list(discover_claims(world.space, timezone.now(), 10, timezone.get_current_timezone())) == []
    value = decision_data(world, claim, line_id, 0, outcome="returned_for_info")
    value.update(line_decisions=[], info_due_at=timezone.now() + timedelta(days=4))
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk, data=value)
    subjects = list(discover_claims(world.space, timezone.now(), 10, timezone.get_current_timezone()))
    old = schedule(world, "event_reimbursements.claim_due", subjects[0])
    claim.refresh_from_db()
    claim_workflow.extend(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=cmd(claim.version, due_revision=claim.due_revision, due_at=claim.info_due_at + timedelta(days=2),
            reason_code="deadline_extension", note="More information needed"))
    claim.refresh_from_db()
    assert claim_identity(claim) != old.subject
    assert resolve(world.space, old, timezone.now(), award=False) is None
    assert list(discover_claims(world.space, timezone.now(), 10, timezone.get_current_timezone()))
