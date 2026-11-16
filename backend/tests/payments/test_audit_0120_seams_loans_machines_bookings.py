"""Payments audit 0.12.0 (decision 256), sub-lane A: loan, machine and booking charge seams.

Covers the fixes of the audit: one charge per subject when a concurrent raise wins the
`payment_one_per_subject` race (machine jobs, services and sessions return the winner instead
of logging a lost debt), the optional rail scheduled after commit and only for a pending
debt, staff-set damage amounts refused when the currency cannot carry their decimals
(JPY 0, KWD capped at the ledger's 2), and seams that stay inert while `charges.*` is off.
"""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.payments.models import Payment
from apps.payments.money import to_minor_units
from apps.payments.pricing.components import component
from apps.payments.pricing.quotes import Quote, line, money
from tests.hardware_requests.test_loan_damage_lost import damaged_return, url
from tests.hardware_requests.test_loan_payments import quiet_storage_and_stripe  # noqa: F401
from tests.fixed_roles.helpers import staff_account
from tests.payments.pricing.helpers import D, client, member, pricing_space, rate, switch

pytestmark = pytest.mark.django_db


def _lost_race(*_args, **_kwargs):
    raise IntegrityError("duplicate key value violates unique constraint payment_one_per_subject")


# --- currency exponents -------------------------------------------------------------

@pytest.mark.parametrize("currency,entered,stored,minor", [
    ("jpy", "1500.4", D("1500"), 1500),
    ("jpy", "1500.5", D("1501"), 1501),
    ("usd", "12.345", D("12.35"), 1235),
    # The ledger column holds two places, so a dinar is quoted to the 10-fils step and
    # the provider is sent exactly that: quote = charge = provider amount.
    ("kwd", "1.234", D("1.23"), 1230),
])
def test_a_quote_line_is_rounded_to_what_the_ledger_and_provider_carry(currency, entered, stored, minor):
    item = line(component("loans", "damage"), currency=currency, quantity=1, unit_amount=D(entered),
                rate_source="staff")
    assert item.gross == stored == money(D(entered), currency)
    assert to_minor_units(item.gross, currency) == minor


def test_a_yen_damage_charge_refuses_sen_and_charges_whole_yen(django_capture_on_commit_callbacks):
    space, _ = pricing_space("audit-a-jpy", default_currency="jpy")
    staff = staff_account(space, "audit-a-jpy-staff", "space_manager")
    rate(space, "loans", damage="1200")
    from tests.return_helpers import make_product
    request = damaged_return(space, staff, make_product(space), callbacks=django_capture_on_commit_callbacks)
    from apps.hardware_requests.models import RequesterAccountability
    row = RequesterAccountability.objects.get(request=request)

    refused = client(staff).post(url(space, request, row), {"amount": "12.50"}, format="json")
    assert refused.status_code == 400, refused.data
    assert not Payment.objects.filter(subject_type="loan_damage", subject_id=row.pk).exists()

    charged = client(staff).post(url(space, request, row), {"amount": "1250"}, format="json")
    assert charged.status_code == 200, charged.data
    payment = Payment.objects.get(subject_type="loan_damage", subject_id=row.pk)
    assert (payment.amount, payment.currency) == (D("1250"), "jpy")
    assert to_minor_units(payment.amount, payment.currency) == 1250
    assert D(payment.pricing_snapshot["total"]) == payment.amount


def test_a_damage_charge_is_inert_while_loan_charges_are_off(django_capture_on_commit_callbacks):
    space, _ = pricing_space("audit-a-dmg-off")
    staff = staff_account(space, "audit-a-dmg-off-staff", "space_manager")
    rate(space, "loans", damage="10.00")
    from tests.return_helpers import make_product
    request = damaged_return(space, staff, make_product(space), callbacks=django_capture_on_commit_callbacks)
    from apps.hardware_requests.models import RequesterAccountability
    row = RequesterAccountability.objects.get(request=request)
    switch(space, "charges.loans", on=False)
    refused = client(staff).post(url(space, request, row), {"amount": "10.00"}, format="json")
    assert refused.status_code >= 400
    assert not Payment.objects.filter(makerspace=space).exists()


# --- one charge per subject under concurrency ---------------------------------------

def test_a_machine_job_that_loses_the_race_returns_the_winning_charge(monkeypatch):
    from apps.machines import job_charges

    winner = SimpleNamespace(pk=7, status=Payment.Status.PAID_OFFLINE, makerspace=None)
    lookups = iter([None, winner])  # the pre-check misses; the re-read after the race finds it
    monkeypatch.setattr(job_charges, "payment_for", lambda job: next(lookups))
    monkeypatch.setattr("apps.payments.availability.charge_tracking_enabled", lambda *_: True)
    monkeypatch.setattr("apps.payments.pricing.charging.raise_priced", _lost_race)
    offered = []
    monkeypatch.setattr("apps.machines.service_payments.offer_checkout",
                        lambda payment, job_id: offered.append(payment))
    job = SimpleNamespace(pk=11, makerspace=None, member=None, requester=None, accepted_by=None, handled_by=None)
    quote = Quote(domain="machines", currency="usd")
    assert job_charges._raise_frozen(job, None, quote) is winner
    assert offered == [winner]


