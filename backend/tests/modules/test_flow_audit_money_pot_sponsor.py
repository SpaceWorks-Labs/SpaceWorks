"""Flow audit (owner addendum A): sponsorship money and the shared-pot style event deposit with the rail OFF.

The refundable hackathon deposit (one per confirmed place, money held for the event) runs the whole offline
lifecycle. A sponsor payment is account-less and, like a gift, comes back only through a staff-approved refund
case: unclaimed, refused as a return before it is settled (`refund_not_settled`), one receipt on settlement, one
open case and a second refused (`refund_request_exists`).
"""
from decimal import Decimal

import pytest

from apps.makerspaces.module_install import uninstall_module
from apps.payments.exceptions_refunds import RefundNotAllowed
from apps.payments.models import ManualSettlement, Payment
from apps.payments.reconciliation import mark_offline
from tests.hackmoney_local.helpers import world  # noqa: F401
from tests.modules.test_flow_audit_money_more_domains import _assert_railless_lifecycle
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db(transaction=True)


def test_a_hackathon_refundable_deposit_pot_with_the_rail_uninstalled_runs_the_whole_offline_lifecycle(world):  # noqa: F811
    """The shared-pot style collaborative-event money: a confirmed place owes one refundable deposit."""
    from tests.hackmoney_local.test_deposits import deposit, deposits_on, place

    uninstall_module(world.space, "payments")
    deposits_on(world)  # noqa: F811
    row = place(world)  # noqa: F811
    _assert_railless_lifecycle(world.manager, deposit(row))


def test_a_sponsorship_charge_with_the_rail_uninstalled_is_settled_offline_and_returned_only_through_a_case():
    from apps.payments.donations.refunds import open_return_case
    from apps.payments.exceptions_refunds import RefundCaseConflict
    from apps.payments.models import RefundCase
    from tests.l18_local.helpers import client, setup
    from tests.l18_local.test_sponsors import _sponsor, url

    space, manager, _donor = setup("fam2-sponsor", "finance.sponsors")
    uninstall_module(space, "payments")
    sponsor = _sponsor(space, manager)
    made = client(manager).post(url(space, f"/{sponsor.pk}/charges"), {"amount": "25000", "description": "2026"},
                                format="json")
    assert made.status_code == 201, made.content
    payment = Payment.objects.get(subject_type="sponsorship", subject_id=made.json()["id"])
    assert (payment.status, payment.provider, payment.member_id) == (
        Payment.Status.PENDING, Payment.Provider.UNCLAIMED, None)  # recorded with no rail and no account
    with pytest.raises(RefundNotAllowed) as unsettled:
        open_return_case(payment, actor=manager, reason="too early")
    assert unsettled.value.detail["code"] == "refund_not_settled"
    with pytest.raises(Exception):
        mark_offline(payment, manager, settlement=None)  # no receipt, no settlement
    mark_offline(payment, manager, settlement=settlement_details(reference="cheque-9"))
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_OFFLINE
    assert ManualSettlement.objects.filter(payment=payment).count() == 1
    case = open_return_case(payment, actor=manager, reason="sponsor withdrew")
    assert (case.area, case.due_amount) == (RefundCase.Area.DONATIONS, Decimal("25000.00"))
    with pytest.raises(RefundCaseConflict) as twice:
        open_return_case(payment, actor=manager, reason="again")
    assert twice.value.detail["code"] == "refund_request_exists"
    assert RefundCase.objects.filter(payment=payment).count() == 1
