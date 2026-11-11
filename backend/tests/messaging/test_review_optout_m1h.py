from unittest.mock import patch

import pytest
from django.db import DatabaseError

from apps.integrations.messaging.consent import grant_consent
from apps.integrations.messaging.protections import recipient_hash, suppressed
from apps.integrations.messaging.webhook_processing import accept_event, process_event
from apps.integrations.models import MessagingDelivery, MessagingSuppression, MessagingWebhookEvent
from apps.tenant_migration.models import SourceMigrationGate
from tests.messaging.helpers_m1h_b import setup_pipeline
from tests.tenant_migration.source_gate_helpers import close_gate

pytestmark = pytest.mark.django_db(transaction=True)


def status_event(pipeline, row):
    return accept_event(provider="twilio", channel="sms", sender_key=pipeline.sms.sender_key,
        dedupe_id=f"SM{row.pk}:failed", kind="status", payload={"message_id": f"SM{row.pk}",
            "status": "failed", "error_code": "21610"})


def prepare(pipeline):
    row = pipeline.enqueue()
    phone = recipient_hash("phone", pipeline.member.phone_e164)
    MessagingDelivery.objects.filter(pk=row.pk).update(provider_message_id=f"SM{row.pk}", recipient_phone_hash=phone)
    return row, phone


def test_frozen_tenant_optout_commits_and_retry_does_not_undo_reconsent(space, member):
    from dataclasses import replace
    from apps.hardware_requests.models import HardwareRequest
    from apps.integrations.messaging.dispatch import enqueue_addressed_messages
    from apps.integrations.models import NotificationPreference
    from apps.makerspaces.models import Makerspace
    from tests.fixed_roles.helpers import assign_builtin_roles

    pipeline = setup_pipeline(space, member)
    other = Makerspace.objects.create(name="Shared sender", slug="shared-sender")
    assign_builtin_roles(member, other, "member")
    grant_consent(user=member, makerspace_id=other.pk, channel="sms", action="opted_in")
    NotificationPreference.objects.create(makerspace=other, feature="hardware_requests", channel="sms", enabled=True)
    loan = HardwareRequest.objects.create(makerspace=other, requester=member, requester_username=member.username)
    row, phone = prepare(pipeline)
    gate = close_gate(space, member)
    event = status_event(pipeline, row)
    event.refresh_from_db()
    assert event.state == "pending" and event.payload["protection_applied"] is True
    assert suppressed("sms", pipeline.sms.sender_key, phone)
    assert MessagingSuppression.objects.get().reason == "provider_opt_out"
    with patch("apps.integrations.messaging.dispatch.schedule_delivery"):
        shared = enqueue_addressed_messages(other, feature="hardware_requests", event="accepted", event_key="shared",
            payload=replace(pipeline.payload, data={"request_id": loan.pk}), channels=("sms",))
    assert next(item for item in shared if item.user_id == member.pk).status == "suppressed"
    row.refresh_from_db()
    assert row.status == "pending"  # Tenant status update was refused.
    assert not process_event(event.pk)
    assert MessagingSuppression.objects.count() == 1

    SourceMigrationGate.objects.filter(pk=gate.pk).update(state="open", owner_id=None)
    grant_consent(user=member, makerspace_id=space.pk, channel="sms", action="opted_in")
    assert not suppressed("sms", pipeline.sms.sender_key, phone)
    assert process_event(event.pk)
    assert not suppressed("sms", pipeline.sms.sender_key, phone)
    assert MessagingSuppression.objects.count() == 1
    assert pipeline.enqueue(key="after-reconsent").status == "pending"


def test_status_database_failure_cannot_roll_back_committed_optout(space, member):
    pipeline = setup_pipeline(space, member)
    row, phone = prepare(pipeline)
    with patch("apps.integrations.messaging.webhook_processing.save_outcome", side_effect=DatabaseError("status write failed")):
        with pytest.raises(DatabaseError):
            status_event(pipeline, row)
    event = MessagingWebhookEvent.objects.get()
    assert event.state == "pending" and event.payload["protection_applied"] is True
    assert suppressed("sms", pipeline.sms.sender_key, phone)
    assert process_event(event.pk)
    assert MessagingSuppression.objects.count() == 1


def test_early_21610_protects_before_delivery_correlation(space, member):
    from apps.integrations.messaging.webhook_payloads import twilio_payload
    pipeline = setup_pipeline(space, member)
    dedupe_id, payload = twilio_payload({"MessageSid": "SMearlyoptout", "MessageStatus": "failed",
        "ErrorCode": "21610", "To": member.phone_e164}, "status")
    assert member.phone_e164 not in str(payload)
    event = accept_event(provider="twilio", channel="sms", sender_key=pipeline.sms.sender_key,
        dedupe_id=dedupe_id, kind="status", payload=payload)
    event.refresh_from_db()
    assert event.state == "pending" and event.payload["protection_applied"] is True
    assert suppressed("sms", pipeline.sms.sender_key, recipient_hash("phone", member.phone_e164))