def test_a_machine_service_charge_that_loses_the_race_returns_the_winner(monkeypatch):
    from apps.machines import service_payments

    winner = SimpleNamespace(pk=8, status=Payment.Status.PENDING, makerspace=None)
    lookups = iter([None, winner])

    class Rows:
        def filter(self, **_lookup):
            return self

        def first(self):
            return next(lookups)

    fake_payment = SimpleNamespace(objects=Rows(), SubjectType=Payment.SubjectType, Status=Payment.Status)
    monkeypatch.setattr(service_payments, "Payment", fake_payment)
    monkeypatch.setattr(service_payments, "charge_tracking_enabled", lambda *_: True)
    monkeypatch.setattr(service_payments, "service_quote",
                        lambda *_a, **_k: Quote(domain="machines", currency="usd"))
    monkeypatch.setattr("apps.payments.pricing.charging.raise_priced", _lost_race)
    monkeypatch.setattr(service_payments, "offer_checkout", lambda *_: None)
    job = SimpleNamespace(pk=12, makerspace=None, assigned_machine_id=3, member=None, requester=None,
                          accepted_by=None, handled_by=None)
    assert service_payments.create_for_completed_request(job, None) is winner


def test_a_machine_session_stop_that_loses_the_race_returns_the_winner(monkeypatch):
    from apps.machines import sessions_billing as billing

    winner = SimpleNamespace(pk=9)
    lookups = iter([None, winner])
    monkeypatch.setattr(billing, "payment_for", lambda session: next(lookups))
    monkeypatch.setattr(billing, "billing_active", lambda _space: True)
    monkeypatch.setattr(billing, "final_quote", lambda *_: Quote(domain="machines", currency="usd"))
    monkeypatch.setattr("apps.payments.pricing.charging.raise_priced", _lost_race)
    session = SimpleNamespace(billable=True, service_request_id=None, pk=5, makerspace=None, makerspace_id=1,
                              machine_id=2, quote_snapshot={}, quote_digest="", machine=SimpleNamespace(name="Laser"))
    assert billing.raise_charge(session, minutes=30, member=SimpleNamespace(pk=1), actor=None) is winner


# --- the rail is optional, post-commit and pending-only -------------------------------

def test_the_machine_rail_waits_for_commit_and_skips_settled_charges(monkeypatch, django_capture_on_commit_callbacks):
    from apps.machines import service_payments

    created = []
    monkeypatch.setattr(service_payments, "online_payments_enabled", lambda *_: True)
    monkeypatch.setattr(service_payments, "create_checkout", created.append)
    pending = SimpleNamespace(pk=1, status=Payment.Status.PENDING, makerspace=None)
    settled = SimpleNamespace(pk=2, status=Payment.Status.PAID_OFFLINE, makerspace=None)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        service_payments.offer_checkout(pending, 1)
        service_payments.offer_checkout(settled, 2)
        service_payments.offer_checkout(None, 3)
        assert created == []  # nothing reaches a provider inside the job's transaction
    assert len(callbacks) == 1
    callbacks[0]()
    assert created == [pending]


def test_a_failing_machine_rail_never_raises_into_fulfilment(monkeypatch, django_capture_on_commit_callbacks):
    from apps.machines import service_payments

    def boom(_payment):
        raise RuntimeError("provider down")

    monkeypatch.setattr(service_payments, "online_payments_enabled", lambda *_: True)
    monkeypatch.setattr(service_payments, "create_checkout", boom)
    with django_capture_on_commit_callbacks(execute=True):
        service_payments.offer_checkout(SimpleNamespace(pk=1, status=Payment.Status.PENDING, makerspace=None), 1)


# --- bookings: recorded independently of the rail, inert when off -------------------

def _booking_space(slug, *, charges_on=True):
    from tests.payments.pricing.test_domain_seams import install
    from tests.payments.test_track3_booking_event_charging import bookable

    space, _ = pricing_space(slug)
    install(space, "bookings")
    if not charges_on:
        switch(space, "charges.bookings", on=False)
    room = bookable(space, amount="5.00")
    return space, room


def test_a_booking_charge_is_recorded_without_any_rail_and_is_frozen():
    from apps.bookings import services_bookings

    space, room = _booking_space("audit-a-book")
    starts = timezone.now() + timedelta(hours=3)
    booking = services_bookings.create_booking(room, starts_at=starts, ends_at=starts + timedelta(hours=1),
                                               member=member(space), actor=None)
    payment = Payment.objects.get(makerspace=space, subject_type="booking", subject_id=booking.pk)
    assert payment.status == Payment.Status.PENDING
    assert payment.provider == Payment.Provider.UNCLAIMED  # no gateway: the debt still exists
    assert D(payment.pricing_snapshot["total"]) == payment.amount == D("5.00")
    from apps.bookings.service_payments import create_for_confirmed_booking
    assert create_for_confirmed_booking(booking, None).pk == payment.pk  # replay: the same one charge
    assert Payment.objects.filter(subject_type="booking", subject_id=booking.pk).count() == 1


def test_a_booking_raises_nothing_while_booking_charges_are_off():
    from apps.bookings import services_bookings

    space, room = _booking_space("audit-a-book-off", charges_on=False)
    starts = timezone.now() + timedelta(hours=3)
    booking = services_bookings.create_booking(room, starts_at=starts, ends_at=starts + timedelta(hours=1),
                                               member=member(space), actor=None)
    assert not Payment.objects.filter(subject_type="booking", subject_id=booking.pk).exists()


def test_a_machine_job_raises_nothing_while_machine_charges_are_off(monkeypatch):
    from apps.machines import service_payments

    monkeypatch.setattr(service_payments, "charge_tracking_enabled", lambda *_: False)
    called = []
    monkeypatch.setattr("apps.payments.pricing.charging.raise_priced", lambda *a, **k: called.append(a))
    job = SimpleNamespace(pk=13, makerspace=None, assigned_machine_id=3)
    assert service_payments.create_for_completed_request(job, None) is None
    assert called == []

