"""Real mentor authority and canonical Meta delivery, with only HTTP stubbed."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from apps.events.contributions.runtime_notices import deliver_help
from apps.events.mentoring.models_queue import EventHelpRequest, EventHelpType
from apps.events.mentoring.models_rounds import MentorNotificationIntent
from apps.events.mentoring.notifications import recipients
from apps.integrations.messaging.resolver import resolve_sender
from apps.integrations.messaging.ties import has_tenant_tie
from apps.integrations.notification_cutover import sending_allowed
from apps.integrations.notification_resolution import endpoint_current
from apps.makerspaces.platform import module_enabled
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint, WhatsAppTemplate
from apps.integrations.models_messaging_consent import MessagingConsent
from apps.integrations.models_notifications import NotificationPreference as TenantPreference
from apps.integrations.notification_delivery import ensure_deliveries, send
from apps.integrations.notification_resolution import resolve
from apps.integrations.notification_sources import source_eligible
from apps.notifications.models_preferences import NotificationPreference
from tests.accounts.account_factories import make_membership
from tests.events.programme.mentoring.helpers import setup_help

pytestmark = pytest.mark.django_db
EVENT = "mentor_help_update"
MARKER = "mentor_whatsapp_policy"


@pytest.fixture
def mentor_notice(settings, monkeypatch, request):
    provider = getattr(request, "param", "meta")
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    space, event, users, mentors, roles, _, _ = setup_help(settings)
    space.enabled_modules = sorted(set(space.enabled_modules) | {"notifications", "membership", "whatsapp"})
    space.save(update_fields=["enabled_modules"])
    now = timezone.now()
    make_membership(mentors[0], space)
    request = EventHelpRequest.objects.create(
        event=event, makerspace=space, type=EventHelpType.objects.get(event=event),
        raised_by=users[0], origin="attendee", summary="PRIVATE-WIRING", exclusive_until=now,
    )
    intent = MentorNotificationIntent.objects.create(
        event=event, makerspace=space, request=request, kind="created", generation=1, available_at=now,
    )
    config = ChannelConfiguration.objects.create(makerspace=space, channel="whatsapp", provider=provider,
        enabled=True, personal_enabled=True, integration_identity="mentor-meta")
    if provider == "twilio":
        from tests.p2_wa_twilio.conftest import ACCOUNT, PUBLIC, SENDER, TOKEN
        config.set_credentials({"account_sid": ACCOUNT, "auth_token": TOKEN,
                                "whatsapp_sender": SENDER, "public_base_url": PUBLIC})
    else:
        config.set_credentials({"app_id": "100", "app_secret": "fake", "business_account_id": "200",
            "phone_number_id": "300", "access_token": "fake-token", "webhook_verify_token": "fake-verify"})
    config.save(update_fields=["credentials"])
    TenantPreference.objects.create(makerspace=space, feature="events", channel="whatsapp", enabled=True)
    endpoints = []
    for user, number in zip(mentors, ("+15551234567", "+15551234568"), strict=True):
        endpoint = NotificationEndpoint.objects.create(
            makerspace=space, user=user, configuration=config, channel="whatsapp", provider=provider,
            destination=number, provider_subject=number, identity_digest=uuid4().hex * 2,
            integration_identity=config.integration_identity, integration_generation=config.generation,
            verified_at=now, consented_at=now, consent_version="v1",
        )
        endpoints.append(endpoint)
        NotificationPreference.objects.create(makerspace=space, user=user, category="events",
            channels=["whatsapp"], email_fallback=False)
        MessagingConsent.objects.create(makerspace=space, user=user, channel="whatsapp",
            action="opted_in", source="member_settings", endpoint=endpoint)
    template = WhatsAppTemplate.objects.create(configuration=config, event=EVENT, audience="member",
        template_name="mentor_notice", variables=["makerspace.name"], approved=True)
    posts = []
    transport = {"reject_first": False}

    def http(method, url, **kwargs):
        if method == "GET":
            assert url.endswith("/200/message_templates")
            body = {"data": [{"name": "mentor_notice", "language": "en", "status": "APPROVED",
                "components": [{"type": "BODY", "text": "Help is available at {{1}}"}]}]}
        else:
            assert method == "POST" and url.endswith("/300/messages")
            posts.append(kwargs["json"])
            if transport["reject_first"] and len(posts) == 1:
                return SimpleNamespace(status_code=429, headers={"Retry-After": "1"},
                                       json=lambda: {"error": {"code": 130429}})
            body = {"messages": [{"id": "wamid.mentor"}]}
        return SimpleNamespace(status_code=200, headers={}, json=lambda: body)

    if provider == "meta":
        monkeypatch.setattr("requests.request", http)
    assert sending_allowed() and module_enabled(space, "whatsapp")
    sender = resolve_sender(space, "whatsapp")
    assert sender and sender.provider == provider and sender.sender_key
    assert all(endpoint_current(endpoint) for endpoint in endpoints)
    assert has_tenant_tie(mentors[0], space) and not has_tenant_tie(mentors[1], space)
    assert set(recipients(request, event)) == {user.pk for user in mentors}
    return SimpleNamespace(space=space, intent=intent, mentors=mentors, endpoints=endpoints,
                           roles=roles, template=template, posts=posts, transport=transport)


def _envelopes(world, key="mentor-test"):
    deliver_help(intent_id=world.intent.pk, recipient_ids=[user.pk for user in world.mentors],
                 payload={"team_alias": "PRIVATE-ALIAS"}, idempotency_key=key)
    return [NotificationEnvelope.objects.get(dedup_key=f"{key}:{user.pk}") for user in world.mentors]


def test_created_mentor_help_uses_own_approved_template_and_reviewed_variables(mentor_notice):
    world = mentor_notice
    tied, assigned_only = _envelopes(world)
    assert source_eligible(tied) and source_eligible(assigned_only)
    assert [target.endpoint.pk for target in resolve(tied)] == [world.endpoints[0].pk]
    assert not resolve(assigned_only)
    ensure_deliveries(tied)
    delivery = tied.deliveries.get()
    send(delivery.pk)
    delivery.refresh_from_db()
    assert delivery.provider_id == "wamid.mentor"
    assert len(world.posts) == 1 and world.posts[0]["to"] == "15551234567"
    template = world.posts[0]["template"]
    assert template["name"] == "mentor_notice"
    assert template["components"] == [{"type": "body", "parameters": [
        {"type": "text", "text": world.space.name}]}]
    assert all(value not in str(world.posts) for value in ("PRIVATE-WIRING", "PRIVATE-ALIAS", MARKER))


@pytest.mark.parametrize("change", ["opt_out", "off_shift", "unreviewed_variable"])
def test_delivery_rechecks_current_consent_shift_and_template_projection(mentor_notice, change):
    world = mentor_notice
    envelope, _ = _envelopes(world)
    ensure_deliveries(envelope)
    delivery = envelope.deliveries.get()
    if change == "opt_out":
        MessagingConsent.objects.create(makerspace=world.space, user=world.mentors[0],
            channel="whatsapp", action="opted_out", source="member_settings", endpoint=world.endpoints[0])
    elif change == "off_shift":
        world.roles[0].availability = [{"starts_at": "2000-01-01T00:00:00+00:00",
                                       "ends_at": "2000-01-01T01:00:00+00:00"}]
        world.roles[0].save(update_fields=["availability"])
    else:
        world.template.variables = [MARKER]
        world.template.save(update_fields=["variables"])
    send(delivery.pk)
    delivery.refresh_from_db()
    assert not world.posts and not delivery.provider_id
    assert delivery.state == ("failed" if change == "unreviewed_variable" else "skipped")


@pytest.mark.parametrize(("kind", "marker"), [("attention", "created_v1"), ("created", None)])
def test_invalid_marker_cannot_admit_a_real_source(mentor_notice, kind, marker):
    world = mentor_notice
    envelope, _ = _envelopes(world)
    MentorNotificationIntent.objects.filter(pk=world.intent.pk).update(kind=kind)
    NotificationEnvelope.objects.filter(pk=envelope.pk).update(context={**envelope.context, MARKER: marker})
    envelope.refresh_from_db()
    assert not source_eligible(envelope)
    assert not resolve(envelope)
    ensure_deliveries(envelope)
    assert not envelope.deliveries.exists() and not world.posts


def test_existing_unmarked_dedup_envelope_does_not_gain_whatsapp(mentor_notice):
    world = mentor_notice
    envelope, _ = _envelopes(world)
    NotificationEnvelope.objects.filter(pk=envelope.pk).update(context={"event_id": world.intent.event_id})
    actual, _ = _envelopes(world)
    assert actual.pk == envelope.pk and MARKER not in actual.context
    assert source_eligible(actual) and not resolve(actual)
    ensure_deliveries(actual)
    assert not actual.deliveries.exists() and not world.posts

@pytest.mark.parametrize("change", ["opt_out", "off_shift"])
def test_provider_rejected_attempt_does_not_retry_after_authority_loss(mentor_notice, change):
    world = mentor_notice
    world.transport["reject_first"] = True
    envelope, _ = _envelopes(world)
    ensure_deliveries(envelope)
    delivery = envelope.deliveries.get()
    send(delivery.pk)
    delivery.refresh_from_db()
    assert len(world.posts) == 1
    assert delivery.attempt_count == 1 and delivery.retryable and delivery.next_attempt_at
    assert delivery.last_error == "rate_limited" and not delivery.provider_id
    if change == "opt_out":
        MessagingConsent.objects.create(makerspace=world.space, user=world.mentors[0],
            channel="whatsapp", action="opted_out", source="member_settings", endpoint=world.endpoints[0])
    else:
        role = world.roles[0]
        role.availability = [{"starts_at": "2000-01-01T00:00:00+00:00",
                              "ends_at": "2000-01-01T01:00:00+00:00"}]
        role.save(update_fields=["availability"])
    type(delivery).objects.filter(pk=delivery.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
    send(delivery.pk)
    delivery.refresh_from_db()
    assert delivery.attempt_count == 2 and delivery.state == "skipped"
    assert delivery.last_error == "live_eligibility_changed" and not delivery.provider_id
    assert len(world.posts) == 1
