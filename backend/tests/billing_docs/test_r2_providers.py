"""Personal PDF provider requests, live endpoint boundaries and WhatsApp media templates."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from apps.integrations.notification_providers import ProviderResult
from apps.integrations.notification_document_transport import personal_destination, multipart
from apps.integrations.notification_slack_http import ProviderFailure

PDF = b"%PDF-1.4\nprivate document\n%%EOF"
ARGS = {"filename": "BILL-1.pdf", "pdf_bytes": PDF, "caption": "Your bill"}


def delivery_for(channel, provider=None):
    provider = provider or channel
    config = NS(pk=4, makerspace_id=8, generation=2, integration_identity="installation",
        channel=channel, provider=provider, enabled=True, personal_enabled=True,
        refresh_from_db=Mock(), get_credentials=lambda: {"bot_token": "token"})
    endpoint = NS(configuration_id=4, makerspace_id=8, integration_generation=2,
        integration_identity="installation", channel=channel, provider=provider, user_id=9,
        revoked_at=None, verification_state="verified", consented_at=True, verified_at=True,
        destination="12345", refresh_from_db=Mock())
    envelope = NS(makerspace_id=8, recipient_id=9, event="document_issued", audience="member",
                  context={"number": "BILL-1"})
    delivery = NS(pk=5, endpoint_id=7, envelope_id=6, makerspace_id=8, integration_generation=2,
        integration_identity="installation", channel=channel, provider=provider,
        endpoint=endpoint, envelope=envelope)
    return config, delivery


@pytest.mark.parametrize("change", ["room", "owner", "tenant", "generation", "revoked", "consent"])
def test_document_destination_refuses_authority_loss(change):
    config, delivery = delivery_for("slack")
    if change == "room":
        delivery.endpoint_id = None
    elif change == "owner":
        delivery.envelope.recipient_id = 99
    elif change == "tenant":
        delivery.envelope.makerspace_id = 99
    elif change == "generation":
        delivery.integration_generation = 1
    elif change == "revoked":
        delivery.endpoint.revoked_at = True
    else:
        delivery.endpoint.consented_at = None
    with pytest.raises(ProviderFailure, match="invalid_endpoint"):
        personal_destination(config, delivery)


def test_multipart_carries_pdf_and_rejects_filename_header_injection():
    body, content_type = multipart({"caption": "Bill"}, filename="BILL-1.pdf", pdf_bytes=PDF)
    assert PDF in body and b"Content-Type: application/pdf" in body
    assert b'filename="BILL-1.pdf"' in body and "boundary=" in content_type
    with pytest.raises(ProviderFailure):
        multipart({}, filename='bad.pdf"\r\nInjected: secret', pdf_bytes=PDF)


def test_telegram_sends_multipart_document_without_keyboard(monkeypatch):
    from apps.integrations.notification_telegram import TelegramProvider
    config, delivery = delivery_for("telegram")
    provider = TelegramProvider(config)
    monkeypatch.setattr(provider, "_endpoint_current", lambda endpoint: True)
    response = Mock(status=200)
    response.read.return_value = b'{"ok":true,"result":{"message_id":42}}'
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opener = Mock()
    opener.open.return_value = response
    monkeypatch.setattr("apps.integrations.notification_telegram_transport.request.build_opener", lambda *args: opener)
    result = provider.send_document(delivery, **ARGS)
    assert result.accepted and result.provider_id == "42"
    req = opener.open.call_args.args[0]
    assert req.full_url.endswith("/sendDocument") and PDF in req.data
    assert b'name="document"' in req.data and b"reply_markup" not in req.data


def test_telegram_document_connection_error_keeps_ambiguous_retry(monkeypatch):
    from urllib.error import URLError
    from apps.integrations.notification_telegram import TelegramProvider
    config, delivery = delivery_for("telegram")
    provider = TelegramProvider(config)
    monkeypatch.setattr(provider, "_endpoint_current", lambda endpoint: True)
    opener = Mock()
    opener.open.side_effect = URLError("private transport failure")
    monkeypatch.setattr("apps.integrations.notification_telegram_transport.request.build_opener", lambda *args: opener)
    result = provider.send_document(delivery, **ARGS)
    assert not result.accepted and result.retryable and result.ambiguous
    assert result.error_code == "unavailable"
    assert "private transport failure" not in str(result)


def test_telegram_timeout_stays_ambiguous(monkeypatch):
    from apps.integrations.notification_telegram_transport import send_document
    opener = Mock()
    opener.open.side_effect = TimeoutError()
    monkeypatch.setattr("apps.integrations.notification_telegram_transport.request.build_opener", lambda *args: opener)
    result = send_document("token", "123", **ARGS)
    assert not result.accepted and result.retryable and result.ambiguous


def test_slack_three_step_upload_shares_only_to_dm(monkeypatch):
    from apps.integrations.notification_slack import SlackProvider, workspace_identity
    config, delivery = delivery_for("slack")
    config.integration_identity = delivery.integration_identity = delivery.endpoint.integration_identity = workspace_identity("T1")
    config.get_credentials = lambda: {"bot_token": "token", "team_id": "T1"}
    calls = []
    def slack(method, **kwargs):
        calls.append((method, kwargs))
        return {"auth.test": {"team_id": "T1"}, "conversations.open": {"channel": {"id": "D1"}},
            "files.getUploadURLExternal": {"upload_url": "https://files.slack.com/upload/v1/private", "file_id": "F1"},
            "files.completeUploadExternal": {"files": [{"id": "F1"}]}}[method]
    upload = Mock(return_value={})
    monkeypatch.setattr("apps.integrations.notification_slack.slack_api", slack)
    monkeypatch.setattr("apps.integrations.notification_chat_documents.api", upload)
    result = SlackProvider(config).send_document(delivery, **ARGS)
    assert result.accepted and result.provider_id == "F1"
    assert upload.call_args.kwargs["raw_body"] == PDF and "token" not in upload.call_args.kwargs
    assert calls[-1][1]["data"]["channel_id"] == "D1"
    assert calls[-1][1]["data"]["initial_comment"] == "Your bill"


def test_slack_rejects_provider_upload_url_to_foreign_origin(monkeypatch):
    from apps.integrations.notification_slack import SlackProvider, workspace_identity
    config, delivery = delivery_for("slack")
    config.integration_identity = delivery.integration_identity = delivery.endpoint.integration_identity = workspace_identity("T1")
    config.get_credentials = lambda: {"bot_token": "token", "team_id": "T1"}
    monkeypatch.setattr("apps.integrations.notification_slack.slack_api", Mock(side_effect=[
        {"team_id": "T1"}, {"channel": {"id": "D1"}},
        {"upload_url": "https://attacker.invalid/upload/a", "file_id": "F1"}]))
    upload = Mock()
    monkeypatch.setattr("apps.integrations.notification_chat_documents.api", upload)
    result = SlackProvider(config).send_document(delivery, **ARGS)
    assert not result.accepted and not result.retryable
    upload.assert_not_called()


def test_discord_dm_file_request_disables_mentions_and_uses_nonce(monkeypatch):
    from apps.integrations.notification_discord import DiscordProvider
    config, delivery = delivery_for("discord")
    config.get_credentials = lambda: {"application_id": "A", "guild_id": "G", "bot_token": "token"}
    config.integration_identity = delivery.integration_identity = delivery.endpoint.integration_identity = "A:G"
    api = Mock(side_effect=[{"id": "123"}, {"id": "456"}])
    monkeypatch.setattr("apps.integrations.notification_chat_documents.api", api)
    result = DiscordProvider(config).send_document(delivery, **ARGS)
    assert result.accepted and result.provider_id == "456"
    body = api.call_args.kwargs["raw_body"]
    assert PDF in body and b'"nonce": "5"' in body and b'"enforce_nonce": true' in body
    assert b'"allowed_mentions": {"parse": []}' in body


def test_mattermost_upload_then_private_post(monkeypatch):
    from apps.integrations.notification_mattermost import MattermostProvider
    config, delivery = delivery_for("mattermost")
    config.integration_identity = delivery.integration_identity = delivery.endpoint.integration_identity = "https://mm.example"
    config.get_credentials = lambda: {"server_url": "https://mm.example", "bot_token": "token"}
    delivery.endpoint.destination = "u" * 26
    api = Mock(side_effect=[{"id": "b" * 26, "is_bot": True}, {"id": "u" * 26},
        {"id": "c" * 26}, {"file_infos": [{"id": "f" * 26}]}, {"id": "post1"}])
    monkeypatch.setattr("apps.integrations.notification_mattermost_http.mattermost_api", api)
    result = MattermostProvider(config).send_document(delivery, **ARGS)
    assert result.accepted and result.provider_id == "post1"
    assert PDF in api.call_args_list[-2].kwargs["raw_body"]
    assert api.call_args.kwargs["data"]["file_ids"] == ["f" * 26]
    assert api.call_args.kwargs["data"]["channel_id"] == "c" * 26


@pytest.mark.parametrize("code,retryable,ambiguous", [("invalid_endpoint", False, False),
    ("unavailable", True, False), ("timeout", True, True)])
def test_document_provider_does_not_send_text_after_upload_failure(monkeypatch, code, retryable, ambiguous):
    from apps.integrations.notification_discord import DiscordProvider
    config, delivery = delivery_for("discord")
    config.get_credentials = lambda: {"application_id": "A", "guild_id": "G", "bot_token": "token"}
    config.integration_identity = delivery.integration_identity = delivery.endpoint.integration_identity = "A:G"
    api = Mock(side_effect=[{"id": "123"}, ProviderFailure(code, retryable=retryable, ambiguous=ambiguous)])
    monkeypatch.setattr("apps.integrations.notification_chat_documents.api", api)
    result = DiscordProvider(config).send_document(delivery, **ARGS)
    assert result.error_code == code and result.retryable == retryable and result.ambiguous == ambiguous
    assert api.call_count == 2


@pytest.mark.parametrize("channel,provider_path", [
    ("telegram", "notification_telegram.TelegramProvider"), ("slack", "notification_slack.SlackProvider"),
    ("discord", "notification_discord.DiscordProvider"), ("mattermost", "notification_mattermost.MattermostProvider"),
    ("whatsapp", "notification_wa_meta.MetaWhatsAppProvider"),
    ("whatsapp", "notification_wa_twilio.TwilioWhatsAppProvider")])
def test_room_delivery_never_reaches_document_transport(channel, provider_path):
    from importlib import import_module
    module, name = provider_path.split(".")
    config, delivery = delivery_for(channel, "meta" if "meta" in module else "twilio" if "twilio" in module else None)
    delivery.endpoint_id = None
    provider = getattr(import_module("apps.integrations." + module), name)(config)
    result = provider.send_document(delivery, **ARGS)
    assert not result.accepted and result.error_code == "invalid_endpoint"


def test_meta_document_upload_then_message_has_callback_identity(monkeypatch):
    from apps.integrations.notification_wa_meta import MetaWhatsAppProvider
    config, delivery = delivery_for("whatsapp", "meta")
    provider = MetaWhatsAppProvider(config)
    monkeypatch.setattr(provider, "_live_target", lambda endpoint: True)
    monkeypatch.setattr("apps.integrations.notification_wa_documents.in_session_window", lambda endpoint: True)
    monkeypatch.setattr("apps.integrations.notification_wa_meta_http.credentials", lambda config: {"phone_number_id": "300"})
    graph = Mock(return_value=(ProviderResult(True), {"id": "700"}))
    send = Mock(return_value=ProviderResult(True, "wamid.1"))
    monkeypatch.setattr("apps.integrations.notification_wa_meta_http.graph", graph)
    monkeypatch.setattr("apps.integrations.notification_wa_meta_http.send_message", send)
    monkeypatch.setattr("apps.integrations.notification_wa_meta_reference.client_reference", lambda *args: "attempt-ref")
    result = provider.send_document(delivery, **ARGS)
    assert result.accepted and graph.call_args.kwargs["files"]["file"] == ("BILL-1.pdf", PDF, "application/pdf")
    content = send.call_args.args[2]
    assert content["document"]["id"] == "700" and content["biz_opaque_callback_data"] == "attempt-ref"


@pytest.mark.parametrize("approval", [ProviderResult(True), ProviderResult(False, error_code="timeout", retryable=True)])
def test_meta_outside_window_without_document_template_preserves_transient_failure(monkeypatch, approval):
    from apps.integrations.notification_wa_meta import MetaWhatsAppProvider
    config, delivery = delivery_for("whatsapp", "meta")
    provider = MetaWhatsAppProvider(config)
    monkeypatch.setattr(provider, "_live_target", lambda endpoint: True)
    monkeypatch.setattr("apps.integrations.notification_wa_documents.in_session_window", lambda endpoint: False)
    monkeypatch.setattr("apps.integrations.notification_wa_meta_templates.sync_templates", lambda config: approval)
    monkeypatch.setattr("apps.integrations.notification_wa_meta_templates.bound_template", lambda *args: None)
    result = provider.send_document(delivery, **ARGS)
    assert result.error_code == ("unsupported" if approval.accepted else "timeout")
    assert result.retryable == (not approval.accepted)


def test_meta_document_template_approval_proves_header_shape():
    from apps.integrations.notification_wa_meta_templates import document_header_approved, template_content
    # 0579b1b3 (recon M): approval also proves the BODY placeholders and the binding's review state.
    binding = NS(approved=True, needs_review=False, feature="billing", template_name="bill_document", locale="en",
                 variables=["__document_header__", "number"])
    body = {"type": "BODY", "text": "Your bill {{1}} is attached."}
    assert not document_header_approved(binding, {"components": [{"type": "HEADER", "format": "IMAGE"}, body]})
    assert document_header_approved(binding, {"components": [{"type": "HEADER", "format": "DOCUMENT"}, body]})
    assert template_content(binding, {"number": "BILL-1"}) is None
    content = template_content(binding, {"number": "BILL-1"}, media_id="700", filename="BILL-1.pdf")
    assert content["template"]["components"][0]["parameters"][0]["type"] == "document"
    assert content["template"]["components"][1]["parameters"] == [{"type": "text", "text": "BILL-1"}]


def test_meta_outside_window_uses_approved_document_header(monkeypatch):
    from apps.integrations.notification_wa_meta import MetaWhatsAppProvider
    config, delivery = delivery_for("whatsapp", "meta")
    provider = MetaWhatsAppProvider(config)
    monkeypatch.setattr(provider, "_live_target", lambda endpoint: True)
    monkeypatch.setattr("apps.integrations.notification_wa_documents.in_session_window", lambda endpoint: False)
    monkeypatch.setattr("apps.integrations.notification_wa_meta_templates.sync_templates", lambda config: ProviderResult(True))
    binding = NS(approved=True, needs_review=False, feature="billing", template_name="bill_document", locale="en", variables=["__document_header__", "number"])
    monkeypatch.setattr("apps.integrations.notification_wa_meta_templates.bound_template", lambda *args: binding)
    monkeypatch.setattr("apps.integrations.notification_wa_meta_http.credentials", lambda config: {"phone_number_id": "300"})
    monkeypatch.setattr("apps.integrations.notification_wa_meta_http.graph", Mock(return_value=(ProviderResult(True), {"id": "700"})))
    monkeypatch.setattr("apps.integrations.notification_wa_meta_reference.client_reference", lambda *args: "attempt-ref")
    send = Mock(return_value=ProviderResult(True, "wamid.1"))
    monkeypatch.setattr("apps.integrations.notification_wa_meta_http.send_message", send)
    result = provider.send_document(delivery, **ARGS)
    assert result.accepted
    content = send.call_args.args[2]
    assert content["type"] == "template" and content["template"]["name"] == "bill_document"
    assert content["template"]["components"][0]["parameters"][0]["document"]["id"] == "700"


@pytest.mark.parametrize("status,code,retryable", [(400, "provider_error", False), (500, "unavailable", True)])
def test_meta_media_http_failure_preserves_retry_policy(monkeypatch, status, code, retryable):
    from apps.integrations.notification_wa_meta_http import graph
    config, _ = delivery_for("whatsapp", "meta")
    values = {"phone_number_id": "300", "access_token": "secret"}
    monkeypatch.setattr("apps.integrations.notification_wa_meta_http.credentials", lambda config: values)
    request = Mock(return_value=NS(status_code=status, headers={}, json=lambda: {"error": {"code": 100}}))
    monkeypatch.setattr("apps.integrations.notification_wa_meta_http.requests.request", request)
    result, data = graph(config, "POST", "300/media", files={"file": ("BILL-1.pdf", PDF, "application/pdf")})
    assert data is None and result.error_code == code and result.retryable == retryable
    assert request.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("window,approved", [(True, False), (False, False), (False, True)])
def test_twilio_media_grant_only_for_supported_document_attempt(monkeypatch, window, approved):
    from apps.integrations.notification_wa_twilio import TwilioWhatsAppProvider
    config, delivery = delivery_for("whatsapp", "twilio")
    provider = TwilioWhatsAppProvider(config)
    monkeypatch.setattr(provider, "active", lambda: True)
    monkeypatch.setattr(provider, "valid_endpoint", lambda endpoint: True)
    monkeypatch.setattr(provider, "credentials", lambda: NS(public_base_url="https://sw.example"))
    monkeypatch.setattr("apps.integrations.notification_wa_documents.in_session_window", lambda endpoint: window)
    template = Mock(side_effect=lambda *args, **kwargs: {"ContentSid": "HX1", "ContentVariables": kwargs["document_url"]} if approved else None)
    monkeypatch.setattr("apps.integrations.notification_wa_twilio_templates.template_payload", template)
    grant = Mock(return_value="https://sw.example/api/v1/integrations/notification-media/secret.pdf")
    monkeypatch.setattr("apps.integrations.notification_media.issue_grant", grant)
    send = Mock(return_value=ProviderResult(True, "SM1"))
    monkeypatch.setattr(provider, "_send", send)
    result = provider.send_document(delivery, **ARGS)
    if window or approved:
        assert result.accepted and grant.call_count == 1 and send.call_count == 1
        payload = send.call_args.args[1]
        assert ("MediaUrl" in payload) == window
        assert send.call_args.args[2] == delivery.pk
    else:
        assert result.error_code == "unsupported" and not result.retryable
        grant.assert_not_called()
        send.assert_not_called()


def test_twilio_approval_proves_pdf_media_and_fixed_origin():
    from apps.integrations.notification_wa_twilio_templates import approved_document_content
    credentials = NS(account_sid="AC1", public_base_url="https://sw.example")
    binding = NS(template_name="HX1", locale="en", variables=["number", "__document_media__"])
    content = {"account_sid": "AC1", "sid": "HX1", "language": "en", "variables": {"2": "example.pdf"},
        "types": {"twilio/media": {"media": ["https://sw.example/{{2}}"], "body": "Your bill {{1}}"}}}
    assert approved_document_content(None, credentials, binding, content)
    content["types"]["twilio/media"]["media"] = ["https://attacker.invalid/{{2}}"]
    assert not approved_document_content(None, credentials, binding, content)
    content["types"]["twilio/media"]["media"] = ["https://sw.example/{{2}}"]
    content["variables"]["2"] = "sample.jpg"
    assert not approved_document_content(None, credentials, binding, content)
