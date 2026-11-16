import ipaddress
import json
import logging
from datetime import UTC, datetime
from functools import lru_cache

import redis
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from config.client_ip import get_throttle_client_ip

logger = logging.getLogger(__name__)

BUCKET_TTL_SECONDS = 2 * 24 * 60 * 60
KEY_PREFIX = "apiclients:usage"
SIGNED_KIND = "signed"
BROWSER_KIND = "browser"


@lru_cache(maxsize=4)
def _client_for_url(url):
    # Short timeouts: this runs inside signed-request authentication (decision 339).
    return redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=1, socket_timeout=2)


def get_redis_client():
    """Return the configured Redis cache client, or None for non-Redis installs."""
    config = settings.CACHES.get("default", {})
    if not str(config.get("BACKEND", "")).endswith("RedisCache"):  # RedisCache or ResilientRedisCache
        return None
    location = config.get("LOCATION")
    if isinstance(location, (list, tuple)):
        location = location[0] if location else ""
    return _client_for_url(str(location)) if location else None


def bucket_key(kind, observed_at):
    minute = observed_at.astimezone(UTC).replace(second=0, microsecond=0)
    return f"{KEY_PREFIX}:{kind}:{minute:%Y%m%d%H%M}"


def record_signed_client_observation(request, client):
    _record_observation(SIGNED_KIND, request, client.client_id)


def record_browser_client_observation(request, client):
    # Browser identity is public and forgeable, so it has a distinct namespace.
    _record_observation(BROWSER_KIND, request, client.client_id)


def _record_observation(kind, request, client_id):
    try:
        observed_at = timezone.now()
        payload = json.dumps(
            {
                "timestamp": observed_at.isoformat(),
                "resolved_ip": _resolved_ip(request),
            },
            separators=(",", ":"),
        )
        redis_client = get_redis_client()
        if redis_client is None:
            _remember_without_redis(kind, client_id, payload, observed_at)
            return
        if getattr(cache, "degraded", False):
            return  # Redis is down; the cache already logged the outage once for this process
        key = bucket_key(kind, observed_at)
        pipeline = redis_client.pipeline()
        pipeline.hset(key, client_id, payload)
        pipeline.expire(key, BUCKET_TTL_SECONDS)
        pipeline.execute()
    except Exception:  # noqa: BLE001 - telemetry must never fail authentication
        logger.warning(
            "ApiClient usage telemetry Redis write failed",
            extra={"client_id": client_id, "telemetry_kind": kind},
            exc_info=True,
        )


def _last_key(kind, client_id):
    return f"{KEY_PREFIX}:last:{kind}:{client_id}"


def _remember_without_redis(kind, client_id, payload, observed_at):
    """Cron mode (no Redis): keep each client's newest observation in the shared database cache.

    At most one write per client per minute, so a busy client does not turn every signed request
    into a cache write; the flush reads these keys for the deployment's known clients.
    """
    minute = observed_at.astimezone(UTC).strftime("%Y%m%d%H%M")
    if cache.add(f"{KEY_PREFIX}:seen:{kind}:{client_id}:{minute}", 1, 120):
        cache.set(_last_key(kind, client_id), payload, BUCKET_TTL_SECONDS)


def _flush_without_redis():
    from apps.apiclients.models import ApiClient

    client_ids = list(ApiClient.objects.filter(is_active=True).values_list("client_id", flat=True))
    keys = {_last_key(kind, client_id): (kind, client_id)
            for client_id in client_ids for kind in (SIGNED_KIND, BROWSER_KIND)}
    newest = {}
    for key, raw_payload in cache.get_many(list(keys)).items():
        observation = _parse_observation(raw_payload)
        if observation is not None:
            newest[keys[key]] = observation
    return _bulk_update_observations(newest)


def _resolved_ip(request):
    return _normalize_ip(get_throttle_client_ip(request))


