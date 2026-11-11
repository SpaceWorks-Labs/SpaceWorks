"""Journey matrix (0.12.0): FREE vs PAID price x every money mode, for events, bookings and membership.

The sibling mode tests cover a PAID subject in FREE/OFFLINE/ONLINE. This file adds the other
half of the owner's matrix: a zero price in every mode (nothing is ever owed), the
`charges.enabled` master switch as its own road to free, the approval booking's frozen quote,
scheduled renewals, and the "debts are never lost" rule for the two membership seams that used
to swallow a ledger failure.

Expected outcome per cell: a charge row exists only for a PAID subject in OFFLINE or ONLINE;
OFFLINE rows are `unclaimed` with no checkout; ONLINE rows get a checkout (or, for renewals, an
online rail the scheduler may use).
"""

from decimal import Decimal

import pytest
from django.db import transaction
from django.utils import timezone

from apps.bookings import services_bookings
from apps.bookings.models import Booking
from apps.events import services as event_services
from apps.events.models import EventRegistration
from apps.makerspaces.membership_plan_services import create_term
from apps.makerspaces.membership_renewal_charges import raise_renewal
from apps.makerspaces.membership_term_charges import raise_term_start
from apps.makerspaces.models import MakerspaceMembership, MembershipPlan, MembershipTerm
from apps.payments.availability import online_payments_enabled_for
from apps.payments.models import Payment
from tests.makerspaces.test_membership_admission_matrix import _setup
from tests.makerspaces.test_membership_j1 import member_role
from tests.money_modes.helpers import (
    FREE, OFFLINE, ONLINE, assert_mode_outcome, charges, fake_provider, master_off, set_mode,
)
from tests.payments.test_track3_booking_event_charging import (
    bookable, create_booking, member_with_phone, published_event,
)
from tests.return_helpers import make_member, make_space

MASTER_OFF = "master_off"
ALL_MODES = (FREE, OFFLINE, ONLINE, MASTER_OFF)
PRICES = ("free", "paid")


def _mode(space, domain, mode, **kwargs):
    if mode == MASTER_OFF:
        return master_off(set_mode(space, domain, OFFLINE, **kwargs))
    return set_mode(space, domain, mode, **kwargs)


def _expect(price, mode, rows, checkout):
    """A paid subject in a tracked mode owes exactly one charge; everything else owes nothing."""
    if price == "free" or mode in (FREE, MASTER_OFF):
        assert rows == []
        assert checkout is None or not checkout.called
        return None
    return assert_mode_outcome(mode, rows, checkout)


@pytest.mark.django_db
@pytest.mark.parametrize("price", PRICES)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_instant_booking(price, mode, monkeypatch, django_capture_on_commit_callbacks):
    space = _mode(make_space(f"fp-book-{price}-{mode}"[:40]), "bookings", mode, extra_modules=("bookings",))
    checkout = fake_provider(monkeypatch) if mode == ONLINE else None
    member = member_with_phone(f"fp-book-{price}-{mode}-m", space)
    amount = "0.00" if price == "free" else "12.50"
    with django_capture_on_commit_callbacks(execute=True):
        booking = create_booking(bookable(space, amount=amount), member)
    assert booking.status == Booking.Status.CONFIRMED  # money never blocks a free or offline booking
    payment = _expect(price, mode, charges(space, "booking"), checkout)
    assert payment is None or payment.amount == Decimal("12.50")


@pytest.mark.django_db
@pytest.mark.parametrize("price", PRICES)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_approval_booking_charges_its_frozen_quote_only_on_approval(
    price, mode, monkeypatch, django_capture_on_commit_callbacks,
):
    space = _mode(make_space(f"fp-appr-{price}-{mode}"[:40]), "bookings", mode, extra_modules=("bookings",))
    checkout = fake_provider(monkeypatch) if mode == ONLINE else None
    member = member_with_phone(f"fp-appr-{price}-{mode}-m", space)
    room = bookable(space, approval_mode="approve", amount="0.00" if price == "free" else "30.00")
    pending = create_booking(room, member)
    assert pending.status == Booking.Status.PENDING
    assert charges(space, "booking") == []  # nothing is owed while staff decide
    if mode in (FREE, MASTER_OFF):
        assert pending.pricing_snapshot == {}  # an untracked domain freezes no price
    with django_capture_on_commit_callbacks(execute=True):
        approved = services_bookings.approve_booking(pending, actor=make_member(f"fp-appr-{price}-{mode}-sm", space))
    assert approved.status == Booking.Status.CONFIRMED
    payment = _expect(price, mode, charges(space, "booking"), checkout)
    assert payment is None or payment.amount == Decimal("30.00")


@pytest.mark.django_db
@pytest.mark.parametrize("price", PRICES)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_event_registration(price, mode, monkeypatch, django_capture_on_commit_callbacks):
    space = _mode(make_space(f"fp-reg-{price}-{mode}"[:40]), "events", mode, extra_modules=("events",))
    checkout = fake_provider(monkeypatch) if mode == ONLINE else None
    event = published_event(space, make_member(f"fp-reg-{price}-{mode}-sm", space),
                            amount="0.00" if price == "free" else "8.00")
    with django_capture_on_commit_callbacks(execute=True):
        registration = event_services.register(event, member=member_with_phone(f"fp-reg-{price}-{mode}-m", space))
    assert registration.status == EventRegistration.Status.REGISTERED
    payment = _expect(price, mode, charges(space, "event_registration"), checkout)
    assert payment is None or payment.amount == Decimal("8.00")


def _membership(makerspace, applicant):
    return MakerspaceMembership.objects.create(
        makerspace=makerspace, user=applicant, assigned_role=member_role(makerspace),
        role="custom", status="active", activated_at=timezone.now(),
    )


