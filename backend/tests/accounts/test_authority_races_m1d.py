"""Parent-first locks preserve the last managers/governors during departure."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest

from apps.accounts import account_deletion as deletion
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from apps.makerspaces.role_services import assign_role
from apps.organizations.governance import MANAGE_ORGANIZATION_MEMBERS
from apps.organizations.models import Organization, OrganizationMembership
from tests.accounts import deletion_factories as f
from tests.accounts.test_obligation_races_m1d import connected, wait_for_lock
from tests.accounts.test_support_m1d import account, m1d_config, proven
from tests.fixed_roles.helpers import assign_builtin_roles

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("kind", ["governor"])
def test_two_remaining_authorities_race_but_exactly_one_can_delete(kind, monkeypatch):
    users = [account(), account()]
    if kind == "manager":
        parent = f.space()
        for user in users:
            assign_builtin_roles(user, parent, "space_manager")
    else:
        parent = Organization.objects.create(name="M1d governors", slug="m1d-governors")
        for user in users:
            OrganizationMembership.objects.create(user=user, organization=parent,
                governance_actions=[MANAGE_ORGANIZATION_MEMBERS])
    requests = [proven(user) for user in users]
    start = Barrier(2)
    real_gates = deletion._gates

    def simultaneous(ids):
        start.wait(timeout=5)
        return real_gates(ids)

    monkeypatch.setattr(deletion, "_gates", simultaneous)

    def depart(req):
        try:
            deletion.request_deletion(req)
            return "deleted"
        except deletion.DeletionBlocked as exc:
            return exc.blockers[0]["code"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(connected, lambda req=req: depart(req)) for req in requests]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(results) == sorted(["deleted", "last_manager" if kind == "manager" else "last_org_governor"])
    survivor = User.objects.get(pk__in=[u.pk for u in users], is_active=True)
    if kind == "manager":
        assert MakerspaceMembership.objects.get(makerspace=parent, status="active").user_id == survivor.pk
    else:
        assert OrganizationMembership.objects.get(organization=parent, status="active").user_id == survivor.pk
    assert AuditLog.objects.filter(action="account.deletion_requested").count() == 1
    assert AuditLog.objects.filter(action="account.deletion_refused").count() == 1


@pytest.mark.skip(reason="#63 (U-A2): no fixed-tenant staff account remains; a person with staff roles leaves through the person path and its blockers")
def test_concurrent_staff_self_deletion_is_refused_without_changing_authority():
    from rest_framework.exceptions import PermissionDenied
    from tests.accounts.account_factories import make_staff
    from tests.accounts.test_reauthentication import request
    from tests.return_helpers import make_space

    space = make_space("fixed-staff-departure")
    user = make_staff(space, username="fixed-staff-departure")
    membership = user.makerspace_memberships.get()
    def attempt():
        try:
            deletion.request_deletion(request(User.objects.get(pk=user.pk)))
        except PermissionDenied:
            return "refused"
        return "deleted"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(connected, attempt) for _ in range(2)]
        assert [future.result(timeout=10) for future in futures] == ["refused", "refused"]
    user.refresh_from_db()
    membership.refresh_from_db()
    assert user.is_active and user.account_kind == "staff" and user.staff_makerspace_id == space.pk
    assert membership.status == "active" and user.deletion_requested_at is None
    assert not AuditLog.objects.filter(action="account.deletion_requested", actor=user).exists()
