"""Decision 263: the only outbound calls to a configured Grafana (health, search, render).

Fail safe: every network, DNS, TLS or protocol failure becomes ``GrafanaUnreachable`` with a
short reason code; nothing here raises anything else, logs the token or echoes a response
body back to the caller. Redirects are never followed and proxy environment variables are
ignored. A SPACE's Grafana must resolve to public addresses only, so a space setting cannot
point the server at the deployment's own network; the platform connection (superadmin) and
deployments that set ``GRAFANA_ALLOW_PRIVATE_HOSTS`` may use a private or local address,
which is how a Grafana next to SpaceWorks in the same compose network is reached.
"""

import logging
import socket
from ipaddress import ip_address
from urllib.parse import urlsplit

from django.conf import settings

logger = logging.getLogger(__name__)

CONNECT_SECONDS = 4
READ_SECONDS = 8
RENDER_READ_SECONDS = 30
JSON_LIMIT = 1024 * 1024
IMAGE_LIMIT = 8 * 1024 * 1024


class GrafanaUnreachable(Exception):
    def __init__(self, reason, status=None):
        super().__init__(reason)
        self.reason, self.status = reason, status


def private_hosts_allowed(scope):
    return scope.platform or bool(getattr(settings, "GRAFANA_ALLOW_PRIVATE_HOSTS", False))


def _getaddrinfo(host, port):
    return socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)


def check_host(base_url, *, allow_private):
    parts = urlsplit(base_url)
    host = parts.hostname or ""
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
        answers = _getaddrinfo(host, port)
    except (OSError, UnicodeError, ValueError):
        raise GrafanaUnreachable("dns_failed") from None
    if not answers:
        raise GrafanaUnreachable("dns_failed")
    if allow_private:
        return
    for _family, _type, _proto, _name, sockaddr in answers:
        address = ip_address(str(sockaddr[0]).split("%", 1)[0])
        address = getattr(address, "ipv4_mapped", None) or address
        if not address.is_global or address.is_multicast or address.is_reserved:
            raise GrafanaUnreachable("private_address")


def _headers(token, org_id):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if org_id:
        headers["X-Grafana-Org-Id"] = str(int(org_id))
    return headers


def fetch(base_url, path, *, allow_private, token="", org_id=None, params=None, accept=None,
          limit=JSON_LIMIT, read_seconds=READ_SECONDS):
    """(status, content type, body bytes). Raises ``GrafanaUnreachable`` on any failure."""
    import httpx

    check_host(base_url, allow_private=allow_private)
    headers = _headers(token, org_id)
    if accept:
        headers["Accept"] = accept
    timeout = httpx.Timeout(read_seconds, connect=CONNECT_SECONDS)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            with client.stream("GET", f"{base_url}{path}", headers=headers, params=params) as response:
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > limit:
                        raise GrafanaUnreachable("response_too_large", response.status_code)
                return response.status_code, response.headers.get("content-type", ""), bytes(body)
    except httpx.TimeoutException:
        raise GrafanaUnreachable("timeout") from None
    except httpx.HTTPError as exc:
        logger.warning("grafana_request_failed", extra={"error": exc.__class__.__name__})
        raise GrafanaUnreachable("connection_failed") from None
