"""The only outbound calls to a space's Anthias player (decision 325c).

Written against the Anthias source (Screenly/Anthias commit 6a8202b47a0b39039ed5d17cac8adde9b4a9aad8):
* `src/anthias_server/django_project/urls.py` mounts the API at `/api/`.
* `src/anthias_server/api/urls/v2.py` and `v1_2.py`: `v2/assets`, `v2/assets/<id>`, `v2/info` and
  `v1.2/assets`, `v1.2/assets/<id>`. v1.2 has no info route (v1's `InfoView` has no version field).
* `api/serializers/v2.py`: booleans for is_enabled/nocache/skip_asset_check, integer duration, ISO dates,
  create answers with the asset under `asset_id`. `api/serializers/v1_2.py`: integer 0/1 flags and a
  string `duration`; v1.2 also demands a unique name. DELETE answers 204, unknown id 404.
* `lib/auth.py`: with auth on, HTTP Basic is accepted; an unauthenticated call is redirected (302) to the
  login page rather than refused with 401. With auth off the API is open.

Every failure becomes `AnthiasError` with a short reason code (never the response body or credentials).
The call goes through the shared bounded transport (`apps.outbound_policy` + `apps.outbound_http`): the host
name is resolved exactly once per request, every answer is checked, and the connection is made to that exact
address (pinned) with the original Host header and TLS server name; no redirects, no proxy environment
variables, at most `BODY_LIMIT` bytes read and the whole exchange stopped at `TOTAL_SECONDS`. Only http(s);
loopback, link-local (cloud metadata), multicast and reserved addresses and the deployment's own service
networks (`anthias_networks`) are always refused; other private LAN addresses only while
`ANTHIAS_ALLOW_PRIVATE_HOSTS` is on (decision 336(g): on by default on self-host, off on a managed deployment).
Replies are shape-checked here, so a malformed answer is `AnthiasError("bad_response")`, never a TypeError.
"""
import base64
import json as jsonlib
import logging
import socket  # noqa: F401 - tests stub `anthias_client.socket.getaddrinfo` (the one resolver call)
from urllib.parse import urlsplit

from django.conf import settings

from apps import outbound_http, outbound_policy

from .anthias_networks import service_networks

logger = logging.getLogger(__name__)

CONNECT_SECONDS, READ_SECONDS, TOTAL_SECONDS, BODY_LIMIT = 4, 10, 20, 1024 * 1024
API_VERSIONS = ("v2", "v1.2")


class AnthiasError(Exception):
    def __init__(self, reason, status=None):
        super().__init__(reason)
        self.reason, self.status = reason, status


def clean_host(value):
    """A normalised `scheme://host[:port]` or `AnthiasError("invalid_host")`; no path, query or userinfo."""
    parts = urlsplit(str(value or "").strip())
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password \
            or parts.path.strip("/") or parts.query or parts.fragment:
        raise AnthiasError("invalid_host")
    try:
        port = parts.port
    except ValueError:
        raise AnthiasError("invalid_host") from None
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    return f"{parts.scheme}://{host}" + (f":{port}" if port else "")


def _target(base_url):
    try:
        return outbound_policy.resolve(base_url, schemes=("http", "https"),
                                       allow_private=bool(getattr(settings, "ANTHIAS_ALLOW_PRIVATE_HOSTS", False)),
                                       extra_blocked=service_networks())
    except outbound_policy.OutboundRefused as exc:
        raise AnthiasError({"invalid_url": "invalid_host", "port_not_allowed": "invalid_host"}.get(
            exc.reason, exc.reason)) from None


def resolve_target(base_url):
    """Resolve once, validate every answer, and return `(pinned_base, host_header, sni_host)`.

    The transport connects to the pinned address, so a second DNS answer can never change the target.
    """
    target = _target(base_url)
    first = target.addresses[0].ip
    literal = f"[{first}]" if ":" in first else first
    return f"{target.scheme}://{literal}:{target.port}", target.host_header, target.hostname


