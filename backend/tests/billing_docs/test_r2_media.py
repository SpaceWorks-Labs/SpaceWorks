"""Single-use provider fetches revalidate every piece of live payer authority."""
import hashlib
import json
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.integrations.models import NotificationPreference as Matrix
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint
from apps.integrations.notification_delivery import ensure_deliveries
from apps.integrations.notification_fake import FakeProvider
from apps.integrations.notification_providers import CallbackEvent, PROVIDERS
from apps.notifications.models import MemberNotificationPreference
from apps.notifications.models_preferences import NotificationPreference

pytestmark = pytest.mark.django_db


@pytest.fixture
def media(lane, document, document_mail, monkeypatch, settings):
    settings.PUBLIC_APP_BASE_URL = "https://api.example.test"
    config = ChannelConfiguration.objects.create(makerspace=lane.space, channel="whatsapp", provider="twilio",
        enabled=True, personal_enabled=True, integration_identity="r2-wa-business")
    config.set_credentials({"account_sid": "AC" + "1" * 32, "auth_token": "2" * 32,
        "whatsapp_sender": "+14155550100", "public_base_url": "https://api.example.test"})
    config.save(update_fields=["credentials"])
    owner = document.payment.member
    endpoint = NotificationEndpoint.objects.create(makerspace=lane.space, user=owner, configuration=config,
        channel="whatsapp", provider="twilio", destination="+14155550123", provider_subject="+14155550123",
        identity_digest="f" * 64, integration_identity=config.integration_identity,
        integration_generation=config.generation, verified_at=timezone.now(), consented_at=timezone.now(), consent_version="v1")
    monkeypatch.setitem(PROVIDERS, ("whatsapp", "twilio"), lambda _: FakeProvider(config))
    Matrix.objects.create(makerspace=lane.space, feature="payments", channel="whatsapp", enabled=True)
    NotificationPreference.objects.filter(makerspace=lane.space, user=owner, category="payments").update(
        channels=["whatsapp"], email_fallback=False)
    envelope = NotificationEnvelope.objects.get(source_kind="payments.document", source_id=str(document.pk))
    envelope.routing_snapshot = {"whatsapp": {"id": endpoint.pk, "generation": config.generation,
                                              "provider": "twilio", "identity": config.integration_identity}}
    envelope.save(update_fields=["routing_snapshot"])
    ensure_deliveries(envelope)
    delivery = envelope.deliveries.get(channel="whatsapp")
    return SimpleNamespace(space=lane.space, owner=owner, config=config, endpoint=endpoint, document=document,
                           delivery=delivery, envelope=envelope, rendered=document_mail.rendered)


def grant(media):
    from apps.integrations.notification_media import issue_grant
    from django.urls import resolve
    url = issue_grant(media.delivery)
    path = urlsplit(url).path
    return path, resolve(path).kwargs["token"]


def model():
    from django.apps import apps
    return apps.get_model("integrations", "NotificationMediaGrant")


def test_media_grant_stores_digest_and_is_single_use(media):
    path, token = grant(media)
    row = model().objects.get(delivery=media.delivery)
    assert row.token_digest == hashlib.sha256(token.encode()).hexdigest()
    assert timedelta(minutes=9) < row.expires_at - timezone.now() <= timedelta(minutes=10)
    assert token not in json.dumps(row.__dict__, default=str)
    client = APIClient()
    response = client.get(path)
    assert response.status_code == 200 and response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert response["Cache-Control"] == "private, no-store"
    assert client.get(path).status_code == 404
    row.refresh_from_db()
    assert row.consumed_at is not None and media.rendered == [media.document.pk]
    persisted = json.dumps(list(AuditLog.objects.values("meta")), default=str)
    persisted += json.dumps(list(NotificationEnvelope.objects.values("context", "message_body")))
    assert token not in persisted and "%PDF" not in persisted


def test_head_never_consumes_media_and_all_responses_are_private(media):
    path, _ = grant(media)
    client = APIClient()
    response = client.head(path)
    assert response.status_code == 405
    assert response["Cache-Control"] == "private, no-store"
    assert model().objects.get(delivery=media.delivery).consumed_at is None
    assert client.get(path).status_code == 200
    response = client.get(path)
    assert response.status_code == 404 and response["Cache-Control"] == "private, no-store"


def test_expired_grant_cannot_render(media):
    path, _ = grant(media)
    model().objects.filter(delivery=media.delivery).update(expires_at=timezone.now() - timedelta(seconds=1))
    assert APIClient().get(path).status_code == 404
    assert media.rendered == []


@pytest.mark.parametrize("change", ["revoked", "stop", "rotation", "identity", "restricted", "preference",
                                        "channel_disabled", "module_disabled", "document_gate", "source", "migrating"])
