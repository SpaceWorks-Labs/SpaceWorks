"""Mobile-API sweep for 0.12.0: the routes a phone app uses must be reachable by a native token.

A native staff grant must send `X-Makerspace-Id`, and the server refuses the call ("Makerspace target could
not be resolved") unless the route is *recognized*, i.e. its tenant comes from the path, a model lookup, a
body or a token. A native member grant never carries staff authority and reaches only the member surface
(`/member/`, `/public/`, `/auth/`, `/memberships/`, push, personal inbox) or MEMBER_ONLY routes.
"""
import pytest
from django.test import RequestFactory
from django.urls import resolve

from apps.accounts.authentication import _member_surface_path_allowed
from apps.accounts.delegated_routes import DELEGABLE, MEMBERSHIP_ONLY, route_class
from apps.makerspaces.origin_scope_routes import request_route_targets

pytestmark = pytest.mark.django_db

CARD_TOKEN = "a" * 43

# (url name, concrete path): staff phone routes that name their tenant by an object id or a token.
LOOKUP_STAFF_ROUTES = (
    ("admin-machine-service-printer-pool-detail", "/api/v1/admin/machine-service/consumable-pools/7"),
    ("admin-machine-service-printer-pool-adjustments", "/api/v1/admin/machine-service/consumable-pools/7/adjustments"),
    ("asset-qr", "/api/v1/admin/assets/7/qr"),
    ("admin-inventory-asset-fix-status", "/api/v1/admin/assets/7/fix-status"),
    ("admin-inventory-asset-qr-history", "/api/v1/admin/assets/7/qr-history"),
    ("admin-inventory-qr-history", "/api/v1/admin/inventory/7/qr-history"),
    ("admin-inventory-assets", "/api/v1/admin/inventory/7/assets"),
    ("admin-card-verification-staff", f"/api/v1/admin/card-verifications/{CARD_TOKEN}/staff"),
    ("admin-machine-access-revoke", "/api/v1/admin/machine-access/3/revoke"),
    ("admin-machine-open-access", "/api/v1/admin/machines/3/open-access"),
    ("admin-shelf-check-detail", "/api/v1/admin/shelf-checks/11111111-1111-4111-8111-111111111111"),
    ("qr-external-assign", "/api/v1/admin/qr/external"),
    # Decision 353: the membership console, report schedules and warranties by object id.
    ("admin-membership-extend", "/api/v1/admin/memberships/7/extend"),
    ("admin-membership-record", "/api/v1/admin/memberships/7/record"),
    ("admin-membership-terms", "/api/v1/admin/memberships/7/terms"),
    ("admin-membership-term-cancel", "/api/v1/admin/membership-terms/7/cancel"),
    ("admin-membership-plan-detail", "/api/v1/admin/membership-plans/7"),
    ("admin-membership-plan-archive", "/api/v1/admin/membership-plans/7/archive"),
    ("admin-membership-title-detail", "/api/v1/admin/membership-titles/7"),
    ("admin-membership-invite-link-revoke", "/api/v1/admin/membership-invite-links/7/revoke"),
    ("admin-invitation-request-invite", "/api/v1/admin/invitation-requests/7/invite"),
    ("report-schedule-detail", "/api/v1/admin/report-schedules/7"),
    ("report-schedule-run-now", "/api/v1/admin/report-schedules/7/run-now"),
    ("admin-asset-warranty", "/api/v1/admin/assets/7/warranty"),
    ("asset-generate", "/api/v1/admin/products/7/assets/generate"),
)
# Staff phone routes whose path carries `makerspace_id`.
PATH_STAFF_ROUTES = (
    ("admin-shelf-show", "/api/v1/admin/makerspace/7/shelf-pointer/show"),
    ("admin-shelf-clear", "/api/v1/admin/makerspace/7/shelf-pointer/clear"),
    ("admin-shelf-locations", "/api/v1/admin/makerspace/7/shelf-pointer/locations"),
    ("admin-shelf-checks", "/api/v1/admin/makerspace/7/shelf-checks"),
    ("admin-machine-access", "/api/v1/admin/makerspaces/7/machine-access"),
    ("admin-machine-access-candidates", "/api/v1/admin/makerspaces/7/machine-access/candidates"),
    ("admin-machine-job-consumables", "/api/v1/admin/makerspaces/7/machine-jobs/3/consumables"),
    ("admin-machine-use-event-options", "/api/v1/admin/makerspace/7/machine-use/events"),
    ("admin-presence-related", "/api/v1/admin/makerspace/7/presence-sessions/3/related"),
    ("admin-guest-pass-scan", "/api/v1/admin/makerspaces/7/guest-passes/scan"),
    ("admin-makerspace-limits", "/api/v1/admin/makerspace/7/limits"),
)
MEMBER_PATHS = (
    "/api/v1/member/profile",
    "/api/v1/member/profile/handle",
    "/api/v1/member/profile/image",
    "/api/v1/member/profile/achievements",
    "/api/v1/member/profile/project-import",
    "/api/v1/member/makerspaces/7/machine-access",
    "/api/v1/member/makerspaces/7/machine-use/events/",
    "/api/v1/member/makerspaces/7/my-usage",
    "/api/v1/member/makerspaces/7/allowances",
    "/api/v1/member/machine-jobs/3/consumables",
    "/api/v1/member/machines/3/sessions/start",
    "/api/v1/member/cards/member/3/photo",
    "/api/v1/member/cards/member/3/photo/cutout",
    "/api/v1/member/cards/member/3/wallet/apple",
    "/api/v1/member/adapter-watch/requests/3",
    "/api/v1/public/demo/machine-jobs",
    "/api/v1/public/makerspaces/demo/machines/now/",
    "/api/v1/public/makerspaces/demo/presence/here-now/",
    "/api/v1/public/profiles/some-handle/",
    "/api/v1/notifications/inbox/7",
    "/api/v1/notifications/inbox/7/families",
    "/api/v1/integrations/push/devices",
    # Payments on mobile (decision 354): own charges, native payment sheet, documents, claims, refunds.
    "/api/v1/member/makerspaces/7/payments",
    "/api/v1/member/makerspaces/7/payments/3/mobile-intent",
    "/api/v1/member/makerspaces/7/payments/3/paid-claim",
    "/api/v1/member/makerspaces/7/payments/3/refund-request",
    "/api/v1/member/makerspaces/7/payment-documents",
    "/api/v1/member/makerspaces/7/payment-documents/3/download-url",
    "/api/v1/member/archived-payments",
    # Sign-in on mobile (decision 355): device login, refresh, grants, MFA, sessions.
    "/api/v1/auth/device/login",
    "/api/v1/auth/device/refresh",
    "/api/v1/auth/device/grants",
    "/api/v1/auth/mfa/verify",
    "/api/v1/auth/devices",
)


