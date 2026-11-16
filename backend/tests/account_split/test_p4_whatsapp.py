"""Exercise the signed Twilio and Meta ingress, including delivery switches off."""
import pytest

from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.models_endpoints import NotificationEndpoint
from tests.p2_wa_twilio.conftest import wa, http
from tests.p2_wa_meta.conftest import wa as meta, no_provider_network
from .p1_helpers import staff

pytestmark = pytest.mark.django_db


def shared_endpoint(endpoint, user):
    values = {field.attname: getattr(endpoint, field.attname)
              for field in NotificationEndpoint._meta.concrete_fields if not field.primary_key}
    values["user_id"] = user.pk
    return NotificationEndpoint.objects.create(**values)


def test_twilio_stop_revokes_both_and_status_updates_only_its_delivery(wa):
    c = wa
    operator, _ = staff(c.space)
    second = shared_endpoint(c.endpoint, operator)
    envelope = NotificationEnvelope.objects.create(makerspace=c.space, recipient=operator,
        feature="hardware_requests", event="accepted", audience="requester", source_kind="wa.test",
        dedup_key="staff-delivery")
    other = NotificationDelivery.objects.create(makerspace=c.space, envelope=envelope, endpoint=second,
        channel="whatsapp", provider="twilio", target_key=f"endpoint:{second.pk}", state="accepted",
        integration_generation=c.config.generation, integration_identity=c.config.integration_identity)
    c.delivery.state = "accepted"
    c.delivery.save()
    c.config.enabled = c.config.personal_enabled = False
    c.config.save()
    assert c.post("status", {"MessageStatus": "delivered"}).status_code == 200
    c.delivery.refresh_from_db()
    other.refresh_from_db()
    assert c.delivery.state == "delivered" and other.state == "accepted"
    assert c.post(params={"Body": "STOP"}).status_code == 200
    for endpoint in (c.endpoint, second):
        endpoint.refresh_from_db()
        assert endpoint.revoked_at is not None


def test_meta_signed_inbound_then_stop_affects_every_live_account(meta):
    c = meta
    first = c.endpoint()
    operator, _ = staff(c.space)
    second = shared_endpoint(first, operator)
    assert c.post(c.payload("messages", [c.message()])).status_code == 200
    for endpoint in (first, second):
        endpoint.refresh_from_db()
        assert endpoint.last_inbound_at is not None
    c.config.enabled = c.config.personal_enabled = False
    c.config.save()
    assert c.post(c.payload("messages", [c.message("STOP")])).status_code == 200
    for endpoint in (first, second):
        endpoint.refresh_from_db()
        assert endpoint.revoked_at is not None
