"""Equipment producers keep authored staff chat wording on every room channel."""
from datetime import timedelta
from types import SimpleNamespace as Bag

import pytest
from django.utils import timezone

from apps.hardware_requests import notifications_p2 as equipment
from apps.hardware_requests import notifications_p2_rooms as rooms
from apps.integrations.destinations import NotificationScope
from apps.integrations.models_chat_templates import ChatTemplate

pytestmark = pytest.mark.django_db


@pytest.fixture
def room_sink(world, monkeypatch):
    dispatched, intents = [], []
    monkeypatch.setattr(equipment, "staff_user_ids_for_feature", lambda *_: [])
    monkeypatch.setattr(rooms, "is_notification_enabled", lambda *_: True)
    monkeypatch.setattr(rooms, "dispatch_channel", lambda **kwargs: dispatched.append(kwargs))
    def sink(**kwargs):
        intents.append(kwargs.copy())
        # Isolate recipient selection/domain relations; exercise the real fanout,
        # room dispatcher seam, shared renderer and database ChatTemplate lookup.
        kwargs.update(subject=world.booking, owner=None, own=None)
        return equipment.fanout(**kwargs)
    return Bag(sink=sink, dispatched=dispatched, intents=intents)


@pytest.mark.parametrize("family", ["maintenance", "certification", "procurement", "inventory", "printer", "machine"])
def test_producer_passes_staff_context_to_shared_room_renderer(world, room_sink, monkeypatch, family):
    now = timezone.now()
    if family == "maintenance":
        from apps.machines import notifications_p2_maintenance as producer
        machine = Bag(pk=9, name="Laser", makerspace=world.space, machine_type=Bag(pk=3), machine_type_id=3)
        row = Bag(pk=18, machine=machine, machine_id=9, created_at=now, summary="Inspected",
            performed_at=now, parts_note="", performed_by_id=world.staff.pk)
        invoke = lambda: producer.notify(row, "logged")
        feature, event, template, expected = "maintenance", "logged", "Inspect {{ machine.name }}", "Inspect Laser"
    elif family == "certification":
        from apps.machines import notifications_p2_certifications as producer
        certification = Bag(pk=4, name="Laser induction", makerspace=world.space, machine_type_id=3)
        row = Bag(pk=19, certification_type=certification, membership=Bag(user=world.owner), membership_id=1,
            granted_at=now, revoked_at=None, expires_at=now + timedelta(days=7))
        invoke = lambda: producer.notify(row, "expiring")
        feature, event, template, expected = "certifications", "expiring", "Renew {{ subject.name }}", "Renew Laser induction"
    elif family == "procurement":
        from apps.machines import notifications_p2_stock as producer
        row = Bag(pk=20, makerspace=world.space, name="Laser filter", updated_at=now, status="received",
            machine_type_id=3, resulting_machine_id=None, source_pool_id=None, resulting_pool_id=None)
        invoke = lambda: producer.notify(row, "procurement_received")
        feature, event, template, expected = "stock", "procurement_received", "Received {{ subject.name }}", "Received Laser filter"
    elif family == "inventory":
        from apps.inventory import notifications_p2 as producer
        row = Bag(pk=21, makerspace=world.space, name="Screws", updated_at=now, available_quantity=2,
            reorder_point=5, category_id=None)
        invoke = lambda: producer.notify_stock(row)
        feature, event, template, expected = "stock", "low_stock", "Buy {{ subject.name }}", "Buy Screws"
    else:
        from apps.machines import notifications_p2_service as producer
        row = Bag(pk=22, makerspace=world.space, updated_at=now, status="accepted", member=world.owner,
            requester=world.owner, member_id=world.owner.pk, requester_id=world.owner.pk, queue_id=2, bucket_id=None,
            assigned_machine_id=None, queue=Bag(name="Printer", machine_type=Bag(pk=3, makerspace_id=None,
                slug="3d_printer" if family == "printer" else "laser")), capability_payload={},
            title="Test part", reason="Print part", requester_name="Maker", contact_email="private@example.test",
            contact_phone="123", reprint_of_id=None, Status=Bag(IN_PROGRESS="in_progress"))
        invoke = lambda: producer.notify_service(row, "accepted")
        feature, event = "printing", "accepted"
        template, expected = "Job {{ print_request.title }}", "Job Test part"
    # Email rendering is unrelated to this regression and requires concrete
    # machine-type FKs. Keep real producer context building and chat rendering.
    monkeypatch.setattr(producer, "render", lambda *_, **__: {
        "subject": "Fallback", "text_body": "Fallback staff text", "html_body": ""})
    monkeypatch.setattr(producer, "fanout", room_sink.sink)
    ChatTemplate.objects.create(makerspace=world.space, feature=feature, event=event, text_body=template)
    invoke()
    assert len(room_sink.intents) == 1
    assert room_sink.intents[0]["staff_context"]
    assert {call["channel"] for call in room_sink.dispatched} == set(rooms.ROOM_CHANNELS)
    assert all(call["text_body"] == expected for call in room_sink.dispatched)
    # Template bags can contain staff fields, but only source IDs/gates persist
    # into the JSON metadata inspected again before send/retry/release.
    assert all(call["payload"]["context"] == room_sink.intents[0]["context"] for call in room_sink.dispatched)
    assert all("staff_context" not in call["payload"] for call in room_sink.dispatched)