@pytest.mark.parametrize("name,path", LOOKUP_STAFF_ROUTES + PATH_STAFF_ROUTES)
def test_staff_phone_route_is_staff_classed_and_recognized_for_the_native_header(name, path):
    match = resolve(path)
    assert match.url_name == name
    assert route_class(name) in {DELEGABLE, MEMBERSHIP_ONLY}
    request = RequestFactory().get(path)
    request.resolver_match = match
    _name, _targets, _invalid, recognized = request_route_targets(request)
    assert recognized is True, f"{name} would be refused for a native staff grant (target not resolvable)"


def test_path_routes_resolve_the_selected_makerspace_from_the_path():
    for name, path in PATH_STAFF_ROUTES:
        request = RequestFactory().get(path)
        request.resolver_match = resolve(path)
        assert request_route_targets(request)[:3] == (name, {7}, False), name


def test_card_check_link_with_an_unknown_token_adds_no_target_and_is_not_invalid():
    path = f"/api/v1/admin/card-verifications/{CARD_TOKEN}/staff"
    request = RequestFactory().get(path)
    request.resolver_match = resolve(path)
    assert request_route_targets(request) == ("admin-card-verification-staff", set(), False, True)


def test_inventory_asset_list_reads_its_product_pk_for_the_target_lookup():
    path = "/api/v1/admin/inventory/987654/assets"
    request = RequestFactory().get(path)
    request.resolver_match = resolve(path)
    name, targets, invalid, recognized = request_route_targets(request)
    # No such product: the lookup ran (invalid), it did not skip the route for lack of a `pk` kwarg.
    assert (name, targets, invalid, recognized) == ("admin-inventory-assets", set(), True, True)


@pytest.mark.parametrize("path", MEMBER_PATHS)
def test_member_phone_route_is_on_the_member_surface(path):
    assert _member_surface_path_allowed(path)


def test_mobile_payment_intent_serializers_expose_publishable_identifiers_only():
    """The native payment sheet gets the client secret / order id and the PUBLISHABLE key id, never a secret key."""
    from apps.payments.serializers_mobile import (
        RazorpayMobilePaymentIntentResponseSerializer, StripeMobilePaymentIntentResponseSerializer,
    )
    forbidden = {"secret_key", "key_secret", "api_key", "webhook_secret", "signing_secret", "secret"}
    for serializer in (StripeMobilePaymentIntentResponseSerializer, RazorpayMobilePaymentIntentResponseSerializer):
        assert not forbidden & set(serializer().fields)
    assert {"client_secret", "publishable_key", "ephemeral_key", "customer_id"} <= set(
        StripeMobilePaymentIntentResponseSerializer().fields)
    assert {"key_id", "order_id", "amount_minor", "currency"} <= set(RazorpayMobilePaymentIntentResponseSerializer().fields)


def test_mobile_payment_intent_route_is_native_only_and_named():
    match = resolve("/api/v1/member/makerspaces/7/payments/3/mobile-intent")
    assert match.url_name == "member-payment-mobile-intent"
    from apps.accounts.views_device import IsDeviceAccessToken
    assert IsDeviceAccessToken in match.func.view_class.permission_classes
