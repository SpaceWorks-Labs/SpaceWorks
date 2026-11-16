"""E-B8 fixtures: the webhook and SMTP validators resolve host names, and the test container is offline."""
import socket

import pytest


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    for module in ("webhook_validation", "smtp_validation"):
        monkeypatch.setattr(f"apps.integrations.{module}.socket.getaddrinfo", lambda *_a, **_k: answers)
