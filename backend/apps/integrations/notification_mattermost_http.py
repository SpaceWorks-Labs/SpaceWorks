"""Mattermost server registration and DNS-pinned requests, including self-host opt-in."""
import socket
from ipaddress import ip_address
from urllib.parse import urlsplit

from django.conf import settings
from rest_framework.exceptions import ValidationError

from .notification_slack_http import api
from .webhook_validation import ResolvedAddress, ResolvedWebhookTarget


def server_url(value):
    try:
        parts = urlsplit(value)
        if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                or parts.query or parts.fragment or parts.path not in ("", "/")
                or not 1 <= (parts.port or 443) <= 65535 or any(c.isspace() for c in value)
                or "\\" in value or "%" in parts.netloc):
            raise ValueError()
        base = f"https://{parts.netloc}".rstrip("/")
        if len(base) > 255:
            raise ValueError()
        return base
    except (ValueError, TypeError):
        raise ValidationError({"server_url": "Use an absolute HTTPS server origin without credentials."}) from None


def resolve_server(value, path):
    base = server_url(value)
    parts = urlsplit(base)
    allow_private = getattr(settings, "NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS", False) is True
    try:
        answers = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
        addresses = []
        for family, socktype, proto, _, sockaddr in answers:
            address = ip_address(sockaddr[0])
            address = getattr(address, "ipv4_mapped", None) or address
            if family not in (socket.AF_INET, socket.AF_INET6) or not allow_private and not address.is_global:
                raise ValueError()
            addresses.append(ResolvedAddress(family, socktype, proto, sockaddr))
        if not addresses:
            raise ValueError()
    except (OSError, ValueError, UnicodeError):
        raise ValidationError({"server_url": "Server must resolve exclusively to permitted addresses."}) from None
    return ResolvedWebhookTarget(base + path, parts.hostname, parts.port or 443,
                                 parts.netloc, path, tuple(addresses))


def mattermost_api(server, method, path, **kwargs):
    target = resolve_server(server, path)
    return api(method, target.url, target=target, **kwargs)
