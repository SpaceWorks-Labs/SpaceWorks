"""Real HMAC requests and tenant-local fixtures for BK-H integration tests."""
import hashlib
import hmac
import time
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.apiclients.models import ApiClient
from apps.bookings.models import BookableSpace, Booking
from tests.return_helpers import make_space

PREFIX = "/api/v1/booking-integration/"
SCOPES = ["booking_resources:read", "bookings:read", "bookings:attendance:read"]


def principal(tenant, scopes=None, **kwargs):
    # Direct rows allow invalid legacy/browser/global combinations to exercise
    # runtime rejection independently of issuance validation.
    row = ApiClient(label="BK-H", makerspace=tenant, scopes=scopes or SCOPES, **kwargs)
    row.set_secret("bkh-test-secret")
    row.save()
    return row


def signed(row, path, *, method="GET", signature=None, **headers):
    timestamp = str(int(time.time()))
    nonce = uuid4().hex
    payload = "\n".join([method, path, timestamp, nonce, ""])
    digest = hmac.new(b"bkh-test-secret", payload.encode(), hashlib.sha256).hexdigest()
    return getattr(APIClient(), method.lower())(path, HTTP_X_CLIENT_ID=row.client_id,
        HTTP_X_TIMESTAMP=timestamp, HTTP_X_NONCE=nonce, HTTP_X_SIGNATURE=signature or digest, **headers)


@pytest.fixture
def read_world(settings):
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.HMAC_PROTECTED_PATH_PREFIXES = []
    settings.APICLIENT_REQUIRE_NONCE = True
    tenant = make_space("bkh-tenant")
    tenant.enabled_features = [*tenant.enabled_features, "bookings.api_read"]
    tenant.save(update_fields=["enabled_features"])
    foreign = make_space("bkh-foreign")
    resource = BookableSpace.objects.create(makerspace=tenant, name="Private bench", is_public=False)
    other = BookableSpace.objects.create(makerspace=foreign, name="Foreign bench")
    start = timezone.now() + timedelta(days=1)
    booking = Booking.objects.create(space=resource, name="Ada Δ", email="private@example.test",
        phone="private-phone", note="private-note", custom_answers={"private": "private-answer"},
        starts_at=start, ends_at=start + timedelta(hours=1))
    foreign_booking = Booking.objects.create(space=other, name="Foreign", email="foreign@example.test",
        phone="foreign-phone", starts_at=start, ends_at=start + timedelta(hours=1))
    return SimpleNamespace(tenant=tenant, foreign=foreign, resource=resource, other=other,
        booking=booking, foreign_booking=foreign_booking, client=principal(tenant))