class AnthiasClient:
    def __init__(self, player):
        self.base = clean_host(player.host_url)
        password = player.get_password()
        self.auth = (player.username, password) if player.username else None
        self.version = player.api_version if player.api_version in API_VERSIONS else ""

    def _request(self, method, path, json=None):
        target = _target(self.base).with_path(path)
        headers = {"Accept": "application/json"}
        body = None
        if json is not None:
            body = jsonlib.dumps(json).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.auth:
            token = base64.b64encode(f"{self.auth[0]}:{self.auth[1] or ''}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        try:
            response = outbound_http.send(target, method, body=body, headers=headers, max_bytes=BODY_LIMIT,
                                          connect_timeout=CONNECT_SECONDS, read_timeout=READ_SECONDS,
                                          deadline=TOTAL_SECONDS)
        except outbound_http.OutboundError as exc:
            logger.warning("anthias_request_failed", extra={"reason": exc.reason})
            raise AnthiasError({"too_large": "http_error"}.get(exc.reason, exc.reason)) from None
        # Anthias answers an unauthenticated call with a 302 to its login page, not a 401.
        if response.status in (301, 302, 303, 307, 308, 401, 403):
            raise AnthiasError("auth_failed", response.status)
        if response.status == 404:
            raise AnthiasError("not_found", 404)
        if response.status >= 400:
            raise AnthiasError("http_error", response.status)
        try:
            return jsonlib.loads(response.body) if response.body else {}
        except (ValueError, UnicodeDecodeError):
            raise AnthiasError("bad_response", response.status) from None

    def _object(self, method, path, json=None):
        """A reply that must be a JSON object (info, create); anything else is `bad_response`."""
        data = self._request(method, path, json)
        if not isinstance(data, dict):
            raise AnthiasError("bad_response")
        return data

    def detect(self):
        """Pick the newest API the player answers on: `(api_version, anthias_version)`. v2 first, then v1.2."""
        last = AnthiasError("unreachable")
        for version in API_VERSIONS:
            try:
                assets = self._request("GET", f"/api/{version}/assets")
                if not isinstance(assets, list):  # an Anthias asset list is always a JSON array
                    raise AnthiasError("bad_response")
            except AnthiasError as exc:
                if exc.reason == "not_found":
                    last = exc
                    continue
                raise
            self.version = version
            return version, self._anthias_version(version)
        raise last

    def _anthias_version(self, version):
        """Only v2 reports a version (`anthias_version` in `/api/v2/info`); v1.2 has none, so it stays blank."""
        if version != "v2":
            return ""
        try:
            return str(self._object("GET", "/api/v2/info").get("anthias_version") or "")[:40]
        except AnthiasError:
            return ""  # the label is a nicety; the assets answered, so the player is usable

    def _assets(self):
        return f"/api/{self.version}/assets"

    def create(self, payload):
        asset_id = self._object("POST", self._assets(), self._body(payload)).get("asset_id")
        if not isinstance(asset_id, (str, int)) or isinstance(asset_id, bool) or not str(asset_id).strip()                 or len(str(asset_id)) > 200 or "/" in str(asset_id):
            raise AnthiasError("bad_response")
        return str(asset_id)

    def update(self, asset_id, payload):
        self._request("PUT", f"{self._assets()}/{asset_id}", self._body(payload))

    def delete(self, asset_id):
        try:
            self._request("DELETE", f"{self._assets()}/{asset_id}")
        except AnthiasError as exc:
            if exc.reason != "not_found":  # already gone is the goal
                raise

    def _body(self, payload):
        """v2 takes booleans and an integer duration; v1.2 takes 0/1 integers and a string duration."""
        body = dict(payload)
        flags = ("is_enabled", "skip_asset_check")
        if self.version == "v1.2":
            for key in flags:
                body[key] = int(bool(body[key]))
            body.update(is_processing=0, nocache=0, duration=str(body["duration"]))
        else:
            for key in flags:
                body[key] = bool(body[key])
            body.update(is_processing=False, nocache=False)
        return body
