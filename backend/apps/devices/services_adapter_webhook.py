"""Webhook push for adapters that prefer push over polling (decision 310 addendum).

A push is a WAKE-UP, never the work itself: the adapter still leases commands and jobs over the signed API, so a
lost or forged push changes nothing. Payloads are a small typed envelope, content-free by default (ids and a type);
staff can opt in to the command/capability names (``include_data``), never parameters, poses or member data.

* Signature: ``X-SpaceWorks-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, "<t>.<body>")>``; the receiver should reject
  a timestamp older than five minutes. The secret is derived (not stored), shown once at create or rotate.
* Delivery: Celery, exponential backoff (``BACKOFF_SECONDS``), ``MAX_ATTEMPTS`` tries per delivery, a delivery log row
  per push, and the endpoint auto-disables after ``DISABLE_AFTER`` consecutive failed attempts.
* Target: public https only on port 443 or 8443, resolved ONCE at send time and dialled at that exact address
  through the shared bounded transport (``apps.outbound_policy`` / ``apps.outbound_http``: every DNS answer must be
  a global address, no redirects, no proxies, at most ``REPLY_BYTES`` of the reply read, one overall deadline), so
  DNS rebinding cannot aim a push into the network. Staff see only delivered or failed: no status code or network
  error detail is kept for a failed attempt, so the delivery log is not a port scanner (security review M1).
"""
import hashlib
import hmac
import json
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.devices.adapter_access import adapters_enabled, authorize_staff, scoped_adapter
from apps.devices.models import AdapterWebhook, AdapterWebhookDelivery
from apps.devices.services_adapter_core import AdapterError
from apps.devices.services_locks import lock_tenant

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 6
DISABLE_AFTER = 10
BACKOFF_SECONDS = (30, 120, 600, 1800, 3600)
TIMEOUT_SECONDS = 5
RETENTION_DAYS = 14
PORTS = frozenset({443, 8443})
REPLY_BYTES = 4096
LEASE_SECONDS = 60  # longer than one push can take (the push task is hard-killed at 45 s); an expired lease retries
SWEEP_BATCH = 40  # 40 x TIMEOUT_SECONDS stays inside the sweep task's soft limit; the rest wait a minute
from apps.devices.adapters.webhook import EVENT_TYPES  # noqa: E402,F401  (the published envelope schema)


def secret_for(webhook):
    key = hashlib.sha256(settings.SECRET_KEY.encode("utf-8") + b"adapter-webhook").digest()
    message = f"{webhook.makerspace_id}:{webhook.pk}:{webhook.secret_version}".encode("utf-8")
    return "whsec_" + hmac.new(key, message, hashlib.sha256).hexdigest()


def sign(secret, timestamp, body):
    return hmac.new(secret.encode("utf-8"), f"{timestamp}.".encode("utf-8") + body, hashlib.sha256).hexdigest()


def _clean_url(url):
    from apps.outbound_policy import is_public_https
    if not is_public_https(url, ports=PORTS):
        raise AdapterError("webhook_url_refused", "The push URL must be a public https address on port 443 or 8443.")
    return url


def _post(url, body, headers):
    """The real push: resolve once, pin, POST, read at most REPLY_BYTES; -> status code."""
    from apps import outbound_http, outbound_policy
    target = outbound_policy.resolve(url, ports=PORTS)
    return outbound_http.send(target, "POST", body=body, headers=headers, max_bytes=REPLY_BYTES, truncate=True,
                              connect_timeout=TIMEOUT_SECONDS, read_timeout=TIMEOUT_SECONDS,
                              deadline=TIMEOUT_SECONDS).status


def _staff_device(actor, device_id):
    # The endpoint receives events for every target the adapter serves: all its machines must be in scope (336i).
    device = scoped_adapter(actor, device_id, whole=True)
    authorize_staff(actor, device.makerspace_id)
    return device


def set_webhook(actor, device_id, url, include_data=False):
    """Create or change the endpoint. Returns ``(webhook, secret_or_None)``: the secret only on first creation."""
    device = _staff_device(actor, device_id)
    url = _clean_url(url)
    with transaction.atomic():
        makerspace = lock_tenant(device.makerspace_id)
        hook = AdapterWebhook.objects.select_for_update().filter(device=device).first()
        secret = None
        if hook is None:
            hook = AdapterWebhook.objects.create(device=device, makerspace=makerspace, url=url,
                                                 include_data=include_data, created_by=actor)
            secret = secret_for(hook)
        else:
            hook.url, hook.include_data = url, include_data
            hook.enabled, hook.disabled_at, hook.disabled_reason, hook.consecutive_failures = True, None, "", 0
            hook.save(update_fields=["url", "include_data", "enabled", "disabled_at", "disabled_reason",
                                     "consecutive_failures"])
        audit.record(actor, "devices.adapter_webhook_set", makerspace=makerspace, target=device, meta={
            "device_id": str(device.pk), "include_data": include_data, "created": secret is not None})
    return hook, secret


