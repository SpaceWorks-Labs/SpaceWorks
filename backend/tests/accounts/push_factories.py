"""Canonical native-push parents for per-device child fixtures.

MemberPushDelivery rows are children of an integrations.NotificationDelivery; the
parent envelope's recipient (not the device or inbox) owns the delivery history.
"""
from uuid import uuid4


def push_parent(space, recipient, *, feature="hardware_requests", audience="member", state="sent", **fields):
    from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope

    envelope = NotificationEnvelope.objects.create(
        makerspace=space, recipient=recipient, feature=feature, event="accepted", audience=audience,
        source_kind="hardware_requests.lifecycle", source_id="1", dedup_key=uuid4().hex,
        message_body="Your request was accepted",
    )
    return NotificationDelivery.objects.create(
        makerspace=space, envelope=envelope, channel="native_push", target_key=uuid4().hex,
        provider="apns", provider_source="platform", state=state, **fields,
    )


def member_push(space, recipient, push_device, **fields):
    from apps.notifications.models_push import MemberPushDelivery

    return MemberPushDelivery.objects.create(
        envelope_delivery=push_parent(space, recipient), push_device=push_device, **fields,
    )
