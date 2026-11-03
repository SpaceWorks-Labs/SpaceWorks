"""The per-space staff IP allow-list (#110c, #128 C-2: ``security.staff_ip_allowlist``).

It guards a space's STAFF routes only, at the staff surface check
(``surface_policy._staff_admits``), never the shared sign-in door: one account per person,
so refusing the sign-in would also lock a staff member out of their member features.

- A route that targets spaces needs the client inside the allow-list of EVERY targeted
  space that has one (an empty list allows any address).
- A route with no target space (space-less staff screens, e.g. the console's start page)
  needs the client inside every non-empty allow-list across the person's staff spaces:
  the strictest across them.
- The superadmin never reaches this check (platform surface; #110 superadmin always on).

A settings read failure falls back to the platform default, an empty list (allow any), the
same way the staff session limits fall back to theirs; it is logged as an error.
"""

import ipaddress
import logging

from rest_framework.exceptions import PermissionDenied

from apps.accounts.login_security_contract import STAFF_IP_ALLOWLIST, STAFF_NETWORK_REFUSED

logger = logging.getLogger(__name__)
_MEMO = "_staff_network_lists"


def _lists(request, user, targets):
    from apps.accounts.staff_identity import staff_makerspace_ids
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.security_settings_person import space_value

    ids = frozenset(int(target) for target in targets) if targets else frozenset(staff_makerspace_ids(user))
    memo = getattr(request, _MEMO, None)
    if memo is None:
        memo = {}
        setattr(request, _MEMO, memo)
    if ids not in memo:
        try:
            memo[ids] = [value for space in Makerspace.objects.filter(pk__in=ids)
                         if (value := space_value(space, STAFF_IP_ALLOWLIST))]
        except Exception:
            logger.exception("staff_ip_allowlist_unreadable")
            memo[ids] = []
    return memo[ids]


def _inside(address, cidrs):
    for cidr in cidrs:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue
        if network.version == address.version and address in network:
            return True
    return False


def allowed(request, user, targets):
    lists = _lists(request, user, targets)
    if not lists:
        return True
    from apps.accounts.ip_rules import parse_address
    from config.client_ip import get_throttle_client_ip

    address = parse_address(get_throttle_client_ip(request))
    return address is not None and all(_inside(address, cidrs) for cidrs in lists)


def assert_staff_network(request, user, targets):
    """Refuse a staff route from a network the space's staff IP allow-list leaves out."""
    if not allowed(request, user, targets):
        raise PermissionDenied({"detail": "Staff screens of this space are not available from this network.",
                                "code": STAFF_NETWORK_REFUSED})
