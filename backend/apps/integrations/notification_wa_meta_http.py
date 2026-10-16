"""Bounded Graph requests; provider bodies and exceptions never become diagnostics."""
import logging
import re

import requests
from django.conf import settings

from .notification_providers import ProviderResult

logger = logging.getLogger(__name__)
ID = re.compile(r"[0-9]{1,64}\Z", re.ASCII)
PHONE = re.compile(r"\+[1-9][0-9]{6,14}\Z", re.ASCII)
REQUIRED = ("app_id", "app_secret", "business_account_id", "phone_number_id",
            "access_token", "webhook_verify_token")


def credentials(configuration):
    try:
        values = configuration.get_credentials()
        if not isinstance(values, dict):
            return {}
        if any(not isinstance(values.get(k), str) or not values[k]
               or len(values[k]) > 8000 or any(ord(c) < 32 for c in values[k]) for k in REQUIRED):
            return {}
        if any(not ID.fullmatch(values[k]) for k in ("app_id", "business_account_id", "phone_number_id")):
            return {}
        if not values["access_token"].isascii() or any(c.isspace() for c in values["access_token"]):
            return {}
        return values
    except Exception:
        return {}


def failure(code, *, retryable=False, ambiguous=False, retry_after=None):
    return ProviderResult(False, error_code=code, sanitized_error=code,
                          retryable=retryable, ambiguous=ambiguous, retry_after=retry_after)


def error_result(status, payload, retry_after=None):
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    code = error.get("code") if isinstance(error, dict) else None
    code = code if type(code) is int else None
    if status == 429 or code in {4, 17, 32, 613, 80007, 130429, 131048, 131056}:
        return failure("rate_limited", retryable=True, retry_after=retry_after)
    if status >= 500 or code in {1, 2, 131000, 131016}:
        return failure("unavailable", retryable=True, retry_after=retry_after)
    if code in {131047, 132000, 132001, 132005, 132007, 132012, 132015, 132016}:
        return failure("template_required")
    if code in {131021, 131026, 131030}:
        return failure("invalid_endpoint")
    if code == 131050:
        return failure("blocked")
    if code in {190, 10, 200, 131005}:
        return failure("not_configured")
    return failure("provider_error")


def graph(configuration, method, resource, *, payload=None, params=None):
    values = credentials(configuration)
    version = getattr(settings, "WHATSAPP_META_GRAPH_VERSION", "v25.0")
    if (not values or not isinstance(version, str) or not re.fullmatch(r"v[0-9]{1,3}\.0", version)
            or not re.fullmatch(r"[0-9]{1,64}/(?:messages|message_templates)", resource)):
        return failure("not_configured"), None
    try:
        response = requests.request(method, f"https://graph.facebook.com/{version}/{resource}",
            headers={"Authorization": f"Bearer {values['access_token']}"},
            json=payload, params=params, timeout=(5, 15), allow_redirects=False)
    except requests.Timeout:
        result = failure("timeout", retryable=True, ambiguous=method == "POST")
    except requests.RequestException:
        # A broken connection after POST may have reached Meta. Bound the retry budget.
        result = failure("unavailable", retryable=True, ambiguous=method == "POST")
    else:
        try:
            data = response.json()
        except (ValueError, TypeError):
            data = None
        if 200 <= response.status_code < 300 and isinstance(data, dict) and "error" not in data:
            return ProviderResult(True), data
        if 200 <= response.status_code < 300 and not isinstance(data, dict):
            return failure("provider_error", retryable=True, ambiguous=method == "POST"), None
        retry = response.headers.get("Retry-After", "")
        delay = min(int(retry), 3600) if isinstance(retry, str) and re.fullmatch(r"[0-9]{1,6}", retry) else None
        result = error_result(response.status_code, data, delay)
    logger.warning("notification.meta_request_failed", extra={
        "configuration_id": configuration.pk, "generation": configuration.generation,
        "error_code": result.error_code, "retryable": result.retryable})
    return result, None


def send_message(configuration, destination, content):
    if not isinstance(destination, str) or not PHONE.fullmatch(destination):
        return failure("invalid_endpoint")
    values = credentials(configuration)
    if not values:
        return failure("not_configured")
    result, data = graph(configuration, "POST", f"{values['phone_number_id']}/messages", payload={
        "messaging_product": "whatsapp", "recipient_type": "individual",
        "to": destination[1:], **content})
    if not result.accepted:
        return result
    messages = data.get("messages")
    provider_id = messages[0].get("id") if isinstance(messages, list) and messages and isinstance(messages[0], dict) else None
    if not isinstance(provider_id, str) or not 0 < len(provider_id) <= 255:
        # A 2xx without a correlatable id is ambiguous, never a delivery success.
        return failure("provider_error", retryable=True, ambiguous=True)
    return ProviderResult(True, provider_id=provider_id)
