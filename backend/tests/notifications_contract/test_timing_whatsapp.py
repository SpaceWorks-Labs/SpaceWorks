from datetime import timedelta

import pytest
from django.utils import timezone

from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.models_endpoints import WhatsAppTemplate
from apps.integrations.notification_delivery import ensure_deliveries, send
from apps.integrations.notification_digest import constituents, render_digest
from apps.integrations.notification_resolution import resolve, whatsapp_template
from apps.notifications.models_preferences import NotificationPreference

pytestmark = pytest.mark.django_db


def test_deferred_release_rechecks_campaign_authority(contract):
    c = contract
    NotificationPreference.objects.create(makerspace=c.space, user=c.user,
        category="hardware_requests", channels=["telegram"], email_fallback=False)
    row = c.envelope(timing_policy="deferred", available_at=timezone.now() + timedelta(hours=1))
    assert [target.channel for target in resolve(row)] == ["telegram"]
    c.state["valid"] = False  # campaign sender grant/resource/audience withdrawn
    NotificationEnvelope.objects.filter(pk=row.pk).update(available_at=timezone.now() - timedelta(seconds=1))
    from apps.integrations.notification_tasks import deliver_envelope
    deliver_envelope(row.pk)
    assert not c.fake.calls


def test_digest_rebuild_excludes_newly_ineligible_sources(contract):
    c = contract
    c.space.enabled_modules = sorted(set(c.space.enabled_modules) | {"notifications"})
    c.space.enabled_features = sorted(set(c.space.enabled_features) | {"notifications.digests"})
    c.space.save(update_fields=["enabled_modules", "enabled_features"])
    NotificationPreference.objects.create(makerspace=c.space, user=c.user,
        category="hardware_requests", channels=["email"])
    child = c.envelope()
    child.timing_policy = "digest"
    child.save(update_fields=["timing_policy"])
    summary = NotificationEnvelope.objects.create(makerspace=c.space, recipient=c.user,
        feature=child.feature, stream=child.stream, audience="requester", event="daily_digest",
        source_kind="notification.digest", dedup_key="test:digest", context={"envelope_ids": [child.pk]})
    assert constituents(summary) and "Your loan changed" in render_digest(summary)["text"]
    c.state["valid"] = False
    assert not constituents(summary) and render_digest(summary)["text"] == ""


def test_whatsapp_template_required_outside_inbound_window(contract, monkeypatch):
    c = contract
    c.config.channel, c.config.provider = "whatsapp", "meta"
    # Reconciled rule: a WhatsApp send needs a resolvable sender, so give the own
    # installation complete (fake) Meta credentials instead of an empty config.
    c.config.set_credentials({"app_id": "1001", "business_account_id": "2002", "phone_number_id": "3003",
        "access_token": "fake-meta-token", "app_secret": "fake-app-secret", "webhook_verify_token": "fake-verify"})
    c.config.save()
    c.endpoint.channel, c.endpoint.provider = "whatsapp", "meta"
    c.endpoint.save(update_fields=["channel", "provider"])
    from apps.integrations.notification_providers import PROVIDERS
    monkeypatch.setitem(PROVIDERS, ("whatsapp", "meta"), lambda _: c.fake)
    NotificationPreference.objects.create(makerspace=c.space, user=c.user,
        category="hardware_requests", channels=["whatsapp"], email_fallback=False)
    envelope = c.envelope()
    ensure_deliveries(envelope)
    row = envelope.deliveries.get()
    assert whatsapp_template(row) is None
    send(row.pk)
    row.refresh_from_db()
    assert row.state == "failed" and row.last_error == "template_required" and not c.fake.calls


def test_only_approved_template_or_live_inbound_window_allows_whatsapp(contract):
    c = contract
    c.config.channel, c.config.provider = "whatsapp", "twilio"
    c.config.save()
    template = WhatsAppTemplate.objects.create(configuration=c.config, event="accepted", audience="requester",
        template_name="approved_loan", variables=["tool"], approved=False)
    from types import SimpleNamespace
    row = SimpleNamespace(endpoint=c.endpoint, envelope=c.envelope())
    assert whatsapp_template(row) is None
    template.approved = True
    template.save()
    assert whatsapp_template(row).pk == template.pk
    c.endpoint.last_inbound_at = timezone.now()
    assert whatsapp_template(row) is None  # live window permits free text


def test_reconnected_endpoint_does_not_receive_old_intent(contract):
    c = contract
    NotificationPreference.objects.create(makerspace=c.space, user=c.user,
        category="hardware_requests", channels=["telegram"], email_fallback=False)
    envelope = c.envelope()
    c.endpoint.revoked_at = timezone.now()
    c.endpoint.save(update_fields=["revoked_at"])
    old_pk = c.endpoint.pk
    c.endpoint.pk = None
    c.endpoint.identity_digest = "b" * 64
    c.endpoint.revoked_at = None
    c.endpoint.save()
    assert c.endpoint.pk != old_pk
    assert not resolve(envelope)
