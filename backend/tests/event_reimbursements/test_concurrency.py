"""Real separate PostgreSQL connections serialize last-budget and offer races."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from django.db import close_old_connections, connection
from apps.accounts.models import User
from apps.accounts import reauthentication
from apps.event_reimbursements import award_workflow, request_workflow
from apps.event_reimbursements.models import GrantAward, GrantRequest
from apps.payments.event_payouts.errors import PayoutError
from tests.accounts.test_reauthentication import request as session_request, PASSWORD
from .conftest import cmd
from .helpers import requested, block

pytestmark = pytest.mark.django_db(transaction=True)


def test_two_last_balance_awards_cannot_overdraw(make_world):
    world = make_world(total=10000)
    one = requested(world)
    second = User.objects.create_user(username="second-traveller", account_kind="member", email="second@example.test", phone="+919988776655")
    from apps.events.services_registration import register
    register(world.event, member=second, actor=second)
    request_workflow.submit(event_id=world.event.pk, actor=second, data=cmd(reimbursement_request=block(world)))
    two = GrantRequest.objects.get(event=world.event, member=second)
    world.pool.refresh_from_db()
    barrier = Barrier(2)
    def offer(request_id):
        close_old_connections()
        try:
            actor = User.objects.get(pk=world.manager.pk)
            request = session_request(actor)
            reauthentication.verify(request, password=PASSWORD)
            grant = GrantRequest.objects.get(pk=request_id)
            barrier.wait(timeout=15)
            award_workflow.decide(request=request, event_id=world.event.pk, request_id=request_id,
                data=cmd(grant.version, outcome="award", amount_minor=10000, currency="INR", reason_code="need_based",
                    expected_award_version=None, expected_pool_version=world.pool.version))
            return "awarded"
        except PayoutError as exc:
            return str(exc.detail["code"])
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(offer, (one.pk, two.pk)))
    assert outcomes.count("awarded") == 1
    assert set(outcomes) <= {"awarded", "stale_pool_version", "budget_exhausted"}
    world.pool.refresh_from_db()
    assert (world.pool.total_minor, world.pool.reserved_minor, world.pool.committed_minor) == (10000, 10000, 0)
    assert GrantAward.objects.filter(request__event=world.event).count() == 1


def test_accept_and_cap_edit_have_one_winner_and_accepted_cap_is_immutable(world):
    grant = requested(world)
    award_workflow.decide(request=world.finance, event_id=world.event.pk, request_id=grant.pk,
        data=cmd(grant.version, outcome="award", amount_minor=8000, currency="INR", reason_code="need_based",
            expected_award_version=None, expected_pool_version=world.pool.version))
    grant.refresh_from_db(); world.pool.refresh_from_db()
    award = GrantAward.objects.get(request=grant)
    barrier = Barrier(2)
    def run(edit):
        close_old_connections()
        try:
            actor = User.objects.get(pk=world.manager.pk if edit else world.owner.pk)
            req = session_request(actor, surface="member")
            if edit:
                reauthentication.verify(req, password=PASSWORD)
            barrier.wait(timeout=15)
            if edit:
                award_workflow.decide(request=req, event_id=world.event.pk, request_id=grant.pk,
                    data=cmd(grant.version, outcome="award", amount_minor=7000, currency="INR", reason_code="need_based",
                        expected_award_version=award.version, expected_pool_version=world.pool.version))
            else:
                award_workflow.respond(event_id=world.event.pk, actor=actor, request=req,
                    data=cmd(award.version, award_revision=1), accept=True)
            return "changed"
        except PayoutError as exc:
            return str(exc.detail["code"])
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(run, (False, True)))
    assert outcomes.count("changed") == 1
    award.refresh_from_db(); world.pool.refresh_from_db()
    assert (award.state, award.amount_minor) in (("accepted", 8000), ("offered", 7000))
    assert world.pool.reserved_minor == award.amount_minor
