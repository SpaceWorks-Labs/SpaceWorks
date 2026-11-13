"""PostgreSQL serialization, replay and rollback of real budget mutations."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4
import pytest
from django.db import close_old_connections, transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.events.models import Event
from apps.makerspaces.models import Makerspace
from apps.event_reimbursements.models import (
    ReimbursementProgramme, ReimbursementBudgetPool, GrantRequest, GrantAward, BudgetReservation, BudgetEntry,
)
from apps.event_reimbursements.budget_service import reserve_locked, release_locked, fund_locked
from apps.payments.event_payouts.validation import PayoutValidationError


@pytest.fixture
def funded(settings):
    settings.PII_ENCRYPTION_ENABLED = False
    space = Makerspace.objects.create(name="Budget race", slug="budget-race")
    from tests.accounts.account_factories import make_staff
    with transaction.atomic():
        actor = make_staff(space, username="budget-finance")
    now = timezone.now()
    event = Event.objects.create(makerspace=space, title="Ordinary event", starts_at=now + timedelta(days=2),
                                 ends_at=now + timedelta(days=3), registration_audience="accounts")
    programme = ReimbursementProgramme.objects.create(event=event, currency="INR", claim_due_at=now + timedelta(days=10),
        approved_by=actor, initialization_operation_id=uuid4(), initialization_digest="a" * 64)
    pool = ReimbursementBudgetPool.objects.create(programme=programme, currency="INR", total_minor=100)
    awards = []
    for number in range(2):
        member = User.objects.create_user(username=f"budget-member-{number}", account_kind="member")
        request = GrantRequest.objects.create(programme=programme, event=event, member=member,
            request_phase="application", mode="rail", currency="INR")
        awards.append(GrantAward.objects.create(request=request, pool=pool, amount_minor=60,
            currency="INR", rule_revision=1, offered_at=now, accept_by=now + timedelta(days=1), issued_by=actor))
    return actor, event, pool, awards


@pytest.mark.django_db(transaction=True)
def test_last_budget_cannot_be_reserved_twice(funded):
    actor, event, pool, awards = funded
    barrier = Barrier(2)

    def reserve(award_id):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            with transaction.atomic():
                Event.objects.select_for_update().get(pk=event.pk)
                locked = ReimbursementBudgetPool.objects.select_for_update().get(pk=pool.pk)
                award = GrantAward.objects.select_for_update().get(pk=award_id)
                reserve_locked(locked, award, 60, operation_id=uuid4(), actor=actor, reason_code="award")
            return "reserved"
        except PayoutValidationError as exc:
            return exc.code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, [row.pk for row in awards]))
    assert sorted(results) == ["budget_exhausted", "reserved"]
    pool.refresh_from_db()
    assert pool.reserved_minor == 60
    assert pool.total_minor - pool.reserved_minor - pool.committed_minor == 40
    assert BudgetEntry.objects.filter(pool=pool).count() == 1
    assert BudgetReservation.objects.filter(pool=pool).count() == 1


@pytest.mark.django_db
def test_reserve_replay_and_release_do_not_consume_twice(funded):
    actor, _, pool, awards = funded
    operation = uuid4()
    with transaction.atomic():
        pool = ReimbursementBudgetPool.objects.select_for_update().get(pk=pool.pk)
        reservation = reserve_locked(pool, awards[0], 60, operation_id=operation, actor=actor, reason_code="award")
        first_version = pool.version
        reserve_locked(pool, awards[0], 60, operation_id=operation, actor=actor, reason_code="award")
        assert pool.version == first_version
        release_operation = uuid4()
        release_locked(pool, reservation, operation_id=release_operation, actor=actor, reason_code="declined")
        release_locked(pool, reservation, operation_id=release_operation, actor=actor, reason_code="declined")
    pool.refresh_from_db()
    assert pool.reserved_minor == 0
    assert BudgetEntry.objects.filter(pool=pool).count() == 2


@pytest.mark.django_db
def test_reducing_budget_below_holds_rolls_back_entry(funded):
    actor, _, pool, awards = funded
    with transaction.atomic():
        pool = ReimbursementBudgetPool.objects.select_for_update().get(pk=pool.pk)
        reserve_locked(pool, awards[0], 60, operation_id=uuid4(), actor=actor, reason_code="award")
    with pytest.raises(PayoutValidationError), transaction.atomic():
        locked = ReimbursementBudgetPool.objects.select_for_update().get(pk=pool.pk)
        fund_locked(locked, -41, operation_id=uuid4(), actor=actor, reason_code="reduce_fund")
    pool.refresh_from_db()
    assert (pool.total_minor, pool.reserved_minor) == (100, 60)
    assert not BudgetEntry.objects.filter(pool=pool, kind="fund").exists()
