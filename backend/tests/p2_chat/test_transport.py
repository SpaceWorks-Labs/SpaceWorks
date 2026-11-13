import json
import socket
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rest_framework.exceptions import ValidationError

from apps.integrations.notification_mattermost_http import resolve_server, server_url, mattermost_api
from apps.integrations.notification_slack_http import api, ProviderFailure


@pytest.mark.parametrize("value", ["http://chat.example", "https://user:pass@chat.example", "https://chat.example/path",
    "https://chat.example?redirect=evil", "https://chat.example/#fragment", "https://chat.example:70000"])
def test_mattermost_requires_https_origin(value):
    with pytest.raises(ValidationError):
        server_url(value)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fd00::1", "::ffff:127.0.0.1"])
def test_mattermost_refuses_private_dns_answers(ip, monkeypatch, settings):
    settings.NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS = False
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    monkeypatch.setattr("apps.integrations.notification_mattermost_http.socket.getaddrinfo",
        Mock(return_value=[(family, socket.SOCK_STREAM, 6, "", (ip, 443))]))
    with pytest.raises(ValidationError):
        resolve_server("https://chat.example", "/api/v4/users/me")


def test_private_host_requires_explicit_self_host_setting(monkeypatch, settings):
    monkeypatch.setattr("apps.integrations.notification_mattermost_http.socket.getaddrinfo", Mock(return_value=[
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))]))
    settings.NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS = True
    target = resolve_server("https://chat.example", "/api/v4/users/me")
    assert target.addresses[0].sockaddr == ("10.0.0.1", 443)


def test_mattermost_pins_checked_ip_and_refuses_rebinding(monkeypatch, settings):
    settings.NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS = False
    dns = Mock(side_effect=[[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
                            [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]])
    monkeypatch.setattr("apps.integrations.notification_mattermost_http.socket.getaddrinfo", dns)
    transport = Mock(return_value={"id": "bot"})
    monkeypatch.setattr("apps.integrations.notification_mattermost_http.api", transport)
    assert mattermost_api("https://chat.example", "GET", "/api/v4/users/me", token="secret")["id"] == "bot"
    assert transport.call_args.kwargs["target"].addresses[0].sockaddr[0] == "8.8.8.8"
    with pytest.raises(ValidationError):
        mattermost_api("https://chat.example", "GET", "/api/v4/users/me", token="secret")
    assert transport.call_count == 1


@pytest.mark.parametrize("status,code,retryable", [(429, "rate_limited", True), (503, "unavailable", True),
    (403, "invalid_endpoint", False), (404, "invalid_endpoint", False), (302, "provider_error", False)])
def test_http_status_mapping_and_no_redirect_credentials(status, code, retryable, monkeypatch):
    response = Mock(status=status)
    response.read.return_value = json.dumps({"retry_after": 7, "message": "private-provider-response"}).encode()
    response.getheader.return_value = None
    connection = Mock()
    connection.getresponse.return_value = response
    factory = Mock(return_value=connection)
    monkeypatch.setattr("apps.integrations.notification_slack_http._PinnedHTTPSConnection", factory)
    target = SimpleNamespace(host_header="chat.example", request_target="/api", addresses=[object()])
    with pytest.raises(ProviderFailure) as error:
        api("POST", "https://chat.example/api", target=target, token="secret", data={"private": "body"})
    assert error.value.result.error_code == code and error.value.result.retryable == retryable
    if status == 429:
        assert error.value.result.retry_after == 7
    assert "private-provider-response" not in str(error.value)
    connection.close.assert_called_once()
    assert connection.request.call_count == 1
