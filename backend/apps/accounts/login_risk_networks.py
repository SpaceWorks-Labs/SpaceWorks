"""Familiar networks for the unusual-login check (#62; IPv6 per /64, #157).

A network is the client's IPv4 /24 or IPv6 /64 (S0's ``KnownNetwork`` granularities),
stored per person as a keyed HMAC, so the table never holds an address. It is familiar
when the person completed a sign-in from it in the last 90 days. The client address is
resolved exactly as DRF throttles, axes and the IP guard resolve it.
"""

import ipaddress

from django.utils import timezone
from django.utils.crypto import salted_hmac

from apps.accounts.login_security_contract import NETWORK_IPV4_24, NETWORK_IPV6_64, RETENTION

_SALT = "spaceworks.accounts.login_risk_networks.v1:"
WINDOW = RETENTION["accounts.KnownNetwork"][1]


def network_of(request):
    """``(granularity, network)`` for the request's client, or None when it has none."""
    from apps.accounts.ip_guard import client_source
    address = client_source(request).address if request is not None else None
    if address is None:
        return None
    granularity, prefix = (NETWORK_IPV4_24, 24) if address.version == 4 else (NETWORK_IPV6_64, 64)
    return granularity, str(ipaddress.ip_network(f"{address}/{prefix}", strict=False))


def prefix_hmac(granularity, network):
    return salted_hmac(_SALT + granularity, network, algorithm="sha256").hexdigest()


def is_familiar(user, request):
    """True when the client's network was seen for this person inside the window. A
    request with no usable address is not evidence of anything and counts as familiar."""
    from apps.accounts.models import KnownNetwork
    found = network_of(request)
    if found is None:
        return True
    granularity, network = found
    return KnownNetwork.objects.filter(
        user_id=user.pk, granularity=granularity, prefix_hmac=prefix_hmac(granularity, network),
        last_seen__gte=timezone.now() - WINDOW).exists()


def remember(user, request):
    """Mark the client's network as seen now; returns its readable label (for an alert)."""
    from apps.accounts.models import KnownNetwork
    found = network_of(request)
    if found is None:
        return None
    granularity, network = found
    KnownNetwork.objects.update_or_create(
        user_id=user.pk, granularity=granularity, prefix_hmac=prefix_hmac(granularity, network),
        defaults={"last_seen": timezone.now()})
    return network
