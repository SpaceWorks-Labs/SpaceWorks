"""Native-client contract fixes: schema shapes, browser-push refusal and slug-route selection.

1. `GET /member/shop/orders/` documents the page envelope it returns, not a bare array.
2. `POST /public/m/{slug}/shop/orders/` documents optional bearer auth (it attaches the buyer).
3. Browser Firebase routes refuse a native device grant (403).
4. A native `X-Makerspace-Id` on a slug-owned route is checked against the slug.
5. The staff presence roster resolves its tenant from the path for native staff headers.
"""
import pytest
from django.test import RequestFactory
from django.urls import resolve, reverse
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from apps.accounts.models import DeviceGrant, User
from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.makerspaces.origin_scope_routes import MODEL_LOOKUPS, request_route_targets
from tests.accounts.account_factories import make_membership
from tests.device_helpers import make_native_app_registration
from tests.return_helpers import make_member, make_space


@pytest.fixture(scope="module")
def document():
    return SchemaGenerator().get_schema(request=None, public=True)


def _operation(document, suffix, method):
    matches = [item[method] for path, item in document["paths"].items()
               if path.endswith(suffix) and method in item]
    assert len(matches) == 1, suffix
    return matches[0]


def _resolve_ref(document, schema):
    return document["components"]["schemas"][schema["$ref"].rsplit("/", 1)[-1]]


def test_member_shop_order_list_documents_the_page_envelope(document):
    operation = _operation(document, "/member/shop/orders/", "get")
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema.get("type") != "array"
    page = _resolve_ref(document, schema)
    assert set(page["properties"]) == {"count", "next", "previous", "results"}
    results = page["properties"]["results"]
    assert results["type"] == "array"
    assert results["items"]["$ref"].endswith("/ShopBuyerOrder")


def test_public_shop_order_create_documents_optional_bearer(document):
    operation = _operation(document, "/m/{makerspace_slug}/shop/orders/", "post")
    # The contract adds the client credentials every public route offers (ServerHMAC, BrowserClient, PublishableKey).
    assert {"jwtAuth": []} in operation["security"] and {} in operation["security"]


def _native_token(user):
    now = timezone.now()
    grant = DeviceGrant.objects.create(
        registration=make_native_app_registration(), user=user, platform="apple",
        app_id="org.spaceworks.app", signing_identity="TEAM.org.spaceworks.app",
        environment="development", attestation_subject_fingerprint="f" * 64,
        attested_at=now, last_used_at=now,
    )
    access, _refresh, _family = issue_device_token_pair(user, grant)
    return access


def _client(access, makerspace=None):
    client = APIClient()
    headers = {"HTTP_AUTHORIZATION": f"Bearer {access}"}
    if makerspace is not None:
        headers["HTTP_X_MAKERSPACE_ID"] = str(makerspace.pk)
    client.credentials(**headers)
    return client


def _member(username, space):
    return make_member(username, space, membership_role="member", role=User.Role.REQUESTER)


@pytest.mark.django_db
@pytest.mark.parametrize("with_header", [False, True])
def test_browser_firebase_refuses_native_device_grants(with_header):
    space = make_space("native-fcm-space")
    user = _member("native-fcm-member", space)
    client = _client(_native_token(user), space if with_header else None)
    owner_epoch = {"owner_epoch": "00000000-0000-0000-0000-000000000001"}
    assert client.get(reverse("notifications:browser-firebase-config", args=[space.pk])).status_code == 403
    assert client.post(reverse("notifications:browser-firebase-may-resume", args=[space.pk]), owner_epoch,
                       format="json").status_code == 403
    assert client.post(reverse("notifications:browser-firebase-global-may-resume"), owner_epoch,
                       format="json").status_code == 403


@pytest.mark.django_db
def test_browser_firebase_still_serves_browser_sessions():
    space = make_space("browser-fcm-space")
    user = _member("browser-fcm-member", space)
    client = APIClient()
    client.force_authenticate(user)
    response = client.post(reverse("notifications:browser-firebase-global-may-resume"),
                           {"owner_epoch": "00000000-0000-0000-0000-000000000001"}, format="json")
    assert response.status_code == 200
    assert response.data == {"may_resume": False}


SLUG_ROUTES = (
    ("get", "hardware_requests:equipment-kit-public-list"),
    ("post", "hardware_requests:request-submit"),
    ("post", "hardware_requests:contextual-request-self"),
    ("get", "public-shop"),
)


def _call(client, method, name, slug):
    url = reverse(name, kwargs={"makerspace_slug": slug})
    return client.get(url) if method == "get" else client.post(url, {}, format="json")


@pytest.mark.django_db
@pytest.mark.parametrize("method,name", SLUG_ROUTES)
def test_native_header_on_slug_route_is_checked_against_the_slug(method, name):
    home, other = make_space("native-slug-home"), make_space("native-slug-other")
    user = _member("native-slug-member", home)
    make_membership(user, other)
    access = _native_token(user)

    # A matching header changes nothing: the route answers exactly as it does without one
    # (whatever the module/body outcome), instead of the old blanket "could not be resolved".
    bare = _call(_client(access), method, name, home.slug)
    matched = _call(_client(access, home), method, name, home.slug)
    assert matched.status_code == bare.status_code, matched.data
    assert "could not be resolved" not in str(getattr(matched, "data", "") or "")

    mismatched = _call(_client(access, other), method, name, home.slug)
    assert mismatched.status_code == 403
    assert "does not match" in str(mismatched.data["detail"])

    unknown = _call(_client(access, home), method, name, "no-such-space")
    assert unknown.status_code == 403


@pytest.mark.django_db
def test_staff_presence_roster_resolves_from_the_path_not_a_model_lookup():
    assert "admin-presence-sessions-current" not in MODEL_LOOKUPS
    path = "/api/v1/admin/makerspace/7/presence-sessions/current"
    request = RequestFactory().get(path)
    request.resolver_match = resolve(path)
    assert request_route_targets(request) == ("admin-presence-sessions-current", {7}, False, True)
