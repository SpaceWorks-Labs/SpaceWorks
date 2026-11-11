"""Provider status order on canonical deliveries, replayed from the durable journal."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.integrations.messaging.protections import recipient_hash, suppressed
from apps.integrations.messaging.webhook_processing import accept_event
from apps.integrations.models_cutover import NotificationIngress
from apps.integrations.notification_ingress import process
from tests.messaging.test_webhooks_m1h_b import leg, pipeline, twilio_post  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("statuses,expected", [
    (["accepted", "failed"], "failed"), (["sent", "undelivered"], "failed"),
    (["failed", "delivered"], "delivered"), (["delivered", "failed"], "delivered"),
    (["read"], "read"), (["read", "sent"], "read"),
])
def test_provider_status_order_and_independent_timestamps(pipeline, statuses, expected):
    row = leg(pipeline, provider_id="SMorder")
    at = timezone.now() - timedelta(hours=1)
    for status in statuses:
        accept_event(provider="twilio", channel="sms", sender_key=pipeline.sms.sender_key,
            dedupe_id=f"SMorder:{status}", kind="status", payload={"message_id": "SMorder", "status": status,
                "timestamp": str(int(at.timestamp())), "error_code": "30003" if status in {"failed", "undelivered"} else ""})
    row.refresh_from_db()
    # Delivered/read evidence wins over failure in either order; progress never regresses.
    assert row.state == expected
    if "failed" in statuses or "undelivered" in statuses:
        assert row.failed_at is not None
    if statuses == ["read"]:
        assert row.read_at is not None
        assert row.sent_at is None and row.delivered_at is None  # Never invented.


def test_statuses_and_stop_work_when_module_off(space, member, pipeline, client):
    row = leg(pipeline)
    space.enabled_modules = [key for key in space.enabled_modules if key not in {"sms", "notifications"}]
    space.save(update_fields=["enabled_modules"])
    assert twilio_post(client, pipeline).status_code == 200
    row.refresh_from_db()
    assert row.state == "delivered"
    fields = {"AccountSid": pipeline.sms.account_sid, "To": pipeline.sms.from_number,
        "From": member.phone_e164, "MessageSid": "SMstopoff", "OptOutType": "STOP"}
    assert twilio_post(client, pipeline, kind="inbound", fields=fields).status_code == 200
    assert suppressed("sms", pipeline.sms.sender_key, recipient_hash("phone", member.phone_e164))


def test_frozen_tenant_status_defers_but_stop_protection_commits(space, member, pipeline, client):
    from apps.tenant_migration.models import SourceMigrationGate
    from tests.tenant_migration.source_gate_helpers import close_gate
    row = leg(pipeline)
    gate = close_gate(space, member)
    stop_sid = "SM" + "b" * 32
    assert twilio_post(client, pipeline).status_code == 200
    fields = {"AccountSid": pipeline.sms.account_sid, "To": pipeline.sms.from_number,
        "From": member.phone_e164, "MessageSid": stop_sid, "OptOutType": "STOP"}
    response = twilio_post(client, pipeline, kind="inbound", fields=fields)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/xml")
    assert response.content == b'<?xml version="1.0" encoding="UTF-8"?><Response/>'
    receipts = {receipt.get_payload()["kind"]: receipt for receipt in NotificationIngress.objects.all()}
    # Sender-level STOP commits regardless of the frozen tenant gate.
    assert receipts["inbound"].state == "processed" and receipts["inbound"].protection_applied
    assert suppressed("sms", pipeline.sms.sender_key, recipient_hash("phone", member.phone_e164))
    row.refresh_from_db()
    assert row.state == "accepted"  # The tenant-gated status update was deferred, not lost.
    status = receipts["status"]
    assert status.state == "held"
    SourceMigrationGate.objects.filter(pk=gate.pk).update(state="open", owner_id=None)
    assert process(status.pk)
    row.refresh_from_db()
    assert row.state == "delivered"
