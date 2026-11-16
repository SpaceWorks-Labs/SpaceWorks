"""Lane F auth routes remain explicit, inspectable claim-token refusals."""
import pytest
from django.urls import path, resolve, reverse

from apps.accounts.claim_pre_auth_guard import validate_pre_auth_route
from apps.accounts.claim_route_guard import ClaimRouteConfigurationError, validate_claim_route_matrix
from apps.accounts.claim_route_inspection import flatten_claim_routes
from apps.accounts.claim_route_types import AnonymousRead, Refused
from apps.accounts.claim_routes_auth import AUTH_CLAIM_ROUTES
from apps.organizations.views_self_service import (
    OrganizationCreationIpThrottle, OrganizationCreationThrottle, OrganizationSelfServiceView,
)

ROUTES = {
    "auth-reauth": ("GET", "HEAD", "POST"),
    "auth-reauth-social-start": ("POST",),
    "auth-reauth-social-complete": ("POST",),
    "auth-reauth-enrollment-email": ("POST",),
    "auth-reauth-enrollment-confirm": ("POST",),
    "auth-organizations-self-service": ("GET", "HEAD", "POST"),
}


def lane_patterns():
    return [path(f"api/v1/auth/lane-f-{index}", resolve(reverse(name)).func, name=name)
            for index, name in enumerate(ROUTES)]


def lane_policies():
    return {key: value for key, value in AUTH_CLAIM_ROUTES.items() if key[0] in ROUTES}


@pytest.mark.parametrize("name,methods", ROUTES.items())
def test_new_auth_routes_have_explicit_claim_refusals_and_inspectable_policies(name, methods):
    for method in methods:
        assert isinstance(AUTH_CLAIM_ROUTES[(name, method)], Refused)
    assert isinstance(AUTH_CLAIM_ROUTES[(name, "OPTIONS")], AnonymousRead)
    routes, errors = flatten_claim_routes(lane_patterns())
    assert errors == []
    route = next(route for route in routes if route.view_name == name)
    assert validate_pre_auth_route(route) == []


def test_real_lane_f_callbacks_pass_claim_matrix_validation():
    assert len(validate_claim_route_matrix(
        lane_patterns(), policies=lane_policies(), require_all_active=False,
        check_middleware=False)) == len(ROUTES)


def test_self_service_uses_declarative_user_and_ip_throttles():
    assert "get_throttles" not in OrganizationSelfServiceView.__dict__
    assert [type(throttle) for throttle in OrganizationSelfServiceView().get_throttles()] == [
        OrganizationCreationThrottle, OrganizationCreationIpThrottle,
    ]


def test_adding_an_unreviewed_throttle_override_still_fails_closed(monkeypatch):
    monkeypatch.setattr(OrganizationCreationThrottle, "allow_request", lambda *args: True)
    with pytest.raises(ClaimRouteConfigurationError, match="unrecognised policy overrides"):
        validate_claim_route_matrix(lane_patterns(), policies=lane_policies(),
                                   require_all_active=False, check_middleware=False)
