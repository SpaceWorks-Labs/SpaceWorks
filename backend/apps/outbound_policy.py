"""The one address policy for server-side calls to tenant-configured destinations.

Device webhooks, the image adapter (and the mask URLs its provider returns) and Anthias players all resolve
their host name through ``resolve`` exactly ONCE, every answer is checked here, and ``apps.outbound_http``
then connects to those exact addresses (pinned), so a second DNS answer can never swap the target
(DNS rebinding).

* Always refused, whatever the caller allows: loopback, unspecified, link-local (169.254.0.0/16 holds the
  common cloud metadata address 169.254.169.254), the Alibaba metadata address 100.100.100.200, the AWS IPv6
  metadata range, multicast, reserved and site-local addresses, any extra network the caller names (the
  deployment's own service networks for Anthias), and IPv6 forms that embed one of those IPv4 addresses
  (IPv4-mapped, NAT64 64:ff9b::/96 and 64:ff9b:1::/48, 6to4 2002::/16).
* Non-global (RFC 1918, carrier-grade NAT 100.64.0.0/10, unique-local fc00::/7): refused unless the caller
  passes ``allow_private=True`` (Anthias, decision 325 / 336(g); the superadmin's platform image adapter).
* Loopback is refused unless ``allow_loopback=True``, which only the superadmin-configured platform image
  adapter passes (an operator may run the provider beside SpaceWorks on one host). Metadata never.
"""
import socket
from dataclasses import dataclass
from ipaddress import IPv4Address, ip_address, ip_network
from urllib.parse import urlsplit

ALWAYS_BLOCKED = tuple(ip_network(net) for net in (
    "0.0.0.0/8", "169.254.0.0/16", "100.100.100.200/32", "224.0.0.0/4", "240.0.0.0/4",
    "::/128", "fe80::/10", "fec0::/10", "ff00::/8", "fd00:ec2::/32",
))
LOOPBACK = (ip_network("127.0.0.0/8"), ip_network("::1/128"))
_NAT64 = (ip_network("64:ff9b::/96"), ip_network("64:ff9b:1::/48"))
_SIXTOFOUR = ip_network("2002::/16")
DEFAULT_PORTS = {"https": 443, "http": 80}


class OutboundRefused(ValueError):
    """The destination is malformed, unresolvable or not allowed. ``reason`` is a short code, never a body."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class PinnedAddress:
    family: int
    sockaddr: tuple

    @property
    def ip(self):
        return str(self.sockaddr[0]).split("%", 1)[0]


@dataclass(frozen=True)
class Target:
    scheme: str
    hostname: str
    port: int
    host_header: str
    request_target: str
    addresses: tuple

    def with_path(self, request_target):
        """The same pinned destination with another path (Anthias calls several routes on one host)."""
        return Target(self.scheme, self.hostname, self.port, self.host_header, request_target, self.addresses)


def _embedded_v4(address):
    if address.version != 6:
        return None
    if address.ipv4_mapped is not None:
        return address.ipv4_mapped
    if any(address in net for net in _NAT64):
        return IPv4Address(int(address) & 0xFFFFFFFF)
    if address in _SIXTOFOUR:
        return IPv4Address((int(address) >> 80) & 0xFFFFFFFF)
    return None


def refusal(raw, *, allow_private=False, extra_blocked=(), allow_loopback=False):
    """The reason ``raw`` (an IP string) may not be dialled, or None when it may."""
    try:
        address = ip_address(str(raw).split("%", 1)[0])
    except ValueError:
        return "blocked_address"
    inner = _embedded_v4(address)
    if inner is not None:
        return refusal(inner, allow_private=allow_private, extra_blocked=extra_blocked, allow_loopback=False)
    if any(address in net for net in LOOPBACK):
        return None if allow_loopback else "blocked_address"
    if (address.is_unspecified or address.is_link_local or address.is_multicast
            or address.is_reserved or getattr(address, "is_site_local", False)
            or any(address in net for net in ALWAYS_BLOCKED)
            or any(address.version == net.version and address in net for net in extra_blocked)):
        return "blocked_address"
    if not address.is_global and not allow_private:
        return "private_address"
    return None


def parse(url, *, schemes=("https",), ports=None):
    """-> (scheme, hostname, port, host_header, request_target) or OutboundRefused("invalid_url"/"port_not_allowed")."""
    parts = urlsplit(str(url or "").strip())
    try:
        hostname, explicit = parts.hostname, parts.port
    except ValueError:
        raise OutboundRefused("invalid_url") from None
    if parts.scheme not in schemes or not hostname or parts.username or parts.password or parts.fragment \
            or "@" in parts.netloc:
        raise OutboundRefused("invalid_url")
    port = explicit or DEFAULT_PORTS[parts.scheme]
    if ports is not None and port not in ports:
        raise OutboundRefused("port_not_allowed")
    literal = f"[{hostname}]" if ":" in hostname else hostname
    host_header = literal if port == DEFAULT_PORTS[parts.scheme] else f"{literal}:{port}"
    request_target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return parts.scheme, hostname, port, host_header, request_target


def resolve(url, *, schemes=("https",), ports=None, allow_private=False, extra_blocked=(), allow_loopback=False):
    """Resolve once and validate EVERY answer (one bad answer refuses the whole name) -> a pinned ``Target``."""
    scheme, hostname, port, host_header, request_target = parse(url, schemes=schemes, ports=ports)
    try:
        answers = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError, ValueError):
        raise OutboundRefused("dns_failed") from None
    if not answers:
        raise OutboundRefused("dns_failed")
    pinned, seen = [], set()
    for family, _type, _proto, _canon, sockaddr in answers:
        if family not in (socket.AF_INET, socket.AF_INET6):
            raise OutboundRefused("blocked_address")
        reason = refusal(sockaddr[0], allow_private=allow_private, extra_blocked=extra_blocked,
                         allow_loopback=allow_loopback)
        if reason:
            raise OutboundRefused(reason)
        if (family, sockaddr) not in seen:
            seen.add((family, sockaddr))
            pinned.append(PinnedAddress(family, tuple(sockaddr)))
    return Target(scheme, hostname, port, host_header, request_target, tuple(pinned))


def is_public_https(url, *, ports=None):
    """True when ``url`` is https and every DNS answer is a public address (a save-time check; calls re-resolve)."""
    try:
        resolve(url, ports=ports)
    except OutboundRefused:
        return False
    return True
