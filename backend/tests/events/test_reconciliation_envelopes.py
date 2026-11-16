"""Source revision, principal and tenant remain authoritative after enqueue."""
import pytest

from apps.events import notification_envelopes as notices
from apps.events.models import EventRegistration
from apps.events.notification_sources import lifecycle_eligible, reminder_eligible
from apps.integrations.models_contract import NotificationEnvelope
from tests.events.test_services import make_event
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db


def setup_registration():
    space = make_space("recon-event")
    space.enabled_modules = sorted((set(space.enabled_modules) | {"events"}) - {"membership", "notifications"})
    space.save(update_fields=["enabled_modules"])
    event = make_event(space)
    owner = make_user("recon-event-owner", access_status="active")
    row = EventRegistration.objects.create(event=event, member=owner, name="Private name",
        email=owner.email, phone="123", custom_answers={"notes": "private"})
    return space, event, owner, row


def test_repeated_lifecycle_uses_source_identity_even_with_new_call_intents(monkeypatch):
    space, event, owner, registration = setup_registration()
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    first = notices.owner_envelope(event, "registration_created", registration, notices.new_intent())
    second = notices.owner_envelope(event, "registration_created", registration, notices.new_intent())
    assert first.pk == second.pk
    assert NotificationEnvelope.objects.filter(recipient=owner).count() == 1
    assert first.context["makerspace.name"] == space.name
    assert first.context["event.id"] == event.pk
    assert "Private name" not in str(first.context) and owner.email not in str(first.context)
    assert lifecycle_eligible(first)
    EventRegistration.objects.filter(pk=registration.pk).update(calendar_sequence=1)
    assert not lifecycle_eligible(first)


def test_lifecycle_cannot_be_retargeted_to_another_account_or_tenant(monkeypatch):
    space, event, owner, row = setup_registration()
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    envelope = notices.owner_envelope(event, "registration_created", row, "request")
    envelope.recipient_id = make_user("recon-event-other", access_status="active").pk
    assert not lifecycle_eligible(envelope)
    envelope.recipient_id = owner.pk
    envelope.makerspace = make_space("recon-event-other-space")
    assert not lifecycle_eligible(envelope)
    envelope.makerspace = space
    row.delete()
    assert not lifecycle_eligible(envelope)


def test_event_reminder_checks_current_offset_and_registration_route(monkeypatch):
    space, event, owner, row = setup_registration()
    # The policy is imported at the source-check boundary.
    monkeypatch.setattr("apps.makerspaces.reminder_policy.reminder_offsets", lambda *args: (3600,))
    from types import SimpleNamespace
    envelope = SimpleNamespace(makerspace=space, makerspace_id=space.pk, recipient_id=owner.pk,
        source_id=str(row.pk), audience="requester", event="reminder", context={
            "event_id": event.pk, "registration_id": row.pk,
            "starts_at": event.starts_at.isoformat(), "offset_seconds": 3600})
    assert reminder_eligible(envelope)
    envelope.context["offset_seconds"] = 60
    assert not reminder_eligible(envelope)
    envelope.context["offset_seconds"] = 3600
    other = make_space("recon-event-route")
    EventRegistration.objects.filter(pk=row.pk).update(registered_via_makerspace=other)
    assert not reminder_eligible(envelope)


def test_existing_random_key_intent_is_reused_on_upgrade(monkeypatch):
    _, event, owner, row = setup_registration()
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    first = notices.owner_envelope(event, "registration_created", row, "before")
    NotificationEnvelope.objects.filter(pk=first.pk).update(dedup_key="ev:old-random-call-key")
    again = notices.owner_envelope(event, "registration_created", row, "after")
    assert again.pk == first.pk and again.dedup_key == "ev:old-random-call-key"
    assert NotificationEnvelope.objects.filter(recipient=owner).count() == 1


def test_staff_legacy_channels_remain_preskipped(monkeypatch):
    space, event, _, row = setup_registration()
    from tests.account_split.p1_helpers import staff
    manager, _ = staff(space, "recon-event-staff", "event_manager", access_status="active")
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    monkeypatch.setattr("apps.integrations.staff_notifications.staff_user_ids_for_feature", lambda *a, **k: [manager.pk])
    notices.staff_envelopes(space, event, "registration_created", row, "request")
    envelope = NotificationEnvelope.objects.get(recipient=manager)
    assert set(envelope.deliveries.values_list("channel", "state", "last_error")) == {
        ("in_app", "skipped", "legacy_matrix_channel"),
        ("native_push", "skipped", "legacy_matrix_channel")}


def test_certificate_notice_is_bound_to_event_owner_route_and_revision(monkeypatch):
    space, event, owner, registration = setup_registration()
    from apps.events.models import EventAttendanceCertificate, EventFeedbackResponse, EventFeedbackSurvey
    from apps.events.notification_sources import certificate_eligible
    survey = EventFeedbackSurvey.objects.create(event=event, title="Feedback", questions=[{
        "id": "rating", "label": "Rating", "type": "number", "options": [], "required": True}])
    response = EventFeedbackResponse.objects.create(survey=survey, registration=registration,
        answers_snapshot="{}", certificate_requested=True)
    certificate = EventAttendanceCertificate.objects.create(response=response, registration=registration,
        revision=1, recipient_name="Owner", event_title=event.title, event_starts_at=event.starts_at,
        event_ends_at=event.ends_at, issuer_name=space.name, object_key="certificates/recon.pdf", status="active")
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    envelope = notices.certificate_envelope(certificate, "certificate_ready")
    assert certificate_eligible(envelope)
    envelope.revision = "2"
    assert not certificate_eligible(envelope)
    envelope.revision = "1"
    envelope.context["event_id"] = make_event(space).pk
    assert not certificate_eligible(envelope)
    envelope.context["event_id"] = event.pk
    envelope.makerspace = make_space("recon-certificate-other")
    assert not certificate_eligible(envelope)
