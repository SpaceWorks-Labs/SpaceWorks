"""Counts-only API usage by channel and area, kept off the request's database path.

A *channel* is how the caller reached the API: ``web`` (browser session), ``ios`` / ``android``
(native device grants) or ``api_client`` (signed API clients and personal access tokens). An
*area* is the Django app that serves the route -- the repo's existing source-map taxonomy, not a
new one. Nothing identifying is counted: no person, session, address, user agent or path.

Hot path: one Redis ``HINCRBY`` into an hourly hash. Without Redis (cron mode) the count sits in
a small per-process buffer that is written to the database at most once a minute. The beat task
``flush_channel_usage_task`` drains the Redis hashes into ``ChannelUsageDay``. Counts are
approximate by design: a worker killed mid-flush may lose or repeat a few increments.
"""

import logging
import threading
import time
from datetime import UTC, timedelta

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)

CHANNELS = ("web", "ios", "android", "api_client")
PHONE_PLATFORM_CHANNEL = {"apple": "ios", "android": "android"}
KEY_PREFIX = "channel-usage"
BUCKET_TTL_SECONDS = 3 * 24 * 60 * 60
LOOKBACK_HOURS = 72
LOCAL_FLUSH_SECONDS = 60
_local = {}
_local_lock = threading.Lock()
_local_flushed_at = [time.monotonic()]


def area_for(request):
    """The app that serves this route (``events``, ``bookings``...), or ``other``."""
    match = getattr(request, "resolver_match", None)
    func = getattr(match, "func", None)
    target = getattr(func, "cls", None) or getattr(func, "view_class", None) or func
    parts = str(getattr(target, "__module__", "")).split(".")
    return parts[1][:48] if len(parts) > 2 and parts[0] == "apps" else "other"


def _bucket_key(at):
    return f"{KEY_PREFIX}:{at.astimezone(UTC):%Y%m%d%H}"


def _field(channel, area, space_id):
    return f"{channel}|{area}|{space_id or 0}"


def record_call(channel, request, makerspace_id=None, area=None):
    """Count one authenticated call. Never raises: telemetry must not fail a request."""
    try:
        if channel not in CHANNELS:
            return
        area = area or area_for(request)
        now = timezone.now()
        from apps.apiclients.telemetry import get_redis_client
        client = get_redis_client()
        if client is None:
            _buffer(channel, area, makerspace_id, now)
        elif not getattr(cache, "degraded", False):
            key = _bucket_key(now)
            pipe = client.pipeline()
            pipe.hincrby(key, _field(channel, area, makerspace_id), 1)
            pipe.expire(key, BUCKET_TTL_SECONDS)
            pipe.execute()
    except Exception:  # noqa: BLE001
        logger.warning("channel_usage_record_failed", exc_info=True)


def _buffer(channel, area, space_id, now):
    day = now.astimezone(UTC).date()
    with _local_lock:
        key = (channel, area, space_id, day)
        _local[key] = _local.get(key, 0) + 1
        due = time.monotonic() - _local_flushed_at[0] >= LOCAL_FLUSH_SECONDS
    if due:
        flush_local_buffer()


def flush_local_buffer():
    with _local_lock:
        pending = dict(_local)
        _local.clear()
        _local_flushed_at[0] = time.monotonic()
    return _write(pending)


def _write(counts):
    written = 0
    for (channel, area, space_id, day), n in counts.items():
        try:
            _upsert(channel, area, space_id, day, n)
            written += n
        except Exception:  # noqa: BLE001 -- one bad row (e.g. a purged space) never stops the rest
            logger.warning("channel_usage_write_failed", exc_info=True)
    return written


def _upsert(channel, area, space_id, day, n):
    from apps.accounts.models_activity import ChannelUsageDay
    rows = ChannelUsageDay.objects.filter(channel=channel, area=area, makerspace_id=space_id, day=day)
    if rows.update(count=F("count") + n):
        return
    try:
        with transaction.atomic():
            ChannelUsageDay.objects.create(channel=channel, area=area, makerspace_id=space_id, day=day, count=n)
    except IntegrityError:
        rows.update(count=F("count") + n)


def flush_usage():
    """Drain the in-process buffer and every Redis hour bucket into ``ChannelUsageDay``."""
    flushed = flush_local_buffer()
    from apps.apiclients.telemetry import get_redis_client
    client = get_redis_client()
    if client is None or getattr(cache, "degraded", False):
        return flushed
    now = timezone.now().replace(minute=0, second=0, microsecond=0)
    hours = [now - timedelta(hours=h) for h in range(LOOKBACK_HOURS + 1)]
    bases = [_bucket_key(at) for at in hours]
    pipe = client.pipeline()
    for base in bases:
        pipe.exists(base)
        pipe.exists(base + ":flushing")
    present = pipe.execute()
    for index, at in enumerate(hours):
        base, flushing = bases[index], bases[index] + ":flushing"
        if present[2 * index + 1]:
            flushed += _drain(client, flushing, at)  # leftover from an interrupted flush
        if present[2 * index]:
            try:
                client.rename(base, flushing)
            except Exception:  # noqa: BLE001 -- another worker took it first
                continue
            flushed += _drain(client, flushing, at)
    return flushed


def _drain(client, key, at):
    counts = {}
    day = at.astimezone(UTC).date()
    for field, value in client.hgetall(key).items():
        channel, area, space = str(field).split("|", 2)
        counts[(channel, area, int(space) or None, day)] = int(value)
    written = _write(counts)
    client.delete(key)
    return written
