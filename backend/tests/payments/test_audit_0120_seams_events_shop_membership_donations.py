"""Payments audit 0.12.0 (decision 256), sub-lane B: charge-raising seams for events, shop,
membership, day passes and donations.

Pins the fixes B-1 (a voided programme charge releases its hold), B-4 (a signed-in giver's double
submit is one gift and one debt, also under a race), B-5 (a gift in a zero-decimal currency must be
whole) and B-6 (a term start fully covered by volunteer credit is audited against its term), plus
the replay idempotency of a day-pass sale.
"""

import threading
from decimal import Decimal

import pytest
from django.db import connection

from apps.audit.models import AuditLog
from apps.payments.models import MakerspacePaymentSettings, Payment

pytestmark = pytest.mark.django_db(transaction=True)


# --- B-1: hackathon entry fee / team charge -------------------------------------------------

from tests.l21b_local.test_money_and_switches import _project, enable, world  # noqa: E402,F401


def test_a_cancelled_programme_charge_no_longer_holds_the_project(world):  # noqa: F811
    from apps.events.judging import options
    from apps.events.programme_charges import raise_charge, settled_or_free
    from apps.payments.reconciliation import cancel_pending
    from tests.events.pairwise_helpers import command

    enable(world, "events.hackathons", "events.entry_fees")
    options.update(world.event.pk, actor=world.manager, data=command(0, entry_fee="500.00"))
    project = _project(world)
    payment = raise_charge(event=world.event, subject_type="submission_fee", subject_id=project.pk,
                           member=project.team.leader, amount="500.00", actor=project.team.leader,
                           audit_action="event.submission.fee_raised", target={})
    assert settled_or_free(world.event, "submission_fee", project.pk) is False  # pending: held
    cancel_pending(makerspace=world.event.makerspace, subject_type="submission_fee", subject_id=project.pk,
                   actor=world.manager)
    assert Payment.objects.get(pk=payment.pk).status == Payment.Status.CANCELED
    assert settled_or_free(world.event, "submission_fee", project.pk) is True


def test_raise_charge_is_once_per_subject_and_never_repriced(world):  # noqa: F811
    from apps.events.programme_charges import raise_charge

    enable(world, "events.hackathons", "events.entry_fees")
    project = _project(world)
    kwargs = dict(event=world.event, subject_type="submission_fee", subject_id=project.pk,
                  member=project.team.leader, actor=project.team.leader,
                  audit_action="event.submission.fee_raised", target={})
    first = raise_charge(amount="500.00", **kwargs)
    again = raise_charge(amount="750.00", **kwargs)  # replay with a changed option
    assert again.pk == first.pk and again.amount == Decimal("500.00")
    assert Payment.objects.filter(subject_type="submission_fee", subject_id=project.pk).count() == 1


def test_programme_charge_is_inert_with_event_charges_off(world):  # noqa: F811
    from apps.events.programme_charges import raise_charge

    project = _project(world)
    world.space.enabled_features = [key for key in world.space.enabled_features if key != "charges.events"]
    world.space.save(update_fields=["enabled_features"])
    assert raise_charge(event=world.event, subject_type="submission_fee", subject_id=project.pk,
                        member=project.team.leader, amount="500.00", actor=project.team.leader,
                        audit_action="event.submission.fee_raised", target={}) is None
    assert not Payment.objects.filter(subject_type="submission_fee", subject_id=project.pk).exists()


# --- B-4 / B-5: donations ------------------------------------------------------------------

def _gift_space(slug, currency="usd"):
    from tests.money_modes.helpers import OFFLINE, set_mode
    from tests.return_helpers import make_space

    space = set_mode(make_space(slug), "donations", OFFLINE)
    space.enabled_features = sorted(set(space.enabled_features) | {"finance.donations"})
    space.save(update_fields=["enabled_features"])
    settings = MakerspacePaymentSettings.for_makerspace(space)
    settings.default_currency = currency
    settings.save()
    return space


def _donor(space, name):
    from apps.payments.donations.identity import Donor
    from tests.return_helpers import make_member

    account = make_member(name, space)
    return Donor(account=account, name=name, email=f"{name}@example.test", actor=account)


def test_a_signed_in_double_submit_is_one_gift_and_one_debt():
    from apps.payments.donations.services import create_gift

    space = _gift_space("b4-gift")
    donor = _donor(space, "b4-giver")
    first, first_payment = create_gift(space, donor, amount=Decimal("50.00"))
    second, second_payment = create_gift(space, donor, amount=Decimal("50.00"))
    assert (second.pk, second_payment.pk) == (first.pk, first_payment.pk)
    assert Payment.objects.filter(makerspace=space, subject_type="donation").count() == 1
    other, _ = create_gift(space, donor, amount=Decimal("75.00"))  # a different gift is a new gift
    assert other.pk != first.pk