def rotate(actor, device_id):
    device = _staff_device(actor, device_id)
    with transaction.atomic():
        makerspace = lock_tenant(device.makerspace_id)
        hook = AdapterWebhook.objects.select_for_update().filter(device=device).first()
        if hook is None:
            from rest_framework.exceptions import NotFound
            raise NotFound()
        hook.secret_version += 1
        hook.save(update_fields=["secret_version"])
        audit.record(actor, "devices.adapter_webhook_rotated", makerspace=makerspace, target=device,
                     meta={"device_id": str(device.pk), "secret_version": hook.secret_version})
    return hook, secret_for(hook)


def disable(actor, device_id):
    device = _staff_device(actor, device_id)
    with transaction.atomic():
        makerspace = lock_tenant(device.makerspace_id)
        updated = AdapterWebhook.objects.filter(device=device, enabled=True).update(
            enabled=False, disabled_at=timezone.now(), disabled_reason="staff")
        if updated:
            audit.record(actor, "devices.adapter_webhook_disabled", makerspace=makerspace, target=device,
                         meta={"device_id": str(device.pk), "reason": "staff"})


def get_webhook(actor, device_id):
    from rest_framework.exceptions import NotFound
    device = _staff_device(actor, device_id)
    hook = AdapterWebhook.objects.filter(device=device).first()
    if hook is None:
        raise NotFound()
    return hook


def recent_deliveries(actor, device_id, limit=50):
    device = _staff_device(actor, device_id)
    return list(AdapterWebhookDelivery.objects.filter(device=device)[:limit])


def wake(device, event_type, *, binding_id=None, capability="", command=""):
    """Record a push for this adapter if it has an enabled endpoint; never raises into the caller's workflow."""
    try:
        hook = AdapterWebhook.objects.filter(device=device, enabled=True).first()
        if hook is None:
            return None
        envelope = {"id": str(uuid.uuid4()), "type": event_type, "api_version": 1, "device_id": str(device.pk),
                    "binding_id": str(binding_id) if binding_id else None, "created_at": int(timezone.now().timestamp())}
        if hook.include_data and capability:
            envelope["data"] = {"capability": capability, **({"command": command} if command else {})}
        row = AdapterWebhookDelivery.objects.create(makerspace_id=device.makerspace_id, device=device,
                                                    event_type=event_type, envelope=envelope)
        from apps.devices.tasks import deliver_adapter_webhook_task
        transaction.on_commit(lambda: deliver_adapter_webhook_task.delay(str(row.pk)))
        return row
    except Exception:  # noqa: BLE001 - a push problem must never fail the workflow that caused it
        logger.warning("adapter webhook wake failed", exc_info=True)
        return None


def _fail(row, hook, now, *, code):
    row.attempts += 1
    row.last_status_code, row.last_error = None, code
    dead = row.attempts >= MAX_ATTEMPTS
    row.status = AdapterWebhookDelivery.Status.DEAD if dead else AdapterWebhookDelivery.Status.PENDING
    row.next_attempt_at = now + timedelta(seconds=BACKOFF_SECONDS[min(row.attempts - 1, len(BACKOFF_SECONDS) - 1)])
    row.save(update_fields=["attempts", "last_status_code", "last_error", "status", "next_attempt_at"])
    hook.consecutive_failures += 1
    if hook.consecutive_failures >= DISABLE_AFTER:
        hook.enabled, hook.disabled_at, hook.disabled_reason = False, now, "too_many_failures"
        audit.record(None, "devices.adapter_webhook_disabled", makerspace=hook.makerspace, target=hook.device,
                     meta={"device_id": str(hook.device_id), "reason": "too_many_failures"})
    hook.save(update_fields=["consecutive_failures", "enabled", "disabled_at", "disabled_reason"])


def deliver(delivery_id, *, now=None, post=None):
    """One attempt. ``post`` is injectable for tests; the default is ``_post`` (pinned, bounded, no redirects).

    The outbound POST runs OUTSIDE any transaction: the row is claimed with a short lease (``LEASE_SECONDS``) so a
    concurrent sweep or duplicate task skips it, the push is sent, and the outcome is recorded in a second
    transaction. A worker killed mid-push leaves the lease to expire and the sweep retries it; the receiver
    deduplicates on ``X-SpaceWorks-Delivery``.
    """
    now = now or timezone.now()
    claimed = _claim(delivery_id, now)
    if isinstance(claimed, str):
        return claimed
    url, body, headers = claimed
    from apps.outbound_policy import OutboundRefused
    try:
        code = (post or _post)(url, body, headers)
    except OutboundRefused:  # the name now resolves somewhere it may not go: refused before any connection
        code = "refused"
    except Exception:  # noqa: BLE001 - network failure is a retryable outcome, never an error to the caller
        logger.info("adapter webhook push failed", exc_info=True)
        code = None
    return _record(delivery_id, now, code)


