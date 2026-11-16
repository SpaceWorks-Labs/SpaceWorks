"""Live-gated website data cannot be revived from a cached success or error."""

import uuid

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

ROUTES = [
    ("public-event-website", {}),
    ("public-event-website-schedule", {}),
    ("public-event-website-speaker", {"slug": "speaker"}),
    ("public-event-website-section", {"slug": "section"}),
    ("public-event-website-session", {"slug": "session"}),
    ("public-event-website-image", {"asset_id": 1}),
    ("public-booking-resource", {}),
    ("public-booking-website", {}),
    ("public-booking-website-image", {"asset_id": 1}),
]


@pytest.mark.parametrize("name,extra", ROUTES)
@pytest.mark.parametrize("method,status", [("get", 404), ("head", 404), ("options", 200)])
def test_public_website_errors_and_metadata_are_not_cached(name, extra, method, status):
    url = reverse(name, kwargs={
        "makerspace_slug": "absent-website-space", "public_token": uuid.uuid4(), **extra,
    })
    response = getattr(APIClient(), method)(url)
    assert response.status_code == status
    assert response["Cache-Control"] == "no-store"
