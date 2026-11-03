"""Automatic IP blocking against credential stuffing (#62, Q7, Q12; decisions #157).

A failed sign-in counts once per (source, account) pair: ``cache.add`` of
``sec:ipf:<source>:<account>`` for the window, and only a NEW pair increments
``sec:ipn:<source>``. When one source has failed against ``LOGIN_IP_BLOCK_DISTINCT_ACCOUNTS``
different accounts inside ``LOGIN_IP_BLOCK_WINDOW_SECONDS`` it gets an ``IPAutoBlock`` for
exactly ``LOGIN_IP_BLOCK_SECONDS`` (one fixed length, no escalation, no decay). The source
is the client's IPv4 address (/32) or its IPv6 /64. A space's shared NAT is never blocked
by one person mistyping, however often: it takes many different accounts.

Never counted: an unparsable address, loopback, private (RFC 1918, carrier-grade NAT, IPv6
unique-local), link-local, a configured proxy hop, or a request whose X-Forwarded-For chain is shorter than
``TRUSTED_PROXY_COUNT`` (the resolved "client" would be a proxy). Every key stored or
audited is a keyed HMAC; the raw network lives only on the block row, for the superadmin.

Cache outage: the counters fail open (nothing is counted, nothing is blocked); existing
blocks are read from the database. Turnstile's "after N failures" counters live here too.
"""

import ipaddress
import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.settings import api_settings

from apps.accounts.ip_rules import parse_address

logger = logging.getLogger(__name__)
_KEY_SALT = "spaceworks.accounts.ip_guard.v1"
DEVICE_FAILURE_LIMIT = 10
PENDING_BLOCK = "_login_ip_block_pending"
_proxy_warning_logged = False
# RFC 1918, carrier-grade NAT (RFC 6598) and IPv6 unique-local: shared private networks.
# (``ipaddress.is_private`` would also cover the documentation ranges, which are public here.)
_NEVER_BLOCKED = tuple(ipaddress.ip_network(cidr) for cidr in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "fc00::/7"))


class ClientSource:
    """The resolved client of one request: address, its blocking network and HMAC key."""

    def __init__(self, address, countable):
        self.address = address
        self.countable = countable
        self.network = network_for(address) if address is not None else ""
        self.key = hmac_key("net", self.network) if self.network else ""


def hmac_key(kind, value):
    return salted_hmac(f"{_KEY_SALT}:{kind}", str(value), algorithm="sha256").hexdigest()


def network_for(address):
    prefix = 32 if address.version == 4 else 64
    return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False))


def account_key(identifier):
    value = str(identifier or "").strip().lower()
    return hmac_key("acct", value) if value else ""


def _proxy_hops(request):
    """``(chain_short, proxy_addresses)`` for the configured proxy count."""
    count = api_settings.NUM_PROXIES or 0
    remote = parse_address(request.META.get("REMOTE_ADDR"))
    if not count:
        return False, set()
    chain = [item.strip() for item in (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",") if item.strip()]
    hops = {remote} | {parse_address(item) for item in chain[len(chain) - count + 1:]} if chain else {remote}
    return len(chain) < count, {hop for hop in hops if hop is not None}


def client_source(request):
    """The request's client as seen by DRF throttles and axes, and whether it may count."""
    global _proxy_warning_logged
    from config.client_ip import get_throttle_client_ip

    address = parse_address(get_throttle_client_ip(request))
    if address is None:
        return ClientSource(None, False)
    short, proxies = _proxy_hops(request)
    if short and not _proxy_warning_logged:
        _proxy_warning_logged = True
        logger.warning("security.proxy_count_exceeds_hops",
                       extra={"trusted_proxy_count": api_settings.NUM_PROXIES})
    countable = not (short or address in proxies or address.is_loopback or address.is_link_local
                     or address.is_unspecified or address.is_multicast
                     or any(address in network for network in _NEVER_BLOCKED if network.version == address.version))
    return ClientSource(address, countable)


def _incr(key, timeout):
    """Increment a windowed counter; the window starts at the first increment."""
    if cache.add(key, 1, timeout):
        return 1
    try:
        return cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.add(key, 1, timeout)
        return 1


def _read(key):
    try:
        return int(cache.get(key) or 0)
    except Exception:
        logger.warning("ip_guard_cache_unavailable", exc_info=True)
        return 0


