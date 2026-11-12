import hashlib
import hmac
import time
import uuid

import pytest
from django.core.exceptions import ValidationError
from django.test import RequestFactory, override_settings
from django.urls import get_resolver, resolve
from rest_framework.test import APIClient

from apps.apiclients import scope_registry
from apps.apiclients.models import ApiClient
from apps.apiclients.scope_registry import (
    LEGACY_SCOPE,
    SCOPE_REGISTRY,
    TARGET_GLOBAL,
    TARGET_TENANT_SLUG,
    TARGET_TENANT_TOKEN,
    ScopeRegistryEntry,
    lookup,
    resolve_target,
    validate_registry,
)
from apps.accounts.programme_route_catalog import ROUTES as PROGRAMME_ROUTES
from apps.hardware_requests.models import HardwareRequest
from apps.machines.models import MachineServiceRequest, MachineType, ServiceQueue
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db

PUBLIC_PREFIXES = ["/api/public/", "/api/v1/public/"]
PUBLIC_DIRECTORY = "/api/v1/public/makerspaces/"
ORIGIN = "http://localhost:5000"

@pytest.fixture(autouse=True)
def _protected_prefixes(settings):
    settings.HMAC_PROTECTED_PATH_PREFIXES = PUBLIC_PREFIXES
    settings.APICLIENT_REQUIRE_NONCE = False


def _request(path, method="get"):
    request = getattr(RequestFactory(), method)(path)
    request.resolver_match = resolve(request.path_info)
    return request


def _signed_headers(api_client, raw_secret, path=PUBLIC_DIRECTORY):
    timestamp = str(int(time.time()))
    message = b"\n".join([b"GET", path.encode(), timestamp.encode(), b""])
    signature = hmac.new(
        raw_secret.encode(), message, hashlib.sha256
    ).hexdigest()
    return {
        "HTTP_X_CLIENT_ID": api_client.client_id,
        "HTTP_X_TIMESTAMP": timestamp,
        "HTTP_X_SIGNATURE": signature,
        "HTTP_ORIGIN": ORIGIN,
    }


def test_registry_has_no_urlconf_drift():
    stale, missing = validate_registry()

    assert not stale, f"Registry entries reference missing URL names: {stale}"
    assert not missing, f"Protected routes missing registry entries: {missing}"


