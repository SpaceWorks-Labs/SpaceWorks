"""Decision 242(a)(b)(c): the own-area Payments queue, owner claim/pay-link/reminder actions, cash refunds.

The queue grants nothing the subject owner did not already hold (217(a)); these tests pin that each manager sees
exactly their own subject types, donations never reach an area manager, and the actions refuse foreign charges.
"""
import pytest
from django.urls import reverse

from apps.payments.models import Payment, PaymentClaim
from tests.fixed_roles.helpers import staff_account
from tests.payments.recon_f_helpers import pending_charge
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def _charge(space, staff, member, subject_type, subject_id, **extra):
    # bulk_create skips `Payment.save()`'s full_clean: these rows point at placeholder subject ids on purpose.
    return Payment.objects.bulk_create([Payment(
        makerspace=space, member=member, created_by=staff, subject_type=subject_type, subject_id=subject_id,
        subject_label=subject_type, amount="5.00", currency="usd", provider="stripe", **extra)])[0]


def _world():
    space, staff, loan_charge = pending_charge("aq242")
    inventory = staff_account(space, "aq-inv", "inventory_manager")
    events = staff_account(space, "aq-events", "event_manager")
    booking = staff_account(space, "aq-booking", "booking_manager")
    handover_free = staff_account(space, "aq-member", "member")
    sub = Payment.SubjectType
    event_charge = _charge(space, staff, loan_charge.member, sub.EVENT_ORDER, 901)
    booking_charge = _charge(space, staff, loan_charge.member, sub.BOOKING, 902)
    gift = _charge(space, staff, loan_charge.member, sub.DONATION, 903)
    return space, loan_charge, event_charge, booking_charge, gift, inventory, events, booking, handover_free


def _ids(client, space, **params):
    response = client.get(reverse("payment-area-queue", args=[space.pk]), params)
    assert response.status_code == 200, response.content
    return {row["id"] for row in response.json()["results"]}


def test_each_manager_sees_only_their_own_subject_types():
    space, loan, event, booking, gift, inv, ev, bk, _ = _world()
    assert _ids(authenticated_client(inv), space) == {loan.pk}
    assert _ids(authenticated_client(ev), space) == {event.pk}
    assert _ids(authenticated_client(bk), space) == {booking.pk}
    for who in (inv, ev, bk):  # donations are record_payment money, never an area manager's
        assert gift.pk not in _ids(authenticated_client(who), space)


def test_space_manager_sees_every_area_and_the_summary_groups_by_area():
    space, loan, event, booking, gift, *_ = _world()
    sm = staff_account(space, "aq-sm", "space_manager")
    client = authenticated_client(sm)
    assert {loan.pk, event.pk, booking.pk, gift.pk} <= _ids(client, space)
    groups = {g["area"]: g for g in client.get(reverse("payment-area-queue-summary", args=[space.pk])).json()["groups"]}
    assert groups["lending"]["pending"] == 1 and groups["events"]["pending"] == 1 and groups["bookings"]["pending"] == 1
    assert _ids(client, space, area="events") == {event.pk}


def test_a_member_without_an_area_action_has_no_queue():
    space, *_, member = _world()
    assert authenticated_client(member).get(reverse("payment-area-queue", args=[space.pk])).status_code == 404


def test_actions_on_a_foreign_charge_are_not_found():
    space, loan, event, booking, gift, inv, ev, bk, _ = _world()
    client = authenticated_client(inv)  # the Inventory Manager does not own event money
    assert client.post(reverse("payment-area-reminder", args=[space.pk, event.pk])).status_code == 404
    assert client.post(reverse("payment-area-pay-link", args=[space.pk, event.pk]), {}, format="json").status_code == 404


def test_owner_confirms_a_claim_on_their_own_charge_only():
    space, loan, event, booking, gift, inv, ev, bk, _ = _world()
    space.enabled_features = sorted(set(space.enabled_features) | {"billing.offline_claims"})
    space.save(update_fields=["enabled_features"])
    own = PaymentClaim.objects.create(makerspace=space, payment=booking, claimant=booking.member, reference="UTR1",
                                      paid_on="2026-11-01", method="upi")
    url = reverse("payment-area-claim-confirm", args=[space.pk, own.pk])
    assert authenticated_client(inv).post(url).status_code == 404  # lending does not own bookings
    assert authenticated_client(bk).post(url).status_code == 200
    booking.refresh_from_db()
    assert booking.status == Payment.Status.PAID_OFFLINE


def test_cash_refund_extends_to_the_owning_area_manager_but_not_donations():
    from apps.payments.reconciliation_authority import CASH_RECORD_ACTIONS

    sub = Payment.SubjectType
    assert sub.BOOKING in CASH_RECORD_ACTIONS and sub.EVENT_ORDER in CASH_RECORD_ACTIONS
    assert sub.LOAN_DEPOSIT in CASH_RECORD_ACTIONS and sub.MACHINE_SESSION in CASH_RECORD_ACTIONS
    assert sub.DONATION not in CASH_RECORD_ACTIONS and sub.SPONSORSHIP not in CASH_RECORD_ACTIONS
