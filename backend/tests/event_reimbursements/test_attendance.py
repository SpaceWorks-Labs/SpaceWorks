"""Only current canonical physical venue evidence or finance attestation qualifies."""
from datetime import timedelta
import pytest
from django.utils import timezone
from apps.event_reimbursements.attendance import evidence
from apps.event_reimbursements import claim_workflow
from apps.events.models import EventCheckInEvent, EventAttendanceCorrection
from apps.events.services_attendance_correction import correct_attendance
from apps.events.services_checkin import mark_attended_with_event
from apps.payments.event_payouts.errors import PayoutError
from .helpers import submitted
from .conftest import cmd

pytestmark = pytest.mark.django_db(transaction=True)


def test_qr_then_correction_then_online_does_not_reuse_old_qr(world, monkeypatch):
    claim, _, _ = submitted(world, monkeypatch)
    registration = claim.award.request.registration
    before = evidence(claim=claim, programme=world.programme)
    corrected, _ = correct_attendance(registration, actor=world.manager)
    marker = EventAttendanceCorrection.objects.get(registration=registration)
    assert marker.invalidated_through_checkin_id >= max(before["checkin_ids"])
    mark_attended_with_event(corrected, actor=world.manager, source="online", attended_at=world.event.starts_at)
    claim = type(claim).objects.get(pk=claim.pk)
    with pytest.raises(PayoutError) as exc:
        evidence(claim=claim, programme=world.programme)
    assert exc.value.detail["code"] == "attendance_required"


def test_manual_online_evidence_needs_revision_bound_finance_attestation(world, monkeypatch):
    claim, _, _ = submitted(world, monkeypatch)
    registration = claim.award.request.registration
    corrected, _ = correct_attendance(registration, actor=world.manager)
    attended, _ = mark_attended_with_event(corrected, actor=world.manager, source="online", attended_at=world.event.starts_at)
    claim.refresh_from_db()
    value = cmd(claim.version, registration_id=registration.pk, expected_attendance_revision=attended.attendance_revision,
        attended_at=world.event.starts_at + timedelta(hours=1), venue_evidence_refs=["staff:venue-desk"],
        reason_code="attendance_exception", note="Private venue confirmation")
    claim_workflow.attest(request=world.finance, event_id=world.event.pk, claim_id=claim.pk, data=value)
    claim = type(claim).objects.get(pk=claim.pk)
    result = evidence(claim=claim, programme=world.programme)
    assert result["attestation_uuid"] and not result["checkin_ids"]
    assert EventCheckInEvent.objects.filter(registration=registration).count() == 2
    correct_attendance(attended, actor=world.manager)
    claim = type(claim).objects.get(pk=claim.pk)
    with pytest.raises(PayoutError):
        evidence(claim=claim, programme=world.programme)


def test_location_without_physical_venue_does_not_qualify_qr(world, monkeypatch):
    claim, _, _ = submitted(world, monkeypatch)
    # Fixture an event whose canonical location declares no physical venue.
    world.event.location_kind = "other"; world.event.save(update_fields=["location_kind"])
    claim = type(claim).objects.get(pk=claim.pk)
    with pytest.raises(PayoutError):
        evidence(claim=claim, programme=world.programme)
