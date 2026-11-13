"""Lane R fixtures create facts only; no sender, dispatch or cutover activation."""
import json
import uuid
from datetime import datetime, UTC

from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.models_cutover import NotificationLegacyMapping
from apps.makerspaces.secrets import encrypt_value
from tests.return_helpers import make_space, make_user


def at(value):
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def report_space(slug, *, zone="Asia/Kolkata", hidden=False):
    space = make_space(slug)
    space.enabled_modules = ["reports", "sms", "whatsapp"]
    space.timezone = zone
    space.save(update_fields=["enabled_modules", "timezone"])
    return space


def delivery(space, *, channel="sms", state="sent", created=None, history=None, **fields):
    identity = uuid.uuid4().hex
    user = make_user("report-" + identity)
    envelope = NotificationEnvelope.objects.create(makerspace=space, recipient=user,
        feature=fields.pop("feature", "bookings"), event="confirmed", audience=fields.pop("audience", "requester"),
        source_kind="migration.history" if history else "bookings.lifecycle",
        source_id="123" if history else "1", dedup_key=identity, message_body="PRIVATE BODY")
    row = NotificationDelivery.objects.create(makerspace=space, envelope=envelope, channel=channel,
        target_key=identity, provider="twilio", provider_source=fields.pop("provider_source", "platform"),
        state=state, historical=bool(history), sender_key="PRIVATE SENDER", provider_id="PRIVATE PROVIDER ID",
        **fields)
    if created:
        NotificationDelivery.objects.filter(pk=row.pk).update(created_at=created)
        row.refresh_from_db()
    if history:
        NotificationLegacyMapping.objects.create(legacy_model="MessagingDelivery", legacy_id=123,
            canonical_model="NotificationDelivery", canonical_id=row.pk, makerspace=space,
            disposition="historical", snapshot=encrypt_value(json.dumps(history)))
    return row
