"""Decision 216 item 18: the new interconnection routes are classified, origin-scoped, and
their linked mutations are session-only (PAT, OAuth and signed API clients are refused)."""
import hashlib
import hmac
import time

import pytest
from cryptography.fernet import Fernet
from django.test import RequestFactory
from django.urls import resolve, reverse
from rest_framework.test import APIClient

from apps.accounts.checks import check_delegated_routes
from apps.accounts.delegated_routes import route_class
from apps.apiclients.models import ApiClient as IntegrationClient
from apps.apiclients.scope_registry import lookup, validate_registry
from apps.apiclients.scope_registry_coverage import unclassified_routes
from apps.makerspaces.origin_scope_routes import MODEL_LOOKUPS, request_route_targets
from tests.api_r2.test_person_credentials import _bearer
from tests.hardware_requests.test_phase2_person_credential_boundary import delegated_credential
from tests.return_helpers import make_member, make_space

# (url name, reverse kwargs, methods). `pk` routes resolve their space through MODEL_LOOKUPS.
NEW_ROUTES = (
    ("admin-shop-order-move-pickup-to-space", {"pk": 11}, ("POST",)),
    ("admin-loan-repairs", {"makerspace_id": 7, "request_id": 11}, ("GET", "POST")),
    ("admin-space-booking-quote", {"pk": 11}, ("POST",)),
    ("admin-space-booking-readiness", {"pk": 11}, ("GET",)),
    ("admin-space-booking-availability", {"pk": 11}, ("GET",)),
    ("admin-booking-readiness", {"pk": 11}, ("GET",)),
    ("admin-event-booking-link", {"makerspace_id": 7, "event_id": 11}, ("GET", "POST")),
    ("admin-event-booking-replacement", {"makerspace_id": 7, "event_id": 11}, ("POST",)),
    ("admin-related-facts-event", {"makerspace_id": 7, "event_id": 11}, ("GET",)),
    ("admin-related-facts-booking", {"makerspace_id": 7, "booking_id": 11}, ("GET",)),
    ("finance-event-linked", {"makerspace_id": 7, "event_id": 11}, ("GET",)),
    ("admin-request-event-context", {"makerspace_id": 7, "request_id": 11}, ("GET", "PUT", "DELETE")),
    ("admin-request-booking-context", {"makerspace_id": 7, "request_id": 11}, ("GET", "PUT", "DELETE")),
)
NAMES = {name for name, _kwargs, _methods in NEW_ROUTES}
# Linked writes refused in the view (403); the booking-link pair is JWT-only (401).
REFUSED_IN_VIEW = ("admin-loan-repairs", "admin-request-event-context", "admin-request-booking-context")
JWT_ONLY = ("admin-event-booking-link", "admin-event-booking-replacement")


@pytest.mark.parametrize("name,kwargs,methods", NEW_ROUTES)
def test_route_is_classified_and_origin_scoped(name, kwargs, methods):
    path = reverse(name, kwargs=kwargs)
    assert path.startswith("/api/v1/admin/") and resolve(path).url_name == name
    assert route_class(name) is not None
    if "pk" in kwargs:
        assert name in MODEL_LOOKUPS
        return
    for method in methods:
        request = RequestFactory().generic(method, path)
        request.resolver_match = resolve(path)
        assert request_route_targets(request) == (name, {7}, False, True)


def test_account_surface_and_api_client_coverage_checks_accept_the_new_routes():
    # Called by keyword, the way Django calls system checks.
    errors = [error.msg for error in check_delegated_routes(app_configs=None)]
    assert not [msg for msg in errors if any(f"({name})" in msg for name in NAMES)]
    assert not [item for item in unclassified_routes() if item[1] in NAMES]
    stale, missing = validate_registry()
    assert not [item for item in stale + missing if item[0] in NAMES]


@pytest.mark.parametrize("name,kwargs,methods", NEW_ROUTES)
def test_no_api_client_scope_authorizes_a_new_route(name, kwargs, methods):
    for method in methods:
        entry = lookup(name, method)
        assert entry is None or (not entry.scopes and not entry.legacy_v1), (name, method)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["pat", "oauth"])
