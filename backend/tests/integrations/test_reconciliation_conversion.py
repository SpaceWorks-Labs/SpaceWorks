import importlib
from types import SimpleNamespace

import pytest
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.utils import timezone

from apps.integrations.models_cutover import NotificationLegacyMapping
from apps.integrations.models_messaging_delivery import MessagingDelivery
from apps.integrations.models_contract import NotificationDelivery
from apps.integrations.notification_cutover import establish_barrier, switch_to_canonical
from .reconciliation_helpers import account, space

pytestmark = pytest.mark.django_db
conversion = importlib.import_module("apps.integrations.migrations._notification_conversion_v1")


def expanded_registry():
    return MigrationLoader(connection).project_state([("integrations", "0041_notification_cutover_expansion")]).apps


def legacy_row(tenant, user, **kwargs):
    return MessagingDelivery.objects.create(makerspace=tenant, user=user, channel="sms", audience="member",
        feature="bookings", event="confirmed", event_key="legacy-row", sender_key="twilio:old:sender", **kwargs)


def test_conversion_refuses_without_recorded_drain_and_stable_snapshot(receipt_only_cutover):
    row = legacy_row(space(), account())
    with pytest.raises(RuntimeError, match="requires deployed compatibility ingress"):
        conversion.copy(expanded_registry(), SimpleNamespace(connection=connection))
    establish_barrier(drained=True)
    MessagingDelivery.objects.filter(pk=row.pk).update(event="cancelled")
    with pytest.raises(RuntimeError, match="snapshot changed"):
        conversion.copy(expanded_registry(), SimpleNamespace(connection=connection))
    assert not NotificationLegacyMapping.objects.exists()


@pytest.mark.parametrize("status,attempts,expected", [("pending", 0, "skipped"),
    ("pending", 1, "held"), ("sending", 1, "held"), ("sent", 1, "sent"), ("failed", 4, "failed")])
def test_every_legacy_disposition_is_inert_and_timestamped(receipt_only_cutover, status, attempts, expected):
    old = legacy_row(space(), account(), status=status, attempts=attempts, quota_reserved_at=timezone.now())
    establish_barrier(drained=True)
    registry = expanded_registry()
    conversion.copy(registry, SimpleNamespace(connection=connection))
    mapping = NotificationLegacyMapping.objects.get(legacy_model="MessagingDelivery", legacy_id=old.pk)
    row = NotificationDelivery.objects.get(pk=mapping.canonical_id)
    assert row.state == expected and row.historical and not row.retryable
    assert row.created_at == old.created_at and row.attempt_count == old.attempts
    assert row.quota_reserved_at == old.quota_reserved_at
    old.refresh_from_db()
    assert old.status not in {"pending", "sending"}
    conversion.copy(registry, SimpleNamespace(connection=connection))
    assert NotificationLegacyMapping.objects.filter(legacy_model="MessagingDelivery").count() == 1
    assert NotificationDelivery.objects.count() == 1


def test_conversion_resumes_after_mapping_commit_without_recopy_or_resend(receipt_only_cutover, monkeypatch):
    legacy_row(space(), account())
    establish_barrier(drained=True)
    original = conversion.templates
    monkeypatch.setattr(conversion, "templates", lambda *args: (_ for _ in ()).throw(RuntimeError("restart")))
    with pytest.raises(RuntimeError, match="restart"):
        conversion.copy(expanded_registry(), SimpleNamespace(connection=connection))
    assert NotificationLegacyMapping.objects.filter(legacy_model="MessagingDelivery").count() == 1
    monkeypatch.setattr(conversion, "templates", original)
    conversion.copy(expanded_registry(), SimpleNamespace(connection=connection))
    assert NotificationDelivery.objects.count() == 1
    switch_to_canonical()
    receipt_only_cutover.refresh_from_db()
    assert receipt_only_cutover.route == "canonical" and not receipt_only_cutover.sending_enabled


