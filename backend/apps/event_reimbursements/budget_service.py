"""Sole quantity writer. Call only after the published parent locks are held."""
from django.db import connection
from django.utils import timezone
from apps.payments.event_payouts.errors import require
from apps.payments.event_payouts.validation import minor
from .budget_math import Balance
from .budget_models import BudgetEntry, BudgetReservation, ReimbursementBudgetPool


def balance(pool):
    return Balance(total_minor=pool.total_minor, reserved_minor=pool.reserved_minor,
                   committed_minor=pool.committed_minor)


def _entry(pool, *, operation_id, actor, kind, amount, reason_code, reservation=None, decision=None):
    require(connection.in_atomic_block, "locked_transaction_required")
    prior = BudgetEntry.objects.filter(pool=pool, operation_id=operation_id, kind=kind,
                                      reservation=reservation).first()
    if prior:
        require((prior.amount_minor, prior.decision_id, prior.reason_code, prior.actor_id) ==
                (amount, getattr(decision, "pk", None), reason_code, actor.pk), "idempotency_conflict")
        return prior, False
    return BudgetEntry.objects.create(pool=pool, operation_id=operation_id, kind=kind,
        amount_minor=amount, actor=actor, reason_code=reason_code, reservation=reservation,
        decision=decision), True


def _apply(pool, *, total=0, reserved=0, committed=0):
    value = balance(pool).change(total=total, reserved=reserved, committed=committed)
    count = ReimbursementBudgetPool.objects.filter(pk=pool.pk, version=pool.version,
        total_minor=pool.total_minor, reserved_minor=pool.reserved_minor, committed_minor=pool.committed_minor).update(
        total_minor=value.total_minor, reserved_minor=value.reserved_minor, committed_minor=value.committed_minor,
        version=pool.version + 1, updated_at=timezone.now())
    require(count == 1, "stale_pool_version")
    pool.total_minor, pool.reserved_minor, pool.committed_minor = (
        value.total_minor, value.reserved_minor, value.committed_minor)
    pool.version += 1


def fund_locked(pool, amount, *, operation_id, actor, reason_code):
    minor(amount, signed=True)
    _, new = _entry(pool, operation_id=operation_id, actor=actor, kind="fund", amount=amount, reason_code=reason_code)
    if new:
        _apply(pool, total=amount)
    return pool


def reserve_locked(pool, award, amount, *, operation_id, actor, reason_code):
    minor(amount)
    require(award.pool_id == pool.pk and award.currency == pool.currency, "pool_currency_mismatch")
    reservation, created = BudgetReservation.objects.get_or_create(pool=pool, award=award)
    require(created or reservation.state == "held", "accepted_award_immutable")
    prior = BudgetEntry.objects.filter(pool=pool, reservation=reservation, operation_id=operation_id, kind="reserve").first()
    if prior:
        require(reservation.held_minor == amount and prior.actor_id == actor.pk and prior.reason_code == reason_code,
                "idempotency_conflict")
        return reservation
    delta = amount - reservation.held_minor
    _, new = _entry(pool, operation_id=operation_id, actor=actor, kind="reserve", amount=delta,
                    reason_code=reason_code, reservation=reservation)
    if new:
        _apply(pool, reserved=delta)
        reservation.held_minor, reservation.version = amount, reservation.version + 1
        reservation.save()
    return reservation


def commit_locked(pool, reservation, approved, *, operation_id, actor, reason_code, decision, appeal_hold=0):
    minor(approved, zero=True)
    minor(appeal_hold, zero=True)
    require(reservation.pool_id == pool.pk, "reservation_scope_mismatch")
    require(approved + appeal_hold <= reservation.award.amount_minor, "award_cap_exceeded")
    kind = "adjust_commitment" if reservation.decision_id else "commit"
    prior = BudgetEntry.objects.filter(pool=pool, reservation=reservation, operation_id=operation_id,
                                      kind__in=("commit", "adjust_commitment")).first()
    if prior:
        require(reservation.committed_minor == approved and reservation.held_minor == appeal_hold
                and prior.decision_id == decision.pk and prior.actor_id == actor.pk, "idempotency_conflict")
        return
    delta = approved - reservation.committed_minor
    _, new = _entry(pool, operation_id=operation_id, actor=actor, kind=kind, amount=delta,
                    reason_code=reason_code, reservation=reservation, decision=decision)
    if new:
        _apply(pool, reserved=appeal_hold - reservation.held_minor, committed=delta)
        reservation.held_minor, reservation.committed_minor = appeal_hold, approved
        reservation.state = "committed" if approved else "held" if appeal_hold else "released"
        reservation.decision, reservation.version = decision, reservation.version + 1
        reservation.save()


def release_locked(pool, reservation, *, operation_id, actor, reason_code, cancel_committed=False):
    require(pool.pk == reservation.pool_id, "reservation_scope_mismatch")
    if reservation.state == "released" and not reservation.held_minor and not reservation.committed_minor:
        return
    if reservation.committed_minor:
        require(cancel_committed, "committed_budget_requires_finance_cancellation")
        _, new = _entry(pool, operation_id=operation_id, actor=actor, kind="adjust_commitment",
            amount=-reservation.committed_minor, reason_code=reason_code, reservation=reservation)
        if new:
            _apply(pool, committed=-reservation.committed_minor)
            reservation.committed_minor = 0
    if reservation.held_minor:
        _, new = _entry(pool, operation_id=operation_id, actor=actor, kind="release",
            amount=-reservation.held_minor, reason_code=reason_code, reservation=reservation)
        if new:
            _apply(pool, reserved=-reservation.held_minor)
            reservation.held_minor = 0
    reservation.state, reservation.released_at = "released", timezone.now()
    reservation.version += 1
    reservation.save()


def hold_appeal_locked(pool, reservation, *, operation_id, actor):
    """A partial decision freed money; an appeal cannot promise that money twice."""
    disputed = reservation.award.amount_minor - reservation.committed_minor
    require(disputed > 0 and reservation.held_minor == 0, "appeal_closed")
    _, new = _entry(pool, operation_id=operation_id, actor=actor, kind="reserve", amount=disputed,
                    reason_code="claim_appeal", reservation=reservation)
    if new:
        _apply(pool, reserved=disputed)
        reservation.held_minor = disputed
        reservation.state = "committed" if reservation.committed_minor else "held"
        reservation.released_at = None
        reservation.version += 1
        reservation.save()


def book_directly_locked(pool, award, amount, *, operation_id, actor):
    """Hack-money G12: travel the organiser booked commits straight from the pool (no claim, no decision)."""
    reservation = reserve_locked(pool, award, amount, operation_id=operation_id, actor=actor, reason_code="direct_booking")
    _, new = _entry(pool, operation_id=operation_id, actor=actor, kind="commit", amount=amount,
                    reason_code="direct_booking", reservation=reservation)
    if new:
        _apply(pool, reserved=-reservation.held_minor, committed=amount)
        reservation.held_minor, reservation.committed_minor, reservation.state = 0, amount, "committed"
        reservation.version += 1
        reservation.save()
    return reservation
