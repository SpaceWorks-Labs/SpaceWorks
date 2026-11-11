"""Real PostgreSQL transactions serialize last-manager removal and concurrent grants."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connection
from rest_framework.exceptions import APIException

from apps.accounts import staff_account_lifecycle as lifecycle, staff_account_services as service
from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership
from .p3_helpers import PASSWORD, context

pytestmark = pytest.mark.django_db(transaction=True)


def _threaded(*calls):
    barrier = Barrier(len(calls))

    def run(call):
        try:
            barrier.wait(timeout=15)
            call()
            return "ok"
        except APIException:
            return "refused"
        finally:
            connection.close()
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        futures = [pool.submit(run, call) for call in calls]
        return [future.result(timeout=45) for future in futures]


@pytest.mark.parametrize("second", ["revoke", "demote"])
def test_concurrent_manager_removal_cannot_leave_zero(settings, second):
    ctx = context(settings)
    rows = {user.pk: MakerspaceMembership.staff_tracks.get(user=user, makerspace=ctx.space).pk
            for user in (ctx.manager, ctx.peer)}

    def first():
        lifecycle.revoke(ctx.root, ctx.space.pk, rows[ctx.manager.pk])

    def other():
        if second == "demote":
            service.change(ctx.root, ctx.space.pk, rows[ctx.peer.pk], roles=["handover"])
        else:
            lifecycle.revoke(ctx.root, ctx.space.pk, rows[ctx.peer.pk])
    outcomes = _threaded(first, other)
    assert sorted(outcomes) == ["ok", "refused"]
    assert MakerspaceMembership.staff_tracks.filter(makerspace=ctx.space, assigned_role__slug="space_manager",
        status="active", user__is_active=True).count() == 1


def test_concurrent_grants_of_one_person_create_one_staff_row(settings):
    ctx = context(settings)
    joiner = User.objects.create_user("p3-race-joiner", password=PASSWORD)
    MakerspaceMembership.objects.create(user=joiner, makerspace=ctx.space, role="member",
                                        assigned_role=ctx.space.roles.get(slug="member"))

    def by(actor, role):
        return lambda: service.grant(actor, ctx.space.pk, user_id=joiner.pk, roles=[role])
    outcomes = _threaded(by(ctx.root, "handover"), by(ctx.manager, "inventory_manager"))
    assert sorted(outcomes) == ["ok", "refused"]
    assert MakerspaceMembership.staff_tracks.filter(makerspace=ctx.space, user=joiner).count() == 1
