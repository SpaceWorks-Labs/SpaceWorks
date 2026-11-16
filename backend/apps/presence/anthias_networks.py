"""Networks an Anthias call may never reach even when private LAN addresses are allowed (decision 336(g)).

A player lives on the space's LAN, so private addresses can be allowed; the deployment's OWN service networks
(the compose network holding the database, Redis, MinIO, Metabase, Grafana ...) are never a player. They are:

* every network named in ``OUTBOUND_BLOCKED_NETWORKS`` (comma-separated CIDRs, set by the operator);
* inside a container (``/.dockerenv``), every directly connected IPv4 network from ``/proc/net/route``: the
  container reaches the space's LAN through its gateway, so a directly connected network is a service network;
* the server's own addresses.

The answer is cached for five minutes; a failure to read the route table blocks nothing extra (the explicit
setting and the always-refused ranges in ``apps.outbound_policy`` still apply).
"""
import socket
import struct
import time
from ipaddress import IPv4Network, ip_address, ip_network
from pathlib import Path

from django.conf import settings

CACHE_SECONDS = 300
_cache = {"at": None, "value": ()}


def _configured():
    nets = []
    for raw in getattr(settings, "OUTBOUND_BLOCKED_NETWORKS", ()) or ():
        try:
            nets.append(ip_network(str(raw).strip(), strict=False))
        except ValueError:
            continue
    return nets


def _connected(route_file="/proc/net/route", marker="/.dockerenv"):
    if not Path(marker).exists():
        return []
    nets = []
    try:
        lines = Path(route_file).read_text().splitlines()[1:]
    except OSError:
        return []
    for line in lines:
        fields = line.split()
        if len(fields) < 8 or fields[2] != "00000000" or fields[1] == "00000000":
            continue
        try:
            network = socket.inet_ntoa(struct.pack("<L", int(fields[1], 16)))
            mask = socket.inet_ntoa(struct.pack("<L", int(fields[7], 16)))
            nets.append(IPv4Network(f"{network}/{mask}", strict=False))
        except (ValueError, struct.error, OSError):
            continue
    return nets


def _own_addresses():
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None)
    except (OSError, UnicodeError):
        return []
    out = []
    for info in infos:
        try:
            out.append(ip_network(ip_address(str(info[4][0]).split("%", 1)[0])))
        except ValueError:
            continue
    return out


def service_networks():
    now = time.monotonic()
    if _cache["at"] is None or now - _cache["at"] > CACHE_SECONDS:
        _cache["value"] = tuple(_configured() + _connected() + _own_addresses())
        _cache["at"] = now
    return _cache["value"]


def reset_cache():
    _cache["at"] = None
