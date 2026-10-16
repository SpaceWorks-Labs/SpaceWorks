"""Bounded Telegram Bot API I/O; upstream bodies never become diagnostics."""
import json
import re
import socket
from urllib import error, request

from django.conf import settings

from .notification_enums import trim_for_channel
from .notification_providers import ProviderResult


def _failure(code, *, retryable=False, ambiguous=False, retry_after=None):
    return ProviderResult(False, retryable=retryable, error_code=code,
                          sanitized_error=code, ambiguous=ambiguous, retry_after=retry_after)


def _response(data, status):
    if status == 403:
        return _failure("invalid_endpoint"), None
    if status == 429:
        parameters = data.get("parameters", {})
        delay = parameters.get("retry_after") if isinstance(parameters, dict) else None
        delay = min(max(delay, 1), 3600) if type(delay) is int else None
        return _failure("rate_limited", retryable=True, retry_after=delay), None
    if status >= 500:
        return _failure("unavailable", retryable=True), None
    if status >= 400 or data.get("ok") is not True:
        return _failure("provider_error"), None
    result = data.get("result")
    if not isinstance(result, dict):
        return _failure("provider_error"), None
    return ProviderResult(True), result


def call(token, method, payload):
    if (method not in {"getMe", "sendMessage"} or not isinstance(payload, dict)
            or (method == "getMe" and payload)
            or (method == "sendMessage" and set(payload) != {"chat_id", "text"})):
        return _failure("provider_error"), None
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,256}", token):
        return _failure("not_configured"), None
    base = getattr(settings, "TELEGRAM_API_URL", "https://api.telegram.org").rstrip("/")
    try:
        req = request.Request(f"{base}/bot{token}/{method}",
            data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=5) as response:
                raw, status = response.read(65537), response.status
        except error.HTTPError as exc:
            with exc:
                if exc.code == 403:
                    return _failure("invalid_endpoint"), None
                raw, status = exc.read(65537), exc.code
        if len(raw) > 65536:
            if status >= 400:
                return _response({}, status)
            return _failure("provider_error"), None
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        # Telegram also reports API error codes inside a JSON response.
        code = data.get("error_code")
        if status < 400 and data.get("ok") is False and type(code) is int:
            status = code
        return _response(data, status)
    except (TimeoutError, socket.timeout):
        return _failure("timeout", retryable=True, ambiguous=method == "sendMessage"), None
    except error.URLError as exc:
        timed_out = isinstance(exc.reason, (TimeoutError, socket.timeout))
        return _failure("timeout" if timed_out else "unavailable", retryable=True,
                        ambiguous=timed_out and method == "sendMessage"), None
    except Exception:
        return _failure("provider_error"), None


def send_text(token, chat_id, text):
    # Fixed payload: neither parse_mode nor reply_markup can enter through rendered content.
    result, data = call(token, "sendMessage", {
        "chat_id": chat_id, "text": trim_for_channel("telegram", text),
    })
    if not result.accepted:
        return result
    message_id = data.get("message_id")
    if type(message_id) is not int or message_id <= 0:
        # Telegram may already have accepted the message. Avoid unbounded duplicate retries.
        return _failure("timeout", retryable=True, ambiguous=True)
    return ProviderResult(True, str(message_id))
