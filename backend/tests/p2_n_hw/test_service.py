import pytest

from apps.machines.models import MachineType, ServiceQueue, MachineServiceRequest
from apps.machines.notifications_p2_service import notify_service
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_resolution import resolve
from apps.integrations.notification_sources import source_eligible
from apps.integrations.notification_tasks import deliver_envelope

pytestmark = pytest.mark.django_db


def request(world, printer=False, status="accepted"):
    machine_type = MachineType.objects.get(slug="3d_printer", makerspace=None) if printer else MachineType.objects.create(
        makerspace=world.space, name="Laser", slug="p2-laser")
    queue = ServiceQueue.objects.create(makerspace=world.space, machine_type=machine_type, name="Queue")
    return MachineServiceRequest.objects.create(makerspace=world.space, queue=queue,
        requester=world.owner, member=world.owner, title="Private job title", contact_email=world.owner.email,
        status=status, handled_by=world.manager, accepted_by=world.manager)


@pytest.mark.parametrize("printer", [True, False])
@pytest.mark.parametrize("event,status", [
    ("submitted", "pending"), ("accepted", "accepted"), ("rejected", "rejected"),
    ("started", "in_progress"), ("completed", "completed"), ("failed", "failed"),
    ("collected", "collected"), ("reprinted", "accepted"),
])
def test_all_machine_service_coverage(equipment, printer, event, status):
    row = request(equipment, printer, status)
    if event == "reprinted":
        row.reprint_of = MachineServiceRequest.objects.create(makerspace=equipment.space, queue=row.queue,
            requester=equipment.owner, member=equipment.owner, title="Original", status="failed")
        row.save(update_fields=["reprint_of", "updated_at"])
    assert notify_service(row, event).scheduled
    envelopes = NotificationEnvelope.objects.filter(source_kind="machines.service")
    assert set(envelopes.values_list("audience", flat=True)) == {"requester", "staff"}
    own = envelopes.get(audience="requester")
    assert own.recipient_id == equipment.owner.pk
    assert own.scope["machine_type_id"] == row.queue.machine_type_id
    assert {target.channel for target in resolve(own)} == {"telegram"}
    deliver_envelope(own.pk)
    assert equipment.fake.calls
    assert str(row.public_token) not in str(equipment.fake.calls)
    from apps.integrations.models import NotificationDeliveryLog
    for log in NotificationDeliveryLog.objects.filter(event=event):
        assert row.title not in log.text_body
        assert equipment.owner.email not in log.text_body
        assert str(row.public_token) not in log.text_body
    notify_service(row, event)
    assert envelopes.count() == 2


def test_staff_scope_is_rechecked_at_send(equipment):
    from tests.machines.certification_helpers import _manager
    from apps.machines.models import MembershipMachineTypeScope
    row = request(equipment)
    manager, membership = _manager(equipment.space, "p2-scoped-manager", row.queue.machine_type)
    notify_service(row, "accepted")
    envelope = NotificationEnvelope.objects.get(source_kind="machines.service", audience="staff", recipient=manager)
    assert source_eligible(envelope)
    MembershipMachineTypeScope.objects.filter(membership=membership).delete()
    assert not source_eligible(envelope)
    assert not resolve(envelope)


def test_room_source_rechecks_resource_and_scope(equipment):
    from apps.integrations.models import NotificationDeliveryLog
    from apps.hardware_requests.notifications_p2_rooms import eligible_room
    row = request(equipment)
    notify_service(row, "accepted")
    log = NotificationDeliveryLog.objects.filter(event="accepted").first()
    assert log is not None and eligible_room(log)
    row.reason = "Changed after queuing"
    row.save(update_fields=["reason", "updated_at"])
    assert not eligible_room(log)


def test_room_transport_skips_stale_equipment_source(equipment):
    from apps.integrations.dispatch_channels_delivery import _deliver_notification
    from apps.integrations.models import NotificationDeliveryLog
    from apps.integrations.models_endpoints import ChannelConfiguration
    # Rooms must be switched on, or the earlier configuration gate skips first.
    ChannelConfiguration.objects.filter(makerspace=equipment.space, channel="telegram").update(room_enabled=True)
    row = request(equipment)
    notify_service(row, "accepted")
    log = NotificationDeliveryLog.objects.filter(event="accepted").first()
    assert log is not None
    row.reason = "Changed after queuing"
    row.save(update_fields=["reason", "updated_at"])
    _deliver_notification(log)
    log.refresh_from_db()
    assert (log.status, log.error) == ("skipped", "equipment_source_no_longer_eligible")
