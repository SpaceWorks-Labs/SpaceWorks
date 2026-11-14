"""Ledger fixtures retain real subjects, receipts, person accounts and both transports."""
from types import SimpleNamespace

from django.utils import timezone

from apps.payments.models import MakerspaceBillingSettings, MakerspacePaymentSettings, Payment
from tests.accounts.account_factories import grant_staff_role, make_staff
from tests.modules.switch_matrix_helpers import live_space
from tests.modules.switch_matrix_object_helpers import client_for
from tests.payments.money_subject_cx11b_p2 import subject
from tests.payments.route_support_cx11b_g5 import foreign_client, personal_client


def seed(native, domain="membership"):
    space = live_space("g5-ledger", {"payments", "events", "bookings", "machines", "membership", "member_accounts", "request_workflow"})
    space.enabled_features = ["charges.enabled", "charges.membership", "charges.loans", "charges.pricing",
        "payments.enabled", "payments.membership", "payments.loans", "billing.offline_claims", "billing.pay_links",
        "finance.donations", "finance.recurring_donations", "finance.tax_exempt_receipts", "charges.donations"]
    space.save(update_fields=["enabled_features"])
    actor = make_staff(space, username="g5-ledger-manager")
    kind, row, payer = subject(space, domain)
    grant_staff_role(payer, space)
    payment = Payment.objects.create(makerspace=space, subject_type=kind, subject_id=row.pk, member=payer,
        amount="100.00", currency="inr", provider="unclaimed", created_by=actor, subject_label="G5 retained charge")
    policy = MakerspaceBillingSettings.objects.create(makerspace=space, payment_instructions="G5 pay at desk")
    rail = MakerspacePaymentSettings.for_makerspace(space)
    rail.default_currency = "inr"
    rail.save()
    return SimpleNamespace(space=space, actor=actor, payer=payer, subject=row, payment=payment, policy=policy, rail=rail,
        client=client_for(actor, space, native), payer_client=personal_client(payer, space, native), foreign=foreign_client(native))


def receipt(reference="G5-RECEIPT"):
    return {"method": "cash", "reference": reference, "received_at": timezone.now()}


def refund_receipt(reference="G5-REFUND"):
    return {"method": "cash", "reference": reference, "refunded_at": timezone.now().isoformat()}


def settled(s):
    from apps.payments.reconciliation import mark_offline
    mark_offline(s.payment, s.actor, settlement=receipt("G5-SEED"))
    s.payment.refresh_from_db()
    return s.payment