def _claim(delivery_id, now):
    """-> (url, body, headers) to send, or the outcome string when there is nothing to send."""
    with transaction.atomic():
        row = AdapterWebhookDelivery.objects.select_for_update().filter(
            pk=delivery_id, status=AdapterWebhookDelivery.Status.PENDING, next_attempt_at__lte=now).first()
        if row is None:
            return "skipped"
        hook = AdapterWebhook.objects.select_for_update().select_related("makerspace", "device").filter(
            device_id=row.device_id).first()
        if hook is None or not hook.enabled:
            row.status, row.last_error = AdapterWebhookDelivery.Status.DEAD, "endpoint_disabled"
            row.save(update_fields=["status", "last_error"])
            return "dead"
        if not adapters_enabled(row.makerspace_id):
            return "skipped"  # switched off for this space: nothing is sent, the row waits (module audit 0.12.0)
        try:
            _clean_url(hook.url)
        except AdapterError:
            _fail(row, hook, now, code="url_refused")
            return "failed"
        body = json.dumps(row.envelope, separators=(",", ":"), sort_keys=True).encode("utf-8")
        stamp = int(now.timestamp())
        headers = {"Content-Type": "application/json", "User-Agent": "SpaceWorks-Adapter-Push/1",
                   "X-SpaceWorks-Event": row.event_type, "X-SpaceWorks-Delivery": str(row.pk),
                   "X-SpaceWorks-Signature": f"t={stamp},v1={sign(secret_for(hook), stamp, body)}"}
        row.next_attempt_at = now + timedelta(seconds=LEASE_SECONDS)
        row.save(update_fields=["next_attempt_at"])
        return hook.url, body, headers


def _record(delivery_id, now, code):
    with transaction.atomic():
        row = AdapterWebhookDelivery.objects.select_for_update().filter(
            pk=delivery_id, status=AdapterWebhookDelivery.Status.PENDING).first()
        hook = AdapterWebhook.objects.select_for_update().select_related("makerspace", "device").filter(
            device_id=row.device_id).first() if row else None
        if row is None or hook is None:
            return "skipped"
        if isinstance(code, int) and 200 <= code < 300:
            row.status, row.attempts, row.last_status_code = AdapterWebhookDelivery.Status.DELIVERED, row.attempts + 1, code
            row.delivered_at, row.last_error = now, ""
            row.save(update_fields=["status", "attempts", "last_status_code", "delivered_at", "last_error"])
            AdapterWebhook.objects.filter(pk=hook.pk).update(consecutive_failures=0, last_success_at=now)
            return "delivered"
        _fail(row, hook, now, code="url_refused" if code == "refused" else "delivery_failed")
        return "failed"


def sweep(now=None):
    """Retry due deliveries and prune old log rows (Celery beat, every minute), one tenant boundary per space."""
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    now = now or timezone.now()
    pending = AdapterWebhookDelivery.objects.filter(status=AdapterWebhookDelivery.Status.PENDING, next_attempt_at__lte=now)
    old = AdapterWebhookDelivery.objects.filter(status__in=("delivered", "dead"),
                                                created_at__lt=now - timedelta(days=RETENTION_DAYS))
    spaces = sorted(set(pending.values_list("makerspace_id", flat=True).distinct().order_by())
                    | set(old.values_list("makerspace_id", flat=True).distinct().order_by()))
    counts, results, pruned, budget = {"skipped": 0}, [], 0, SWEEP_BATCH
    for space_id in spaces:
        with fanout_tenant_write(space_id, operation="devices.adapter_webhook", counts=counts) as should_process:
            if not should_process:
                continue
            pruned += old.filter(makerspace_id=space_id).delete()[0]
            # A space with the adapters switched off sends nothing; its rows wait and never use the batch budget.
            if budget <= 0 or not adapters_enabled(space_id):
                continue
            due = list(pending.filter(makerspace_id=space_id).values_list("pk", flat=True)[:budget])
            budget -= len(due)
            results += [deliver(pk, now=now) for pk in due]
    return {"attempted": len(results), "delivered": results.count("delivered"), "pruned": pruned,
            "skipped_spaces": counts["skipped"]}
