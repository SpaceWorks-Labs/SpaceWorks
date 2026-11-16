"""#162(2): RBAC suppresses staff-track authority inside native member grants and claim sessions.

The route gate already refuses staff routes for both; these tests pin the RBAC seam a
MEMBER route reaches through ``rbac.can``: after authentication, a native member grant
sees no staff action, a native staff grant only its fixed tenant's, a claim session none,
and a browser session (no limit) keeps every staff role.
"""

import pytest
from django.urls import resolve
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.accounts import rbac, session_authority
from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import device_grant, grant_staff_role, make_membership, make_staff

pytestmark = pytest.mark.django_db
ACTION = rbac.Action.EDIT_INVENTORY


@pytest.fixture(autouse=True)
def clean_limit():
    token = session_authority.reset()
    yield
    session_authority.restore(token)


def _authenticate(authorization, path="/api/v1/auth/me", **headers):
    raw = APIRequestFactory().get(path, HTTP_AUTHORIZATION=authorization, **headers)
    raw.resolver_match = resolve(path)
    return SpaceWorksJWTAuthentication().authenticate(Request(raw))


@pytest.fixture
def spaces():
    return (Makerspace.objects.create(name="Limit A", slug="limit-a"),
            Makerspace.objects.create(name="Limit B", slug="limit-b"))


def test_browser_session_keeps_every_staff_role(spaces):
    a, b = spaces
    manager = make_staff(a, username="limit-browser")
    grant_staff_role(manager, b)
    assert session_authority.staff_authority_limit(manager) is None
    assert rbac.can(manager, ACTION, a.pk) and rbac.can(manager, ACTION, b.pk)


def test_native_member_grant_sees_no_staff_action(spaces):
    a, _b = spaces
    manager = make_staff(a, username="limit-member-grant")
    make_membership(manager, a)
    access, _refresh, _family = issue_device_token_pair(manager, device_grant(manager))
    user, _token = _authenticate(f"Bearer {access}")
    assert session_authority.staff_authority_limit(user) == frozenset()
    assert not rbac.can(user, ACTION, a.pk)
    assert rbac.effective_actions(user, a.pk) == set()
    assert not rbac.is_space_manager_identity(user, a.pk)
    assert rbac.makerspaces_for_action(user, ACTION) == set()
    # Resolve scope keeps the community row (membership), never the staff-only space.
    assert rbac.resolve_scope(user) == {a.pk}
    # A re-read actor keeps the limit: it is keyed by account, not by object.
    from apps.accounts.models import User
    assert not rbac.can(User.objects.get(pk=user.pk), ACTION, a.pk)


def test_native_staff_grant_sees_only_its_tenant(spaces, settings, monkeypatch):
    from tests.accounts.test_device_staff_grants import _staff_session

    a, b = spaces
    manager, tokens = _staff_session(a, settings, monkeypatch, "limit-staff-grant")
    grant_staff_role(manager, b)
    session_authority.restore(session_authority.reset())
    user, _token = _authenticate(f"Bearer {tokens['access']}", HTTP_X_MAKERSPACE_ID=str(a.pk))
    assert session_authority.staff_authority_limit(user) == frozenset({a.pk})
    assert rbac.can(user, ACTION, a.pk)
    assert not rbac.can(user, ACTION, b.pk)


def test_claim_session_sees_no_staff_action():
    from tests.accounts.claim_helpers_p7 import redeemed_claim

    harness = redeemed_claim("limit")
    grant_staff_role(harness.member, harness.space, role_slug="inventory_manager")
    assert rbac.can(harness.member, ACTION, harness.space.pk)
    user, _token = _authenticate(harness.claim_client._credentials["HTTP_AUTHORIZATION"])
    assert session_authority.staff_authority_limit(user) == frozenset()
    assert not rbac.can(user, ACTION, harness.space.pk)


def test_limit_is_per_account(spaces):
    a, _b = spaces
    first = make_staff(a, username="limit-first")
    second = make_staff(a, username="limit-second", role_slug="inventory_manager")
    session_authority.limit_staff_authority(first)
    assert not rbac.can(first, ACTION, a.pk)
    assert rbac.can(second, ACTION, a.pk)