def test_legacy_cutover_is_explicit_and_new_entries_default_to_excluded():
    excluded = {key for key, entry in SCOPE_REGISTRY.items() if not entry.legacy_v1}
    expected_routes = (
        ('public-membership-admission', ('GET', 'HEAD')),
        ('hardware_requests:public-tool-checklist', ('POST',)),
        ('public-event-detail', ('GET', 'HEAD')),
        ('public-event-share-image', ('GET', 'HEAD')),
        ('public-event-short-code', ('GET', 'HEAD')),
        ('public-event-organization-eligibility', ('GET', 'HEAD')),
        ('member-booking-pass', ('GET', 'HEAD')),
        ('member-booking-confirmation', ('GET', 'HEAD')),
        ('member-booking-confirmation-png', ('GET', 'HEAD')),
        ('member-booking-calendar', ('GET', 'HEAD')),
        ('member-booking-rotate-checkin', ('POST',)),
        ('member-booking-list', ('GET', 'HEAD')),
        ('member-booking-cancel', ('POST',)),
        ('member-booking-checkout', ('POST',)),
        ('public-event-venue', ('GET', 'HEAD')),
        ('public-presence-now', ('GET', 'HEAD')),
        ('presence-renew', ('POST',)),
        ('presence-projects', ('GET', 'HEAD')),
        ('presence-preferences', ('GET', 'HEAD', 'PATCH')),
        ('member-booking-reschedule', ('POST',)),
        ('member-booking-feed-settings', ('GET', 'HEAD', 'POST', 'DELETE')),
        ('public-booking-feed', ('GET', 'HEAD')),
        ('public-machine-detail', ('GET', 'HEAD')),
        ('public-machine-details', ('GET', 'HEAD')),
        ('public-machine-intake', ('GET', 'HEAD')),
        ('public-inventory-watch', ('POST', 'DELETE')),
        ('v1:public-inventory-watch', ('POST', 'DELETE')),
        # Routes added after the legacy cutover: excluded from legacy:v1 by default.
        *((name, ('GET', 'HEAD')) for name in (
            'integration-booking-detail', 'integration-booking-list',
            'integration-booking-resource-detail', 'integration-booking-resource-list',
            'integration-booking-resource-reservations',
            'integration-event-detail', 'integration-event-list', 'integration-event-participants',
            'public-booking-resource', 'public-booking-website', 'public-booking-website-image',
            'public-event-website', 'public-event-website-image', 'public-event-website-schedule',
            'public-event-website-section', 'public-event-website-session',
            'public-event-website-speaker',
            'public-profile', 'public-profile-activity', 'public-profile-events',
            'public-profile-projects',
            'public-profile-github',
            'public-machine-service-status',
        )),
        # Integration 2026-10-19: mobile messaging routes and the Pages public-page
        # reads, all excluded from legacy:v1 by default.
        # L16: account-less issue reports and the technician opt-in page.
        ('public-issue-report', ('POST',)),
        ('public-issue-photo-upload', ('POST',)),
        ('public-technician-opt-in', ('GET', 'HEAD', 'POST')),
        ('member-messaging', ('GET', 'HEAD')),
        ('member-messaging-consent', ('POST',)),
        ('messaging-meta', ('GET', 'HEAD', 'POST')),
        ('messaging-meta-platform', ('GET', 'HEAD', 'POST')),
        ('messaging-settings', ('GET', 'HEAD', 'PATCH')),
        ('messaging-test', ('POST',)),
        ('messaging-twilio-inbound', ('POST',)),
        ('messaging-twilio-platform-inbound', ('POST',)),
        ('messaging-twilio-platform-status', ('POST',)),
        ('messaging-twilio-status', ('POST',)),
        ('public-event-code', ('GET', 'HEAD')),
        ('public-makerspace-page', ('GET', 'HEAD')),
        ('public-makerspace-page-asset', ('GET', 'HEAD')),
        ('public-organization-makerspaces', ('GET', 'HEAD')),
        ('public-organization-page', ('GET', 'HEAD')),
        ('public-organization-page-asset', ('GET', 'HEAD')),
        ('public-page-handle', ('GET', 'HEAD')),
        ('whatsapp-template-catalog', ('GET', 'HEAD')),
        ('whatsapp-template-detail', ('PATCH', 'DELETE')),
        ('whatsapp-template-list', ('GET', 'HEAD', 'POST')),
        # Release 2 L6: the public ticket shop and the orders:read server reads.
        ('public-event-ticket-shop', ('GET', 'HEAD', 'POST')),
        ('integration-order-list', ('GET', 'HEAD')),
        ('integration-order-detail', ('GET', 'HEAD')),
        ('integration-application-counts', ('GET', 'HEAD')),
        # Release 2 L3: the public card check and the ID-programme join routes.
        ('public-card-verification', ('GET', 'HEAD')),
        ('public-organization-id-programmes', ('GET', 'HEAD')),
        ('public-id-programme', ('GET', 'HEAD')),
        ('public-id-programme-join', ('POST',)),
        ('public-id-programme-join-photo', ('POST',)),
        # Hosting requests (lane/hosting-requests): public intake, excluded from legacy:v1.
        ('public-hosting-invitation-resolve', ('POST',)),
        ('public-hosting-invitation-submit', ('POST',)),
        ('public-hosting-request-open', ('POST',)),
        ('public-hosting-request-submit', ('POST',)),
        ('public-hosting-request-resubmit', ('POST',)),
        # Release 2 L4: public plan cards/pages and the invite-link check.
        ('public-membership-plans', ('GET', 'HEAD')),
        ('public-membership-plan-detail', ('GET', 'HEAD')),
        ('public-membership-invite', ('GET', 'HEAD')),
        # Release 2 L5: a signed pay link for someone without an account, excluded from legacy:v1.
        ('pay-link', ('GET', 'HEAD')),
        ('pay-link-checkout', ('POST',)),
        ('pay-link-claim', ('POST',)),
        # Release 2 L15: the public price preview, excluded from legacy:v1.
        ('pricing-quote', ('POST',)),
        # Release 2 L18: donations, sponsor walls, a guest's signed links and the calendar feeds.
        ('public-donation-page', ('GET', 'HEAD')), ('public-sponsor-wall', ('GET', 'HEAD')),
        ('public-event-sponsors', ('GET', 'HEAD')), ('public-listed-events-calendar', ('GET', 'HEAD')),
        ('public-shift-calendar-feed', ('GET', 'HEAD')), ('public-combined-calendar-feed', ('GET', 'HEAD')),
        ('public-donation-email-code', ('POST',)), ('public-donations', ('POST',)),
        ('public-donation-pledges', ('POST',)), ('public-donation-status', ('GET', 'HEAD')),
        ('public-donation-tax-receipt', ('GET', 'HEAD')), ('public-donation-checkout', ('POST',)),
        ('public-donation-claim', ('POST',)), ('public-pledge-manage', ('GET', 'HEAD', 'POST')),
        # Stale after L22 2b21db63/13d7af2a: the public shop, excluded from legacy:v1 by default.
        ('public-shop', ('GET', 'HEAD')), ('public-shop-products', ('GET', 'HEAD')),
        ('public-shop-product', ('GET', 'HEAD')), ('public-shop-quote', ('POST',)),
        ('public-shop-email-code', ('POST',)), ('public-shop-orders', ('POST',)),
        ('public-shop-order-status', ('GET', 'HEAD')),
        # #135 Q-S18 follow-up: the shop items an event offers.
        ('public-shop-event-offers', ('GET', 'HEAD')),
        # Stale after da9901d0 (programme-join prefill) and 80453032 (space-controls availability).
        ('public-id-programme-prefill', ('GET', 'HEAD')),
        ('public-makerspace-availability', ('GET', 'HEAD')),
        # 0.12.0 routes: every new route or method starts excluded from the legacy:v1 cutover until reviewed.
        ('admin-direct-loan-booking-context', ('GET','HEAD','PUT','DELETE')), ('admin-direct-loan-event-context', ('GET','HEAD','PUT','DELETE')),
        ('admin-event-booking-link', ('GET','HEAD','POST')), ('admin-event-booking-replacement', ('POST',)), ('admin-event-create-with-room', ('POST',)),
        ('admin-event-registration-queue', ('GET','HEAD')), ('admin-event-room-choices', ('GET','HEAD')), ('admin-event-venue', ('GET','HEAD')),
        ('admin-event-workshop-machine-link', ('DELETE',)), ('admin-event-workshop-machine-replacement', ('POST',)), ('admin-event-workshop-machines', ('GET','HEAD','POST')),
        ('admin-makerspace-telemetry', ('GET','HEAD')), ('admin-platform-firebase-web-settings', ('GET','HEAD','PATCH')), ('admin-platform-telemetry', ('GET','HEAD','PATCH')),
        ('admin-request-booking-context', ('GET','HEAD','PUT','DELETE')), ('admin-request-event-context', ('GET','HEAD','PUT','DELETE')),
        ('auth-browser-state', ('GET','HEAD')), ('hardware_requests:contextual-request-self', ('POST',)),
        ('hardware_requests:equipment-kit-public-detail', ('GET','HEAD')), ('hardware_requests:equipment-kit-public-list', ('GET','HEAD')),
        ('notifications:browser-firebase-challenge', ('POST','DELETE')), ('notifications:browser-firebase-config', ('GET','HEAD')), ('notifications:browser-firebase-confirm', ('POST',)),
        ('notifications:browser-firebase-global-may-resume', ('POST',)), ('notifications:browser-firebase-may-resume', ('POST',)),
        ('public-day-passes', ('GET','HEAD')), ('public-machines-now', ('GET','HEAD')), ('public-member-units', ('GET','HEAD')),
        ('public-organization-directory', ('GET','HEAD')), ('public-presence-here-now', ('GET','HEAD')),
        # Events programme: only its public routes sit behind the protected prefix.
        *((name, methods) for name, methods, _target in PROGRAMME_ROUTES
          if name.startswith("events-programme-public-")),
    )
    assert excluded == {(name, method) for name, methods in expected_routes for method in methods}
    new_entry = ScopeRegistryEntry(frozenset({"public:read"}), TARGET_GLOBAL)

    assert new_entry.legacy_v1 is False


