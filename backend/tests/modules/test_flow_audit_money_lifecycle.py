"""Flow audit (owner addendum A): the money lifecycle of every charging area with the online rail OFF.

For bookings, events, machines and membership: a charge raised with no payment rail is recorded and stays
`pending` and `unclaimed`; a restricted member still sees it; switching the charging module off while it is
owed leaves it visible; staff settle it offline with exactly one ManualSettlement receipt (a settlement without a
receipt is refused and replay adds nothing); a partial refund is recorded, over-refund is refused and the audit
trail has one row per recorded action. Complements modules/test_switch_matrix_money_mail.py, which proves the
rail/mail switch states, and payments/test_offline_refunds.py, which owns the refund rules in isolation.
"""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.module_install import uninstall_module
from apps.payments.exceptions_refunds import RefundNotAllowed
from apps.payments.models import ManualSettlement, Payment, Refund
from apps.payments.reconciliation import mark_offline
from apps.payments.services_refunds_offline import record_offline_refund
from tests.modules.test_offstate_money import DOMAIN_MODULES, _configured_space, _invoke_charge_caller
from tests.return_helpers import make_member, settlement_details

pytestmark = pytest.mark.django_db

DOMAINS = tuple(DOMAIN_MODULES)


def _owed(slug, domain):
    space = _configured_space(slug, domain, payments_on=False)  # payments module uninstalled: no rail
    # The Stripe keys saved by `_configured_space` stay: module-off alone must still leave the debt unclaimed.
    member = make_member(f"{slug}-m", space, membership_role="custom", role=User.Role.REQUESTER)
    manager = make_member(f"{slug}-sm", space)
    _subject, charge = _invoke_charge_caller(domain, space, member)
    assert charge is not None
    return space, member, manager, Payment.objects.get(pk=charge.pk)


def _history(space, member):
    client = APIClient(raise_request_exception=False)
    client.force_authenticate(member)
    return client.get(reverse("member-payment-history", args=[space.pk]))


def _ids(response):
    body = response.data
    rows = body["results"] if isinstance(body, dict) and "results" in body else body
    return {row["id"] for row in rows}


@pytest.mark.parametrize("domain", DOMAINS)
def test_a_railless_charge_is_unclaimed_and_stays_visible_to_a_restricted_member_and_after_its_module_goes_off(domain):
    space, member, _manager, charge = _owed(f"fam-vis-{domain}", domain)
    assert (charge.status, charge.provider) == (Payment.Status.PENDING, "unclaimed")
    assert charge.id in _ids(_history(space, member))
    User.objects.filter(pk=member.pk).update(access_status=User.AccessStatus.RESTRICTED)
    member.refresh_from_db()
    restricted = _history(space, member)
    assert restricted.status_code == 200 and charge.id in _ids(restricted)
    for module in DOMAIN_MODULES[domain] - {"machine_service"}:
        uninstall_module(space, module)  # the charging module goes away while the money is owed
    after = _history(space, member)
    assert after.status_code == 200 and charge.id in _ids(after)
    assert Payment.objects.get(pk=charge.pk).status == Payment.Status.PENDING


@pytest.mark.parametrize("domain", DOMAINS)
def test_offline_settlement_needs_a_receipt_writes_exactly_one_and_replay_adds_nothing(domain):
    space, _member, manager, charge = _owed(f"fam-set-{domain}", domain)
    with pytest.raises(Exception):
        mark_offline(charge, manager, settlement=None)
    charge.refresh_from_db()
    assert charge.status == Payment.Status.PENDING and not ManualSettlement.objects.filter(payment=charge).exists()
    mark_offline(charge, manager, settlement=settlement_details(reference="slip-1"))
    charge.refresh_from_db()
    assert charge.status == Payment.Status.PAID_OFFLINE
    receipt = ManualSettlement.objects.get(payment=charge)
    assert (receipt.method, receipt.reference) == ("cash", "slip-1")
    try:  # a replay is refused or a no-op; either way no second receipt and the status holds
        mark_offline(charge, manager, settlement=settlement_details(reference="slip-2"))
    except Exception:
        pass
    assert ManualSettlement.objects.filter(payment=charge).count() == 1
    assert Payment.objects.get(pk=charge.pk).status == Payment.Status.PAID_OFFLINE


@pytest.mark.parametrize("domain", DOMAINS)
def test_partial_then_full_offline_refund_is_recorded_once_each_and_over_refund_is_refused(domain):
    space, member, manager, charge = _owed(f"fam-ref-{domain}", domain)
    with pytest.raises(Exception):  # nothing is settled yet, so nothing can be returned
        record_offline_refund(charge, amount="1.00", reason="early", actor=manager,
                              receipt={"method": "cash", "reference": "r0", "refunded_at": timezone.now()})
    assert not Refund.objects.filter(payment=charge).exists()
    mark_offline(charge, manager, settlement=settlement_details())
    charge.refresh_from_db()
    paid = Decimal(charge.amount)
    part = (paid / 2).quantize(Decimal("0.01"))
    record_offline_refund(charge, amount=str(part), reason="part", actor=manager,
                          receipt={"method": "cash", "reference": "r1", "refunded_at": timezone.now()})
    with pytest.raises(RefundNotAllowed) as over:
        record_offline_refund(charge, amount=str(paid), reason="too much", actor=manager,
                              receipt={"method": "cash", "reference": "r2", "refunded_at": timezone.now()})
    assert over.value.detail["code"] == "refund_exceeds_balance"
    assert Refund.objects.filter(payment=charge).count() == 1
    rest = paid - part
    record_offline_refund(charge, amount=str(rest), reason="rest", actor=manager,
                          receipt={"method": "upi", "reference": "r3", "refunded_at": timezone.now()})
    assert sum(r.amount for r in Refund.objects.filter(payment=charge)) == paid
    assert AuditLog.objects.filter(action="payment.refund_recorded", makerspace=space).count() == 2