def record_failure(request, identifier):
    """One failed sign-in (``user_login_failed`` or S-B's ``login_refused``)."""
    if request is None:
        return
    source = client_source(request)
    account = account_key(identifier)
    window = settings.LOGIN_IP_BLOCK_WINDOW_SECONDS
    try:
        if source.key:
            _incr(f"sec:capf:ip:{source.key}", window)
        if account:
            _incr(f"sec:capf:acct:{account}", window)
        device = known_device_hmac(request)
        if device:
            _incr(f"sec:devf:{device}", window)
        if not (settings.LOGIN_IP_BLOCK_ENABLED and source.countable and account):
            return
        if not cache.add(f"sec:ipf:{source.key}:{account}", 1, window):
            return
        distinct = _incr(f"sec:ipn:{source.key}", window)
    except Exception:  # cache outage: fail open
        logger.warning("ip_guard_cache_unavailable", exc_info=True)
        return
    if distinct < settings.LOGIN_IP_BLOCK_DISTINCT_ACCOUNTS:
        return
    from django.db import connection

    if connection.in_atomic_block:
        # A failed sign-in inside a transaction is usually rolled back with it, and the
        # block must survive that: the middleware writes it once the response is built.
        setattr(getattr(request, "_request", request), PENDING_BLOCK, source)
    else:
        block(source)


def block(source):
    """Create (or renew an EXPIRED) automatic block; an active block is left alone."""
    from apps.accounts.models import IPAutoBlock
    from apps.audit import services as audit

    now = timezone.now()
    until = now + timedelta(seconds=settings.LOGIN_IP_BLOCK_SECONDS)
    row, created = IPAutoBlock.objects.get_or_create(
        ip_key=source.key, defaults={"network": source.network, "blocked_until": until, "created_at": now})
    if not created:
        if row.blocked_until > now:
            return row
        IPAutoBlock.objects.filter(pk=row.pk, blocked_until__lte=now).update(
            network=source.network, blocked_until=until, created_at=now)
    try:
        cache.delete(f"sec:ipn:{source.key}")
    except Exception:
        logger.warning("ip_guard_cache_unavailable", exc_info=True)
    audit.record(None, "auth.ip_auto_blocked", target_type="accounts.ipautoblock",
                 meta={"ip_key": source.key, "seconds": settings.LOGIN_IP_BLOCK_SECONDS})
    logger.warning("security.ip_auto_blocked", extra={"ip_key": source.key})
    return row


def active_block(source):
    """The live ``IPAutoBlock`` for this source, or None (read from the database)."""
    if not source.key:
        return None
    from apps.accounts.models import IPAutoBlock

    return IPAutoBlock.objects.filter(ip_key=source.key, blocked_until__gt=timezone.now()).first()


def failures(source, identifier=""):
    """The larger of this source's and this account's recent failures (Turnstile)."""
    counts = [_read(f"sec:capf:ip:{source.key}")] if source.key else [0]
    account = account_key(identifier)
    if account:
        counts.append(_read(f"sec:capf:acct:{account}"))
    return max(counts)


# --- Remembered-device bypass (Q12) ------------------------------------------------------
# LOCAL reader of S-B's signed ``sw_device`` cookie: ``signing.dumps({"d": <128-bit>},
# salt="accounts.device")``, stored as ``KnownDevice.device_hmac`` = this HMAC of ``d``.
# S-B replaces ``known_device_hmac`` with ``device_memory.lookup`` at its merge.
def known_device_hmac(request):
    """The HMAC of a valid remembered-device cookie that matches a live KnownDevice."""
    from django.core import signing

    from apps.accounts.login_security_contract import DEVICE_COOKIE
    from apps.accounts.models import KnownDevice

    raw = getattr(request, "COOKIES", {}).get(DEVICE_COOKIE)
    if not raw:
        return ""
    try:
        device = signing.loads(raw, salt="accounts.device", max_age=400 * 86400).get("d")
    except (signing.BadSignature, AttributeError):
        return ""
    if not isinstance(device, str) or not device:
        return ""
    digest = salted_hmac("spaceworks.accounts.device_memory.v1", device, algorithm="sha256").hexdigest()
    fresh = timezone.now() - timedelta(days=settings.LOGIN_REMEMBERED_DEVICE_DAYS)
    live = KnownDevice.objects.filter(device_hmac=digest, revoked_at__isnull=True, last_verified_at__gte=fresh)
    return digest if live.exists() else ""


def device_bypasses_auto_block(request):
    """A remembered device skips AUTOMATIC blocks (never deny rules) until it has failed
    ``DEVICE_FAILURE_LIMIT`` times inside the window itself."""
    device = known_device_hmac(request)
    return bool(device) and _read(f"sec:devf:{device}") < DEVICE_FAILURE_LIMIT
