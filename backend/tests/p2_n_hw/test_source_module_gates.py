"""Shared categories cannot add unrelated modules to live domain delivery."""
import pytest

from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_resolution import resolve
from apps.integrations.notification_tasks import deliver_envelope
from apps.machines.notifications_p2_service import notify_service
from tests.module_helpers import disable_module
from tests.p2_n_hw.test_service import request

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("printer", [False, True])
def test_service_delivery_reaches_printer_jobs_without_a_separate_printing_switch(equipment, printer):
    # Decision 340b: printer jobs are machine-service jobs; a stale `printing` key changes nothing.
    row = request(equipment, printer=printer)
    notify_service(row, "accepted")
    envelope = NotificationEnvelope.objects.get(source_kind="machines.service", audience="requester")
    disable_module(equipment.space, "printing")
    assert bool(resolve(envelope)) is True
    deliver_envelope(envelope.pk)
    assert bool(equipment.fake.calls) is True


def test_generic_service_still_requires_machine_service(equipment):
    row = request(equipment)
    notify_service(row, "accepted")
    envelope = NotificationEnvelope.objects.get(source_kind="machines.service", audience="requester")
    disable_module(equipment.space, "machine_service")
    assert resolve(envelope) == []
    deliver_envelope(envelope.pk)
    assert equipment.fake.calls == []


def test_generic_service_category_stays_configurable_without_printing(equipment):
    from apps.integrations.notification_availability import available_channels
    from apps.notifications.preferences import preference_cells
    disable_module(equipment.space, "printing")
    equipment.space.refresh_from_db()
    assert "telegram" in available_channels(equipment.space, "printing")
    assert any(cell["feature"] == "printing" and cell["available"]
               for cell in preference_cells(equipment.space, equipment.owner))


def test_unverified_proven_owner_mute_cannot_fall_back_to_direct_mail(equipment):
    from apps.hardware_requests.notifications_p2_requests import notify_request
    from apps.integrations.models import EmailLog, EmailNotificationMute
    from apps.notifications.models_preferences import NotificationPreference
    from tests.p2_n_hw.test_hardware import loan
    equipment.owner.email_verified_at = None
    equipment.owner.save(update_fields=["email_verified_at"])
    NotificationPreference.objects.filter(user=equipment.owner, category="hardware_requests").update(
        channels=["email", "telegram"])
    EmailNotificationMute.objects.create(makerspace=equipment.space, stream="hardware",
        audience="requester", target="requester", event="request_accepted")
    row = loan(equipment)
    notify_request(row, "accepted")
    envelope = NotificationEnvelope.objects.get(source_kind="hardware.request", audience="requester")
    assert {target.channel for target in resolve(envelope)} == {"telegram"}
    assert not EmailLog.objects.filter(source_kind="hardware.owner_mailbox").exists()
    deliver_envelope(envelope.pk)
    assert not envelope.deliveries.filter(channel="email").exists()
    assert equipment.fake.calls
