import pytest

from apps.integrations.models_cutover import NotificationIngress, NotificationProviderReference
from apps.integrations.notification_privacy import scrub_account
from apps.integrations.notification_provider_references import remember
from apps.integrations.notification_ingress import accept_legacy
from apps.integrations.messaging.protections import recipient_hash, suppressed
from .reconciliation_helpers import account, delivery, space

pytestmark = pytest.mark.django_db


def test_scrub_uses_account_ids_when_member_and_staff_share_contact():
    tenant = space()
    member = account(phone_e164="+14155550123")
    # A valid staff principal (exactly one fixed-tenant membership) sharing contacts.
    from tests.fixed_roles.helpers import staff_account
    staff = staff_account(tenant, "staff", "space_manager", email=member.email,
        phone_e164=member.phone_e164)
    own, other = delivery(tenant, member), delivery(tenant, staff, number=2)
    for row in [own, other]:
        envelope = row.envelope
        envelope.message_body = '{"text":"private"}'
        envelope.save(update_fields=["message_body"])
    receipt = NotificationIngress(makerspace=tenant, makerspace_reference=tenant.pk, signed_user=member,
        channel="whatsapp", provider="meta", transport="canonical", sender_key="sender", dedupe_key="a" * 64)
    receipt.set_payload({"event": {"proof": {"code": "x" * 43}}, "proof_user_id": member.pk})
    receipt.save()
    scrub_account(member, tenant.pk)
    own.envelope.refresh_from_db()
    other.envelope.refresh_from_db()
    receipt.refresh_from_db()
    assert own.envelope.message_body == ""
    assert other.envelope.message_body == '{"text":"private"}'
    assert receipt.signed_user_id is None and receipt.get_payload()["event"]["proof"] is None


def test_provider_opt_out_survives_retirement_of_its_tenant_delivery():
    tenant = space()
    digest = recipient_hash("phone", "+14155550123")
    row = delivery(tenant, account(), state="sent", provider_id="SM-retired", sender_key="sender",
        recipient_phone_hash=digest)
    remember(row)
    row.delete()
    receipt = accept_legacy(provider="twilio", channel="sms", sender_key="sender", makerspace_id=tenant.pk,
        dedupe_id="SM-retired:failed", kind="status", payload={"message_id": "SM-retired", "status": "failed", "error_code": "21610"})
    receipt.refresh_from_db()
    assert receipt.state == "processed" and receipt.protection_applied
    assert suppressed("sms", "sender", digest)
    assert NotificationProviderReference.objects.get().phone_hash == digest