def test_fetch_rechecks_live_personal_authority(media, lane, change):
    path, _ = grant(media)
    if change == "revoked":
        media.endpoint.revoked_at = timezone.now()
        media.endpoint.save(update_fields=["revoked_at"])
    elif change == "stop":
        from apps.integrations.notification_destination_events import apply_destination_event
        apply_destination_event(media.config, CallbackEvent(identity_digest=media.endpoint.identity_digest, opt_out=True))
    elif change in {"rotation", "identity", "channel_disabled"}:
        field, value = {"rotation": ("generation", media.config.generation + 1),
                        "identity": ("integration_identity", "replacement-business"),
                        "channel_disabled": ("personal_enabled", False)}[change]
        setattr(media.config, field, value)
        media.config.save(update_fields=[field])
    elif change == "restricted":
        media.owner.access_status = "restricted"
        media.owner.save(update_fields=["access_status"])
    elif change == "preference":
        MemberNotificationPreference.objects.create(makerspace=media.space, user=media.owner,
            feature="payments", channel="whatsapp", enabled=False)
    elif change == "module_disabled":
        from tests.module_helpers import disable_module
        disable_module(media.space, "notifications")
    elif change == "document_gate":
        media.space.enabled_features = [key for key in media.space.enabled_features if key != "billing.documents"]
        media.space.save(update_fields=["enabled_features"])
    elif change == "source":
        media.envelope.revision = "withdrawn-source-revision"
        media.envelope.save(update_fields=["revision"])
    else:
        from tests.tenant_migration.source_gate_helpers import close_gate
        close_gate(media.space, lane.manager)
    assert APIClient().get(path).status_code == 404
    assert media.rendered == []


def test_render_failure_consumes_grant_without_leaking_error(media, monkeypatch):
    path, _ = grant(media)
    monkeypatch.setattr("apps.payments.document_pdf.render_document_pdf",
                        lambda row: (_ for _ in ()).throw(RuntimeError("secret-pdf-details")))
    response = APIClient().get(path)
    assert response.status_code == 404 and b"secret-pdf-details" not in response.content
    assert model().objects.get(delivery=media.delivery).consumed_at is not None
    assert APIClient().get(path).status_code == 404


def test_media_cannot_be_issued_for_non_twilio_or_group_delivery(media):
    from apps.payments.document_delivery import DocumentDeliveryError
    from apps.integrations.notification_media import issue_grant
    media.delivery.endpoint = None
    media.delivery.save(update_fields=["endpoint"])
    with pytest.raises(DocumentDeliveryError):
        issue_grant(media.delivery)


def test_cleanup_removes_spent_and_expired_grants_but_keeps_live(media):
    from apps.integrations.notification_media import cleanup_grants
    grant(media)
    expired = model().objects.latest("pk")
    model().objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    grant(media)
    consumed = model().objects.latest("pk")
    model().objects.filter(pk=consumed.pk).update(consumed_at=timezone.now())
    grant(media)
    live = model().objects.latest("pk")
    cleanup_grants()
    assert list(model().objects.values_list("pk", flat=True)) == [live.pk]


def test_cleanup_skips_frozen_tenant_then_recovers(media):
    from unittest.mock import patch
    from apps.integrations.notification_media import cleanup_grants
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
    grant(media)
    expired = model().objects.latest("pk")
    model().objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    with patch("apps.tenant_migration.gate_runtime.assert_write_allowed",
               side_effect=SourceMigrationGateClosed("Frozen", purpose="tenant_exit")):
        counts = cleanup_grants()
    assert counts == {"deleted": 0, "skipped": 1, "failed": 0}
    assert model().objects.filter(pk=expired.pk).exists()
    assert not AuditLog.objects.filter(makerspace=media.space, action="notification.media_grant_cleaned").exists()
    assert cleanup_grants() == {"deleted": 1, "skipped": 0, "failed": 0}
    assert not model().objects.filter(pk=expired.pk).exists()


def test_media_fetch_is_rate_limited_without_consuming_grant(media, monkeypatch):
    from apps.integrations.notification_media_views import MediaFetchThrottle
    monkeypatch.setattr(MediaFetchThrottle, "rate", "1/min")
    path, _ = grant(media)
    client = APIClient(REMOTE_ADDR="203.0.113.82")
    assert client.get(path.replace(path.split("/")[-1], "invalid.pdf")).status_code == 404
    response = client.get(path)
    assert response.status_code == 429 and response["Cache-Control"] == "private, no-store"
    assert model().objects.get(delivery=media.delivery).consumed_at is None


@pytest.mark.django_db(transaction=True)
def test_concurrent_fetches_consume_grant_exactly_once(media):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import close_old_connections
    from apps.integrations.notification_media import consume_grant
    _, token = grant(media)
    barrier = Barrier(2)

    def consume():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return consume_grant(token)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: consume(), range(2)))
    assert sum(result is not None for result in results) == 1
    assert media.rendered == [media.document.pk]
