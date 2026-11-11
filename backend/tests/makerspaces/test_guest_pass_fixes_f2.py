"""Final audit 0.12.0, lane F2: M3 waiver gate, M4 replay, M6 priced = has a charge, M7 expiry voids debt."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.makerspaces import guest_pass_day, guest_pass_issue, guest_pass_lifecycle
from apps.makerspaces.guest_pass_policy import GuestPassError
from apps.makerspaces.guest_pass_queries import active_pass_for, payment_cleared, require_waiver
from apps.makerspaces.models import GuestPass, MakerspaceWaiver
from apps.payments.models import Payment
from apps.payments.reconciliation import mark_offline
from tests.makerspaces.l4_helpers import features_off
from tests.makerspaces.test_guest_passes import _product, _space, _sponsor
from tests.makerspaces.test_membership_j1 import manager, user
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db(transaction=True)


def test_waiver_gate_is_off_while_guest_passes_are_off():  # decision 226(a)
    makerspace = _space("f2-waiver")
    MakerspaceWaiver.objects.create(makerspace=makerspace, version="1", body="x", is_active=True, created_by=manager(makerspace))
    guest = user("f2-waiver-guest")
    from apps.presence.guard import WaiverAcceptanceRequired
    with pytest.raises(WaiverAcceptanceRequired):
        require_waiver(guest, makerspace, None)
    features_off(makerspace, "guest_passes")
    require_waiver(guest, makerspace, None)  # pre-0.12 behaviour: no gate


def test_day_pass_retry_returns_the_same_pass_and_charge_even_when_the_cap_is_now_full():
    makerspace = _space("f2-replay", charges=True)
    guest = user("f2-replay-guest")
    product = _product(makerspace, daily_cap=1)
    row, payment = guest_pass_day.sell_day_pass(guest, makerspace, guest, product, operation_id="op-1")
    again, payment_again = guest_pass_day.sell_day_pass(guest, makerspace, guest, product, operation_id="op-1")
    assert again.pk == row.pk and payment_again.pk == payment.pk
    assert Payment.objects.filter(subject_id=row.pk, subject_type=Payment.SubjectType.GUEST_PASS).count() == 1
    other = user("f2-replay-other")
    with pytest.raises(GuestPassError) as refused:
        guest_pass_day.sell_day_pass(other, makerspace, other, product, operation_id="op-1")
    assert refused.value.status_code == 409


def test_sponsored_retry_replays_before_the_sponsor_limits():
    makerspace = _space("f2-sponsor")
    sponsor, guest = _sponsor(makerspace), user("f2-sponsor-guest")
    first, created = guest_pass_issue.issue_sponsored_pass(sponsor, makerspace, guest, operation_id="s-1")
    assert created
    sponsor_row = GuestPass.objects.get(pk=first.pk)
    assert sponsor_row.sponsor_id == sponsor.pk
    again, created_again = guest_pass_issue.issue_sponsored_pass(sponsor, makerspace, guest, operation_id="s-1")
    assert again.pk == first.pk and not created_again


def test_repricing_a_product_never_changes_whether_a_sold_pass_is_cleared():
    makerspace = _space("f2-reprice", charges=True)
    staff, guest = manager(makerspace), user("f2-reprice-guest")
    product = _product(makerspace)
    row, payment = guest_pass_day.sell_day_pass(guest, makerspace, guest, product)
    product.amount = Decimal("0")
    product.save(update_fields=["amount"])
    row = GuestPass.objects.select_related("product").get(pk=row.pk)
    assert not payment_cleared(row) and active_pass_for(guest, makerspace) is None  # the debt stands
    mark_offline(payment, staff, settlement=settlement_details())
    assert payment_cleared(GuestPass.objects.select_related("product").get(pk=row.pk))
    free_guest = user("f2-reprice-free")
    free_row, free_payment = guest_pass_day.sell_day_pass(free_guest, makerspace, free_guest, product)
    product.amount = Decimal("9")
    product.save(update_fields=["amount"])
    assert free_payment is None and active_pass_for(free_guest, makerspace).pk == free_row.pk


def test_expired_unpaid_day_pass_voids_its_pending_charge_and_keeps_the_row():
    makerspace = _space("f2-expire", charges=True)
    guest = user("f2-expire-guest")
    row, payment = guest_pass_day.sell_day_pass(guest, makerspace, guest, _product(makerspace))
    guest_pass_lifecycle.expire_due_passes(makerspace, now=row.valid_until + timedelta(minutes=1))
    payment.refresh_from_db()
    assert payment.status == Payment.Status.CANCELED
    assert Payment.objects.filter(pk=payment.pk).exists() and GuestPass.objects.get(pk=row.pk).status == "expired"


def test_expired_paid_day_pass_keeps_its_settled_charge():
    makerspace = _space("f2-expire-paid", charges=True)
    staff, guest = manager(makerspace), user("f2-expire-paid-guest")
    row, payment = guest_pass_day.sell_day_pass(guest, makerspace, guest, _product(makerspace))
    mark_offline(payment, staff, settlement=settlement_details())
    guest_pass_lifecycle.expire_due_passes(makerspace, now=timezone.now() + timedelta(days=2))
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_OFFLINE
