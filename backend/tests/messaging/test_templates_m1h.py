import pytest
from rest_framework.exceptions import ValidationError

from apps.integrations.messaging.projections import PROJECTION_KEYS, project_context
from apps.integrations.messaging.serializers import WhatsAppBindingSerializer
from apps.integrations.messaging.templates import save_binding, validate_binding
from tests.messaging.canonical_helpers import whatsapp_channel

pytestmark = pytest.mark.django_db


def binding(**changes):
    return dict(feature="hardware_requests", event="accepted", audience="member", template_name="loan_accepted",
                language="en_US", parameters=["request.id"], **changes)


@pytest.mark.parametrize("change", [{"language": "en-AU"}, {"parameters": ["request.requester_contact_phone"]},
    {"parameters": ["public_token"]}, {"components": [{"type": "HEADER", "format": "IMAGE"}]},
    {"components": [{"type": "BUTTONS"}]}, {"components": [{"type": "BODY", "text": "{{name}}"}]},
    {"components": [{"type": "BODY", "text": "{{2}}"}]}, {"event": "broadcast"}])
def test_reject_unsupported_templates(change):
    values = binding()
    values.update(change)
    with pytest.raises(ValidationError):
        validate_binding(values)


def own_meta(business_account_id):
    return {"app_id": "111", "app_secret": "own-secret", "business_account_id": business_account_id,
            "phone_number_id": "321", "access_token": "own-access", "webhook_verify_token": "own-verify"}


def test_binding_and_sender_waba_change_requires_review(space, manager):
    from apps.integrations.models_endpoints import WhatsAppTemplate
    from apps.integrations.notification_legacy_api import LegacyMessagingRetired
    # D1: the duplicate legacy binding writer is retired; canonical templates bind to
    # the configured installation and a sender/WABA change requires fresh review.
    with pytest.raises(LegacyMessagingRetired):
        save_binding(manager, space, binding())
    config = whatsapp_channel(space, manager, credentials=own_meta("456"))
    assert config.sender_key == "meta:456:321"
    row = WhatsAppTemplate.objects.create(configuration=config, feature="hardware_requests", event="accepted",
        audience="member", locale="en_US", template_name="loan_accepted", variables=["request.id"],
        provider_identity=config.integration_identity, approved=True, needs_review=False)
    config = whatsapp_channel(space, manager, credentials=own_meta("789"))
    assert config.sender_key == "meta:789:321"
    row.refresh_from_db()
    assert row.needs_review and not row.approved


def test_projection_omits_free_text_contacts_and_tokens():
    result = project_context("hardware_requests", "accepted", "member", {
        "makerspace": {"name": "Lab"}, "request": {"id": 42, "requester_contact_phone": "hidden",
        "requested_for": "private notes", "public_token": "secret"}, "public_token": "secret",
    })
    assert result["request.id"] == 42
    assert "hidden" not in str(result) and "secret" not in str(result) and "private notes" not in str(result)
    assert ("members", "broadcast", "member") not in PROJECTION_KEYS


def test_api_rejects_named_parameters_and_extra_provider_components():
    values = binding()
    values["parameter_format"] = "NAMED"
    serializer = WhatsAppBindingSerializer(data=values)
    assert not serializer.is_valid()


@pytest.mark.parametrize("components,parameter_format,valid", [
    ([{"type": "BODY", "text": "Loan {{1}} accepted"}], "POSITIONAL", True),
    ([{"type": "BODY", "text": "Loan {{name}} accepted"}], "NAMED", False),
    ([{"type": "HEADER", "format": "IMAGE"}, {"type": "BODY", "text": "Loan {{1}}"}], "POSITIONAL", False),
    ([{"type": "BODY", "text": "Loan {{1}}"}, {"type": "BUTTONS"}], "POSITIONAL", False),
])
def test_authoritative_meta_template_shape(components, parameter_format, valid):
    import json
    from unittest.mock import MagicMock, patch
    from apps.integrations.messaging.templates_provider import validate_provider_template
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps({"data": [{"name": "loan_accepted",
        "language": "en_US", "status": "APPROVED", "components": components,
        "parameter_format": parameter_format}]}).encode()
    kwargs = dict(business_account_id="456", access_token="token", template_name="loan_accepted",
                  language="en_US", parameters=["request.id"])
    with patch("apps.integrations.messaging.templates_provider.urlopen", return_value=response):
        if valid:
            validate_provider_template(**kwargs)
        else:
            with pytest.raises(ValidationError):
                validate_provider_template(**kwargs)
