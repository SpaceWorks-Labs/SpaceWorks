"""Once-only requester milestone intents: next / started / completed / cancelled."""

import pytest
from django.db import transaction
from django.test import TestCase

from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_sources import render, source_eligible
from apps.machines import role_scope
from apps.machines.models import MachineServiceRequest, ServiceQueue
from apps.machines.notifications_p2_service import notify_service
from apps.machines.service_queue_notices import reevaluate_head
from apps.machines.service_workflow import accept, cancel, collect, complete, create_reprint, start
from tests.machines.eta_helpers import approved, enable, interleave, is_deadlock, job, owner, world

pytestmark = pytest.mark.django_db


def mine(row, event):
    return NotificationEnvelope.objects.filter(source_kind="machines.service", source_id=str(row.pk),
                                               event=event, audience="requester")


def test_next_started_completed_reserve_exactly_once_and_stay_eligible():
    w = world("notice-life")
    row = job(w)
    assert not mine(row, "next").exists()  # never "next" while pending
    accept(row, w.staff, estimated_minutes=30)
    assert mine(row, "next").count() == 1
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    complete(row, w.staff, actual_minutes=30, consumptions=[])
    for event in ("next", "started", "completed"):
        assert mine(row, event).count() == 1
    row.refresh_from_db()
    notify_service(row, "started")
    notify_service(row, "completed")
    assert mine(row, "started").count() == mine(row, "completed").count() == 1
    collect(row, w.staff)
    assert source_eligible(mine(row, "started").get())      # survives completion
    assert source_eligible(mine(row, "completed").get())    # survives collection
    assert not source_eligible(mine(row, "next").get())     # stale once started


