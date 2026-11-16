"""The SpaceWorks side of the image adapter contract: sign, send, bound and validate.

`call` returns validated PNG bytes or raises `AdapterError` with a typed code. Every call (the provider and any
mask URL it returns) goes through the shared bounded transport: the host name is resolved once and checked against
the URL policy at call time, the connection is pinned to that address (Host and TLS name kept), redirects are never
followed, proxies are ignored, the reply is read up to the contract's bound and the whole exchange has one deadline,
so a provider that drips bytes cannot hold a worker. No photo bytes or secrets are ever logged.
"""
import json
import logging
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urlsplit

import requests

from apps import outbound_http

from . import contract, png_validation, signing, url_policy
from .errors import AdapterError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderConfig:
    url: str
    secret: str
    scope: str  # "space" | "platform"


# One overall deadline per exchange (connect + send + every read). A health check is small and quick.
CALL_DEADLINE = contract.CONNECT_TIMEOUT + contract.READ_TIMEOUT
HEALTH_DEADLINE, HEALTH_BYTES = 15, 64 * 1024


def _exchange(target, method, *, body=None, headers=None, max_bytes, deadline, unreachable):
    try:
        return outbound_http.send(target, method, body=body, headers=headers or {}, max_bytes=max_bytes,
                                  connect_timeout=contract.CONNECT_TIMEOUT, read_timeout=contract.READ_TIMEOUT,
                                  deadline=deadline)
    except outbound_http.OutboundError as exc:
        if exc.reason == "too_large":
            raise AdapterError("response_too_large") from None
        if exc.reason == "timeout" and unreachable == "provider_unreachable":
            raise AdapterError("provider_timeout") from None
        logger.warning("image_adapter_unreachable", extra={"reason": exc.reason})
        raise AdapterError(unreachable) from None


def _send(config, method, path, *, files=None, data=None, max_bytes=None, deadline=None):
    base = urlsplit(config.url)
    full_path = base.path.rstrip("/") + path
    url = f"{base.scheme}://{base.netloc}{full_path}"
    try:
        pinned = url_policy.target(url, scope=config.scope)
    except ValueError:
        raise AdapterError("url_not_allowed") from None
    # `requests` only encodes the multipart body here; nothing is sent through it.
    prepared = requests.Request(method, url, files=files, data=data).prepare()
    body = prepared.body if isinstance(prepared.body, bytes) else (prepared.body or "").encode()
    headers = {key: value for key, value in prepared.headers.items()
               if key.lower() in ("content-type", "content-length")}
    headers.update(signing.sign(config.secret, method, full_path, body))
    headers[contract.HEADER_VERSION] = contract.VERSION
    response = _exchange(pinned, method, body=body or None, headers=headers,
                         max_bytes=max_bytes or contract.MAX_OUTPUT_BYTES, deadline=deadline or CALL_DEADLINE,
                         unreachable="provider_unreachable")
    return response.status, response.content_type, response.body


def _provider_error(status, kind, body):
    """Map a non-2xx answer to a typed error: the provider's own code when it is one we know.

    Retryability is ours, never the provider's: a known code is retried per ``contract.RETRYABLE``, and anything else
    falls back to the status (429, 503, other 5xx) or is a final ``invalid_response`` (docs/image-adapters/errors.md),
    whatever ``retryable`` the body claims.
    """
    code = ""
    if kind == "application/json":
        try:
            error = json.loads(body.decode()).get("error") or {}
            code = str(error.get("code", ""))
        except (ValueError, AttributeError, UnicodeDecodeError):
            pass
    if code in contract.PROVIDER_ERRORS:
        return AdapterError(code)
    if status == 429:
        return AdapterError("rate_limited")
    if status >= 500:
        return AdapterError("unavailable" if status == 503 else "internal_error")
    return AdapterError("invalid_response")


def _image_size(data):
    from PIL import Image
    try:
        with Image.open(BytesIO(data)) as image:
            return image.size
    except Exception:
        raise AdapterError("input_not_allowed") from None


def _fetch_mask(url):
    """A provider-returned mask URL is the provider's word, never trusted: public https only, whatever the scope."""
    try:
        pinned = url_policy.target(url, scope="space")
    except ValueError:
        raise AdapterError("url_not_allowed") from None
    response = _exchange(pinned, "GET", max_bytes=contract.MAX_MASK_BYTES, deadline=CALL_DEADLINE,
                         unreachable="mask_unreachable")
    if response.status != 200:
        raise AdapterError("mask_unreachable")
    return response.body


def remove_background(config, data, content_type):
    """image.remove_background -> (png_bytes, width, height)."""
    if content_type not in contract.INPUT_TYPES or not data or len(data) > contract.MAX_INPUT_BYTES:
        raise AdapterError("input_not_allowed")
    size = _image_size(data)
    if max(size) > contract.MAX_INPUT_EDGE:
        raise AdapterError("input_not_allowed")
    capability = contract.CAPABILITIES["image.remove_background"]
    status, kind, body = _send(config, "POST", capability.path, files={"image": ("photo", data, content_type)},
                               data={"options": json.dumps({"output": "png"})})
    if status != 200:
        raise _provider_error(status, kind, body)
    if kind == "image/png":
        return png_validation.validate_png(body, size)
    if kind == "application/json":
        try:
            mask_url = json.loads(body.decode()).get("mask_url", "")
        except (ValueError, AttributeError, UnicodeDecodeError):
            raise AdapterError("invalid_response") from None
        return png_validation.apply_mask(data, _fetch_mask(mask_url), size)
    raise AdapterError("response_not_png")


def test_connection(config):
    """Signed health check -> {"ok", "capabilities", "contract"}; raises AdapterError."""
    status, kind, body = _send(config, "GET", contract.HEALTH_PATH, max_bytes=HEALTH_BYTES, deadline=HEALTH_DEADLINE)
    if status != 200 or kind != "application/json":
        raise _provider_error(status, kind, body)
    try:
        info = json.loads(body.decode())
        capabilities = [str(item) for item in info.get("capabilities", [])][:20]
        version = str(info.get("contract", ""))
    except (ValueError, AttributeError, UnicodeDecodeError):
        raise AdapterError("invalid_response") from None
    if version != contract.VERSION:
        raise AdapterError("invalid_response", "unsupported contract version")
    if "image.remove_background" not in capabilities:
        raise AdapterError("invalid_response", "provider lacks image.remove_background")
    return {"ok": True, "contract": version, "capabilities": capabilities}
