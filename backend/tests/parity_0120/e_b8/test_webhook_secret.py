"""E-B8: generated, shown-once webhook signing secret; rotation with a grace window; audit; never readable."""
import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.integrations import webhooks
from apps.integrations.models import NotificationDestination
from apps.integrations.webhook_secrets import live_previous_secret
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db

TS = 1_700_000_000


def _manager(slug):
    space = make_space(slug)
    return space, authenticated_client(make_member(f"{slug}-sm", space))


def _create(client, space, label="ERP", **extra):
    body = {"channel": "webhook", "label": label, "webhook_url": "https://hooks.example.org/in", **extra}
    return client.post(f"/api/v1/admin/makerspace/{space.pk}/notification-destinations", body, format="json")


def _verifies(header, secret, body):
    expected = webhooks.sign_webhook_body(secret, body, TS).split(",", 1)[1]
    return expected in header.split(",")


def test_create_generates_a_secret_returned_once_and_never_again():
    space, client = _manager("eb8-create")
    created = _create(client, space)
    assert created.status_code == 201
    secret = created.json()["signing_secret"]
    assert secret.startswith("whsec_") and len(secret) > 40
    assert created["Cache-Control"] == "no-store"
    dest = NotificationDestination.objects.get(pk=created.json()["id"])
    assert dest.get_signing_secret() == secret
    assert secret not in dest.signing_secret  # stored as ciphertext
    listing = client.get(f"/api/v1/admin/makerspace/{space.pk}/notification-destinations")
    assert secret not in json.dumps(listing.json())
    assert listing.json()[0]["signing_secret_set"] is True
    assert "signing_secret" not in listing.json()[0]
    audit = AuditLog.objects.get(action="notification.destination_created")
    assert audit.meta["secret_generated"] is True and secret not in json.dumps(audit.meta)


def test_supplied_secret_is_stored_but_not_echoed():
    space, client = _manager("eb8-supplied")
    created = _create(client, space, signing_secret="correct-horse-battery-staple-32")
    assert created.status_code == 201
    assert "signing_secret" not in created.json()


def test_rotation_keeps_old_secret_during_grace_then_drops_it():
    space, client = _manager("eb8-rotate")
    created = _create(client, space).json()
    old = NotificationDestination.objects.get(pk=created["id"]).get_signing_secret()
    url = f"/api/v1/admin/makerspace/{space.pk}/notification-destinations/{created['id']}/rotate-secret"
    rotated = client.post(url, {"grace_hours": 2}, format="json")
    assert rotated.status_code == 200
    fresh = rotated.json()["signing_secret"]
    assert fresh != old and rotated.json()["previous_valid_until"]
    dest = NotificationDestination.objects.get(pk=created["id"])
    header = webhooks.signature_header_for(dest, b"{}", TS)
    assert _verifies(header, fresh, b"{}")
    assert _verifies(header, old, b"{}")  # still inside the grace window
    dest.previous_secret_valid_until = timezone.now() - timedelta(seconds=1)
    dest.save()
    assert live_previous_secret(dest) == ""
    expired = webhooks.signature_header_for(dest, b"{}", TS)
    assert _verifies(expired, fresh, b"{}")
    assert not _verifies(expired, old, b"{}")
    meta = AuditLog.objects.get(action="notification_destination.secret_rotated").meta
    assert meta["grace_hours"] == 2 and fresh not in json.dumps(meta)


def test_zero_grace_invalidates_the_old_signature_at_once():
    space, client = _manager("eb8-zero")
    created = _create(client, space).json()
    old = NotificationDestination.objects.get(pk=created["id"]).get_signing_secret()
    url = f"/api/v1/admin/makerspace/{space.pk}/notification-destinations/{created['id']}/rotate-secret"
    fresh = client.post(url, {"grace_hours": 0}, format="json").json()["signing_secret"]
    dest = NotificationDestination.objects.get(pk=created["id"])
    header = webhooks.signature_header_for(dest, b"{}", TS)
    assert _verifies(header, fresh, b"{}")
    assert not _verifies(header, old, b"{}")


def test_rotation_refused_for_other_channels_and_other_spaces():
    space, client = _manager("eb8-guard")
    slack = NotificationDestination(makerspace=space, channel="slack", label="Room")
    slack.set_webhook_url("https://hooks.slack.com/services/T/B/x")
    slack.save()
    url = f"/api/v1/admin/makerspace/{space.pk}/notification-destinations/{slack.pk}/rotate-secret"
    assert client.post(url, {}, format="json").status_code == 400
    other = make_space("eb8-guard-other")
    foreign = NotificationDestination(makerspace=other, channel="webhook", label="x")
    foreign.set_webhook_url("https://hooks.example.org/x")
    foreign.set_signing_secret("s" * 20)
    foreign.save()
    cross = f"/api/v1/admin/makerspace/{space.pk}/notification-destinations/{foreign.pk}/rotate-secret"
    assert client.post(cross, {}, format="json").status_code == 404
