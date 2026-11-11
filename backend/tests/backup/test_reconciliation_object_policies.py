"""Erasure journals and sender identities must never resurrect private objects."""

from types import SimpleNamespace

from apps.backup.archive_objects import NON_OBJECT_KEY_FIELDS, collect_model_objects
from apps.backup.object_ownership_registry import ReferencePolicy, validate_object_reference_registry


def test_sender_identifiers_are_not_storage_keys():
    expected = {
        ("integrations.MakerspaceMessagingSettings", "sms_sender_key"),
        ("integrations.MakerspaceMessagingSettings", "whatsapp_sender_key"),
        ("integrations.MessagingDelivery", "event_key"),
        *[(label, "sender_key") for label in (
            "integrations.MessagingDelivery", "integrations.MessagingRecipientAlias",
            "integrations.MessagingRecipientCorrelation", "integrations.MessagingSenderIdentity",
            "integrations.MessagingSuppression", "integrations.MessagingWebhookEvent",
        )],
    }
    assert expected <= NON_OBJECT_KEY_FIELDS


def test_account_erasure_object_is_coordination_only_in_compound_backup():
    rules = validate_object_reference_registry()
    rule = next(item for item in rules if item.model_label == "accounts.AccountPurgeObject")
    assert rule.policy == ReferencePolicy.COORDINATION_ONLY
    assert rule.coordination_path == "makerspace_id"


def test_legacy_backup_does_not_capture_account_erasure_journal_keys():
    model = SimpleNamespace(_meta=SimpleNamespace(label="accounts.AccountPurgeObject"))
    result = {"private": {}, "public_image": {}}
    collect_model_objects(None, model, result)
    assert result == {"private": {}, "public_image": {}}
