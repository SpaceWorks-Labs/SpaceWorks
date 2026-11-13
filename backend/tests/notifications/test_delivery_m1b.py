"""One canonical intent, optional inbox and real FCM/APNs wire contracts."""
from uuid import NAMESPACE_URL, uuid5

import pytest
from django.db import IntegrityError, transaction

from apps.integrations.notification_delivery import send
from apps.notifications.member_push import deliver_row, enqueue_member_push, send_envelope_push
from apps.notifications.models_push import MemberPushDelivery
from apps.notifications.tasks import deliver_member_push, sweep_member_push
from tests.notifications.test_support_m1b import push_case, wire_message  # noqa: F401

pytestmark = pytest.mark.django_db


def deliver(case):
    return send_envelope_push(case.parent, case.rendered)


@pytest.mark.parametrize("push_case", ["fcm", "apns"], indirect=True)
@pytest.mark.parametrize("inbox", [True, False])
def test_one_child_per_envelope_device_with_optional_inbox(push_case, inbox):
    case = push_case
    parent = case.prepare(inbox=inbox)
    assert deliver(case).accepted
    assert deliver(case).accepted
    assert len(case.calls) == 1
    child = MemberPushDelivery.objects.get(envelope_delivery=parent)
    assert child.inbox_row_id == (case.inbox.pk if inbox else None)
    assert child.status == "sent" and child.attempts == 1
    assert child.sent_at and child.lease_token is None and child.lease_until is None
    with pytest.raises(IntegrityError), transaction.atomic():
        MemberPushDelivery.objects.create(envelope_delivery=parent, push_device=case.device)
    alert, data = wire_message(case)
    from apps.integrations.push_payload import short_body
    assert alert == {"title": "Your booking", "body": short_body(case.summary)}
    assert data["category"] == ("sw.inbox" if inbox else "sw.open")
    assert data["v"] == "3" and data["event_id"] == str(uuid5(NAMESPACE_URL, case.envelope.dedup_key))
    assert data["makerspace_id"] == str(case.space.pk)
    assert data["feature"] == "bookings" and data["event"] == "confirmed"
    assert ("inbox_row_id" in data) is inbox
    assert all(isinstance(value, str) for value in data.values())
    assert case.staff_text not in str(case.calls)
    if case.device.provider == "apns":
        assert case.calls[0]["json"]["aps"]["thread-id"] == str(case.space.pk)
        assert "apns-collapse-id" not in case.calls[0]["headers"]


@pytest.mark.parametrize("gate", ["module", "member_inbox", "in_app_matrix", "personal_in_app"])
def test_push_does_not_require_an_inbox_or_its_module(push_case, gate):
    from apps.integrations.models import NotificationPreference as Matrix
    from apps.notifications.models import MemberNotificationPreference
    case = push_case
    if gate == "module":
        case.space.enabled_modules.remove("notifications")
        case.space.save(update_fields=["enabled_modules"])
    elif gate == "member_inbox":
        case.space.enabled_features.remove("notifications.member_inbox")
        case.space.save(update_fields=["enabled_features"])
    elif gate == "in_app_matrix":
        Matrix.objects.filter(makerspace=case.space, channel="in_app").update(enabled=False)
    else:
        MemberNotificationPreference.objects.create(makerspace=case.space, user=case.user,
            feature="bookings", channel="in_app", enabled=False)
    case.prepare(inbox=False)
    assert deliver(case).accepted and len(case.calls) == 1
    assert MemberPushDelivery.objects.get(envelope_delivery=case.parent).inbox_row_id is None


def test_deleting_inbox_sets_null_and_keeps_sent_child_without_resend(push_case):
    case = push_case
    case.prepare()
    assert deliver(case).accepted
    case.inbox.delete()
    child = MemberPushDelivery.objects.get(envelope_delivery=case.parent)
    assert child.inbox_row_id is None and child.status == "sent"
    assert deliver(case).accepted and len(case.calls) == 1


def test_legacy_inbox_writer_and_queued_task_cannot_start_a_push(push_case):
    case = push_case
    inbox = case.enqueue()
    case.queued.assert_not_called()
    assert enqueue_member_push(inbox.pk) is False
    assert deliver_row(inbox.pk) is False
    assert deliver_member_push.run(inbox.pk) is False
    assert not MemberPushDelivery.objects.exists() and case.calls == []


