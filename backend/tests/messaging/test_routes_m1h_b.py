from unittest.mock import patch

import pytest
from django.urls import resolve, reverse
from django.utils import timezone

from apps.integrations.messaging.consent import grant_consent
from apps.integrations.models import NotificationPreference
from apps.integrations.models_contract import NotificationDelivery
from tests.messaging.canonical_helpers import platform_sms, sms_channel

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def sms_sender(space):
    platform_sms()
    NotificationPreference.objects.update_or_create(makerspace=space, feature="hardware_requests",
                                                    channel="sms", defaults={"enabled": True})
    return sms_channel(space)


def verify_phone(user):
    # A phone edit clears verification; OTP confirmation is a separate write.
    user.phone_e164 = "+14155552672"
    user.save(update_fields=["phone_e164"])
    user.phone_verified_at = timezone.now()
    user.save(update_fields=["phone_verified_at"])


def test_test_send_own_verified_consented_phone_and_audit(space, member, manager, client,
                                                          django_capture_on_commit_callbacks):
    from apps.audit.models import AuditLog
    verify_phone(manager)
    grant_consent(user=manager, makerspace_id=space.pk, channel="sms", action="opted_in")
    client.force_authenticate(manager)
    path = reverse("messaging-test", kwargs={"makerspace_id": space.pk})
    capture = django_capture_on_commit_callbacks(execute=True)
    with patch("apps.integrations.notification_outbox.enqueue") as queued, capture:
        response = client.post(path, {"channel": "sms"}, format="json")
    assert response.status_code == 202 and response.data["status"] == "retrying"
    row = NotificationDelivery.objects.get(pk=response.data["delivery_id"])
    # The diagnostic is addressed to the caller's own consented phone and nobody else.
    assert row.channel == "sms" and row.envelope.recipient_id == manager.pk
    assert row.envelope.source_kind == "notification.test" and row.quota_reserved_at is None
    queued.assert_called_once_with(row.envelope_id)
    assert AuditLog.objects.filter(actor=manager, action="messaging.test_enqueued").exists()
    assert client.post(path, {"channel": "sms", "to": member.phone_e164}, format="json").status_code == 400


def test_test_send_refuses_unverified_or_unconsented_and_is_throttled(space, member, manager, client):
    from django.core.cache import cache
    cache.clear()
    client.force_authenticate(manager)
    path = reverse("messaging-test", kwargs={"makerspace_id": space.pk})
    with patch("apps.integrations.notification_outbox.enqueue"):
        response = client.post(path, {"channel": "sms"}, format="json")
        # No verified phone: no addressed leg is ever created for the diagnostic.
        assert response.status_code == 202 and response.data["status"] == "skipped"
        assert response.data["delivery_id"] == 0
        verify_phone(manager)
        client.force_authenticate(manager)
        response = client.post(path, {"channel": "sms"}, format="json")
        # Verified but unconsented: still nothing to send.
        assert response.data["status"] == "skipped" and response.data["delivery_id"] == 0
        for _ in range(3):
            client.post(path, {"channel": "sms"}, format="json")
        assert client.post(path, {"channel": "sms"}, format="json").status_code == 429
    assert not NotificationDelivery.objects.exists()


def test_messaging_routes_explicitly_deny_api_clients():
    from apps.apiclients.scope_registry import lookup, scope_allows
    from apps.apiclients.scope_registry_messaging import DENIED_KEYS
    for name, method in DENIED_KEYS:
        entry = lookup(name, method)
        assert entry is not None
        assert not scope_allows(entry, ["legacy:v1", "public:*", "admin:*"])


def test_origin_targets_for_test_and_member_routes(space):
    from apps.makerspaces.origin_scope_routes import request_route_targets
    from rest_framework.test import APIRequestFactory
    factory = APIRequestFactory()
    path = reverse("messaging-test", kwargs={"makerspace_id": space.pk})
    request = factory.post(path)
    request.resolver_match = resolve(path)
    assert request_route_targets(request)[1] == {space.pk}


def test_schedulers_and_source_gate_declarations():
    from django.conf import settings
    from apps.operations.management.commands.run_scheduled_tasks import SCHEDULED_TASKS
    from apps.tenant_migration.gate_policy_tasks import TASK_INTERNAL_PARTICIPANTS, FANOUT_GATE_PARTICIPANTS
    task = "apps.integrations.tasks_messaging.sweep_messaging_task"
    assert settings.CELERY_BEAT_SCHEDULE["messaging-recovery"]["task"] == task
    assert ("messaging-recovery", task, 5) in SCHEDULED_TASKS
    assert task in TASK_INTERNAL_PARTICIPANTS
    # Recovery replays receipts only (the retired send loop's tenant fan-out is gone);
    # tenant_migration's fan-out guard checks that registry against the code itself.


def test_every_new_route_has_openapi():
    from drf_spectacular.generators import SchemaGenerator
    paths = SchemaGenerator().get_schema(public=True)["paths"]
    assert "post" in paths["/api/v1/admin/makerspace/{makerspace_id}/messaging-settings/test"]
    for owner in ("platform", "m/{makerspace_id}"):
        for kind in ("status", "inbound"):
            assert "post" in paths[f"/api/v1/integrations/messaging/twilio/{owner}/{kind}"]
        assert {"get", "post"} <= paths[f"/api/v1/integrations/messaging/whatsapp/{owner}"].keys()