def test_bearer_tokens_cannot_make_linked_writes_but_keep_ordinary_reads(settings, kind):
    from apps.maintenance.models import IssueReport
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/v1/public/"]
    maker = make_space(f"item18-bearer-{kind}")
    actor = make_member(f"item18-{kind}-manager", maker)
    api = _bearer(delegated_credential(kind, actor, maker))
    ids = {"makerspace_id": maker.pk}
    before = IssueReport.objects.count()
    for name in REFUSED_IN_VIEW:
        path = reverse(name, kwargs={**ids, "request_id": 999999})
        methods = ("POST",) if name == "admin-loan-repairs" else ("PUT", "DELETE")
        for method in methods:
            response = api.generic(method, path, b"{}", content_type="application/json")
            assert response.status_code == 403, (name, method, response.content)
            assert b"staff session" in response.content, (name, method, response.content)
        read = api.get(path)
        assert read.status_code != 401 and b"staff session" not in read.content, (name, read.content)
    for name in JWT_ONLY:
        path = reverse(name, kwargs={**ids, "event_id": 999999})
        assert api.post(path, {}, format="json").status_code == 401, name
    assert api.get(reverse("admin-event-booking-link", kwargs={**ids, "event_id": 999999})).status_code == 401
    assert IssueReport.objects.count() == before


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["pat", "oauth"])
def test_bearer_token_cannot_move_a_shop_pickup_but_keeps_the_desk_actions(settings, kind):
    from apps.shop.models import ShopOrder
    from tests.shop.test_move_event_pickup import _event_order
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/v1/public/"]
    space, actor, _buyer, _event, _variant, order, path = _event_order(f"item18-shop-{kind}")
    api = _bearer(delegated_credential(kind, actor, space))
    pickup = ShopOrder.objects.filter(pk=order.pk).values_list("pickup_at", "pickup_event_id").get()
    denied = api.post(path)
    assert denied.status_code == 403 and b"staff session" in denied.content, denied.content
    assert ShopOrder.objects.filter(pk=order.pk).values_list("pickup_at", "pickup_event_id").get() == pickup
    sibling = api.post(reverse("admin-shop-order-ready", kwargs={"pk": order.pk}))
    assert sibling.status_code != 401 and b"staff session" not in sibling.content, sibling.content
    assert b"own space only" not in sibling.content


MUTATIONS = (
    ("POST", "admin-shop-order-move-pickup-to-space", {"pk": 1}),
    ("POST", "admin-loan-repairs", {"makerspace_id": 1, "request_id": 1}),
    ("POST", "admin-event-booking-link", {"makerspace_id": 1, "event_id": 1}),
    ("POST", "admin-event-booking-replacement", {"makerspace_id": 1, "event_id": 1}),
    ("PUT", "admin-request-event-context", {"makerspace_id": 1, "request_id": 1}),
    ("DELETE", "admin-request-booking-context", {"makerspace_id": 1, "request_id": 1}),
)


@pytest.mark.django_db
@pytest.mark.parametrize("method,name,kwargs", MUTATIONS)
def test_signed_client_is_refused_even_under_widened_prefixes(settings, method, name, kwargs):
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/v1/public/", "/api/v1/admin/"]
    settings.API_CLIENT_AUTH_REQUIRED = True
    settings.APICLIENT_REQUIRE_NONCE = False
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    maker = make_space(f"item18-signed-{name}"[:50])
    client, secret = IntegrationClient.issue(label="legacy", scopes=["legacy:v1"], makerspace=maker,
                                             client_type="server", allowed_origins=["https://integration.example"])
    path = reverse(name, kwargs=kwargs)
    body, stamp = b"{}", str(int(time.time()))
    signature = hmac.new(secret.encode(), b"\n".join([method.encode(), path.encode(), stamp.encode(), body]),
                         hashlib.sha256).hexdigest()
    response = APIClient().generic(method, path, body, content_type="application/json",
                                   HTTP_X_CLIENT_ID=client.client_id, HTTP_X_TIMESTAMP=stamp,
                                   HTTP_X_SIGNATURE=signature, HTTP_ORIGIN="https://integration.example")
    assert response.status_code in (401, 403), response.content
