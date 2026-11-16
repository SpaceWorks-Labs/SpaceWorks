"""Bounded read-only service diagnostics and explicit selected test mail."""

import json
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener

from .errors import SetupError


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def readiness(origin):
    from .answers import https_url
    https_url(origin, "api_origin", origin=True)
    with build_opener(NoRedirect).open(Request(origin.rstrip("/") + "/api/v1/health/readiness/"), timeout=10) as response:
        payload = response.read(65537)
        if len(payload) > 65536 or response.status != 200:
            raise SetupError("readiness_failed", "Inspect the cloud deployment readiness failure privately.")
    document = json.loads(payload)
    if document.get("status") != "ready" or document.get("database") != "ok":
        raise SetupError("readiness_failed", "Complete release, identity, source and mandatory encryption readiness first.")
    return {"status": "passed"}


def redis_probe(values, answers):
    if answers["task_profile"] == "brokerless":
        if any(values.get(key) for key in ("CELERY_BROKER_URL", "CACHE_URL", "LIVE_REDIS_URL")):
            raise SetupError("brokerless_conflict", "Clear Redis URLs for the selected no-Redis recipe.")
        return {"status": "passed", "profile": "database-cache-and-polling", "runtime_cache_test": "required"}
    from urllib.parse import urlsplit
    import redis
    url = values.get("CELERY_BROKER_URL", "")
    if urlsplit(url).scheme != "rediss":
        raise SetupError("redis_tls_required", "Supply a managed Redis TCP/TLS rediss URL; REST-only Redis is unsupported.")
    client = redis.Redis.from_url(url, socket_timeout=5, socket_connect_timeout=5, ssl_cert_reqs="required")
    try:
        if client.ping() is not True:
            raise SetupError("redis_unreachable", "Verify managed Redis TLS, CA and network access.")
    finally:
        client.close()
    return {"status": "passed", "profile": "redis", "worker_roundtrip": "required"}


def scanner_probe(values, answers):
    if answers["scan_policy"] == "none":
        return {"status": "passed", "notice": "Malware scanning is off. Files are validated by type and size, but are not scanned for malware. Configure an external ClamAV service to enable scanning."}
    import socket
    host, port = values.get("CLAMD_HOST"), int(values.get("CLAMD_PORT", "3310"))
    if not host or not 1 <= port <= 65535:
        raise SetupError("scanner_configuration", "Configure a private external ClamAV endpoint and compatible file/timeout limits.")
    with socket.create_connection((host, port), timeout=5) as client:
        client.settimeout(5)
        client.sendall(b"zVERSION\0")
        result = client.recv(1024)
    if not result.startswith(b"ClamAV "):
        raise SetupError("scanner_version_failed", "Verify the private scanner's VERSION, signature age and scan limits.")
    return {"status": "passed", "signature_and_stream_checks": "required"}


def email_probe(values, answers, *, send=False):
    provider = answers["email_provider"]
    if answers["provider"] == "render" and answers["profile"] == "free" and provider == "smtp":
        raise SetupError("render_smtp_blocked", "Select an HTTP email provider for Render Free.")
    if provider == "smtp":
        if not values.get("EMAIL_HOST") or values.get("EMAIL_USE_TLS", "True").lower() == "true" and values.get("EMAIL_USE_SSL", "False").lower() == "true":
            raise SetupError("smtp_configuration", "Supply a real SMTP host and select TLS or SSL, never both.")
    else:
        from .secret_files import read_config
        path = values.get("EMAIL_PROVIDER_CONFIG_FILE")
        if not path:
            raise SetupError("email_config_required", "Mount the selected HTTP provider's protected typed configuration JSON.")
        from .email_config import validate_config
        validate_config(provider, read_config(values, "EMAIL_PROVIDER_CONFIG_FILE"))
    if not send:
        return {"status": "passed", "provider": provider, "send": "not_requested", "inbox": "unconfirmed"}
    recipient = answers.get("send_test_recipient")
    if not recipient:
        raise SetupError("test_recipient_required", "Explicitly select a test recipient in setup input before sending.")
    # Use the real platform transport; never bypass provider budgets via a raw SDK.
    import django
    django.setup()
    from apps.integrations.dispatch import dispatch_email
    from apps.audit.services import record
    record(None, "deployment.setup_test_mail_requested", meta={"provider": provider})
    log = dispatch_email(
        to_email=recipient, subject="Space Works setup verification",
        text_body="This explicitly requested setup message verifies provider acceptance. Confirm receipt separately in your inbox.",
        makerspace=None, stream="account", event="setup_test", audience="user",
        connection="platform", persist_body=False, sync=True,
    )
    if log.status != log.Status.SENT:
        raise SetupError("test_mail_not_accepted", "Verify the selected provider and sender; no fallback is attempted.")
    return {"status": "passed", "provider": provider, "send": "accepted", "inbox": "unconfirmed", "log_id": str(log.pk), "message_id_status": "recorded" if getattr(log, "provider_message_id", "") else "unavailable"}