@pytest.mark.parametrize("prefix", PUBLIC_PREFIXES)
def test_each_protected_prefix_is_covered_independently(prefix):
    route_prefix = prefix.lstrip("/")
    protected = [
        (view_name, method)
        for route, view_name, methods in scope_registry._urlconf_routes(
            get_resolver().url_patterns
        )
        if route.startswith(route_prefix)
        for method in methods
    ]

    assert protected, f"No concrete routes found beneath {prefix}"
    assert not [key for key in protected if key not in SCOPE_REGISTRY]


@pytest.mark.parametrize(
    "path,legacy_name,versioned_name",
    [
        ("makerspaces/", "public-makerspaces", "v1:public-makerspaces"),
        ("alpha/inventory/", "public-inventory", "v1:public-inventory"),
        ("alpha/stats/", "public-makerspace-stats", "v1:public-makerspace-stats"),
        (
            "alpha/inventory/categories/",
            "public-inventory-categories",
            "v1:public-inventory-categories",
        ),
        (
            "alpha/inventory/1/",
            "public-inventory-detail",
            "v1:public-inventory-detail",
        ),
    ],
)
def test_duplicate_inventory_routes_use_distinct_namespaced_keys(
    path, legacy_name, versioned_name
):
    legacy_match = resolve(f"/api/public/{path}")
    versioned_match = resolve(f"/api/v1/public/{path}")

    assert legacy_match.view_name == legacy_name
    assert versioned_match.view_name == versioned_name
    assert legacy_match.view_name != versioned_match.view_name
    assert lookup(legacy_match.view_name, "GET") is not None
    assert lookup(versioned_match.view_name, "GET") is not None


