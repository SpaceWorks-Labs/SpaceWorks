"""Platform IP allow/deny rules (#62, Q12): one cached list, read by the login IP guard.

The superadmin keeps the rules in ``/control/`` (``admin_ip_access``). An ALLOW rule
beats every DENY rule and every automatic block; a DENY rule always applies, even to a
remembered device. Rules are cached for 60 seconds and the cache is dropped whenever a
rule is saved or deleted. When the cache is unreachable the rules are read from the
database instead, so a cache outage never lifts a deny rule.
"""

import ipaddress
import logging

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.utils import timezone

from apps.accounts.login_security_contract import IP_ALLOW, IP_DENY

logger = logging.getLogger(__name__)
CACHE_KEY = "sec:iprules:v1"
CACHE_SECONDS = 60


def parse_address(value):
    """An ``ipaddress`` address, or None when ``value`` is not one (IPv4-mapped IPv6
    collapses to its IPv4 address so one rule covers both spellings)."""
    try:
        address = ipaddress.ip_address(str(value or "").strip())
    except ValueError:
        return None
    mapped = getattr(address, "ipv4_mapped", None)
    return mapped or address


def canonical_cidr(value):
    """The canonical network text of a rule, e.g. ``203.0.113.0/24`` (``ValueError``)."""
    return str(ipaddress.ip_network(str(value).strip(), strict=False))


def _load_from_database():
    from apps.accounts.models import IPAccessRule

    now = timezone.now()
    rows = IPAccessRule.objects.values_list("cidr", "action", "expires_at")
    return [(cidr, action, expires.timestamp() if expires else None)
            for cidr, action, expires in rows if expires is None or expires > now]


def active_rules():
    """``[(cidr, action, expires_ts | None)]`` for every rule that has not expired."""
    try:
        rules = cache.get(CACHE_KEY)
    except Exception:  # cache outage: the database still answers
        logger.warning("ip_rules_cache_unavailable", exc_info=True)
        return _load_from_database()
    if rules is None:
        rules = _load_from_database()
        try:
            cache.set(CACHE_KEY, rules, CACHE_SECONDS)
        except Exception:
            logger.warning("ip_rules_cache_unavailable", exc_info=True)
    now = timezone.now().timestamp()
    return [rule for rule in rules if rule[2] is None or rule[2] > now]


def covering(address, action, rules=None):
    """The rules of ``action`` whose network contains ``address`` (an ``ipaddress`` value)."""
    if address is None:
        return []
    found = []
    for cidr, rule_action, expires in active_rules() if rules is None else rules:
        if rule_action != action:
            continue
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue
        if network.version == address.version and address in network:
            found.append((cidr, rule_action, expires))
    return found


def decision(address):
    """``(IP_ALLOW | IP_DENY | None, retry_after_seconds | None)`` for this address.

    Allow beats deny. A deny without an expiry reports no retry time."""
    rules = active_rules()
    if covering(address, IP_ALLOW, rules):
        return IP_ALLOW, None
    denies = covering(address, IP_DENY, rules)
    if not denies:
        return None, None
    expiries = [expires for _cidr, _action, expires in denies]
    if any(expires is None for expires in expiries):
        return IP_DENY, None
    return IP_DENY, max(1, int(max(expiries) - timezone.now().timestamp()))


def invalidate(**_kwargs):
    try:
        cache.delete(CACHE_KEY)
    except Exception:
        logger.warning("ip_rules_cache_unavailable", exc_info=True)


def connect_signals():
    from apps.accounts.models import IPAccessRule

    for signal in (post_save, post_delete):
        signal.connect(invalidate, sender=IPAccessRule, dispatch_uid=f"accounts.ip_rules.{signal}")


def axes_whitelisted(request, credentials=None, *args, **kwargs):
    """``AXES_WHITELIST_CALLABLE``: never lock out the platform superadmin's own allow-listed
    address. Exempt only when the address is ALLOW-listed AND the username is the platform
    superadmin; everyone else on that network is counted as usual."""
    from apps.accounts.models import User
    from apps.accounts.staff_identity import platform_q
    from config.client_ip import get_throttle_client_ip

    username = (credentials or {}).get("username") if isinstance(credentials, dict) else None
    if not username or request is None:
        return False
    try:
        if not covering(parse_address(get_throttle_client_ip(request)), IP_ALLOW):
            return False
    except Exception:
        logger.warning("axes_whitelist_check_failed", exc_info=True)
        return False
    return User.objects.filter(platform_q(), username=username, is_active=True).exists()
