"""Native staff header registry (decision 353, MOB-STAFF): every staff route the web SPA calls is resolvable.

A native staff grant must send `X-Makerspace-Id`; the server refuses a route it cannot tie to a makerspace
("Makerspace target could not be resolved"). The SPA's staff screens are read from the repo's frontend sources,
every route they call that is staff-classed must be recognized by the origin-scope tables or the native-only
resolvers, or be declared in `NATIVE_STAFF_WEB_ONLY` with its reason. A new staff route without a lookup fails here.
"""
import pytest
from django.test import RequestFactory
from django.urls import URLPattern, URLResolver, get_resolver, resolve

from apps.accounts.delegated_routes import DELEGABLE, MEMBERSHIP_ONLY, route_class
from apps.makerspaces.origin_scope_native_slug import native_slug_targets
from apps.makerspaces.origin_scope_native_staff import native_staff_targets
from apps.makerspaces.origin_scope_routes import request_route_targets
from apps.makerspaces.origin_scope_routes_mobstaff import NATIVE_STAFF_WEB_ONLY, PROGRAMME_MODEL_LOOKUPS
from tests.api_r2.spa_staff_routes import match_for, spa_schema_paths

pytestmark = pytest.mark.django_db
STAFF = {DELEGABLE, MEMBERSHIP_ONLY}
# Staff-classed, called by the SPA, and reached by a native MEMBER grant with no header (the invite token is the proof).
NO_HEADER = {"event-staff-invite-redeem"}

# (url name, concrete path) of the routes fixed by MOB-STAFF that the shared tables resolve (programme routes included).
TABLE_ROUTES = (
    ("admin-event-image", "/api/v1/admin/events/7/image"),
    ("admin-space-organization-booking", "/api/v1/admin/spaces/7/organization-bookings/"),
    ("admin-space-organization-booking-choices", "/api/v1/admin/spaces/7/organization-bookings/choices/"),
    ("admin-oauth-app", "/api/v1/admin/oauth-apps/7"),
    ("telegram-test-alert", "/api/v1/integrations/telegram/test-alert"),
    ("events-programme-admin-space-insights", "/api/v1/admin/events/insights/"),
    ("admin-makerspaces", "/api/v1/admin/makerspaces"),
    ("admin-event-host-options", "/api/v1/admin/events/host-options/"),
    ("admin-bulk-requests", "/api/v1/admin/bulk/requests/accept"),
    ("admin-bulk-bookings", "/api/v1/admin/bulk/bookings/approve"),
    ("admin-bulk-event-registrations", "/api/v1/admin/bulk/event-registrations/approve"),
    ("events-programme-admin-tracks-list", "/api/v1/admin/events/7/tracks/"),
    ("events-programme-admin-judging-rounds-list", "/api/v1/admin/events/7/judging-rounds/"),
    ("events-programme-admin-badge-print-create", "/api/v1/admin/events/7/badges/print-jobs/"),
    ("events-programme-series-guests", "/api/v1/admin/event-series/7/guests/"),
)
# Routes resolved only for a native header, by the object's own id (nullable owner).
NATIVE_ONLY_ROUTES = (
    ("admin-api-client", "/api/v1/admin/api-clients/7"),
    ("admin-api-client-rotate-secret", "/api/v1/admin/api-clients/7/rotate-secret"),
)


def _request(path, method="get", **extra):
    request = getattr(RequestFactory(), method)(path, **extra)
    request.resolver_match = resolve(path)
    return request


def native_recognized(request):
    _name, _targets, _invalid, recognized = request_route_targets(request)
    return recognized or native_staff_targets(request) is not None or native_slug_targets(request) is not None


@pytest.mark.parametrize("name,path", TABLE_ROUTES)
def test_fixed_route_is_staff_classed_and_recognized(name, path):
    request = _request(path, "post" if name.startswith(("admin-bulk", "telegram")) else "get")
    assert request.resolver_match.url_name == name
    assert route_class(name) in STAFF
    assert request_route_targets(request)[3] is True, f"{name} would be refused for a native staff header"


@pytest.mark.parametrize("name,path", NATIVE_ONLY_ROUTES)
def test_native_only_route_resolves_its_owner_and_never_feeds_the_web_resolver(name, path):
    request = _request(path)
    assert request.resolver_match.url_name == name and route_class(name) in STAFF
    assert request_route_targets(request)[3] is False  # web scoping is unchanged
    # No such object: the lookup ran and marks the target invalid (the header is then refused).
    assert native_staff_targets(request) == (set(), True)


def test_programme_routes_resolve_their_event_space_for_the_web_resolver_too():
    request = _request("/api/v1/admin/events/987654/tracks/")
    # No such event: the shared lookup ran (invalid), so web origin scope, the source gate and RLS see a target.
    assert request_route_targets(request) == ("events-programme-admin-tracks-list", set(), True, True)


def test_event_programme_staff_routes_all_take_their_event_from_pk():
    seen = []

    def walk(patterns, converters):
        for entry in patterns:
            if isinstance(entry, URLResolver):
                walk(entry.url_patterns, {**converters, **getattr(entry.pattern, "converters", {})})
            elif isinstance(entry, URLPattern) and entry.name:
                seen.append((entry.name, set(converters) | set(getattr(entry.pattern, "converters", {}))))

    walk(get_resolver().url_patterns, {})
    names = set(PROGRAMME_MODEL_LOOKUPS)
    params = {name: kwargs for name, kwargs in seen if name in names}
    assert params and set(params) <= names
    assert [name for name, kwargs in params.items() if "pk" not in kwargs] == []


def test_registry_walk_every_spa_staff_route_is_resolvable_or_declared_web_only():
    paths = spa_schema_paths()
    if paths is None:
        pytest.skip("frontend sources are not mounted next to backend/")
    refused, unresolved = [], []
    for schema_path in sorted(paths):
        concrete, match = match_for(schema_path)
        if match is None:
            unresolved.append(schema_path)
            continue
        name = match.url_name
        if route_class(name) not in STAFF or name in NO_HEADER:
            continue
        request = _request(concrete)
        if name in NATIVE_STAFF_WEB_ONLY:
            assert not native_recognized(request), f"{name} is declared web-only but is resolvable"
        elif not native_recognized(request):
            refused.append(name)
    assert len(unresolved) < max(5, len(paths) // 20), unresolved[:10]
    assert sorted(set(refused)) == [], (
        "staff routes the SPA calls have no native makerspace target: add a lookup in "
        "origin_scope_routes_mobstaff.py (or declare NATIVE_STAFF_WEB_ONLY with the reason)")


def test_every_web_only_declaration_names_a_staff_classed_route_with_a_reason():
    for name, reason in NATIVE_STAFF_WEB_ONLY.items():
        assert route_class(name) in STAFF and reason, name
