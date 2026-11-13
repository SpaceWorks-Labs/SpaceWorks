"""A minimal signed client for the Device Adapter API v1. Runs against any server by URL (no Django needed).

Signing is the existing device protocol (``docs/device-protocol.md``): an Ed25519 signature over the length-framed
method, raw request target, timestamp, nonce and body hash. ``apps.devices.protocol`` and ``apps.ed25519`` are pure
helpers (stdlib and ``cryptography``); an adapter in another repo re-implements the same few lines.
"""
import json
import time
import urllib.error
import urllib.request

from apps.devices import protocol
from apps.ed25519 import encode_key, sign_bytes

PREFIX = "/api/v1/device/adapter/v1/"


class UrlTransport:
    """HTTP over urllib; ``send`` returns ``(status, parsed_json_or_None)`` and never raises on 4xx/5xx."""

    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def send(self, method, path, body, headers):
        request = urllib.request.Request(self.base_url + path, data=body if method == "POST" else None,
                                         method=method, headers={"Content-Type": "application/json", **headers})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - the URL is operator-supplied
                return response.status, _json(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, _json(exc.read())


def _json(raw):
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


class AdapterClient:
    def __init__(self, transport, device_id, key_version, private_key):
        self.transport, self.device_id, self.key_version, self.private = transport, str(device_id), key_version, private_key

    def headers(self, method, path, body, *, nonce=None, timestamp=None):
        timestamp = int(time.time()) if timestamp is None else timestamp
        nonce = nonce or protocol.b64url_encode(__import__("os").urandom(16))
        message = protocol.request_message(method=method, raw_target=path, timestamp=timestamp, nonce=nonce, body=body)
        return {"X-Device-Id": self.device_id, "X-Device-Key-Version": str(self.key_version),
                "X-Device-Signature-Version": "v1", "X-Device-Timestamp": str(timestamp), "X-Device-Nonce": nonce,
                "X-Device-Signature": encode_key(sign_bytes(message, self.private))}

    def call(self, method, route, data=None, **signing):
        path = PREFIX + route
        body = json.dumps(data if data is not None else {}, separators=(",", ":")).encode() if method == "POST" else b""
        return self.transport.send(method, path, body, self.headers(method, path, body, **signing))

    def post(self, route, data=None, **signing):
        return self.call("POST", route, data, **signing)

    def get(self, route, **signing):
        return self.call("GET", route, None, **signing)
