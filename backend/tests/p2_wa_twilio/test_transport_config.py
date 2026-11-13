import base64
import io
import json
from urllib.error import HTTPError, URLError

import pytest

from apps.integrations.notification_wa_twilio_config import ConfigurationError, validate_credentials
from apps.integrations.notification_wa_twilio_http import call, send_message, NoRedirect
from .conftest import ACCOUNT, CONTENT, PUBLIC, SENDER, TOKEN


def credentials(**overrides):
    return {"account_sid": ACCOUNT, "auth_token": TOKEN, "whatsapp_sender": SENDER,
            "public_base_url": PUBLIC, **overrides}


@pytest.mark.parametrize("values", [
    {"account_sid": "../wrong"}, {"auth_token": ""}, {"auth_token": "short"},
    {"api_key_sid": "SK" + "a" * 32}, {"api_key_secret": "a" * 32},
    {"whatsapp_sender": "4155550100"}, {"whatsapp_sender": ""},
    {"messaging_service_sid": "bad"}, {"public_base_url": "http://api.example.test"},
    {"public_base_url": "https://user:secret@api.example.test"}, {"public_base_url": PUBLIC + "/path"},
    {"public_base_url": PUBLIC + "?query=1"}, {"public_base_url": PUBLIC + "\n"}, {"unknown_token": "bad"},
])
def test_invalid_credentials_fail_with_static_error(values):
    with pytest.raises(ConfigurationError) as exc:
        validate_credentials(credentials(**values))
    assert str(exc.value) in {"not_configured", "invalid_endpoint"}


def test_api_keys_and_service_sender_are_supported_but_callback_needs_auth_token(http):
    values = credentials(api_key_sid="SK" + "5" * 32, api_key_secret="6" * 32,
                         whatsapp_sender="", messaging_service_sid="MG" + "7" * 32)
    parsed = validate_credentials(values)
    assert parsed.auth_token == TOKEN and parsed.messaging_service_sid.startswith("MG")
    send_message(parsed, {"To": "whatsapp:+14155550123", "ContentSid": CONTENT})
    authorization = http.calls[-1][0].get_header("Authorization").removeprefix("Basic ")
    assert base64.b64decode(authorization).decode() == values["api_key_sid"] + ":" + values["api_key_secret"]
    assert TOKEN not in repr(parsed)
    del values["auth_token"]
    with pytest.raises(ConfigurationError):
        validate_credentials(values)


@pytest.mark.parametrize("status,code,expected,retryable", [
    (429, 0, "rate_limited", True), (500, 0, "unavailable", True), (503, 0, "unavailable", True),
    (400, 63016, "template_required", False), (400, 63040, "template_required", False),
    (400, 21610, "blocked", False), (400, 63033, "blocked", False),
    (400, 21211, "invalid_endpoint", False), (400, 63024, "invalid_endpoint", False),
    (401, 20003, "not_configured", False), (400, 99999, "provider_error", False),
    (400, 63007, "not_configured", False), (400, 63010, "unavailable", True),
])
def test_error_mapping_never_contains_provider_text(http, status, code, expected, retryable):
    http.state["error"] = HTTPError("https://api.twilio.com", status, "private", {},
        io.BytesIO(json.dumps({"code": code, "message": "private destination"}).encode()))
    result = send_message(validate_credentials(credentials()), {"Body": "private"})
    assert result.error_code == result.sanitized_error == expected and result.retryable is retryable


def test_http_error_body_is_redacted_and_retry_after_bounded(http, caplog):
    http.state["error"] = HTTPError("https://api.twilio.com", 429, "secret message", {"Retry-After": "99999"},
        io.BytesIO(json.dumps({"code": 20429, "message": "secret message +14155550123"}).encode()))
    _, result = call(validate_credentials(credentials()), "https://api.twilio.com", {"Body": "private"})
    assert result.error_code == "rate_limited" and result.retry_after == 3600
    assert "secret message" not in caplog.text and "+14155550123" not in caplog.text
    assert "private" not in repr(result)


@pytest.mark.parametrize("error,name", [(TimeoutError("secret"), "timeout"),
    (URLError(TimeoutError("secret")), "timeout"), (URLError("connection reset"), "unavailable")])
def test_network_errors_are_retryable_and_ambiguous(http, error, name):
    http.state["error"] = error
    result = send_message(validate_credentials(credentials()), {"Body": "private"})
    assert not result.accepted and result.retryable and result.ambiguous and result.error_code == name
    assert "secret" not in repr(result)


def test_redirects_never_forward_credentials():
    assert NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://evil.example") is None
