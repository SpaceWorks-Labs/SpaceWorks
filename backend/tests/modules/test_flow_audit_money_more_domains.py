"""Flow audit (owner addendum A, decision 470): the rail-off money lifecycle for the remaining charging seams.

Loan late fee, donation gift, hackathon/collaborative-event programme charge and online shop order are each raised
with the payments module uninstalled (saved credentials left in place where the fixture has them). Every one is
recorded `pending` + `unclaimed`, is settled offline with exactly one ManualSettlement receipt (refused without one),
and can be partly then fully refunded offline; an over-refund is refused with `refund_exceeds_balance`.
Bookings, events, machines and membership are in test_flow_audit_money_lifecycle.py.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.makerspaces.module_install import uninstall_module
from apps.payments.exceptions_refunds import RefundNotAllowed
from apps.payments.models import ManualSettlement, Payment, Refund
from apps.payments.reconciliation import mark_offline
from apps.payments.services_refunds_offline import record_offline_refund
from tests.hardware_requests.test_loan_payments import close, loan_payment, loan_space, quiet_storage_and_stripe  # noqa: F401
from tests.l21b_local.test_money_and_switches import _project, enable, world  # noqa: F401
from tests.return_helpers import make_issued_request, make_product, settlement_details

pytestmark = pytest.mark.django_db(transaction=True)


def _receipt(reference):
    return {"method": "cash", "reference": reference, "refunded_at": timezone.now()}


def _assert_railless_lifecycle(manager, payment):
    assert (payment.status, payment.provider) == (Payment.Status.PENDING, Payment.Provider.UNCLAIMED)
    assert payment.online_rail is None
    with pytest.raises(Exception):  # no receipt, no settlement
        mark_offline(payment, manager, settlement=None)
    assert not ManualSettlement.objects.filter(payment=payment).exists()
    mark_offline(payment, manager, settlement=settlement_details(reference="slip"))
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_OFFLINE
    assert ManualSettlement.objects.filter(payment=payment).count() == 1
    paid = Decimal(payment.amount)
    part = (paid / 2).quantize(Decimal("0.01"))
    record_offline_refund(payment, amount=str(part), reason="part", actor=manager, receipt=_receipt("r1"))
    with pytest.raises(RefundNotAllowed) as over:
        record_offline_refund(payment, amount=str(paid), reason="too much", actor=manager, receipt=_receipt("r2"))
    assert over.value.detail["code"] == "refund_exceeds_balance"
    record_offline_refund(payment, amount=str(paid - part), reason="rest", actor=manager, receipt=_receipt("r3"))
    assert sum(r.amount for r in Refund.objects.filter(payment=payment)) == paid


def test_a_loan_late_fee_with_the_rail_uninstalled_runs_the_whole_offline_lifecycle(
        django_capture_on_commit_callbacks):
    space, staff = loan_space("fam2-late", loan_late_fee_per_day=Decimal("2.00"), loan_late_fee_cap=Decimal("15.00"),
                              loan_grace_days=1)
    uninstall_module(space, "payments")
    request = make_issued_request(space, staff, [(make_product(space), 1)])
    request.return_due_at = timezone.now() - timedelta(days=10)
    request.save(update_fields=["return_due_at"])
    close(staff, request, django_capture_on_commit_callbacks)
    fee = loan_payment(request, Payment.SubjectType.LOAN_LATE_FEE)
    assert fee.amount == Decimal("15.00")  # capped, as with the rail on
    _assert_railless_lifecycle(staff, fee)


def test_a_donation_gift_without_a_rail_runs_the_whole_offline_lifecycle():
    from apps.payments.donations.services import create_gift
    from tests.payments.test_audit_0120_seams_events_shop_membership_donations import _donor, _gift_space

    space = _gift_space("fam2-gift")
    donor = _donor(space, "fam2-giver")
    _gift, payment = create_gift(space, donor, amount=Decimal("50.00"))
    _assert_railless_lifecycle(donor.account, payment)


def test_a_programme_entry_fee_with_the_rail_uninstalled_runs_the_whole_offline_lifecycle(world):  # noqa: F811
    from apps.events.judging import options
    from apps.events.programme_charges import raise_charge
    from tests.events.pairwise_helpers import command

    enable(world, "events.hackathons", "events.entry_fees")
    uninstall_module(world.space, "payments")
    options.update(world.event.pk, actor=world.manager, data=command(0, entry_fee="500.00"))
    project = _project(world)
    payment = raise_charge(event=world.event, subject_type="submission_fee", subject_id=project.pk,
                           member=project.team.leader, amount="500.00", actor=project.team.leader,
                           audit_action="event.submission.fee_raised", target={})
    _assert_railless_lifecycle(world.manager, payment)


def test_an_online_shop_order_with_the_rail_uninstalled_runs_the_whole_offline_lifecycle():
    from apps.shop.checkout import Buyer, place_online_order
    from tests.shop.helpers import line, manager, member, payment_for, product, shop_space

    space = shop_space("fam2-shop", "shop.online", "shop.holds", "charges.enabled", "charges.shop")
    uninstall_module(space, "payments")
    sm = manager(space)
    _row, variant = product(space, sm, stock=2)
    buyer = member(space, "fam2-buyer")
    order, payment = place_online_order(space, Buyer(buyer, buyer.username, buyer.email, buyer),
                                        {"lines": [line(variant)]})
    assert payment.pk == payment_for(order).pk  # the ledger row the order owns
    _assert_railless_lifecycle(sm, payment)
