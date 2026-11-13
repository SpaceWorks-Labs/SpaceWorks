from datetime import timedelta

import pytest
from apps.makerspaces.models import MakerspaceMembership
from django.utils import timezone

from apps.apiclients.models import ApiKeyRequest
from apps.apiclients.notifications import notify_api_key_request_resolved
from apps.devices.models import Device, DeviceEvent
from apps.devices.notifications import notify_device_state
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_resolution import resolve
from apps.integrations.notification_sources import source_eligible
from apps.makerspaces.models import SubdomainRequest
from apps.makerspaces.subdomain_notifications import notify_subdomain_request_resolved

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("domain", ["api", "subdomain"])
@pytest.mark.parametrize("status", ["approved", "rejected"])
def test_access_outcomes_separate_private_note_from_staff_summary(lane, domain, status):
    owner = lane.account("technical-requester")
    if domain == "api":
        row = ApiKeyRequest.objects.create(makerspace=lane.space, requester=owner, label="ERP", status=status,
            resolved_by=lane.manager, resolved_at=timezone.now(), resolution_note="Private resolution note")
        notify_api_key_request_resolved(row)
        event = "api_key_request_resolved"
    else:
        row = SubdomainRequest.objects.create(makerspace=lane.space, requested_by=owner, requested_label="workshop",
            status=status, decided_by=lane.manager, decided_at=timezone.now(), note="Private resolution note")
        notify_subdomain_request_resolved(row)
        event = "subdomain_request_resolved"
    envelope = lane.deliver(event, owner)
    assert source_eligible(envelope)
    assert envelope.deliveries.get(channel="telegram").state == "accepted"
    assert envelope.stream != "account"
    assert status in lane.fake.calls[-1][1]["text"]
    staff = NotificationEnvelope.objects.get(event=event, audience="staff")
    from apps.integrations.notification_sources import render
    assert "Private resolution note" not in render(staff)["text"]
    MakerspaceMembership.all_tracks.filter(user=lane.manager).update(status="revoked")
    assert resolve(envelope) == []


@pytest.mark.parametrize("event", ["offline", "recovered"])
def test_device_state_edges_reach_scoped_staff_only(lane, event):
    device = Device.objects.create(makerspace=lane.space, kind="generic", name="Bench sensor", status="active",
        public_key="public-key", key_fingerprint="b"*64, last_seen_at=timezone.now()-timedelta(hours=1))
    edge = DeviceEvent.objects.create(makerspace=lane.space, device=device, device_id_snapshot=str(device.pk),
        device_name=device.name, device_key_version=1,
        event_type="offline_detected" if event == "offline" else "recovered")
    notify_device_state(lane.space, device, event, now=timezone.now())
    envelope = lane.deliver(event, lane.manager)
    assert envelope.source_id == str(edge.pk)
    assert source_eligible(envelope)
    assert not NotificationEnvelope.objects.filter(recipient=lane.owner).exists()
    assert event in lane.fake.calls[-1][1]["text"].lower()
    device.status = "revoked"
    device.save(update_fields=["status"])
    assert resolve(envelope) == []


def test_device_recovery_does_not_rewrite_encrypted_outage_snapshot(lane):
    from apps.integrations.notification_sources import render
    device = Device.objects.create(makerspace=lane.space, kind="generic", name="Sensor", status="active",
        public_key="public-key", key_fingerprint="c"*64, offline_since=timezone.now())
    DeviceEvent.objects.create(makerspace=lane.space, device=device, device_id_snapshot=str(device.pk),
        device_name=device.name, device_key_version=1, event_type="offline_detected")
    notify_device_state(lane.space, device, "offline", now=timezone.now())
    envelope = NotificationEnvelope.objects.get()
    before = render(envelope)
    device.offline_since = None
    device.save(update_fields=["offline_since"])
    assert render(envelope) == before
