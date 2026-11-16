"""Where a provider URL may point.

Platform-wide (superadmin) trusts private networks and loopback (a compose service name, or a provider beside
SpaceWorks on one host); a space-level override must be a public https address, so a Space Manager cannot aim
the server at an internal one. Both use the shared address policy (``apps.outbound_policy``): cloud metadata,
link-local, multicast and reserved addresses are refused for every scope, and carrier-grade NAT
(100.64.0.0/10, including 100.100.100.200) counts as private. A provider-returned mask URL is held to the
space rule whatever the scope. ``target`` resolves ONCE and is what the client dials (pinned), so a name that
answers differently the second time cannot redirect the call.
"""
from urllib.parse import urlsplit

from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps import outbound_policy


def _rules(scope):
    if scope == "platform":
        return {"schemes": ("https", "http"), "allow_private": True, "allow_loopback": True}
    return {"schemes": ("https",)}


def target(url, *, scope):
    """The pinned ``outbound_policy.Target`` for a call, or ValueError("url_not_allowed")."""
    try:
        return outbound_policy.resolve(url, **_rules(scope))
    except outbound_policy.OutboundRefused:
        raise ValueError("url_not_allowed") from None


def clean_base_url(value, *, scope):
    value = (value or "").strip().rstrip("/")
    parts = urlsplit(value)
    if parts.scheme not in ("https", "http") or not parts.hostname or parts.username or parts.query or parts.fragment:
        raise ValidationError({"provider_url": gettext("Enter the provider's address, like https://eraser.example.org.")})
    if scope == "space":
        try:
            target(value, scope="space")
        except ValueError:
            raise ValidationError({"provider_url": gettext("A space's provider must be a public https address.")}) from None
    return value


def assert_callable(base_url, *, scope):
    """Re-check at call time (DNS can change after save). Raises ValueError for a refused target."""
    target(base_url, scope=scope)


def public_https(url):
    return outbound_policy.is_public_https(url)
