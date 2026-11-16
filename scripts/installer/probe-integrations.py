"""Selected full-host scanner, HTTPS edge and mail checks."""
from datetime import datetime, timezone
import os
import socket
import struct
from urllib.parse import urlsplit

from probe_common import ProbeError, json_get


def clamd(host, port, payload=None):
    with socket.create_connection((host, port), timeout=5) as peer:
        peer.settimeout(10)
        if payload is None:
            peer.sendall(b"zVERSION\0")
        else:
            peer.sendall(b"zINSTREAM\0" + struct.pack("!I", len(payload)) + payload + b"\0" * 4)
        response = b""
        while b"\0" not in response and len(response) < 4096:
            chunk = peer.recv(1024)
            if not chunk:
                break
            response += chunk
        return response.rstrip(b"\0\n").decode("ascii", "strict")


def scanner():
    from django.conf import settings
    policy = getattr(settings, "UPLOAD_SCAN_POLICY", "none")
    if policy == "none":
        return "explicitly_disabled"
    if policy != "clamav":
        raise ProbeError("invalid_scan_policy")
    host, port = settings.CLAMD_HOST, settings.CLAMD_PORT
    version = clamd(host, port)
    try:
        signature = datetime.strptime(version.split("/", 2)[2], "%a %b %d %H:%M:%S %Y").replace(tzinfo=timezone.utc)
    except (ValueError, IndexError):
        raise ProbeError("scanner_signature_unknown") from None
    if not -300 <= (datetime.now(timezone.utc) - signature).total_seconds() <= 7 * 86400:
        raise ProbeError("scanner_signature_stale")
    if clamd(host, port, b"Space Works clean scan diagnostic") != "stream: OK":
        raise ProbeError("scanner_clean_scan_failed")
    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    if not clamd(host, port, eicar).endswith(" FOUND"):
        raise ProbeError("scanner_infected_scan_failed")
    return "fresh_signatures_clean_and_infected_verified"


def edge():
    from django.conf import settings
    origin = settings.PUBLIC_APP_BASE_URL.rstrip("/")
    parsed = urlsplit(origin)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ProbeError("edge_invalid_origin")
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
        return "explicit_loopback_http"
    if parsed.scheme != "https":
        raise ProbeError("edge_requires_https")
    if json_get(origin + "/api/v1/health/readiness/").get("status") != "ready":
        raise ProbeError("edge_not_ready")
    return "trusted_certificate_and_edge_readiness_verified"


def email():
    from django.core.mail import EmailMessage, get_connection
    from django.core.validators import validate_email
    from apps.integrations.email import platform_mail_connection
    recipient = os.environ.get("SPACEWORKS_INSTALLER_TEST_EMAIL", "")
    if not recipient:
        return "not_selected_configure_and_test_in_control"
    validate_email(recipient)
    connection, sender = platform_mail_connection()
    connection = connection or get_connection(timeout=10)
    backend = type(connection).__module__
    if not (backend == "django.core.mail.backends.smtp" or backend.startswith("anymail.backends.")
            or backend in {"apps.integrations.mail_providers.resend", "apps.integrations.mail_providers.ses",
                           "apps.integrations.mail_providers.sendgrid"}):
        raise ProbeError("email_nondelivering_backend")
    with connection:
        sent = connection.send_messages([EmailMessage(
            "Space Works installation diagnostic", "The configured mail transport accepted this installation test.",
            sender, [recipient], connection=connection)])
    if sent != 1:
        raise ProbeError("email_not_accepted")
    return "provider_accepted_check_recipient_inbox"
