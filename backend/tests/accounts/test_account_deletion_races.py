"""Real session proofs and parent locks protect concurrent platform departures."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest
from cryptography.fernet import Fernet
from django.db import close_old_connections, connection

from apps.accounts import account_deletion, reauthentication
from apps.accounts.models import User
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from apps.makerspaces.role_services import assign_role
from apps.organizations.governance import MANAGE_ORGANIZATION_MEMBERS
from apps.organizations.models import Organization, OrganizationMembership
from tests.accounts.test_reauthentication import ORIGIN, PASSWORD, request
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def configuration(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    settings.ACCOUNT_DELETION_RETENTION_DAYS = 90


def proven(name):
    user = User.objects.create_user(username=name, email=f"{name}@example.test", password=PASSWORD)
    req = request(user, surface="member")
    reauthentication.verify(req, password=PASSWORD)
    assert ReauthenticationSession.objects.filter(user=user, auth_time__isnull=False).exists()
    return user, req


def connected(function):
    close_old_connections()
    try:
        # A lock-order regression fails within the test, rather than hanging the suite.
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '5s'")
            cursor.execute("SET statement_timeout = '8s'")
        return function()
    finally:
        close_old_connections()


def delete(req):
    try:
        account_deletion.request_deletion(req)
        return "deleted"
    except account_deletion.DeletionBlocked as exc:
        return exc.blockers[0]["code"]


@pytest.mark.parametrize("kind", ["governor"])
def test_two_last_authorities_cannot_depart_together(kind, monkeypatch):
    one, first = proven(f"first-{kind}")
    two, second = proven(f"second-{kind}")
    if kind == "manager":
        space = make_space("last-managers-race")
        assign_builtin_roles(one, space, "space_manager")
        assign_builtin_roles(two, space, "space_manager")
    else:
        organization = Organization.objects.create(name="Governors", slug="governors-race")
        for user in (one, two):
            OrganizationMembership.objects.create(
                organization=organization, user=user, governance_actions=[MANAGE_ORGANIZATION_MEMBERS],
            )
    start = Barrier(2)
    original = account_deletion._gates

    def synchronized(ids):
        start.wait(timeout=5)
        return original(ids)

    monkeypatch.setattr(account_deletion, "_gates", synchronized)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(connected, lambda req=req: delete(req)) for req in (first, second)]
        outcomes = sorted(future.result(timeout=15) for future in futures)
    assert outcomes == sorted(["deleted", "last_manager" if kind == "manager" else "last_org_governor"])
    assert User.objects.filter(pk__in=[one.pk, two.pk], is_active=True).count() == 1
    if kind == "manager":
        assert MakerspaceMembership.objects.filter(makerspace=space, status="active").count() == 1
    else:
        assert OrganizationMembership.objects.filter(organization=organization, status="active").count() == 1
    assert AuditLog.objects.filter(action="account.deletion_requested").count() == 1
    assert AuditLog.objects.filter(action="account.deletion_refused").count() == 1


def test_concurrent_staff_self_deletion_without_proof_is_refused_without_changing_authority():
    """One account per person: staff may self-delete, but never without fresh re-authentication."""
    from rest_framework.exceptions import PermissionDenied
    from tests.accounts.account_factories import make_staff
    from tests.accounts.test_reauthentication import request
    from tests.return_helpers import make_space

    space = make_space("fixed-staff-departure")
    user = make_staff(space, username="fixed-staff-departure")
    membership = MakerspaceMembership.staff_tracks.get(user=user)
    def attempt():
        try:
            account_deletion.request_deletion(request(User.objects.get(pk=user.pk)))
        except PermissionDenied:
            return "refused"
        return "deleted"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(connected, attempt) for _ in range(2)]
        assert [future.result(timeout=10) for future in futures] == ["refused", "refused"]
    user.refresh_from_db()
    membership.refresh_from_db()
    assert user.is_active and user.account_kind == "member" and user.staff_makerspace_id is None
    assert membership.status == "active" and user.deletion_requested_at is None
    assert not AuditLog.objects.filter(action="account.deletion_requested", actor=user).exists()
