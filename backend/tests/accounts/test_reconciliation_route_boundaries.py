"""Account tests for C-owned surface classifications and native delegation denial."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.delegated_routes import SHARED_ACCOUNT_UTILITY, route_class
from apps.accounts.native_session import _NATIVE_USER_ID, mark_native_session
from apps.accounts.surface_policy import _delegated
from apps.accounts.tokens import SpaceWorksRefreshToken
from tests.accounts.test_reconciliation_sessions import principal

pytestmark = pytest.mark.django_db


def test_logout_all_is_an_account_utility_for_every_kind():
    assert route_class("auth-logout-all") == SHARED_ACCOUNT_UTILITY


@pytest.mark.parametrize("kind", ["member", "staff", "platform"])
def test_deletion_route_is_member_only_through_real_bearer_authentication(kind):
    user = principal(kind)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {SpaceWorksRefreshToken.for_user(user).access_token}",
                       HTTP_ORIGIN="http://localhost:5000")
    response = client.get("/api/v1/auth/account/deletion")
    assert response.status_code == (403 if kind == "platform" else 200)  # U-A1: staff-track holders are people


def test_native_member_governance_cannot_open_a_delegated_staff_route(monkeypatch):
    user = principal("member")
    # C's route policy must honor the same request-scoped native marker as RBAC,
    # including its organization-governance fast path with no tenant target.
    monkeypatch.setattr("apps.organizations.governance.has_any_governance", lambda actor: True)
    token = _NATIVE_USER_ID.set(None)
    try:
        mark_native_session(user)
        assert not _delegated(user, set(), "admin-organization-list")
    finally:
        _NATIVE_USER_ID.reset(token)
