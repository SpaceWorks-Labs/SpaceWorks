"""SWITCH-MATRIX regressions: routes the whole-API crawl found answering 500."""

import pytest
from django.urls import reverse

from tests.modules.switch_matrix_helpers import live_space, root_client, MODULE_KEYS

pytestmark = pytest.mark.django_db


def test_oidc_sign_in_route_reaches_its_handler_with_the_slug_and_validates_the_body():
    # Was TypeError -> 500 for every OIDC sign-in: the route's `slug` kwarg reached `post(request)`.
    response = root_client().post(reverse("social-oidc", args=["acme"]), {}, format="json")
    assert (response.status_code, response.data["code"]) == (400, "invalid")


def test_certificate_signatory_detail_missing_event_is_typed_not_found():
    # DELETE resolves the event; collection handlers must never receive a detail slot.
    space = live_space("sx-signatory", MODULE_KEYS)
    client = root_client()
    url = reverse("events-programme-admin-certificate-signatory-detail", kwargs={"pk": 987654, "slot": 1})
    for method in ("get", "post", "patch", "put"):
        response = getattr(client, method)(url, {}, format="json")
        assert (response.status_code, response.data["code"]) == (405, "method_not_allowed")
        assert response["Allow"] == "DELETE"
    response = client.delete(url)
    assert (response.status_code, response.data["code"]) == (404, "not_found")
    assert space.pk