def test_expansion_follows_both_parent_histories_and_preserves_helpers():
    loader = MigrationLoader(connection)
    plan = loader.graph.forwards_plan(("integrations", "0042_notification_history_conversion"))
    assert ("integrations", "0035_messaging_tenant_tie") in plan
    assert ("integrations", "0039_bd_r2_notification_media") in plan
    # 0044 is the data-only receipt-time repair chained after the 0042 copy. The
    # destructive 0043 retirement stays deliberately absent until reconciliation.
    # 0045 keeps addressed SMS/WhatsApp generations when the optional inbox module is removed.
    # 0046 opens the gate only on a fresh install (no prior deployment data).
    # 0047/0048 (cloud email providers, events programme certificate media) follow on staging.
    assert loader.graph.leaf_nodes("integrations") == [("integrations", "0048_notification_media_certificate_subject")]
    assert ("integrations", "0042_notification_history_conversion") in loader.graph.forwards_plan(
        ("integrations", "0044_restore_receipt_received_at"))
    assert not any(app == "integrations" and name.startswith("0043") for app, name in loader.graph.nodes)
    registry = expanded_registry()
    choices = dict(registry.get_model("integrations", "NotificationPreference")._meta.get_field("channel").choices)
    assert {"sms", "whatsapp"} <= choices.keys()
    features = dict(registry.get_model("integrations", "NotificationPreference")._meta.get_field("feature").choices)
    assert "presence" in features


def test_original_snapshot_digest_detects_preserved_attempt_or_provider_drift(receipt_only_cutover):
    from apps.integrations.notification_conversion_snapshot import verify_original_mapping
    from apps.makerspaces.secrets import decrypt_value, encrypt_value
    import json

    old = legacy_row(space(), account(), status="sent", attempts=2, provider_message_id="SMoriginal")
    establish_barrier(drained=True)
    conversion.copy(expanded_registry(), SimpleNamespace(connection=connection))
    receipt_only_cutover.refresh_from_db()
    expected = receipt_only_cutover.snapshot["MessagingDelivery"]
    rows = NotificationLegacyMapping.objects.filter(legacy_model="MessagingDelivery")
    verify_original_mapping(rows, expected)
    mapping = rows.get(legacy_id=old.pk)
    saved = json.loads(decrypt_value(mapping.snapshot))
    saved["provider_message_id"] = "SMchanged"
    mapping.snapshot = encrypt_value(json.dumps(saved))
    mapping.save(update_fields=["snapshot"])
    with pytest.raises(ValueError, match="differ from the cutover barrier"):
        verify_original_mapping(rows, expected)


@pytest.mark.parametrize("partial", [False, True])
def test_settings_copy_preserves_empty_platform_choice_and_partial_own_refusal(receipt_only_cutover, partial):
    from apps.integrations.models_endpoints import ChannelConfiguration
    from apps.integrations.models_messaging_settings import MakerspaceMessagingSettings
    tenant = space()
    MakerspaceMessagingSettings.objects.create(makerspace=tenant, use_platform_sender=True,
        sms_account_sid="ACpartial" if partial else "")
    establish_barrier(drained=True)
    conversion.copy(expanded_registry(), SimpleNamespace(connection=connection))
    row = ChannelConfiguration.objects.get(makerspace=tenant, channel="sms")
    assert row.use_platform_sender and row.activation_hold
    assert not row.enabled and not row.personal_enabled
    assert bool(row.get_credentials()) is partial
    if partial:
        assert row.get_credentials()["account_sid"] == "ACpartial"


def test_conversion_refuses_push_schema_or_row_drift_after_barrier(receipt_only_cutover, monkeypatch):
    helper = importlib.import_module("apps.integrations.migrations._notification_push_snapshot_v1")
    legacy_row(space(), account())
    establish_barrier(drained=True)
    receipt_only_cutover.refresh_from_db()
    changed = {**receipt_only_cutover.snapshot["_push"], "sha256": "0" * 64}
    monkeypatch.setattr(helper, "snapshot", lambda connection: changed)
    with pytest.raises(RuntimeError, match="Push rows or their schema changed"):
        conversion.copy(expanded_registry(), SimpleNamespace(connection=connection))
    assert not NotificationLegacyMapping.objects.exists()