@pytest.mark.parametrize("state", ["absent", "inactive", "empty", "broken"])
def test_room_renderer_preserves_fallback_for_unusable_overrides(world, room_sink, state):
    if state != "absent":
        ChatTemplate.objects.create(makerspace=world.space, feature="maintenance", event="logged",
            text_body={"inactive": "Override", "empty": "{{ absent }}", "broken": "{% invalid %}"}[state],
            is_active=state != "inactive")
    rooms.queue_rooms(space=world.space, feature="maintenance", event="logged", kind="machines.maintenance",
        source=world.booking.pk, version="1", subject=world.booking, scope=NotificationScope(),
        context={"schedule": False}, body="Staff fallback", key="fallback-test",
        staff_context={"machine": Bag(name="Laser")})
    assert len(room_sink.dispatched) == len(rooms.ROOM_CHANNELS)
    assert all(call["text_body"] == "Staff fallback" for call in room_sink.dispatched)


def test_certification_digest_has_its_own_staff_template_context(world, room_sink, monkeypatch):
    from apps.machines import notifications_p2_certifications as producer
    from apps.machines.models import CertificationType, MachineType
    machine_type = MachineType.objects.create(makerspace=world.space, name="Laser", slug="digest-laser")
    CertificationType.objects.create(makerspace=world.space, machine_type=machine_type, name="Laser training")
    monkeypatch.setattr(producer, "fanout", room_sink.sink)
    ChatTemplate.objects.create(makerspace=world.space, feature="certifications", event="expiring",
        text_body="Training at {{ makerspace.name }}: {{ subject.name }}")
    producer.notify_digest(world.space, Bag(subject=f"{machine_type.pk}:2026-10-17"),
        Bag(title="Expiry", body="Review training"))
    assert room_sink.dispatched
    assert all(call["text_body"] == f"Training at {world.space.name}: Laser training" for call in room_sink.dispatched)


def test_hardware_lifecycle_uses_staff_context_and_keeps_owner_template_out_of_rooms(world, room_sink, monkeypatch):
    from apps.hardware_requests import notifications_p2_requests as producer
    from apps.hardware_requests.models import HardwareRequest
    row = HardwareRequest.objects.create(makerspace=world.space, requester=world.owner,
        requester_username=world.owner.username, status="accepted")
    monkeypatch.setattr(producer, "fanout", room_sink.sink)
    monkeypatch.setattr("apps.hardware_requests.notifications_p2_contact.notify", lambda *_: None)
    monkeypatch.setattr(producer, "render", lambda *_, **__: {"subject": "Mail", "text_body": "Owner/private", "html_body": ""})
    ChatTemplate.objects.create(makerspace=world.space, feature="hardware_requests", event="accepted",
        text_body="Staff loan {{ request.id }} {{ request.status }}")
    producer.notify_request(row, "accepted")
    assert room_sink.dispatched
    assert all(call["text_body"] == f"Staff loan {row.pk} accepted" for call in room_sink.dispatched)


def test_hardware_charge_has_staff_request_context(world, room_sink, monkeypatch):
    from apps.hardware_requests import notifications_p2_requests as producer
    from apps.hardware_requests.models import HardwareRequest
    row = HardwareRequest.objects.create(makerspace=world.space, requester=world.owner, requester_username=world.owner.username)
    monkeypatch.setattr(producer, "fanout", room_sink.sink)
    ChatTemplate.objects.create(makerspace=world.space, feature="hardware_requests", event="deposit_raised",
        text_body="Loan {{ request.id }} needs deposit")
    producer.notify_charge(row, "deposit_raised", Bag(pk=33, created_at=timezone.now(), subject_type="loan", subject_id=str(row.pk)))
    assert room_sink.dispatched
    assert all(call["text_body"] == f"Loan {row.pk} needs deposit" for call in room_sink.dispatched)


def test_problem_report_has_declared_staff_template_variables(world, room_sink, monkeypatch):
    from apps.hardware_requests import notifications_p2_reports as producer
    row = Bag(pk=34, makerspace=world.space, created_at=timezone.now(), request_id=None, requester_id=world.owner.pk, loan_id=5)
    monkeypatch.setattr(producer, "fanout", room_sink.sink)
    ChatTemplate.objects.create(makerspace=world.space, feature="hardware_requests", event="problem_report.filed",
        text_body="Report {{ problem_report_id }} at {{ makerspace.name }}")
    producer.notify_report(row)
    assert room_sink.dispatched
    assert all(call["text_body"] == f"Report 34 at {world.space.name}" for call in room_sink.dispatched)


def test_staff_loan_escalation_keeps_staff_summary_template_context(world, room_sink, monkeypatch):
    from apps.hardware_requests import notifications_p2_reminders as producer
    from apps.hardware_requests.models import HardwareRequest
    row = HardwareRequest.objects.create(makerspace=world.space, requester=world.owner,
        requester_username=world.owner.username, status="issued", return_due_at=timezone.now() - timedelta(days=2))
    monkeypatch.setattr(producer, "fanout", room_sink.sink)
    monkeypatch.setattr(producer, "render", lambda *_, **__: {"subject": "Overdue", "text_body": "Fallback", "html_body": ""})
    ChatTemplate.objects.create(makerspace=world.space, feature="hardware_requests", event="overdue_escalated",
        text_body="Loan {{ request.id }}: {{ staff_summary }}")
    producer.deliver(world.space, row, Bag(kind="escalation", offset_seconds=3600),
        Bag(body="Escalate custody"), timezone.get_current_timezone())
    assert room_sink.dispatched
    assert all(call["text_body"] == f"Loan {row.pk}: Escalate custody" for call in room_sink.dispatched)
