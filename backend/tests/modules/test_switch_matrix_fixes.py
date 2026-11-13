"""SWITCH-MATRIX regressions: routes the whole-API crawl found answering 500."""

import pytest
from django.urls import reverse

from tests.modules.switch_matrix_helpers import live_space, root_client, MODULE_KEYS

pytestmark = pytest.mark.django_db


def test_oidc_sign_in_route_reaches_its_handler_with_the_slug_and_validates_the_body():
    # Was TypeError -> 500 for every OIDC sign-in: the route's `slug` kwarg reached `post(request)`.
    response = root_client().post(reverse("social-oidc", args=["acme"]), {}, format="json")
    assert response.status_code == 400, response.status_code


def test_certificate_signatory_detail_route_only_offers_delete():
    # Was TypeError -> 500 on GET/POST: the list view's handlers take no `slot`.
    space = live_space("sx-signatory", MODULE_KEYS)
    client = root_client()
    url = reverse("events-programme-admin-certificate-signatory-detail", kwargs={"pk": 987654, "slot": 1})
    assert client.get(url).status_code == 405
    assert client.post(url, {}, format="json").status_code == 405
    assert client.delete(url).status_code == 404
    assert space.pk