def test_a_paid_or_desk_gift_is_never_reused_as_a_twin():
    from apps.payments.donations.services import create_gift

    space = _gift_space("b4-paid")
    donor = _donor(space, "b4-paid-giver")
    first, payment = create_gift(space, donor, amount=Decimal("50.00"))
    Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.PAID_OFFLINE)
    second, _ = create_gift(space, donor, amount=Decimal("50.00"))
    assert second.pk != first.pk


def test_parallel_double_submit_raises_one_debt():
    from apps.payments.donations.services import create_gift

    space = _gift_space("b4-race")
    donor = _donor(space, "b4-race-giver")
    barrier, results, errors = threading.Barrier(2), [], []

    def give():
        try:
            barrier.wait(timeout=10)
            results.append(create_gift(space, donor, amount=Decimal("20.00"))[0].pk)
        except Exception as exc:  # noqa: BLE001 - surfaced by the assertion below
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=give) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert errors == []
    assert len(set(results)) == 1
    assert Payment.objects.filter(makerspace=space, subject_type="donation").count() == 1


@pytest.mark.parametrize("currency, raw, ok", [
    ("jpy", "1000", True), ("jpy", "1000.50", False), ("usd", "10.25", True), ("kwd", "1.25", True),
])
def test_gift_amount_respects_the_currency_exponent(currency, raw, ok):
    from apps.payments.donations.gates import DonationRefused
    from apps.payments.donations.services import clean_amount

    space = _gift_space(f"b5-{currency}-{raw.replace('.', '-')}", currency)
    if ok:
        assert clean_amount(space, raw) == Decimal(raw)
    else:
        with pytest.raises(DonationRefused) as refused:
            clean_amount(space, raw)
        assert refused.value.detail["code"] == "amount_invalid"


# --- B-6: membership term start covered by volunteer credit --------------------------------

def test_a_fully_covered_term_start_is_audited_against_its_term():
    from apps.makerspaces import volunteer_hours
    from apps.makerspaces.membership_plan_services import create_term
    from apps.makerspaces.membership_term_charges import raise_term_start
    from tests.money_modes.test_volunteer_credit import _today, _world

    makerspace, actor, member, plan, membership = _world(per=60, amount=Decimal("50.00"))
    volunteer_hours.log_hours(actor, makerspace, member, minutes=60, worked_on=_today(), by_staff=True)
    term = create_term(actor, membership, plan)
    assert raise_term_start(actor, term) is None
    assert not Payment.objects.filter(makerspace=makerspace, subject_type="membership_term_start").exists()
    entry = AuditLog.objects.get(makerspace=makerspace, action="membership.term_charge_raised")
    assert entry.meta["term_id"] == term.pk and entry.meta["covered_by_credit"] is True
    assert entry.meta["payment_id"] is None


def test_term_start_charge_is_inert_with_membership_charges_off():
    from apps.makerspaces.membership_plan_services import create_term
    from apps.makerspaces.membership_term_charges import raise_term_start
    from tests.money_modes.helpers import FREE, set_mode
    from tests.money_modes.test_volunteer_credit import _world

    makerspace, actor, _member, plan, membership = _world()
    set_mode(makerspace, "membership", FREE)
    assert raise_term_start(actor, create_term(actor, membership, plan)) is None
    assert not Payment.objects.filter(makerspace=makerspace, subject_type="membership_term_start").exists()


# --- Day pass replay (223(b)) --------------------------------------------------------------

def test_day_pass_replay_returns_the_first_pass_and_its_one_charge():
    from apps.makerspaces import guest_pass_day
    from tests.makerspaces.test_guest_passes import _product, _space
    from tests.makerspaces.test_membership_j1 import user

    makerspace = _space("b-daypass-replay", charges=True)
    guest = user("b-daypass-buyer")
    product = _product(makerspace)
    row, payment = guest_pass_day.sell_day_pass(guest, makerspace, guest, product, operation_id="op-1")
    again, again_payment = guest_pass_day.sell_day_pass(guest, makerspace, guest, product, operation_id="op-1")
    assert (again.pk, again_payment.pk) == (row.pk, payment.pk)
    assert Payment.objects.filter(makerspace=makerspace, subject_type="guest_pass").count() == 1
    assert payment.amount == product.amount and payment.currency == "usd"
