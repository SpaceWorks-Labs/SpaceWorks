"""Task, scheduler and live diagnostics. No business task or tenant data is created."""
from datetime import datetime, timezone
import time
import uuid

from probe_common import ProbeError, json_get


def worker():
    from config.celery import app
    from django.core.cache import cache
    from django.conf import settings
    if app.conf.task_always_eager:
        raise ProbeError("worker_eager_is_not_roundtrip")
    # J registers this bounded, nonce-only task. Shared cache acknowledgement works
    # with the existing result-backend=None default; never turn on a result store.
    cache_backend = settings.CACHES["default"]["BACKEND"].lower()
    if "locmem" in cache_backend or "dummy" in cache_backend:
        raise ProbeError("worker_requires_shared_cache")
    nonce = uuid.uuid4().hex
    key = "spaceworks:installer:roundtrip:" + nonce
    try:
        app.send_task("apps.operations.cloud_jobs.diagnostics.installer_roundtrip",
                      args=[nonce], expires=45, retry=False, ignore_result=True)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if cache.get(key) == nonce:
                return "task_roundtrip_verified"
            time.sleep(0.25)
        raise ProbeError("worker_roundtrip_timeout")
    finally:
        cache.delete(key)


def scheduler(snapshot, now=None):
    # J owns progress recording; V consumes facts, never manufactures freshness by
    # invoking run_scheduled_tasks itself. A start/claim timestamp is not success.
    now = now or datetime.now(timezone.utc)
    if (snapshot.get("schema_version") != 1 or snapshot.get("mode") not in {"beat", "loop", "external"}
            or snapshot.get("failed") is not False):
        raise ProbeError("scheduler_contract_or_failure")
    for key in ("heartbeat_at", "last_success_at"):
        value = snapshot.get(key)
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ProbeError("scheduler_missing_progress")
        if not -5 <= (now - value).total_seconds() <= 180:
            raise ProbeError("scheduler_stale")
    return "heartbeat_and_success_fresh"


def live():
    from apps.operations import live as transport
    # ALLOWED_HOSTS names the backend service, not every internal process.
    json_get("http://live:8000/api/v1/health/", host="backend")
    client = transport.redis_client()
    if client is None:
        # This is only an admitted brokerless full deployment, never a Redis outage.
        if transport.live_redis_url():
            raise ProbeError("live_transport_unavailable")
        json_get("http://backend:8000/api/v1/health/readiness/")
        return "poll_fallback_readiness_verified"
    channel = "spaceworks:installer:" + uuid.uuid4().hex
    nonce = uuid.uuid4().hex
    try:
        with client.pubsub() as subscription:
            subscription.subscribe(channel)
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                event = subscription.get_message(timeout=1)
                if event and event["type"] == "subscribe":
                    break
            else:
                raise ProbeError("live_subscribe_timeout")
            if not transport.publish(channel, nonce):
                raise ProbeError("live_publish_failed")
            while time.monotonic() < deadline:
                event = subscription.get_message(ignore_subscribe_messages=True, timeout=1)
                if event and event["data"] in (nonce, nonce.encode()):
                    return "publish_subscribe_verified"
            raise ProbeError("live_roundtrip_timeout")
    finally:
        client.close()
