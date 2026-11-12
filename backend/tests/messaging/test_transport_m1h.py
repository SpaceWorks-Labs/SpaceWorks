import io
import json
import socket
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from apps.integrations.messaging.segments import count_segments, prepare_sms
from apps.integrations.messaging.transport import send_request

OPENER = "apps.integrations.messaging.transport.request.build_opener"


def provider_http(**kwargs):
    """Patch the redirect-refusing opener the transport really uses; yield its open()."""
    opener = MagicMock()
    opener.open = MagicMock(**kwargs)
    return patch(OPENER, return_value=opener), opener.open


@pytest.mark.parametrize("body,expected", [
    ("", 0), ("a" * 160, 1), ("a" * 161, 2), ("a" * 304, 2), ("a" * 305, 3),
    ("^" * 80, 1), ("^" * 81, 2), ("€{}[]~|\\", 1), ("界" * 70, 1), ("界" * 71, 2),
    ("😀" * 35, 1), ("😀" * 36, 2), ("界" * 133, 3),
])
def test_segment_vectors(body, expected):
    assert count_segments(body) == expected


@pytest.mark.parametrize("body", ["a" * 1000, "^" * 1000, "界" * 1000, "😀" * 1000])
def test_cap_uses_ascii_ellipsis_and_recounts(body):
    result = prepare_sms(body)
    assert result.body.endswith("...")
    assert result.estimated_segments == count_segments(result.body) == 3


@pytest.mark.parametrize("provider,status,code,retryable,ambiguous", [
    ("twilio", 400, 21610, False, False), ("twilio", 400, 21211, False, False),
    ("twilio", 400, 21614, False, False), ("twilio", 400, 20429, True, False),
    ("twilio", 429, 20429, True, False), ("twilio", 503, None, True, False),
    ("meta", 400, 131026, False, False), ("meta", 400, 131047, False, False), ("meta", 400, 132000, False, False),
    ("meta", 400, 130429, True, False), ("meta", 400, 131048, True, False),
    ("meta", 400, 131056, True, False), ("meta", 503, 2, True, False),
    ("meta", 503, None, True, True),
])
def test_provider_rejections(provider, status, code, retryable, ambiguous):
    data = {"code": code}
    if provider == "meta":
        data = {"error": data} if code else {}
    exc = HTTPError("https://provider.test", status, "rejected", {}, io.BytesIO(json.dumps(data).encode()))
    patcher, _ = provider_http(side_effect=exc)
    with patcher as build_opener:
        result = send_request(Request("https://provider.test"), provider=provider)
    # Provider calls never follow a redirect that could forward credentials.
    from apps.integrations.notification_wa_twilio_http import NoRedirect
    assert isinstance(build_opener.call_args.args[0], NoRedirect)
    assert result.retryable == retryable
    assert result.permanent != retryable
    assert result.ambiguous == ambiguous
    assert result.error_code == (str(code) if code else f"http_{status}")


@pytest.mark.parametrize("exc,ambiguous", [(TimeoutError(), True), (ConnectionResetError(), True),
    (URLError(socket.gaierror()), False), (URLError(ConnectionRefusedError()), False)])
def test_probe_transport_distinguishes_before_write_failure_from_ambiguous(exc, ambiguous):
    patcher, _ = provider_http(side_effect=exc)
    with patcher:
        result = send_request(Request("https://provider.test"), provider="meta")
    assert result.retryable and result.ambiguous == ambiguous


def test_meta_positional_body_and_delivery_callback_identity(settings):
    from apps.integrations.messaging.resolver import ResolvedSender
    from apps.integrations.messaging.whatsapp import send_message
    sender = ResolvedSender("whatsapp", "meta:b:p", "meta", "own", 1,
                            phone_number_id="123", access_token="token")
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"messages":[{"id":"wamid.1"}]}'
    patcher, http = provider_http(return_value=response)
    with patcher:
        result = send_message(sender, to="+14155552671", template_name="loan_accepted", language="en_US",
                              parameters=["42", "2026-10-17"], delivery_id=99)
    req = http.call_args.args[0]
    data = json.loads(req.data)
    assert result.message_id == "wamid.1"
    assert f"/{settings.WHATSAPP_META_GRAPH_VERSION}/123/messages" in req.full_url  # the configured Graph version
    assert data["biz_opaque_callback_data"] == "99"
    assert data["template"]["components"] == [{"type": "body", "parameters": [
        {"type": "text", "text": "42"}, {"type": "text", "text": "2026-10-17"}]}]
    assert http.call_args.kwargs["timeout"] == 10


def test_otp_bool_transport_does_not_require_notification_callback_or_json():
    from types import SimpleNamespace
    from apps.integrations.sms.twilio import TwilioSmsProvider
    row = SimpleNamespace(account_sid="ACtest", from_number="+14155550001", get_auth_token=lambda: "secret")
    response = MagicMock()
    response.__enter__.return_value.status = 201
    with patch("apps.integrations.sms.twilio.urllib_request.urlopen", return_value=response) as http:
        assert TwilioSmsProvider(row).send(to="+14155552671", body="OTP") is True
    assert b"StatusCallback" not in http.call_args.args[0].data


def test_twilio_notification_explicit_number_and_exact_callback(settings):
    from urllib.parse import parse_qs
    from apps.integrations.messaging.resolver import ResolvedSender
    from apps.integrations.messaging.twilio import send_message
    sender = ResolvedSender("sms", "twilio:ACtest:+14155550002", "twilio", "own", 7,
                            account_sid="ACtest", from_number="+14155550002", auth_token="secret")
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"sid":"SM123", "status":"queued"}'
    patcher, http = provider_http(return_value=response)
    with patcher:
        result = send_message(sender, to="+14155552671", body="Loan accepted")
    data = parse_qs(http.call_args.args[0].data.decode())
    assert data["From"] == ["+14155550002"]
    assert data["StatusCallback"] == ["https://callbacks.example.test/api/v1/integrations/messaging/twilio/m/7/status#rc=5&rp=5xx,ct,rt"]
    assert result.message_id == "SM123" and result.provider_status == "queued"
