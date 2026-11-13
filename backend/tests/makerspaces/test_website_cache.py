"""Website cache privacy survives unknown subjects and non-GET methods."""

import uuid

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.claim_route_types import AnonymousRead
from apps.accounts.claim_routes import policy_for
from apps.makerspaces.confirmation_privacy import _PUBLIC_NO_STORE_ROUTES as PUBLIC_WEBSITE_ROUTES


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(PUBLIC_WEBSITE_ROUTES))
def test_public_website_errors_and_options_are_no_store_with_anonymous_claim_policy(name):
    kwargs = {"makerspace_slug": "missing-website-space", "public_token": uuid.uuid4()}
    if name.endswith(("-speaker", "-section", "-session")):
        kwargs["slug"] = "missing-section"
    if name.endswith("-image"):
        kwargs["asset_id"] = 999999
    url = reverse(name, kwargs=kwargs)
    client = APIClient()
    for method, status in (("GET", 404), ("HEAD", 404), ("OPTIONS", 200), ("POST", 405)):
        response = client.generic(method, url)
        assert response.status_code == status
        assert response["Cache-Control"] == "no-store"
        if method != "POST":
            assert isinstance(policy_for(name, method), AnonymousRead)
