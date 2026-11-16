"""R4 security: webhook and SMTP guards allow only global unicast addresses, and the SMTP
backend re-checks the connected peer before it speaks (DNS rebinding). Local only."""

import smtplib
import socket

import pytest
from django.core.exceptions import ValidationError

from apps.integrations.mail_providers import smtp_guarded
from apps.integrations.smtp_validation import validate_smtp_endpoint
from apps.integrations.webhook_validation import UnsafeWebhookUrl, resolve_webhook_target

BLOCKED = [
    "100.100.100.200", "100.64.0.1", "::ffff:100.100.100.200", "127.0.0.1", "169.254.169.254",
    "64:ff9b::a9fe:a9fe",
]


def _answers(address, port=443):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    sockaddr = (address, port, 0, 0) if ":" in address else (address, port)
    return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr)]


@pytest.mark.parametrize("address", BLOCKED)
def test_webhook_refuses_non_global_answers(monkeypatch, address):
    monkeypatch.setattr("apps.integrations.webhook_validation.socket.getaddrinfo",
                        lambda *_a, **_k: _answers(address))
    with pytest.raises(UnsafeWebhookUrl):
        resolve_webhook_target("https://hooks.example.org/x")


@pytest.mark.parametrize("address", BLOCKED)
def test_smtp_refuses_non_global_answers(monkeypatch, address):
    monkeypatch.setattr("apps.integrations.smtp_validation.socket.getaddrinfo",
                        lambda host, port, type=None: _answers(address, port))
    with pytest.raises(ValidationError):
        validate_smtp_endpoint("smtp.example.org", 587)


def test_public_answers_still_pass(monkeypatch):
    monkeypatch.setattr("apps.integrations.smtp_validation.socket.getaddrinfo",
                        lambda host, port, type=None: _answers("93.184.216.34", port))
    validate_smtp_endpoint("smtp.example.org", 587)


class _FakeSocket:
    def __init__(self, peer):
        self.peer, self.sent, self.closed = peer, [], False

    def getpeername(self):
        return (self.peer, 587)

    def sendall(self, data):
        self.sent.append(data)

    def close(self):
        self.closed = True


@pytest.mark.parametrize("peer", ["127.0.0.1", "10.0.0.5", "100.100.100.200", "64:ff9b::a9fe:a9fe"])
def test_guarded_backend_refuses_a_rebound_peer_before_speaking(monkeypatch, peer):
    fake = _FakeSocket(peer)
    monkeypatch.setattr(smtplib.socket, "create_connection", lambda *_a, **_k: fake)
    backend = smtp_guarded.EmailBackend(host="smtp.example.org", port=587, username="u", password="p",
                                        use_tls=True, fail_silently=False, timeout=5)
    with pytest.raises(smtplib.SMTPConnectError):
        backend.open()
    assert fake.closed and fake.sent == []


def test_guarded_backend_is_the_smtp_provider_backend():
    from apps.integrations.mail_providers.config import BACKENDS
    from django.core.mail.backends.smtp import EmailBackend
    from django.utils.module_loading import import_string
    assert issubclass(import_string(BACKENDS["smtp"]), EmailBackend)
