"""Hack-money G14 (a separate crew pool) and G12 (travel the organiser booked directly).

Real services and a real database: finance commands run with a reauthenticated session; the pool,
the reservation and the ledger are read back. Nothing here sends money.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.event_reimbursements import award_workflow, direct_booking, pools
from apps.event_reimbursements.budget_models import BudgetReservation, ReimbursementBudgetPool
from apps.event_reimbursements.models import GrantAward, GrantRequest
from apps.payments.event_payouts.errors import PayoutError
from apps.payments.event_payouts.validation import PayoutValidationError
from apps.payments.models_ledger_entries import LedgerEntry
from .conftest import cmd
from .helpers import requested

pytestmark = pytest.mark.django_db(transaction=True)


def crew_on(world):
    world.space.enabled_features = sorted(set(world.space.enabled_features) | {"events.crew", "events.crew_claims"})
    world.space.save(update_fields=["enabled_features"])


def crew_pool(world, total=50000):
    crew_on(world)
    made = pools.create_crew_pool(request=world.finance, event_id=world.event.pk,
                                  data=cmd(0, initial_total_minor=total))
    return ReimbursementBudgetPool.objects.get(pk=made["pool_id"])


def decide(world, grant, pool, amount=10000):
    return award_workflow.decide(request=world.finance, event_id=world.event.pk, request_id=grant.pk,
        data=cmd(grant.version, expected_award_version=None, expected_pool_version=pool.version,
                 outcome="award", amount_minor=amount, currency="INR", reason_code="need_based"))


# G14 ------------------------------------------------------------------------------------------

def test_finance_adds_one_funded_crew_pool(world):
    pool = crew_pool(world)
    assert (pool.audience, pool.total_minor, pool.currency) == ("crew", 50000, "INR")
    assert world.pool.audience == "participants"
    with pytest.raises(PayoutError) as twice:
        pools.create_crew_pool(request=world.finance, event_id=world.event.pk, data=cmd(0, initial_total_minor=1))
    assert twice.value.detail["code"] == "crew_pool_exists"


def test_the_crew_pool_needs_crew_claims(world):
    # #183B: a switch-off route answers 404 feature_disabled (was 403 crew_claims_disabled).
    from apps.makerspaces.guards import SurfaceOff
    with pytest.raises(SurfaceOff) as off:
        pools.create_crew_pool(request=world.finance, event_id=world.event.pk, data=cmd(0, initial_total_minor=1))
    assert off.value.key == "events.crew_claims"


def test_crew_awards_reserve_from_the_crew_pool_and_participants_do_not(world):
    crew = crew_pool(world)
    grant = requested(world)
    GrantRequest.objects.filter(pk=grant.pk).update(kind="crew")
    grant.refresh_from_db()
    decide(world, grant, crew)
    award = GrantAward.objects.get(request=grant)
    crew.refresh_from_db(); world.pool.refresh_from_db()
    assert award.pool_id == crew.pk and crew.reserved_minor == 10000
    assert world.pool.reserved_minor == 0  # the participant travel budget is untouched


def test_without_a_crew_pool_crew_awards_use_the_participant_pool(world):
    assert pools.read_pool(world.programme, "crew").pk == world.pool.pk
    assert pools.pool_for({world.pool.pk: world.pool}, world.programme, "crew").pk == world.pool.pk


def test_an_existing_award_keeps_its_pool_after_a_crew_pool_is_added(world):
    grant = requested(world)
    GrantRequest.objects.filter(pk=grant.pk).update(kind="crew")
    grant.refresh_from_db()
    decide(world, grant, world.pool)
    crew = crew_pool(world)
    award = GrantAward.objects.get(request=grant)
    assert pools.pool_for({world.pool.pk: world.pool, crew.pk: crew}, world.programme, "crew", award).pk == world.pool.pk


# G12 ------------------------------------------------------------------------------------------

def book(world, grant, pool, amount=8000, **extra):
    return direct_booking.record(request=world.finance, event_id=world.event.pk, request_id=grant.pk, data=cmd(
        grant.version, expected_pool_version=pool.version, amount_minor=amount, currency="INR", vendor="Kerala RTC",
        booked_on=date(2026, 11, 1), method="bank_transfer", reference="PNR-42", **extra))


def test_a_direct_booking_commits_the_pool_and_records_a_travel_expense(world):
    grant = requested(world)
    world.pool.refresh_from_db()
    result = book(world, grant, world.pool)
    award = GrantAward.objects.get(request=grant)
    assert (award.state, award.reason_code, award.amount_minor) == ("closed", "direct_booking", 8000)
    reservation = BudgetReservation.objects.get(award=award)
    assert (reservation.state, reservation.committed_minor, reservation.held_minor) == ("committed", 8000, 0)
    world.pool.refresh_from_db()
    assert (world.pool.committed_minor, world.pool.reserved_minor) == (8000, 0)
    entry = LedgerEntry.objects.get(pk=result["ledger_entry_id"])
    assert (entry.kind, entry.domain, entry.category, entry.amount) == ("expense", "events", "travel", Decimal("80.00"))
    assert (entry.source_kind, entry.source_id, entry.counterparty) == (direct_booking.SOURCE_KIND, str(award.uuid), "Kerala RTC")
    grant.refresh_from_db()
    assert grant.state == "awarded"


def test_event_cancellation_never_releases_a_booked_ticket(world):
    from apps.event_reimbursements.deadlines import close_award_locked
    grant = requested(world)
    world.pool.refresh_from_db()
    book(world, grant, world.pool)
    award = GrantAward.objects.get(request=grant)
    assert close_award_locked(None, pool=world.pool, award=award, claim=None, reason="event_cancelled") is False


def test_finance_cancels_a_booking_voids_the_expense_and_releases_the_budget(world):
    grant = requested(world)
    world.pool.refresh_from_db()
    result = book(world, grant, world.pool)
    grant.refresh_from_db(); world.pool.refresh_from_db()
    direct_booking.cancel(request=world.finance, event_id=world.event.pk, request_id=grant.pk, data=cmd(
        grant.version, expected_pool_version=world.pool.version, reason="Booked the wrong date"))
    entry = LedgerEntry.objects.get(pk=result["ledger_entry_id"])
    world.pool.refresh_from_db()
    award = GrantAward.objects.get(request=grant)
    assert entry.voided_at is not None and world.pool.committed_minor == 0
    assert (award.state, award.reason_code) == ("forfeited", "direct_booking_cancelled")


def test_a_booking_cannot_replace_an_accepted_award(world):
    from .helpers import accepted
    award = accepted(world)
    grant = award.request
    grant.refresh_from_db(); world.pool.refresh_from_db()
    with pytest.raises(PayoutError) as refused:
        book(world, grant, world.pool)
    assert refused.value.detail["code"] == "accepted_award_immutable"


def test_a_booking_must_fit_the_pool(world):
    grant = requested(world)
    world.pool.refresh_from_db()
    # The service raises the domain error; the HTTP layer maps budget_exhausted to a typed 409 (http.py).
    with pytest.raises((PayoutError, PayoutValidationError)) as refused:
        book(world, grant, world.pool, amount=world.pool.total_minor + 1)
    assert getattr(refused.value, "code", None) == "budget_exhausted" or refused.value.detail["code"] == "budget_exhausted"