def test_head_advances_on_start_and_reorders_never_duplicate_next():
    w = world("notice-head")
    first = approved(w, 30, created=-30, title="First")
    second = approved(w, 30, created=-20, title="Second")
    assert (mine(first, "next").count(), mine(second, "next").count()) == (1, 0)
    start(first, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    assert mine(second, "next").count() == 1
    older = job(w, "Older")
    MachineServiceRequest.objects.filter(pk=older.pk).update(created_at=second.created_at.replace(year=2020))
    accept(older, w.staff, estimated_minutes=10)            # an older approval takes the head
    assert mine(older, "next").count() == 1
    assert not source_eligible(mine(second, "next").get())  # lost first place: stale, not re-sent
    cancel(older, w.staff)
    assert mine(second, "next").count() == 1                # reclaimed: still exactly one
    assert source_eligible(mine(second, "next").get())


def test_a_cancelling_member_promotes_another_members_head_exactly_once():
    w = world("notice-promote")
    a_owner, b_owner = owner("notice-a"), owner("notice-b")
    a_job = approved(w, 20, created=-20, member=a_owner, title="A")
    b_job = approved(w, 20, created=-10, member=b_owner, title="B")
    assert not mine(b_job, "next").exists()
    cancel(a_job, a_owner, by_owner=True)
    cancel(a_job, a_owner, by_owner=True)                   # retry: no second release/audit/notice
    envelope = mine(b_job, "next").get()
    assert envelope.recipient_id == b_owner.pk and envelope.context["initiator"] == f"user:{a_owner.pk}"
    assert source_eligible(envelope)                         # B's own ownership authorizes it
    assert mine(a_job, "cancelled").count() == 1 and source_eligible(mine(a_job, "cancelled").get())
    b_owner.is_active = False
    b_owner.save(update_fields=["is_active"])
    assert not source_eligible(envelope)                     # standing re-checked at delivery
    reevaluate_head(b_job, initiator="test")
    assert mine(b_job, "next").count() == 1                  # never re-reserved


def test_reprint_children_get_independent_markers_and_next():
    w = world("notice-reprint")
    row = approved(w, 15, created=-5)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    complete(row, w.staff, actual_minutes=15, consumptions=[])
    child = create_reprint(row, w.staff)
    assert child.started_notice_at is None and mine(child, "next").count() == 1


def test_device_completion_without_actor_delivers_one_completed_notice_after_staff_scope_loss():
    w = world("notice-device")
    row = approved(w, 15, created=-5)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    complete(row, None, actual_minutes=15, consumptions=[], initiator="device:7")
    envelope = mine(row, "completed").get()
    assert envelope.context["initiator"] == "device:7" and source_eligible(envelope)
    w.staff.is_active = False
    w.staff.save(update_fields=["is_active"])
    assert source_eligible(mine(row, "started").get())      # staff scope never gates an owner notice


def test_ownership_module_and_imported_guards_refuse_or_skip():
    w = world("notice-guards")
    row = approved(w, 15, created=-5)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    envelope = mine(row, "started").get()
    enable(w.space, off=("machine_service",))
    assert not source_eligible(envelope)
    enable(w.space)
    MachineServiceRequest.objects.filter(pk=row.pk).update(member=owner("notice-new-owner"))
    assert not source_eligible(envelope)
    imported = approved(w, 15, created=-4)
    MachineServiceRequest.objects.filter(pk=imported.pk).update(imported_head_notified=True)
    NotificationEnvelope.objects.filter(source_id=str(imported.pk), event="next").delete()
    reevaluate_head(imported, initiator="import")
    assert not mine(imported, "next").exists()


def test_reservation_failure_rolls_back_marker_envelope_and_transition(monkeypatch):
    w = world("notice-rollback")
    row = approved(w, 15, created=-5)
    monkeypatch.setattr("apps.machines.service_queue_notices.emit", lambda **kw: (_ for _ in ()).throw(RuntimeError("db")))
    with pytest.raises(RuntimeError):
        cancel(row, w.staff)
    row.refresh_from_db()
    assert (row.status, row.cancelled_at, row.cancelled_notice_at) == ("accepted", None, None)
    assert not mine(row, "cancelled").exists()


def test_broker_outage_leaves_a_recoverable_committed_intent(monkeypatch):
    w = world("notice-broker")
    row = job(w)
    def down(*_args, **_kwargs):
        raise ConnectionError("broker down")
    monkeypatch.setattr("apps.integrations.notification_tasks.deliver_envelope.delay", down)
    with TestCase.captureOnCommitCallbacks(execute=True):
        accept(row, w.staff, estimated_minutes=5)
    assert mine(row, "next").count() == 1


def test_owner_content_is_rendered_at_delivery_without_private_bearers():
    w = world("notice-content")
    row = approved(w, 15, created=-5, title="Very private title")
    envelope = mine(row, "next").get()
    stored, rendered = envelope.message_body, render(envelope)
    for text in (stored, str(rendered), str(envelope.context)):
        assert "Very private title" not in text and str(row.public_token) not in text
    assert rendered["subject"] == f"Your machine service request #{row.pk} is next"
    from apps.hardware_requests.notifications_p2_email import allowed
    from apps.integrations.models import EmailNotificationMute
    EmailNotificationMute.objects.create(makerspace=w.space, target="requester", stream="printing",
                                         event="next", audience="requester")
    assert allowed(envelope) is False


@pytest.mark.django_db(transaction=True)
def test_concurrent_head_reevaluations_reserve_one_intent():
    w = world("notice-race")
    row = approved(w, 15, created=-5)
    NotificationEnvelope.objects.filter(event="next").delete()

    def evaluate():
        ServiceQueue.objects.select_for_update().get(pk=w.queue.pk)
        local = MachineServiceRequest.objects.select_related("queue__machine_type", "makerspace").get(pk=row.pk)
        return reevaluate_head(local, initiator="race")

    first, second = interleave(evaluate, lambda: transaction.atomic()(evaluate)())
    assert not is_deadlock(first) and not is_deadlock(second)
    assert mine(row, "next").count() == 1


def test_direct_adapter_keeps_a_stable_requester_key_beside_revisioned_staff_intents():
    w = world("notice-adapter")
    row = approved(w, 15, created=-5)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    row.refresh_from_db()
    own = mine(row, "started").get()
    owner_id = row.member_id or row.requester_id
    assert own.dedup_key == f"machines.service:{row.pk}:started:requester:{owner_id}"
    staff_keys = list(NotificationEnvelope.objects.filter(source_id=str(row.pk), event="started", audience="staff")
                      .values_list("dedup_key", flat=True))
    assert all(key.startswith(f"machines.service:{row.pk}:started:") and ":staff:" in key for key in staff_keys)
    notify_service(row, "started")
    assert mine(row, "started").count() == 1


def test_tenant_import_treats_accepted_rows_as_already_told_next():
    from apps.tenant_migration.row_planning import mark_imported_head
    flag = MachineServiceRequest._meta.get_field("imported_head_notified").column
    status = MachineServiceRequest._meta.get_field("status").column
    for value, expected in (("accepted", True), ("pending", False), ("in_progress", False)):
        row = {status: value, flag: False}
        mark_imported_head(MachineServiceRequest, row)
        assert row[flag] is expected