def test_resolve_target_distinguishes_global_valid_and_unknown_slugs():
    makerspace = make_space("scope-registry-slug")
    global_request = _request(PUBLIC_DIRECTORY)
    global_entry = lookup(global_request.resolver_match.view_name, "GET")
    valid_request = _request(f"/api/v1/public/{makerspace.slug}/inventory/")
    slug_entry = lookup(valid_request.resolver_match.view_name, "GET")
    unknown_request = _request("/api/v1/public/not-a-real-space/inventory/")

    assert global_entry.target_mode == TARGET_GLOBAL
    assert resolve_target(global_request, global_entry) == (None, True)
    assert slug_entry.target_mode == TARGET_TENANT_SLUG
    assert resolve_target(valid_request, slug_entry) == (makerspace, True)
    assert resolve_target(unknown_request, slug_entry) == (None, False)


def test_resolve_target_handles_both_opaque_status_tokens(monkeypatch):
    monkeypatch.setattr(
        "apps.encryption.write_fence.assert_mapped_write_allowed", lambda _scope: None
    )
    makerspace = make_space("scope-registry-token")
    requester = make_user("scope-registry-token-user")
    hardware_request = HardwareRequest.objects.create(
        makerspace=makerspace,
        requester=requester,
        requester_username=requester.username,
    )
    printer_type = MachineType.objects.create(
        makerspace=makerspace,
        name="Registry printer",
        slug="3d_printer",
    )
    print_queue = ServiceQueue.objects.create(
        makerspace=makerspace,
        machine_type=printer_type,
        name="Registry queue",
    )
    print_request = MachineServiceRequest.objects.create(
        makerspace=makerspace,
        queue=print_queue,
        requester=requester,
        title="Registry target",
    )
    cases = [
        (
            f"/api/v1/public/requests/{hardware_request.public_token}/status",
            hardware_request.public_token,
        ),
        (
            "/api/v1/public/machine-service/3d-printer/requests/"
            f"{print_request.public_token}/status",
            print_request.public_token,
        ),
    ]

    for path, _token in cases:
        request = _request(path)
        entry = lookup(request.resolver_match.view_name, "GET")
        assert entry.target_mode == TARGET_TENANT_TOKEN
        assert resolve_target(request, entry) == (makerspace, True)

        unknown_path = path.replace(str(_token), str(uuid.uuid4()))
        assert resolve_target(_request(unknown_path), entry) == (None, False)


