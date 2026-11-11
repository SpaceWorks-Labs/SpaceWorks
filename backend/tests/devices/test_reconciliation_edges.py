"""Repeated outages retain distinct immutable source edges, with one intent each."""
import pytest
from django.utils import timezone

from apps.devices.models import Device, DeviceEvent
from apps.devices.notifications_p2 import eligible, notify_device_state
from apps.devices.services_events import record_device_event
from apps.integrations.models_contract import NotificationEnvelope
from tests.devices.helpers import active_device

pytestmark = pytest.mark.django_db


def test_outage_recovery_outage_has_three_nonreplayed_sources(monkeypatch):
    space, manager, _, device_id, _ = active_device("recon-device-edges")
    device = Device.objects.get(pk=device_id)
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    for event in ("offline", "recovered", "offline"):
        edge = record_device_event(space, device, DeviceEvent.EventType.OFFLINE if event == "offline"
                                   else DeviceEvent.EventType.RECOVERED)
        for _ in range(2):
            assert notify_device_state(space, device, event, now=timezone.now()).scheduled
        assert NotificationEnvelope.objects.filter(recipient=manager, source_id=str(edge.pk)).count() == 1
    envelopes = list(NotificationEnvelope.objects.filter(recipient=manager, source_kind="devices.state_edge"))
    assert len(envelopes) == 3 and len({row.revision for row in envelopes}) == 3
    assert all(eligible(row) for row in envelopes)
    space.enabled_modules.remove("devices")
    space.save(update_fields=["enabled_modules"])
    assert all(not eligible(row) for row in envelopes)
