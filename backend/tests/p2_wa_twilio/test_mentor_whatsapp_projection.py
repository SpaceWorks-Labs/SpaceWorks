"""Actual Twilio provider wiring, with the established HTTP-only stub."""
import json

import pytest

from apps.integrations.models_endpoints import WhatsAppTemplate
from apps.integrations.notification_delivery import ensure_deliveries
from apps.integrations.notification_wa_twilio import TwilioWhatsAppProvider
from tests.events.programme.mentoring.test_personal_whatsapp_decision145 import (
    _envelopes, mentor_notice,  # noqa: F401 - pytest discovers the fixture by import
)
from tests.p2_wa_twilio.conftest import CONTENT

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("mentor_notice", ["twilio"], indirect=True)
@pytest.mark.parametrize("key", ["makerspace.name", "mentor_whatsapp_policy", "event_id"])
def test_mentor_template_can_bind_only_reviewed_context(mentor_notice, http, key):
    world = mentor_notice
    config = world.endpoints[0].configuration
    world.template.delete()
    binding = WhatsAppTemplate.objects.create(configuration=config, event="mentor_help_update",
        audience="member", template_name=CONTENT, variables=[key], approved=True)
    envelope, _ = _envelopes(world)
    ensure_deliveries(envelope)
    delivery = envelope.deliveries.get()
    result = TwilioWhatsAppProvider(config).send(delivery, {"text": "Private body"})
    posts = [payload for request, payload in http.calls if request.get_method() == "POST"]
    if key != "makerspace.name":
        assert not result.accepted and result.error_code == "template_required"
        assert not posts
        return
    assert result.accepted and len(posts) == 1
    assert posts[0]["ContentSid"] == [binding.template_name]
    assert json.loads(posts[0]["ContentVariables"][0]) == {"1": world.space.name}
    assert "Body" not in posts[0]
