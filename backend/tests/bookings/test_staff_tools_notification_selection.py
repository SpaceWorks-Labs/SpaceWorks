"""Restored lifecycle delivery consumes configured recipient/subject selectors."""

import pytest

from apps.bookings.services_restore import restore_booking
from apps.integrations.models_recipients import NotificationRecipient, RecipientMachineTypeScope
from apps.notifications.models_inbox import NotificationInboxRow
from tests.bookings.test_restored_notifications import cancelled, deliver_restored, enable_inbox, restored_logs
from tests.machines.certification_helpers import _machine_type

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("include_requester", [False, True])
def test_staff_only_selection_suppresses_requester_until_explicitly_selected(
    monkeypatch, django_capture_on_commit_callbacks, include_requester,
):
    tenant, actor, member, resource, booking, send, message = cancelled(monkeypatch)
    enable_inbox(tenant)
    NotificationRecipient.objects.create(makerspace=tenant, feature="bookings", event="restored", kind="user", user=actor)
    if include_requester:
        NotificationRecipient.objects.create(makerspace=tenant, feature="bookings", event="restored", kind="requester")
    with django_capture_on_commit_callbacks(execute=True):
        restore_booking(booking, actor=actor)
    deliver_restored(tenant)
    expected = {actor.email, member.email} if include_requester else {actor.email}
    assert set(restored_logs(tenant).values_list("to_email", flat=True)) == expected
    assert NotificationInboxRow.objects.filter(makerspace=tenant, user=member, event="restored").exists() is include_requester


@pytest.mark.parametrize("matching", [False, True])
def test_scoped_selection_only_overrides_matching_resource_machine_type(
    monkeypatch, django_capture_on_commit_callbacks, matching,
):
    tenant, actor, member, resource, booking, send, message = cancelled(monkeypatch)
    enable_inbox(tenant)
    linked = _machine_type(tenant, "Linked resource type")
    unrelated = _machine_type(tenant, "Unrelated resource type")
    resource.machine_type = linked
    resource.save(update_fields=["machine_type"])
    selected = NotificationRecipient.objects.create(makerspace=tenant, feature="bookings", event="restored", kind="user", user=actor)
    RecipientMachineTypeScope.objects.create(recipient=selected, machine_type=linked if matching else unrelated)
    with django_capture_on_commit_callbacks(execute=True):
        restore_booking(booking, actor=actor)
    # An unrelated selection says nothing about this resource, so existing
    # requester/action-based defaults remain effective.
    deliver_restored(tenant)
    expected = {actor.email} if matching else {actor.email, member.email}
    assert set(restored_logs(tenant).values_list("to_email", flat=True)) == expected
    assert NotificationInboxRow.objects.filter(makerspace=tenant, user=member, event="restored").exists() is not matching


def test_restored_chat_fanout_carries_resource_machine_subject_scope(
    monkeypatch, django_capture_on_commit_callbacks,
):
    tenant, actor, member, resource, booking, send, message = cancelled(monkeypatch)
    linked = _machine_type(tenant, "Scoped chat type")
    resource.machine_type = linked
    resource.save(update_fields=["machine_type"])
    observed = []
    def dispatch(**kwargs):
        observed.append(kwargs)
        return []
    monkeypatch.setattr("apps.integrations.notify.dispatch_channel", dispatch)
    with django_capture_on_commit_callbacks(execute=True):
        restore_booking(booking, actor=actor)
    telegram = next(call for call in observed if call["channel"] == "telegram")
    assert telegram["scope"].machine_type_id == linked.pk
    assert telegram["scope"].machine_id is None
    assert "Status: confirmed" in telegram["text_body"]