@pytest.mark.parametrize("push_case", ["fcm", "apns"], indirect=True)
def test_invalid_provider_token_deactivates_only_the_device(push_case):
    case = push_case
    case.prepare()
    case.status = 410 if case.device.provider == "apns" else 404
    case.error = {"reason": "Unregistered"} if case.device.provider == "apns" else {
        "error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}}
    assert not deliver(case).accepted
    case.device.refresh_from_db()
    child = MemberPushDelivery.objects.get(envelope_delivery=case.parent)
    assert not case.device.active and case.device.invalidated_at
    assert child.status == "failed" and child.attempts == 1
    assert not child.retryable and child.last_error == "invalid_token"
    assert sweep_member_push()["enqueued"] == 0
    assert not deliver(case).accepted and len(case.calls) == 1


def test_explicit_transient_rejections_retry_to_canonical_budget(push_case):
    case = push_case
    case.prepare()
    case.status, case.error = 503, {"error": {"status": "UNAVAILABLE"}}
    for attempt in range(1, 5):
        result = deliver(case)
        assert result.retryable is (attempt < 4)
        child = MemberPushDelivery.objects.get(envelope_delivery=case.parent)
        assert child.status == "failed" and child.attempts == attempt
        assert child.retryable is (attempt < 4)
    assert not deliver(case).accepted and len(case.calls) == 4
    case.inbox.refresh_from_db()
    assert case.inbox.summary == case.summary


def test_network_outcome_is_held_and_never_retried(push_case):
    case = push_case
    case.prepare()
    case.before_http = lambda: (_ for _ in ()).throw(TimeoutError("private provider detail"))
    result = deliver(case)
    assert result.ambiguous and not result.retryable
    child = MemberPushDelivery.objects.get(envelope_delivery=case.parent)
    assert child.status == "held" and child.last_error == "unknown_provider_outcome"
    assert deliver(case).ambiguous
    assert child.attempts == 1 and case.calls == []
    assert sweep_member_push()["enqueued"] == 0
    case.parent.refresh_from_db()
    assert case.parent.state == "held"


def test_canonical_pipeline_uses_registered_adapter_and_finishes_parent(push_case):
    case = push_case
    case.prepare(inbox=False)
    send(case.parent.pk)
    case.parent.refresh_from_db()
    assert case.parent.state == "sent"
    assert MemberPushDelivery.objects.get(envelope_delivery=case.parent).status == "sent"
    send(case.parent.pk)
    assert len(case.calls) == 1


@pytest.mark.parametrize("link,expected", [
    ("/member/events/42/ticket", True), ("/m/m1b-push/member", True),
    ("/m/m1b-push/admin/notifications", False), ("/control/", False),
    ("https://evil.example/member", False), ("//evil.example/member", False),
    ("javascript:alert(1)", False), ("/member?token=secret", False),
    ("/member#fragment", False), ("/member\\secret", False), ("/member\n", False), ("", False),
])
def test_only_supported_local_links_enter_payload(push_case, link, expected):
    case = push_case
    case.rendered["link"] = link
    case.prepare(inbox=False)
    assert deliver(case).accepted
    assert ("link" in wire_message(case)[1]) is expected


def test_broker_outage_keeps_child_recoverable_and_inbox_readable(push_case):
    case = push_case
    case.prepare()
    MemberPushDelivery.objects.create(envelope_delivery=case.parent, push_device=case.device)
    case.parent_queue.side_effect = RuntimeError("offline")
    assert sweep_member_push() == {"enqueued": 0, "skipped": 0, "failed": 1}
    assert case.inbox.summary == case.summary and case.calls == []


def test_canonical_and_legacy_inbox_writers_share_intent_without_push_fanout(push_case):
    from apps.notifications.inbox import write_envelope_inbox
    from apps.notifications.models_inbox import NotificationInboxRow
    case = push_case
    case.prepare()
    row = write_envelope_inbox(case.envelope, case.rendered)
    assert row.pk == case.inbox.pk
    assert NotificationInboxRow.objects.filter(event_key=row.event_key).count() == 1
    assert case.calls == []
    assert deliver(case).accepted and len(case.calls) == 1
    write_envelope_inbox(case.envelope, case.rendered)
    assert deliver(case).accepted and len(case.calls) == 1


@pytest.mark.parametrize("audience,expected", [("member", "member"), ("requester", "member"), ("staff", "staff")])
def test_canonical_inbox_adapter_preserves_audience_and_scope_without_enqueuing(push_case, audience, expected):
    from apps.notifications.inbox import write_envelope_inbox
    case = push_case
    case.prepare(inbox=False)
    case.envelope.audience = audience
    case.envelope.scope = {"category_id": 42}
    row = write_envelope_inbox(case.envelope, case.rendered)
    assert row.audience == expected and row.scope == {"category_id": 42}
    assert row.summary == case.summary[:2000]
    case.queued.assert_not_called()
    assert case.calls == []


def test_late_invalid_token_does_not_deactivate_rotated_destination(push_case):
    case = push_case
    case.prepare(inbox=False)
    case.status = 404
    case.error = {"error": {"status": "NOT_FOUND"}}

    def rotate():
        case.device.token_fingerprint = "r" * 64
        case.device.set_token("fresh-token")
        case.device.save(update_fields=["token_fingerprint", "token_ciphertext"])

    case.before_http = rotate
    assert not deliver(case).accepted
    case.device.refresh_from_db()
    assert case.device.active and case.device.invalidated_at is None
    assert MemberPushDelivery.objects.get(envelope_delivery=case.parent).last_error == "invalid_token"


def test_emitted_null_scope_means_no_subject_for_inbox_and_push(push_case):
    """Domain fan-out persists NotificationScope().as_dict(); its nulls are "no subject"."""
    from apps.integrations.destinations import NotificationScope
    from apps.notifications.inbox import write_envelope_inbox
    case = push_case
    case.prepare(inbox=False, scope=NotificationScope())
    assert case.envelope.scope == {"machine_id": None, "machine_type_id": None, "category_id": None}
    assert write_envelope_inbox(case.envelope, case.rendered).scope == {}
    assert deliver(case).accepted and len(case.calls) == 1
