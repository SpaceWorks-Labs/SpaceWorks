"""Opt-in browser notifications for the personal inbox (X38, `notifications.web_push`).

A person opts in per space from their browser; each new inbox row they receive in that
space is then pushed to their subscribed browsers as an encrypted W3C Web Push message
(title, a short summary and the in-app link -- the same text the inbox already shows).
Riding the in-app channel means the person's existing channel choice, mutes and quiet
hours already decided that this row exists. Dormant until the deployment sets
`WEB_PUSH_VAPID_PRIVATE_KEY` and `WEB_PUSH_VAPID_SUBJECT`.

Subscription endpoints are user-supplied URLs the server will POST to, so only the
public push services are accepted (HTTPS, port 443, an allow-listed host): no SSRF.
A 404/410 from the push service retires the subscription; five failures in a row too.
"""

import json
import logging
import urllib.error
import urllib.request
from hashlib import sha256
from urllib.parse import urlsplit

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)
FEATURE = "notifications.web_push"
PUSH_HOSTS = ("fcm.googleapis.com", "android.googleapis.com", "updates.push.services.mozilla.com",
              "web.push.apple.com")
PUSH_SUFFIXES = (".push.services.mozilla.com", ".notify.windows.com", ".push.apple.com")
MAX_FAILURES = 5


def configured():
    return bool((settings.WEB_PUSH_VAPID_PRIVATE_KEY or "").strip() and (settings.WEB_PUSH_VAPID_SUBJECT or "").strip())


def public_key():
    from .browser_alert_crypto import public_key as derive
    return derive(settings.WEB_PUSH_VAPID_PRIVATE_KEY.strip()) if configured() else ""


def allowed_endpoint(endpoint):
    try:
        parts = urlsplit(endpoint)
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    return (parts.scheme == "https" and parts.port in (None, 443) and not parts.username and not parts.password
            and (host in PUSH_HOSTS or host.endswith(PUSH_SUFFIXES)) and len(endpoint) <= 1024)


def endpoint_hash(endpoint):
    return sha256(endpoint.encode()).hexdigest()


def enqueue(row_id):
    try:
        if configured():
            deliver_browser_alert.delay(row_id)
    except Exception:
        logger.warning("browser_alert_enqueue_failed", extra={"row_id": row_id})


def _payload(row):
    body = {"title": row.title[:120], "body": (row.summary or "")[:240], "url": row.link or "/",
            "tag": str(row.event_key)}
    return json.dumps(body, separators=(",", ":")).encode()


def _post(subscription, payload):
    from .browser_alert_crypto import encrypt, vapid_headers
    endpoint = subscription.get_endpoint()
    if not allowed_endpoint(endpoint):
        return 410
    body = encrypt(payload, subscription.p256dh, subscription.get_auth_secret())
    headers = vapid_headers(endpoint, settings.WEB_PUSH_VAPID_PRIVATE_KEY.strip(),
                            settings.WEB_PUSH_VAPID_SUBJECT.strip())
    request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


@shared_task
def deliver_browser_alert(row_id):
    from apps.makerspaces.platform import feature_enabled, module_enabled
    from .models_inbox import NotificationInboxRow
    row = NotificationInboxRow.objects.select_related("makerspace").filter(pk=row_id).first()
    if (row is None or not configured() or not module_enabled(row.makerspace, "notifications")
            or not feature_enabled(row.makerspace, FEATURE)):
        return 0
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    with fanout_tenant_write(row.makerspace_id, operation="browser_alert", counts={}) as allowed:
        return _deliver(row) if allowed else 0


def _deliver(row):
    from .models_browser_alerts import BrowserAlertSubscription
    sent = 0
    payload = _payload(row)
    for subscription in BrowserAlertSubscription.objects.filter(
            makerspace=row.makerspace, user_id=row.user_id, revoked_at__isnull=True).order_by("pk")[:10]:
        try:
            status = _post(subscription, payload)
        except Exception:
            status = 0
        now = timezone.now()
        if status in (200, 201, 202):
            subscription.last_sent_at, subscription.failures = now, 0
            sent += 1
        else:
            subscription.failures += 1
            if status in (404, 410) or subscription.failures >= MAX_FAILURES:
                subscription.revoked_at = now
        subscription.save(update_fields=["last_sent_at", "failures", "revoked_at"])
    return sent
