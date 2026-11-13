"""Payer projections render approved templates without exposing amounts to staff."""
import json
from datetime import datetime, UTC

import pytest
from django.utils import timezone

from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.models_endpoints import ChannelConfiguration, WhatsAppTemplate
from apps.integrations.notification_wa_meta_templates import template_content
from apps.integrations.notification_wa_twilio_templates import template_payload
from apps.payments.notifications import notify_payment
from apps.payments.reconciliation import mark_offline
from apps.payments.services_refunds_offline import record_offline_refund
from tests.payments.recon_f_helpers import pending_charge
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db
VARIABLES = ["subject.id", "subject.status", "subject.amount", "subject.currency", "subject.due_date"]
DUE = datetime(2026, 10, 18, 23, 0, tzinfo=UTC)


def assert_template_values(payment, event, amount):
    owner = NotificationEnvelope.objects.get(makerspace=payment.makerspace, recipient=payment.member,
        source_kind="payments.ledger", event=event)
    values = [str(payment.pk), payment.status, amount, payment.currency, "2026-10-19"]
    assert [str(owner.context[key]) for key in VARIABLES] == values
    config = ChannelConfiguration.objects.create(makerspace=payment.makerspace, channel="whatsapp", provider="twilio")
    binding = WhatsAppTemplate.objects.create(configuration=config, event=event, audience="member",
        locale="en", template_name="HX" + "a" * 32, approved=True, needs_review=False, variables=VARIABLES)
    twilio = template_payload(config, event, "member", "en", owner.context)
    assert twilio is not None
    assert list(json.loads(twilio["ContentVariables"]).values()) == values
    binding.template_name = "payment_update"
    meta = template_content(binding, owner.context)
    assert meta is not None
    assert [p["text"] for p in meta["template"]["components"][0]["parameters"]] == values
    for staff in NotificationEnvelope.objects.filter(makerspace=payment.makerspace, event=event, audience="staff"):
        assert not any(staff.context.get(key) is not None for key in VARIABLES[2:])


@pytest.mark.parametrize("event", ["charge_raised", "payment_due_soon", "payment_due_today",
                                  "payment_overdue", "payment_failed"])
def test_pending_payer_envelope_has_payment_template_values(event):
    space, _, payment = pending_charge("fr-payer-context", due_at=DUE)
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    notify_payment(payment, event)
    assert_template_values(payment, event, "10.00")


def test_refund_projection_uses_refund_amount_and_keeps_staff_context_sanitized():
    space, staff, payment = pending_charge("fr-refund-context", due_at=DUE)
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    mark_offline(payment, staff, settlement=settlement_details())
    payment.refresh_from_db()
    refund = record_offline_refund(payment, amount="3.00", reason="Return", actor=staff,
        receipt={"method": "cash", "reference": "desk", "refunded_at": timezone.now()})
    assert_template_values(payment, "refund_issued", "3.00")
    owner = NotificationEnvelope.objects.get(makerspace=space, event="refund_issued", recipient=payment.member)
    assert owner.context["refund_id"] == refund.pk
    assert NotificationEnvelope.objects.filter(makerspace=space, event="refund_issued", audience="staff").exists()
