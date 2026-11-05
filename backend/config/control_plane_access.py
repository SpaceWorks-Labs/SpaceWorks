"""Who may reach the Django control plane at all (#189 as revised by #191).

The control plane is ``/control/``, its MFA step ``/mfa/control/`` and the control
re-authentication step ``/mfa/reauth/``. This layer only decides whether the request may
*see* it; the superadmin-only, MFA, re-authentication and axes checks behind it are
unchanged.

* ``CONTROL_PLANE_PROXY=false`` (the default) is server-only. A request is let through when
  it comes from the server itself -- a loopback peer that carries no forwarding header, as
  with ``manage.py runserver`` on the machine -- or through the SSH-tunnel listener. The
  tunnel's own Caddy site stamps ``X-SpaceWorks-Control-Tunnel``; the backend believes the
  stamp only when this deployment runs the tunnel overlay (``CONTROL_PLANE_TUNNEL=on``) and
  the stamp arrives from a private (Compose-network) peer, so a client on the internet that
  sends the header to an exposed backend is still refused. Everything else gets a plain 404:
  no login page, no hint that a console exists.
* ``CONTROL_PLANE_PROXY=true`` keeps the opt-in website route exactly as before: the proxy's
  own CIDR allowlist (``CONTROL_PLANE_ALLOW_CIDRS``) applies at the edge, and nothing here
  changes. Existing installs are never migrated off it (#191).
"""

import ipaddress

from django.conf import settings
from django.http import HttpResponseNotFound

TUNNEL_HEADER = "HTTP_X_SPACEWORKS_CONTROL_TUNNEL"
# A loopback peer is "the server itself" only when no proxy hop says otherwise.
FORWARDING_HEADERS = ("HTTP_X_FORWARDED_FOR", "HTTP_X_REAL_IP", "HTTP_FORWARDED")
CONTROL_PREFIXES = ("/control/", "/mfa/control/", "/mfa/reauth/")


def is_control_path(path):
    return path == "/control" or path.startswith(CONTROL_PREFIXES)


def _peer(request):
    try:
        return ipaddress.ip_address((request.META.get("REMOTE_ADDR") or "").strip())
    except ValueError:
        return None


def from_server(request):
    """True for a request that reached the backend from the server or its tunnel listener."""
    peer = _peer(request)
    if peer is None:
        return False
    if peer.is_loopback and not any(request.META.get(name) for name in FORWARDING_HEADERS):
        return True
    return bool(
        getattr(settings, "CONTROL_PLANE_TUNNEL", False)
        and request.META.get(TUNNEL_HEADER) == "1"
        and (peer.is_private or peer.is_loopback)
    )


def may_reach_control_plane(request):
    return bool(getattr(settings, "CONTROL_PLANE_PROXY", False)) or from_server(request)


class ControlPlaneReachMiddleware:
    """Defence in depth behind the edge proxies: the public origin never sees /control/."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_control_path(request.path) and not may_reach_control_plane(request):
            return HttpResponseNotFound(b"Not found.", content_type="text/plain")
        return self.get_response(request)
