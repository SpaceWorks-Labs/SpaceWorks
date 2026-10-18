"""Retained-data cancellation prefix installed by G, including runtime-off mode."""
from dataclasses import dataclass
from apps.events.models import Event, EventSeries
from apps.makerspaces.models import Makerspace
from apps.payments.event_payouts.authority import authorize
from apps.payments.event_payouts.errors import require
from apps.payments.event_payouts.transactions import lock_finance_authority
from .config_models import ReimbursementProgramme
from .budget_models import ReimbursementBudgetPool, BudgetReservation
from .request_models import GrantRequest
from .award_models import GrantAward
from .claim_models import ReimbursementClaim
from .budget_service import release_locked


@dataclass
class CancellationPrefix:
    event_id: int
    pool_id: int
    request_id: int
    award_id: int
    claim_id: int
    series_id: int | None
    pool: object = None
    claim: object = None

    def lock_before_obligation(self, *, request, seed):
        if self.series_id:
            EventSeries.objects.select_for_update().get(pk=self.series_id)
        event = Event.objects.select_for_update().get(pk=self.event_id)
        require(event.series_id == self.series_id and event.makerspace_id == seed.makerspace_id, "payout_coordination_changed")
        space = Makerspace.objects.select_for_update().get(pk=seed.makerspace_id)
        actor = lock_finance_authority(request.user, space)
        request.user = actor
        authorize(request, space, mutation=True)
        programme = ReimbursementProgramme.objects.select_for_update().get(event=event)
        self.pool = ReimbursementBudgetPool.objects.select_for_update().get(pk=self.pool_id, programme=programme)
        grant_request = GrantRequest.objects.select_for_update().get(pk=self.request_id, programme=programme)
        award = GrantAward.objects.select_for_update().get(pk=self.award_id, request=grant_request, pool=self.pool)
        self.claim = ReimbursementClaim.objects.select_for_update().get(pk=self.claim_id, award=award)
        return space, actor

    def recheck_locked(self, *, obligation, expected_pool_version):
        require(obligation.source_uuid == self.claim.uuid and obligation.event_id_snapshot == self.event_id
                and obligation.owner_member_id == self.claim.member_id, "payout_coordination_changed")
        require(self.pool.version == expected_pool_version, "stale_pool_version")

    def close_locked(self, *, obligation, revision, actor, operation_id):
        reservation = BudgetReservation.objects.select_for_update().get(award_id=self.award_id, pool=self.pool)
        release_locked(self.pool, reservation, operation_id=operation_id, actor=actor,
                       reason_code="finance_cancelled", cancel_committed=True)
        from .claim_workflow import close_by_cancellation_locked
        close_by_cancellation_locked(self.claim, cancellation_revision=revision, terminal_at=obligation.terminal_financial_at)


class RetainedCancellationProvider:
    @staticmethod
    def resolve(*, obligation):
        claim = ReimbursementClaim.objects.select_related("award__request", "event").get(uuid=obligation.source_uuid)
        return CancellationPrefix(claim.event_id, claim.award.pool_id, claim.award.request_id,
                                  claim.award_id, claim.pk, claim.event.series_id)
