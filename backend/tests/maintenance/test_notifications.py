import pytest
from django.test import override_settings
from django.utils import timezone

from apps.integrations import notify
from apps.integrations.models import (
    EmailLog,
    MachineTypeEmailTemplate,
    NotificationPreference,
)
from apps.machines.models import Machine, MachineType
from apps.maintenance import notifications, services, services_workflows
from apps.maintenance.models import MaintenanceLog
from tests.maintenance.helpers import make_machine_setup

pytestmark = pytest.mark.django_db


def test_each_maintenance_service_lifecycle_reaches_fanout_once(monkeypatch):
    calls = []
    monkeypatch.setattr(
        services_workflows,
        "notify_maintenance_lifecycle",
        lambda instance, name, **kwargs: calls.append((name, kwargs)),
    )
    _, manager, machine, _ = make_machine_setup("maintenance-fanout")
    services.log_maintenance(machine, actor=manager, summary="Cleaned")
    schedule = services.create_schedule(
        machine,
        actor=manager,
        description="Monthly",
        interval_days=30,
        next_due=timezone.localdate(),
    )
    services.update_schedule(schedule, actor=manager, description="Quarterly")
    services.complete_due(schedule, actor=manager, summary="Completed")
    services.deactivate_schedule(schedule, actor=manager)

    assert [name for name, _ in calls] == [
        "logged",
        "schedule_created",
        "schedule_updated",
        "schedule_completed",
        "schedule_deactivated",
    ]
    assert set(calls[3][1]) == {"log_id"}


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_maintenance_notifications_are_silent_until_email_cell_enabled(monkeypatch, mailoutbox):
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.notification_resolution import resolve
    from apps.integrations.notification_tasks import deliver_envelope
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    makerspace, manager, machine, _ = make_machine_setup("maintenance-pref")
    log = MaintenanceLog.objects.create(machine=machine, performed_by=manager,
        summary="Checked belts", parts_note="No replacement needed")
    accepted = notifications.notify_maintenance_lifecycle(log, "logged", sync=True)
    assert accepted.scheduled and accepted.delivered_counts == {}
    envelope = NotificationEnvelope.objects.get(event="logged", recipient=manager)
    assert "email" not in [target.channel for target in resolve(envelope)]
    assert not EmailLog.objects.filter(stream="maintenance").exists() and not mailoutbox
    NotificationPreference.objects.create(makerspace=makerspace, feature="maintenance", channel="email", enabled=True)
    deliver_envelope.run(envelope.pk)
    assert [message.to for message in mailoutbox] == [[manager.email]]
    assert envelope.deliveries.get(channel="email").state == "sent"
    deliver_envelope.run(envelope.pk)
    assert len(mailoutbox) == 1


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_maintenance_alerts_render_the_actual_machine_type_override(monkeypatch, django_capture_on_commit_callbacks):
    from apps.integrations.notification_tasks import deliver_envelope
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", deliver_envelope.run)
    makerspace, manager, laser, _ = make_machine_setup("maintenance-type-render")
    printer_type = MachineType.objects.get(makerspace__isnull=True, slug="3d_printer")
    printer = Machine.objects.create(makerspace=makerspace, machine_type=printer_type, name="Printer", type_payload={"model": "MK4"})
    for machine_type, label in ((laser.machine_type, "LASER"), (printer_type, "PRINTER")):
        MachineTypeEmailTemplate.objects.create(makerspace=makerspace, machine_type=machine_type,
            stream="maintenance", audience="staff", key="logged", subject=label,
            text_body=f"{label} {{{{ machine.name }}}}")
    NotificationPreference.objects.create(makerspace=makerspace, feature="maintenance", channel="email", enabled=True)
    with django_capture_on_commit_callbacks(execute=True):
        for machine, summary in ((laser, "Laser"), (printer, "Printer")):
            notifications.notify_maintenance_lifecycle(
                MaintenanceLog.objects.create(machine=machine, performed_by=manager, summary=summary),
                "logged", sync=True)
        assert not EmailLog.objects.filter(stream="maintenance").exists()
    assert list(EmailLog.objects.filter(stream="maintenance").values_list("subject", flat=True)) == ["PRINTER", "LASER"]
    assert set(EmailLog.objects.filter(stream="maintenance").values_list("to_email", flat=True)) == {manager.email}


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_maintenance_type_override_drives_chat_and_email_with_staff_native_refused(
    monkeypatch, django_capture_on_commit_callbacks, mailoutbox,
):
    from rest_framework.exceptions import AuthenticationFailed
    from apps.accounts.services_device_tokens import issue_device_token_pair
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.notification_tasks import deliver_envelope
    from apps.notifications.models_preferences import NotificationPreference as PersonalPreference
    makerspace, manager, machine, _ = make_machine_setup("maintenance-type-channels")
    makerspace.enabled_features = sorted(set(makerspace.enabled_features) | {"mobile.push"})
    makerspace.save(update_fields=["enabled_features"])
    MachineTypeEmailTemplate.objects.create(makerspace=makerspace, machine_type=machine.machine_type,
        stream="maintenance", audience="staff", key="logged", subject="Type subject",
        text_body="TYPE CHANNEL WORDING {{ machine.name }}")
    for channel in ("slack", "native_push", "email"):
        NotificationPreference.objects.create(makerspace=makerspace, feature="maintenance", channel=channel, enabled=True)
    PersonalPreference.objects.create(makerspace=makerspace, user=manager, category="maintenance",
        channels=["native_push"], email_fallback=True)
    # Staff notifications remain operational. A staff native session needs a real, MFA-backed
    # device grant (0579b1b3); without one no staff device credential is created.
    with pytest.raises(AuthenticationFailed, match="Invalid device authorization"):
        issue_device_token_pair(manager, None)
    rooms, pushes = [], []
    monkeypatch.setattr("apps.hardware_requests.notifications_p2_rooms.dispatch_channel", lambda **kw: rooms.append(kw) or [])
    monkeypatch.setattr("apps.integrations.push_fcm.send_fcm", lambda *args: pushes.append(args))
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", deliver_envelope.run)
    with django_capture_on_commit_callbacks(execute=True):
        log = MaintenanceLog.objects.create(machine=machine, performed_by=manager, summary="Done")
        notifications.notify_maintenance_lifecycle(log, "logged", sync=True)
        assert pushes == []
    # Room channels are catalog-default on; the real dispatch_channel (patched here) drops channels with no
    # configured destination. What this test protects: every room leg carries the machine-type override wording.
    room_text = {call["channel"]: call["text_body"] for call in rooms}
    assert "slack" in room_text
    assert set(room_text.values()) == {f"TYPE CHANNEL WORDING {machine.name}"}
    assert pushes == []
    assert len(mailoutbox) == 1 and mailoutbox[0].to == [manager.email]
    assert mailoutbox[0].subject == "Type subject"
    assert mailoutbox[0].body == f"TYPE CHANNEL WORDING {machine.name}"
    envelope = NotificationEnvelope.objects.get(event="logged", recipient=manager)
    assert not envelope.deliveries.filter(channel="native_push").exists()
    assert envelope.deliveries.get(channel="email").state == "sent"
