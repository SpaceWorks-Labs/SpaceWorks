import pytest
from django.db import DatabaseError, IntegrityError, transaction

from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.models_endpoints import ChannelConfiguration
from apps.integrations.notification_delivery import ensure_deliveries
from apps.notifications.models_preferences import NotificationPreference
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def test_intent_written_before_commit_enqueue_after_commit(contract, monkeypatch, django_capture_on_commit_callbacks):
    calls = []
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", calls.append)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        row = contract.envelope()
        assert NotificationEnvelope.objects.filter(pk=row.pk).exists()
        assert calls == []
    assert len(callbacks) == 1
    callbacks[0]()
    assert calls == [row.pk]


def test_rollback_removes_intent_and_enqueue(contract, monkeypatch, django_capture_on_commit_callbacks):
    calls = []
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", calls.append)
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError), transaction.atomic():
            contract.envelope()
            raise RuntimeError("domain rollback")
    assert not NotificationEnvelope.objects.exists() and not calls


def test_intents_and_null_endpoint_deliveries_are_deduplicated(contract):
    c = contract
    first, second = c.envelope(), c.envelope()
    assert first.pk == second.pk
    NotificationPreference.objects.create(makerspace=c.space, user=c.user, category="hardware_requests", channels=["email"])
    ensure_deliveries(first)
    ensure_deliveries(second)
    assert first.deliveries.count() == 1


def test_channel_per_tenant_is_unique(contract):
    with pytest.raises(IntegrityError), transaction.atomic():
        ChannelConfiguration.objects.create(makerspace=contract.space, channel="telegram", provider="telegram")


def test_invalid_whatsapp_provider_refused_by_database(contract):
    with pytest.raises(IntegrityError), transaction.atomic():
        ChannelConfiguration.objects.create(makerspace=contract.space, channel="whatsapp", provider="sms")


def test_credentials_are_always_ciphertext_and_readable(contract):
    c = contract
    c.config.set_credentials({"bot_token": "private-token"})
    c.config.save()
    c.config.refresh_from_db()
    assert "private-token" not in c.config.credentials
    assert c.config.get_credentials() == {"bot_token": "private-token"}


def test_endpoint_cross_tenant_fk_refused(contract):
    c = contract
    other = make_space("notification-other")
    with pytest.raises(DatabaseError), transaction.atomic():
        type(c.endpoint).objects.filter(pk=c.endpoint.pk).update(makerspace=other)


def test_never_deferred_is_inherited_not_caller_controlled(contract):
    row = contract.envelope(event="return_reminder", timing_policy="digest")
    assert row.mandatory and row.timing_policy == "immediate" and row.available_at is None


def test_sensitive_template_context_refused(contract):
    with pytest.raises(ValueError):
        contract.envelope(context={"contact_email": "private@example.com"})


def test_all_models_have_drop_and_pii_dispositions():
    from apps.data_export.classification import OMITTED_MODELS
    from apps.encryption.registry import fields_for_label
    from apps.tenant_migration.catalog_notifications_contract import FIELD_NAMES
    from apps.tenant_migration.tenant_dump_model_catalog import FIRST_PARTY_MODEL_RULES
    from apps.tenant_migration.tenant_dump_types import ModelDisposition
    for label in FIELD_NAMES:
        if label == "notifications.NotificationPreference":
            assert label not in OMITTED_MODELS
            assert FIRST_PARTY_MODEL_RULES[label].disposition is ModelDisposition.PROJECT
            continue
        assert label in OMITTED_MODELS
        assert FIRST_PARTY_MODEL_RULES[label].disposition is ModelDisposition.DROP
    assert {f.field_name for f in fields_for_label("integrations.NotificationEndpoint")} == {"destination", "provider_subject"}
    assert {f.field_name for f in fields_for_label("integrations.NotificationEnvelope")} == {"message_body"}
