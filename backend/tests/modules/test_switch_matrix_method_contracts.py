"""Source-reviewed PUT/PATCH/DELETE responses for the method shards.

These are fixture contracts, not values learned from the first HTTP response.
Missing objects, unavailable configuration and authority refusals are explicitly
classified; they never count as seeded successful operations. Successful settings
writes use valid bodies and the real tenant, authority and service paths.
"""
import copy

import pytest

ADMIN = "/api/v1/admin/makerspace/<int:makerspace_id>/"
SPACE = "/api/v1/admin/makerspaces/<int:makerspace_id>/"

# Sources: the named views for each route (APIView handlers and DRF generic views).
METHOD_ON_GROUPS = {
    (200, None, None, "success"): (
        f"PUT {ADMIN}stocktake-policy",
        f"PUT {SPACE}card-number-schemes",
        f"PATCH {SPACE}community-policy",
        f"PUT {SPACE}events/embed-policy/",
        f"PATCH {SPACE}events/report-switches/",
        f"PUT {SPACE}member-card-settings",
        f"PUT {SPACE}member-card-template",
        f"PATCH {SPACE}membership-admission",
        f"PUT {SPACE}membership-summary",
        f"PATCH {SPACE}metabase/connection",
        f"PATCH {SPACE}grafana/connection",
        f"PATCH {SPACE}shop/settings/",
        f"PUT {SPACE}staff-cards/settings",
        f"PATCH {SPACE}telemetry",
        "PATCH /api/v1/integrations/makerspace/<int:makerspace_id>/timing-policy",
        "PATCH /api/v1/notifications/preferences/<int:makerspace_id>",
    ),
    (204, None, None, "success"): (
        "DELETE /api/v1/notifications/browser-firebase/<int:makerspace_id>/challenge",
    ),
    (404, "not_found", None, "missing_object"): (
        f"PUT {ADMIN}machine-types/<int:machine_type_id>/policy",
        f"PUT {ADMIN}machine-use/<str:kind>/<int:pk>/event",
        f"PATCH {ADMIN}organizations/<int:organization_id>/hours-bank/",
        f"DELETE {ADMIN}stocktake-schedules/<int:pk>",
        f"PATCH {ADMIN}stocktake-schedules/<int:pk>",
        f"PATCH {SPACE}event-certificate-library/<int:template_id>/",
        f"DELETE {SPACE}machine-materials/<int:pk>",
        f"PATCH {SPACE}machine-materials/<int:pk>",
        f"DELETE {SPACE}machine-types/<int:type_id>/documents/<int:pk>",
        f"PUT {SPACE}machine-types/<int:type_id>/intake",
        f"PUT {SPACE}machine-types/<int:type_id>/job-settings",
        f"PATCH {SPACE}machine-types/<int:type_id>/setup",
        f"PATCH {SPACE}member-units/<int:pk>",
        f"PUT {SPACE}membership-plans/<int:plan_id>/units",
        f"PUT {SPACE}memberships/<int:membership_id>/unit",
        f"DELETE {SPACE}saved-report-views/<int:pk>",
        f"PATCH {SPACE}saved-report-views/<int:pk>",
        f"PUT {SPACE}staff/<int:membership_id>/unit-scope",
    ),
    (404, "not_found", None, "unconfigured_provider"): (
        "DELETE /api/v1/notifications/browser-alerts/<int:makerspace_id>",
    ),
    (403, "permission_denied", None, "no_managed_machine"): (
        f"DELETE {SPACE}maintenance/feed",
    ),
    (403, "membership_required", None, "no_membership"): (
        "DELETE /api/v1/public/<slug:makerspace_slug>/my-bookings/calendar/",
    ),
    (409, "analytics_login_missing", None, "missing_login"): (
        f"DELETE {SPACE}metabase/login",
    ),
    (409, "grafana_token_missing", None, "missing_provider_token"): (
        f"DELETE {SPACE}grafana/token",
    ),
}
METHOD_ON = {route: value[:3] for value, routes in METHOD_ON_GROUPS.items() for route in routes}
METHOD_CLASSIFICATIONS = {route: value[3] for value, routes in METHOD_ON_GROUPS.items() for route in routes}
METHOD_BODIES = {
    f"PUT {ADMIN}stocktake-policy": {"blind_default": True},
    f"PUT {SPACE}card-number-schemes": {"prefix": "", "pattern": ""},
    f"PUT {SPACE}events/embed-policy/": {"enabled": True, "allowed_origins": []},
    f"PATCH {SPACE}events/report-switches/": {"switches": {"reports.event_pdf": True}},
    f"PUT {SPACE}member-card-settings": {"verify_show_name": False},
    f"PUT {SPACE}member-card-template": {"back_text": "Switch matrix"},
    f"PUT {SPACE}membership-summary": {"enabled": True},
    f"PUT {SPACE}staff-cards/settings": {"prefix": "", "pattern": ""},
    "DELETE /api/v1/notifications/browser-firebase/<int:makerspace_id>/challenge": {
        "project_id": "matrix-project", "fid": "matrix-fid-12345",
    },
    "PATCH /api/v1/notifications/preferences/<int:makerspace_id>": {
        "feature": "hardware_requests", "channel": "email", "enabled": False,
    },
}


def method_body(route):
    identity = " ".join(route)
    if identity == f"PATCH {SPACE}telemetry":
        from apps.makerspaces.telemetry_defaults import defaults
        return {"config": defaults()}
    return copy.deepcopy(METHOD_BODIES.get(identity, {}))


def assert_method_on(route, response):
    identity = " ".join(route)
    assert identity in METHOD_ON, (identity, "declare a reviewed method-specific on response")
    assert tuple(response) == METHOD_ON[identity], (identity, response, METHOD_ON[identity])


def test_every_live_method_variant_has_an_independent_response_and_classification():
    from tests.modules.switch_matrix_helpers import variant_cases
    for _kind, _key, route, _reference in variant_cases():
        identity = " ".join(route)
        assert identity in METHOD_ON, identity
        assert identity in METHOD_CLASSIFICATIONS, identity
    assert len(METHOD_ON) == sum(len(routes) for routes in METHOD_ON_GROUPS.values())
    assert METHOD_BODIES.keys() <= METHOD_ON.keys()


def test_missing_method_targets_are_not_claimed_as_success():
    route = f"PATCH {SPACE}machine-materials/<int:pk>"
    assert METHOD_CLASSIFICATIONS[route] == "missing_object"
    assert METHOD_ON[route] == (404, "not_found", None)
