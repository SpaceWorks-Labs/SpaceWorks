"""Hack-money G14: a programme's participant pool, and an optional separate crew pool.

Every programme has one participant pool (created with it). Finance may add ONE crew pool in the
programme currency; from then on new crew awards reserve from it, so crew expense claims no longer
eat the participant travel budget. An award keeps the pool it reserved from for its whole life
(`GrantAward.pool`), so adding a crew pool never moves an existing reservation.

`lock_pools` takes every pool of a programme in primary-key order, which is the one lock order
for pools; callers then pick the award's pool, or the pool a new award should use.
"""
from apps.payments.event_payouts.errors import require
from apps.payments.event_payouts.validation import minor
from .budget_models import ReimbursementBudgetPool

PARTICIPANTS, CREW = "participants", "crew"


def lock_pools(programme):
    rows = ReimbursementBudgetPool.objects.select_for_update().filter(programme=programme).order_by("pk")
    return {row.pk: row for row in rows}


def _choose(rows, programme, kind):
    rows = [row for row in rows if row.currency == programme.currency]
    crew = next((row for row in rows if row.audience == CREW), None) if kind == "crew" else None
    return crew or next(row for row in rows if row.audience == PARTICIPANTS)


def pool_for(pools, programme, kind, award=None):
    """The award's own pool, else the crew pool for a crew request (when one exists), else participants."""
    if award is not None:
        return pools[award.pool_id]
    return _choose(pools.values(), programme, kind)


def read_pool(programme, kind):
    """Unlocked variant for screening reads."""
    return _choose(ReimbursementBudgetPool.objects.filter(programme=programme).order_by("pk"), programme, kind)


def create_crew_pool(*, request, event_id, data):
    """Finance adds the crew pool once, funded in the same transaction (idempotent by operation)."""
    from apps.makerspaces.platform import feature_enabled
    from .budget_service import fund_locked
    from .config_models import ReimbursementProgramme
    from .transactions import command
    minor(data["initial_total_minor"], zero=True)
    with command(event_id=event_id, actor=request.user, request=request, data=data,
                 action="programme.crew_pool", finance=True) as ctx:
        if ctx.replay:
            return ctx.replay
        if not feature_enabled(ctx.event.makerspace, "events.crew_claims"):
            # #183B: the crew pool route exists only for crew claims, so off answers 404.
            from apps.makerspaces.guards import feature_off
            raise feature_off("events.crew_claims", "Crew claims are turned off for this makerspace.")
        programme = ReimbursementProgramme.objects.select_for_update().filter(event=ctx.event).first()
        require(programme is not None, "programme_not_initialized")
        pools = lock_pools(programme)
        require(not any(row.audience == CREW for row in pools.values()), "crew_pool_exists")
        pool = ReimbursementBudgetPool.objects.create(programme=programme, currency=programme.currency, audience=CREW)
        fund_locked(pool, data["initial_total_minor"], operation_id=data["operation_id"], actor=ctx.actor,
                    reason_code="initial_funding")
        pool.version = 1
        pool.save(update_fields=["version"])
        ctx.audit("event.reimbursement.crew_pool_created", programme, pool_id=pool.pk)
        return ctx.finish(programme, pool_id=pool.pk, pool_version=pool.version)
