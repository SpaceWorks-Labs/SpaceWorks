"""Cross-lane seams on the canonical account/envelope/device graph."""
from datetime import timedelta
from unittest.mock import Mock
from uuid import NAMESPACE_URL, uuid5

import pytest
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.integrations.models_contract import NotificationDelivery
from apps.integrations.notification_delivery import claim, record_result
from apps.integrations.notification_providers import ProviderResult
from apps.integrations.notification_builtin import send_builtin
from apps.integrations.messaging.consent import grant_consent, live_consent, member_space
from tests.account_split.p1_helpers import staff
from .reconciliation_helpers import account, delivery, sms_config, space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("error,retryable", [("ambiguous_timeout", False), ("timeout", True)])
def test_unknown_push_outcome_is_held_without_email_fallback(monkeypatch, error, retryable):
    row = delivery(space(), account(), channel="native_push", attempt_count=1)
    row.provider = "builtin"
    row.save(update_fields=["provider"])
    fallback = Mock()
    monkeypatch.setattr("apps.integrations.notification_delivery.fallback_if_exhausted", fallback)
    result = record_result(row, ProviderResult(False, ambiguous=True, retryable=retryable, error_code=error))
    assert result.state == "held" and not result.retryable and result.next_attempt_at is None
    fallback.assert_not_called()


@pytest.mark.parametrize("error,retryable", [("provider_error", True), ("provider_error", False), ("skipped", False)])
def test_sweep_hold_survives_an_older_uncertain_result(error, retryable):
    row = delivery(space(), account(), channel="native_push", attempt_count=1)
    row.provider = "builtin"
    row.save(update_fields=["provider"])
    NotificationDelivery.objects.filter(pk=row.pk).update(state="held", retryable=False)
    assert record_result(row, ProviderResult(False, error_code=error, retryable=retryable)).state == "held"
    assert record_result(row, ProviderResult(True)).state == "sent"


def test_expired_native_parent_claim_is_held_instead_of_reclaimed():
    row = delivery(space(), account(), channel="native_push", attempt_count=1,
        claim_until=timezone.now() - timedelta(seconds=1))
    assert claim(row.pk) is None
    row.refresh_from_db()
    assert row.state == "held" and row.attempt_count == 1


def test_in_app_adapter_preserves_member_audience_scope_and_never_starts_push(monkeypatch):
    row = delivery(space(), account(), channel="in_app")
    row.envelope.scope = {"machine_id": 7}
    row.envelope.save(update_fields=["scope"])
    queued = Mock()
    monkeypatch.setattr("apps.notifications.tasks.deliver_member_push.delay", queued)
    result = send_builtin(row, {"subject": "Member notice", "text": "Personal body", "link": "/member"})
    from apps.notifications.models_inbox import NotificationInboxRow
    inbox = NotificationInboxRow.objects.get(event_key=uuid5(NAMESPACE_URL, row.envelope.dedup_key))
    assert result.accepted and inbox.audience == "member" and inbox.scope == {"machine_id": 7}
    queued.assert_not_called()


def test_staff_consent_is_own_phone_and_fixed_tenant_bound(monkeypatch):
    from types import SimpleNamespace
    tenant = space()
    # A phone edit clears its verification stamp (User.save); verified at creation.
    user, _ = staff(tenant, "cross-staff", "space_manager", access_status="active",
        phone_e164="+14155550123", phone_verified_at=timezone.now())
    config = sms_config(tenant)
    monkeypatch.setattr("apps.integrations.messaging.consent.resolve_sender",
        lambda *args: SimpleNamespace(sender_key=config.sender_key))
    grant_consent(user=user, makerspace_id=tenant.pk, channel="sms", action="opted_in")
    assert live_consent(tenant, user, "sms", configuration=config)
    user.phone_verified_at += timedelta(seconds=1)
    assert not live_consent(tenant, user, "sms", configuration=config)
    with pytest.raises(NotFound):
        member_space(user, space("foreign-staff-consent").pk)


def test_original_receipt_time_is_repaired_by_forward_migration():
    import importlib
    import json
    from django.apps import apps
    from django.db import connection
    from types import SimpleNamespace
    from apps.integrations.models_cutover import NotificationIngress, NotificationLegacyMapping
    from apps.makerspaces.secrets import encrypt_value
    old = timezone.now() - timedelta(days=3)
    receipt = NotificationIngress.objects.create(channel="sms", provider="twilio", transport="legacy",
        sender_key="physical", dedupe_key="repair-time", payload=encrypt_value("{}"))
    NotificationLegacyMapping.objects.create(legacy_model="MessagingWebhookEvent", legacy_id=123456,
        canonical_model="NotificationIngress", canonical_id=receipt.pk,
        snapshot=encrypt_value(json.dumps({"received_at": old.isoformat()})))
    migration = importlib.import_module("apps.integrations.migrations.0044_restore_receipt_received_at")
    migration.restore_received_at(apps, SimpleNamespace(connection=connection))
    receipt.refresh_from_db()
    assert receipt.received_at == old



def test_explicit_selection_enable_lifts_only_own_legacy_veto(monkeypatch):
    from django.urls import reverse
    from rest_framework.test import APIClient
    from apps.makerspaces.models import MakerspaceMembership
    from apps.notifications.models_inbox import MemberNotificationPreference
    from apps.notifications.models_preferences import NotificationPreference
    tenant, user, other = space(), account(), account("other-pref")
    MakerspaceMembership.objects.create(makerspace=tenant, user=user, role="custom",
        assigned_role=tenant.roles.get(slug="member"), status="active")
    for owner in (user, other):
        MemberNotificationPreference.objects.create(makerspace=tenant, user=owner,
            feature="bookings", channel="native_push", enabled=False)
    monkeypatch.setattr("apps.integrations.notification_availability.available_channels",
        lambda *args: ["native_push", "email"])
    api = APIClient()
    api.force_authenticate(user)
    response = api.put(reverse("contract-preferences", kwargs={"makerspace_id": tenant.pk}),
        {"preferences": [{"category": "bookings", "channels": ["native_push"], "email_fallback": False}]}, format="json")
    assert response.status_code == 200
    assert MemberNotificationPreference.objects.get(user=user).enabled
    assert not MemberNotificationPreference.objects.get(user=other).enabled
    assert NotificationPreference.objects.get(user=user).channels == ["native_push"]
