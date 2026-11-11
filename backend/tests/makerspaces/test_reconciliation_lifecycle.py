"""C-owned migration, storage and optional-inbox reconciliation contracts."""

import importlib
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.apps import apps
from django.db import connection
from django.utils import timezone

from apps.accounts.models import User
from apps.evidence.models import EvidencePhoto
from apps.evidence.storage import staging_key
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_purge_collectors import notifications_delete
from apps.makerspaces.storage_key_collectors import collect_private_object_keys
from apps.notifications.models import MemberNotificationPreference, NotificationInboxRow
from apps.notifications.models_preferences import NotificationPreference

pytestmark = pytest.mark.django_db


def test_optional_inbox_purge_preserves_delivery_authority_and_explicit_opt_outs():
    space = Makerspace.objects.create(name="Inbox", slug="recon-inbox")
    other = Makerspace.objects.create(name="Other", slug="recon-other")
    user = User.objects.create_user(username="recon-recipient")
    config = ChannelConfiguration.objects.create(makerspace=space, channel="whatsapp", provider="meta")
    now = timezone.now()
    endpoint = NotificationEndpoint.objects.create(
        makerspace=space, user=user, channel="whatsapp", provider="meta",
        configuration=config, destination="private", provider_subject="private",
        identity_digest="a" * 64, integration_identity="installation", integration_generation=1,
        verified_at=now, consented_at=now, consent_version="v1",
    )
    preference = NotificationPreference.objects.create(
        makerspace=space, user=user, category="bookings", channels=[], email_fallback=False,
    )
    legacy = MemberNotificationPreference.objects.create(
        makerspace=space, user=user, feature="bookings", channel="native_push", enabled=False,
    )
    envelope = NotificationEnvelope.objects.create(
        makerspace=space, recipient=user, feature="bookings", stream="bookings", event="confirmed",
        audience="requester", source_kind="bookings.booking", source_id="1", dedup_key=uuid4().hex,
    )
    delivery = NotificationDelivery.objects.create(
        makerspace=space, envelope=envelope, endpoint=endpoint, channel="whatsapp",
        target_key="endpoint", provider="meta", state="delivered",
    )
    own = NotificationInboxRow.objects.create(
        makerspace=space, user=user, feature="bookings", event="confirmed", event_key=uuid4(), title="Own",
    )
    foreign = NotificationInboxRow.objects.create(
        makerspace=other, user=user, feature="bookings", event="confirmed", event_key=uuid4(), title="Other",
    )
    result = notifications_delete(space, None)
    assert not NotificationInboxRow.objects.filter(pk=own.pk).exists()
    assert NotificationInboxRow.objects.filter(pk=foreign.pk).exists()
    for row in (config, endpoint, preference, legacy, envelope, delivery):
        assert type(row).objects.filter(pk=row.pk).exists()
    assert "integrations.NotificationEnvelope" not in result.model_labels
    assert "integrations.ChannelConfiguration" not in result.model_labels
    assert "notifications.MemberNotificationPreference" not in result.model_labels


def test_whatsapp_upgrade_preserves_only_previously_enabled_canonical_installations():
    upgrade = importlib.import_module("apps.makerspaces.migrations.0097_reconcile_enabled_modules")
    # The real opt-in default; the autouse test fixture would otherwise enable EVERYTHING.
    from apps.makerspaces.module_registry_helpers import default_enabled_module_keys
    spaces = [Makerspace.objects.create(name=str(i), slug=f"recon-wa-{i}",
                                        enabled_modules=default_enabled_module_keys()) for i in range(3)]
    for row in spaces:
        assert "sms" not in row.enabled_modules and "whatsapp" not in row.enabled_modules
    ChannelConfiguration.objects.create(makerspace=spaces[0], channel="whatsapp", provider="meta", enabled=True)
    ChannelConfiguration.objects.create(makerspace=spaces[1], channel="whatsapp", provider="twilio", enabled=False)
    schema = SimpleNamespace(connection=connection)
    upgrade.preserve_enabled_whatsapp(apps, schema)
    upgrade.preserve_enabled_whatsapp(apps, schema)
    for index, row in enumerate(spaces):
        row.refresh_from_db()
        assert row.enabled_modules.count("whatsapp") == (1 if index == 0 else 0)
        assert "sms" not in row.enabled_modules
    # New spaces keep the opt-in default (the autouse fixture patches the field default).
    assert "whatsapp" not in default_enabled_module_keys() and "sms" not in default_enabled_module_keys()


def test_whole_tenant_storage_closure_includes_both_evidence_keys():
    space = Makerspace.objects.create(name="Evidence", slug="recon-evidence")
    other = Makerspace.objects.create(name="Other", slug="recon-evidence-other")
    user = User.objects.create_user(username="recon-uploader")
    photo = EvidencePhoto.objects.create(
        makerspace=space, uploaded_by=user, evidence_type="issue", object_key="evidence/recon.jpg",
    )
    foreign = EvidencePhoto.objects.create(
        makerspace=other, uploaded_by=user, evidence_type="issue", object_key="evidence/foreign.jpg",
    )
    assert {photo.object_key, staging_key(photo.object_key)} <= set(collect_private_object_keys(space))
    assert foreign.object_key not in collect_private_object_keys(space)
    assert staging_key(photo.object_key) not in collect_private_object_keys(space, include_coordination=False)


@pytest.mark.parametrize("channel", ["sms", "whatsapp"])
def test_addressed_purge_adapts_provider_counts_to_provenance_contract(monkeypatch, channel):
    from apps.integrations.messaging import purge
    from apps.makerspaces import module_purge_collectors_addressed as collectors

    space = Makerspace.objects.create(name="Addressed", slug=f"recon-{channel}")
    seen = []

    def delete(makerspace, selected):
        seen.append((makerspace.pk, selected))
        return {"messaging_consents": 2}

    monkeypatch.setattr(purge, "purge_channel", delete)
    result = getattr(collectors, f"{channel}_delete")(space, None)
    assert seen == [(space.pk, channel)]
    assert result["messaging_consents"] == 2
    assert "integrations.MessagingConsent" in result.model_labels
    assert "integrations.MessagingSuppression" not in result.model_labels
    assert "integrations.MessagingRecipientAlias" not in result.model_labels