def _normalize_ip(raw):
    try:
        return str(ipaddress.ip_address(raw)) if raw else None
    except (TypeError, ValueError):
        return None


def flush_usage_observations(*, now=None, redis_client=None):
    """Persist closed Redis buckets with one monotonic bulk update."""
    redis_client = redis_client or get_redis_client()
    if redis_client is None:
        return _flush_without_redis()
    current_minute = (now or timezone.now()).astimezone(UTC).replace(
        second=0, microsecond=0
    )
    newest = {}
    consumed_keys = []
    for kind in (SIGNED_KIND, BROWSER_KIND):
        for raw_key in redis_client.scan_iter(match=f"{KEY_PREFIX}:{kind}:*"):
            key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
            bucket = _parse_bucket(key)
            if bucket is None or bucket >= current_minute:
                continue
            # Detach the bucket before reading it. HGETALL followed by DEL is not atomic:
            # a request that selected this minute just before the boundary but executed its
            # HSET between the two would be deleted unseen, and a low-frequency client's
            # last_seen_at would stay stale. RENAME is atomic, so a late write lands in a
            # freshly recreated bucket that the next flush picks up.
            drained_key = f"{key}:draining"
            try:
                redis_client.rename(key, drained_key)
            except redis.ResponseError:
                # The bucket vanished between the scan and here -- a concurrent flush took
                # it. Not an error, and not ours to process.
                continue
            except Exception:
                # Anything else is a real Redis problem. Log it: swallowing it silently
                # would stop all usage telemetry while looking like an idle deployment,
                # which is exactly the wrong signal for deciding a client is stale.
                logger.warning(
                    "api_client_usage_bucket_detach_failed",
                    extra={"bucket": key},
                    exc_info=True,
                )
                continue
            consumed_keys.append(drained_key)
            for raw_client_id, raw_payload in redis_client.hgetall(drained_key).items():
                client_id = (
                    raw_client_id.decode()
                    if isinstance(raw_client_id, bytes)
                    else raw_client_id
                )
                observation = _parse_observation(raw_payload)
                if observation is None:
                    continue
                lookup = (kind, client_id)
                if lookup not in newest or observation[0] > newest[lookup][0]:
                    newest[lookup] = observation

    updated = _bulk_update_observations(newest)
    if consumed_keys:
        redis_client.delete(*consumed_keys)
    return updated


def _parse_bucket(key):
    try:
        return datetime.strptime(key.rsplit(":", 1)[1], "%Y%m%d%H%M").replace(
            tzinfo=UTC
        )
    except (IndexError, ValueError):
        return None


def _parse_observation(raw_payload):
    try:
        if isinstance(raw_payload, bytes):
            raw_payload = raw_payload.decode()
        payload = json.loads(raw_payload)
        observed_at = parse_datetime(payload["timestamp"])
        if observed_at is None:
            return None
        if timezone.is_naive(observed_at):
            observed_at = timezone.make_aware(observed_at, UTC)
        return observed_at, _normalize_ip(payload.get("resolved_ip"))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _bulk_update_observations(newest):
    from apps.apiclients.models import ApiClient

    client_ids = {client_id for _kind, client_id in newest}
    if not client_ids:
        return 0
    with transaction.atomic():
        clients = list(
            ApiClient.objects.select_for_update().filter(client_id__in=client_ids)
        )
        changed = []
        for client in clients:
            candidates = [newest.get((SIGNED_KIND, client.client_id))]
            if client.client_type == BROWSER_KIND:
                candidates.append(newest.get((BROWSER_KIND, client.client_id)))
            observation = max(
                (item for item in candidates if item),
                key=lambda item: item[0],
                default=None,
            )
            if observation is None or (
                client.last_seen_at is not None and observation[0] <= client.last_seen_at
            ):
                continue
            client.last_seen_at, client.last_seen_ip = observation
            changed.append(client)
        if changed:
            ApiClient.objects.bulk_update(changed, ["last_seen_at", "last_seen_ip"])
    return len(changed)