@override_settings(API_CLIENT_AUTH_REQUIRED=True, CORS_ALLOWED_ORIGINS=[ORIGIN])
def test_empty_scope_issue_is_rejected():
    with pytest.raises(ValidationError, match="At least one API-client scope"):
        ApiClient.issue(
            label="legacy cutover client",
            allowed_origins=[ORIGIN],
            client_type="server",
            scopes=[],
        )


@override_settings(API_CLIENT_AUTH_REQUIRED=True, CORS_ALLOWED_ORIGINS=[ORIGIN])
def test_registry_exception_fails_closed(monkeypatch):
    api_client, raw_secret = ApiClient.issue(
        label="broken registry observer",
        allowed_origins=[ORIGIN],
        client_type="server",
        scopes=[LEGACY_SCOPE],
    )

    def broken_lookup(*_args, **_kwargs):
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(scope_registry, "lookup", broken_lookup)

    response = APIClient().get(
        PUBLIC_DIRECTORY,
        **_signed_headers(api_client, raw_secret),
    )

    assert response.status_code == 401


def test_undetectable_methods_on_a_protected_route_count_as_drift(monkeypatch):
    """Methodless protected routes must fail rather than disappear from the guard."""
    real = scope_registry._urlconf_routes

    def with_a_methodless_protected_route(*args, **kwargs):
        yield from real(*args, **kwargs)
        yield "api/public/mystery/", "public-mystery-function-view", set()

    monkeypatch.setattr(
        scope_registry, "_urlconf_routes", with_a_methodless_protected_route
    )

    stale, missing = scope_registry.validate_registry()

    assert stale == []
    assert ("public-mystery-function-view", "") in missing


def test_a_dropped_method_leaves_a_stale_registry_entry(monkeypatch):
    """Dropping a method must invalidate that key even when the view name survives."""
    real = scope_registry._urlconf_routes

    def without_the_directory_post(*args, **kwargs):
        for route, view_name, methods in real(*args, **kwargs):
            if view_name == "v1:public-makerspaces":
                yield route, view_name, set()
                continue
            yield route, view_name, methods

    monkeypatch.setattr(scope_registry, "_urlconf_routes", without_the_directory_post)

    stale, _missing = scope_registry.validate_registry()

    assert ("v1:public-makerspaces", "GET") in stale
    assert ("v1:public-makerspaces", "HEAD") in stale


def test_a_route_leaving_the_protected_prefix_is_stale(monkeypatch):
    real = scope_registry._urlconf_routes

    def moved_out_of_the_public_prefix(*args, **kwargs):
        for route, view_name, methods in real(*args, **kwargs):
            if view_name == "v1:public-makerspaces":
                yield "api/v1/internal/makerspaces/", view_name, methods
                continue
            yield route, view_name, methods

    monkeypatch.setattr(scope_registry, "_urlconf_routes", moved_out_of_the_public_prefix)

    stale, _missing = scope_registry.validate_registry()

    assert ("v1:public-makerspaces", "GET") in stale


def test_event_detail_requires_explicit_public_scope():
    entry = lookup("public-event-detail", "GET")
    assert scope_registry.scope_allows(entry, ["public:read"])
    assert scope_registry.scope_allows(entry, ["public:*"])
    assert not scope_registry.scope_allows(entry, [LEGACY_SCOPE])
