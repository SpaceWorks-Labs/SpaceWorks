"""Channel analytics hooks: which client an authenticated request came from.

Web sessions get one deployment-local ``WebSessionActivityDay`` row per session, space and day
(the browser twin of ``DeviceActivityDay``); phone grants keep theirs in ``device_activity``.
Every authenticated call is also counted by channel and app area (``channel_usage``). All of it
is counts only -- no address, user agent, token or session marker is stored -- and none of it
may fail a request, so every entry point swallows its own errors.
"""

import logging
import re
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .channel_usage import PHONE_PLATFORM_CHANNEL, record_call

logger = logging.getLogger(__name__)
APP_VERSION = re.compile(r"[0-9A-Za-z.+_-]{1,32}")
SPACES_TTL = 600
MAX_SPACES = 20


def app_version_from(request):
    """The optional ``X-SpaceWorks-App-Version`` build string; anything else counts as unknown ("")."""
    value = request.headers.get("X-SpaceWorks-App-Version", "")
    return value if APP_VERSION.fullmatch(value) else ""


def _stash(request, channel, space_id):
    """Tell the response-side middleware which channel this call used (the DRF wrapper hides it)."""
    raw = getattr(request, "_request", request)
    raw.sw_channel, raw.sw_channel_space = channel, space_id


def _active_space_ids(user):
    key = f"channel-activity-spaces:{user.pk}"
    try:
        cached = cache.get(key)
    except Exception:  # noqa: BLE001
        cached = None
    if cached is not None:
        return cached
    from apps.makerspaces.models import MakerspaceMembership
    ids = sorted(MakerspaceMembership.both_tracks().filter(user=user, status="active")
                 .values_list("makerspace_id", flat=True)[:MAX_SPACES])
    try:
        cache.set(key, ids, SPACES_TTL)
    except Exception:  # noqa: BLE001
        pass
    return ids


def _route_space_id(request):
    kwargs = getattr(getattr(request, "resolver_match", None), "kwargs", None) or {}
    for name in ("makerspace_id", "makerspace_pk"):
        try:
            return int(kwargs[name])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _web_space_id(request, user):
    """The space a web call belongs to: the route's own, else the person's only space."""
    space_id = _route_space_id(request)
    if space_id is not None:
        return space_id
    ids = _active_space_ids(user)
    return ids[0] if len(ids) == 1 else None


def _record_web_session_day(user, token):
    from .models_activity import WebSessionActivityDay
    marker = str(token.get("sid") or f"legacy:{user.pk}")
    digest = salted_hmac("web-session-activity", marker).hexdigest()[:32]
    now = timezone.now()
    key = f"web-activity:{digest}:{now:%Y%m%d%H}"
    try:
        if cache.get(key):
            return
    except Exception:  # noqa: BLE001
        logger.warning("web_activity_cache_unavailable")
    from apps.makerspaces.models import Makerspace
    ids = _active_space_ids(user)
    zones = dict(Makerspace.objects.filter(pk__in=ids).values_list("pk", "timezone")) if ids else {}
    for space_id in ids or [None]:
        day = timezone.localdate(now, ZoneInfo(zones.get(space_id) or settings.TIME_ZONE))
        WebSessionActivityDay.objects.get_or_create(
            user=user, session_hash=digest, makerspace_id=space_id, local_day=day)
    try:
        cache.set(key, True, 3600)
    except Exception:  # noqa: BLE001
        logger.warning("web_activity_cache_unavailable")


def note_web_request(request, user, token):
    """A browser-session call: dedupe one activity row per session, space and day; count the call."""
    try:
        _record_web_session_day(user, token)
        space_id = _web_space_id(request, user)
        _stash(request, "web", space_id)
        record_call("web", request, space_id)
    except Exception:  # noqa: BLE001 -- analytics never fails authentication
        logger.warning("web_activity_failed", exc_info=True)


def note_phone_request(request, grant, membership=None):
    """A native-grant call; the session-day row itself is ``device_activity.record_device_activity``."""
    try:
        channel = PHONE_PLATFORM_CHANNEL.get(grant.registration.platform)
        if channel is not None:
            space_id = membership.makerspace_id if membership is not None else None
            _stash(request, channel, space_id)
            record_call(channel, request, space_id)
    except Exception:  # noqa: BLE001
        logger.warning("phone_activity_failed", exc_info=True)
