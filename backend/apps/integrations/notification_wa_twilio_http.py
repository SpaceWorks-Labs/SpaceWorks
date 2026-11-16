"""Bounded Twilio REST I/O; never expose provider text, bodies or destinations."""
import base64
import json
import logging
import socket
from dataclasses import replace
from urllib import error, parse, request

from .notification_providers import ProviderResult
from .notification_wa_twilio_config import sid

logger = logging.getLogger(__name__)
MESSAGE_ROOT = "https://api.twilio.com/2010-04-01/Accounts"
CONTENT_ROOT = "https://content.twilio.com/v1/Content"
TIMEOUT = 10
MAX_RESPONSE = 65536


class NoRedirect(request.HTTPRedirectHandler):
    # A provider redirect must never forward Basic credentials to another host.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def failure(status=0, code=0):
    try:
        code = int(code or 0)
    except (ValueError, TypeError):
        code = 0
    if status == 429 or code in {20429, 63018, 63038, 63039}:
        name, retry = "rate_limited", True
    elif status >= 500 or code in {63009, 63010, 63012}:
        name, retry = "unavailable", True
    elif code in {63016, 63027, 63028, 63040, 63054}:
        name, retry = "template_required", False
    elif code in {21610, 63014, 63033}:
        name, retry = "blocked", False
    elif code in {21211, 21612, 21614, 63003, 63024}:
        name, retry = "invalid_endpoint", False
    elif status in {401, 403} or code in {20003, 20005, 63001, 63002, 63007, 63008}:
        name, retry = "not_configured", False
    else:
        name, retry = "provider_error", False
    return ProviderResult(False, retryable=retry, error_code=name, sanitized_error=name)


def _json(response):
    raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError()
    return data


def call(credentials, url, payload=None):
    authorization = base64.b64encode(f"{credentials.username}:{credentials.password}".encode()).decode("ascii")
    req = request.Request(url, data=None if payload is None else parse.urlencode(payload).encode(),
        headers={"Authorization": f"Basic {authorization}", "Content-Type": "application/x-www-form-urlencoded"},
        method="GET" if payload is None else "POST")
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=TIMEOUT) as response:
            if not 200 <= response.status < 300:
                return None, failure(response.status)
            return _json(response), None
    except error.HTTPError as exc:
        # Twilio error messages often echo PII. Only interpret their numeric code.
        try:
            code = int(_json(exc).get("code", 0))
        except (ValueError, TypeError, OSError):
            code = 0
        finally:
            exc.close()
        result = failure(exc.code, code)
        try:
            delay = min(max(int(exc.headers.get("Retry-After", "0")), 0), 3600)
        except (ValueError, TypeError, AttributeError):
            delay = 0
        if result.retryable and delay:
            result = replace(result, retry_after=delay)
        logger.warning("whatsapp_twilio_rejected", extra={"status": exc.code, "error_code": result.error_code})
        return None, result
    except (TimeoutError, socket.timeout):
        return None, ProviderResult(False, retryable=True, error_code="timeout", sanitized_error="timeout", ambiguous=True)
    except error.URLError as exc:
        timed_out = isinstance(exc.reason, (TimeoutError, socket.timeout))
        name = "timeout" if timed_out else "unavailable"
        # A dropped connection can occur after Twilio accepted a POST too.
        return None, ProviderResult(False, retryable=True, error_code=name, sanitized_error=name,
                                    ambiguous=payload is not None)
    except Exception:
        logger.warning("whatsapp_twilio_failed", extra={"error_code": "provider_error"})
        return None, ProviderResult(False, error_code="provider_error", sanitized_error="provider_error",
                                    ambiguous=payload is not None)


def send_message(credentials, payload):
    data, result = call(credentials, f"{MESSAGE_ROOT}/{credentials.account_sid}/Messages.json", payload)
    if result:
        return result
    if not sid(data.get("sid"), "SM") and not sid(data.get("sid"), "MM"):
        return ProviderResult(False, retryable=True, error_code="provider_error", ambiguous=True)
    if data.get("status") in {"failed", "undelivered", "canceled"}:
        return failure(code=data.get("error_code"))
    return ProviderResult(True, provider_id=data["sid"])