def _plan(makerspace, price):
    return MembershipPlan.objects.create(
        makerspace=makerspace, name=f"Plan {price}", interval="monthly",
        amount=Decimal("0") if price == "free" else Decimal("20.00"), currency="usd",
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("price", PRICES)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_staff_opened_membership_term(price, mode, monkeypatch, django_capture_on_commit_callbacks):
    makerspace, actor, applicant, _default, _ = _setup(paid=price == "paid")
    _mode(makerspace, "membership", mode)
    checkout = fake_provider(monkeypatch) if mode == ONLINE else None
    plan = _plan(makerspace, price)
    with django_capture_on_commit_callbacks(execute=True):
        raise_term_start(actor, create_term(actor, _membership(makerspace, applicant), plan))
    payment = _expect(price, mode, charges(makerspace, "membership_term_start"), checkout)
    assert payment is None or (payment.amount, payment.member_id) == (Decimal("20.00"), applicant.pk)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("price", PRICES)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_scheduled_renewal_records_once_and_rails_only_online(price, mode, monkeypatch):
    makerspace, actor, applicant, _default, _ = _setup(paid=price == "paid")
    _mode(makerspace, "membership", mode)
    if mode == ONLINE:
        fake_provider(monkeypatch)
    term = create_term(actor, _membership(makerspace, applicant), _plan(makerspace, price))
    load = lambda: MembershipTerm.objects.select_related(  # noqa: E731
        "membership__makerspace", "membership__user", "plan").get(pk=term.pk)
    tracked = price == "paid" and mode in (OFFLINE, ONLINE)
    assert raise_renewal(load()) == ("charged" if tracked else "skipped")
    rows = charges(makerspace, "membership_term")
    if not tracked:
        assert rows == []
        return
    # One charge per owner: a second sweep finds the stamped payment and raises nothing.
    assert raise_renewal(load()) == "skipped"
    [payment] = charges(makerspace, "membership_term")
    assert payment.status == Payment.Status.PENDING and payment.amount == Decimal("20.00")
    assert online_payments_enabled_for(payment) is (mode == ONLINE)
    if mode == OFFLINE:
        assert payment.provider == Payment.Provider.UNCLAIMED  # the first online checkout claims it


@pytest.mark.django_db(transaction=True)
def test_a_term_whose_debt_cannot_be_recorded_is_not_opened(monkeypatch):
    """Debts are never lost: a ledger failure rolls the staff-opened term back with it."""
    makerspace, actor, applicant, _default, _ = _setup(paid=True)
    set_mode(makerspace, "membership", OFFLINE)
    membership = _membership(makerspace, applicant)
    plan = _plan(makerspace, "paid")

    def broken(**_kwargs):
        raise RuntimeError("ledger down")

    monkeypatch.setattr("apps.payments.services.create_payment", broken)
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            raise_term_start(actor, create_term(actor, membership, plan))
    assert not MembershipTerm.objects.filter(membership=membership).exists()
    assert charges(makerspace, "membership_term_start") == []


@pytest.mark.django_db
def test_legacy_dues_ledger_failure_refuses_the_activation(monkeypatch):
    """The legacy dues seam used to swallow every error and activate a member debt-free."""
    from apps.accounts.models import User
    from apps.makerspaces.membership_activation import _activate_membership
    from apps.makerspaces.models import MakerspaceRole
    from tests.return_helpers import make_user

    makerspace = set_mode(make_space("fp-dues-broken"), "membership", OFFLINE, extra_modules=("membership",))
    makerspace.membership_dues_amount = Decimal("15.00")
    makerspace.save(update_fields=["membership_dues_amount", "updated_at"])
    manager = make_member("fp-dues-broken-sm", makerspace)
    joiner = make_user("fp-dues-broken-joiner", access_status=User.AccessStatus.ACTIVE)
    role = MakerspaceRole.objects.filter(makerspace=makerspace, slug="member").order_by("id").first()

    def broken(**_kwargs):
        raise RuntimeError("ledger down")

    monkeypatch.setattr("apps.makerspaces.membership_payments.create_payment", broken)
    with pytest.raises(RuntimeError):
        _activate_membership(manager, makerspace, joiner, role, source="join")
    assert not MakerspaceMembership.objects.filter(makerspace=makerspace, user=joiner, status="active").exists()


@pytest.mark.django_db
def test_legacy_dues_rail_failure_keeps_the_recorded_debt(monkeypatch, django_capture_on_commit_callbacks):
    """The other half of the contract: a provider failure after the debt is recorded only logs."""
    from apps.accounts.models import User
    from apps.makerspaces.membership_activation import _activate_membership
    from apps.makerspaces.models import MakerspaceRole
    from tests.return_helpers import make_user

    makerspace = set_mode(make_space("fp-dues-rail"), "membership", ONLINE, extra_modules=("membership",))
    fake_provider(monkeypatch)
    makerspace.membership_dues_amount = Decimal("15.00")
    makerspace.save(update_fields=["membership_dues_amount", "updated_at"])
    manager = make_member("fp-dues-rail-sm", makerspace)
    joiner = make_user("fp-dues-rail-joiner", access_status=User.AccessStatus.ACTIVE)
    role = MakerspaceRole.objects.filter(makerspace=makerspace, slug="member").order_by("id").first()

    def down(_payment):
        raise RuntimeError("provider down")

    monkeypatch.setattr("apps.makerspaces.membership_payments.create_checkout", down)
    with django_capture_on_commit_callbacks(execute=True):
        membership = _activate_membership(manager, makerspace, joiner, role, source="join")
    assert membership.status == "active"
    [payment] = charges(makerspace, "makerspace_membership")
    assert payment.status == Payment.Status.PENDING and payment.amount == Decimal("15.00")
