"""Bounded JSON/form transport; pin DNS before sending any credential."""
import http.client
import json
import logging
import math
from urllib.parse import urlencode

from .notification_providers import ProviderResult
from .webhook_validation import resolve_webhook_target
from .webhooks import _PinnedHTTPSConnection

logger = logging.getLogger(__name__)


class ProviderFailure(Exception):
    def __init__(self, code, *, retryable=False, retry_after=None, ambiguous=False):
        self.result = ProviderResult(False, error_code=code, sanitized_error=code,
            retryable=retryable, retry_after=retry_after, ambiguous=ambiguous)
        super().__init__(code)


def credentials_for(config):
    try:
        value = config.get_credentials()
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except Exception:
        raise ProviderFailure("not_configured") from None


def retry_delay(value):
    try:
        return max(1, min(3600, math.ceil(float(value))))
    except (TypeError, ValueError, OverflowError):
        return 60


def api(method, url, *, token="", auth="Bearer", data=None, form=False, target=None,
        raw_body=None, content_type="application/octet-stream", raw_response=False):
    if target is None:
        try:
            target = resolve_webhook_target(url)
        except ValueError:
            # Fixed Slack/Discord hosts may have a transient DNS outage. No
            # credential is sent if resolution or address validation refuses.
            raise ProviderFailure("unavailable", retryable=True) from None
    headers = {"Accept": "application/json", "Host": target.host_header,
               "User-Agent": "SpaceWorks-Notifications/1"}
    if token:
        headers["Authorization"] = f"{auth} {token}"
    body = None
    if data is not None:
        body = (urlencode(data) if form else json.dumps(data)).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
    if raw_body is not None:
        body = raw_body
        headers["Content-Type"] = content_type
    connection = _PinnedHTTPSConnection(target, target.addresses[0])
    try:
        connection.request(method, target.request_target, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read(1024 * 1024 + 1)
        if response.status == 429:
            delay = response.getheader("Retry-After")
            if not delay:
                try:
                    delay = json.loads(raw).get("retry_after")
                except (ValueError, AttributeError):
                    delay = None
            raise ProviderFailure("rate_limited", retryable=True,
                                  retry_after=retry_delay(delay))
        if response.status >= 500:
            raise ProviderFailure("unavailable", retryable=True)
        if response.status in (401, 403, 404):
            raise ProviderFailure("invalid_endpoint")
        if not 200 <= response.status < 300 or len(raw) > 1024 * 1024:
            raise ProviderFailure("provider_error", retryable=response.status < 300,
                                  ambiguous=method == "POST" and response.status < 300)
        if raw_response:
            return {}
        value = json.loads(raw) if raw else {}
        if not isinstance(value, dict):
            raise ProviderFailure("provider_error", retryable=method == "POST", ambiguous=method == "POST")
        return value
    except (TimeoutError, OSError, http.client.HTTPException):
        # The server may have accepted a POST before the connection broke.
        raise ProviderFailure("timeout", retryable=True, ambiguous=method == "POST") from None
    except (ValueError, UnicodeError):
        raise ProviderFailure("provider_error", retryable=method == "POST", ambiguous=method == "POST") from None
    finally:
        connection.close()


def failure_result(channel, operation):
    try:
        return operation()
    except ProviderFailure as exc:
        return exc.result
    except Exception:
        logger.warning("Notification provider operation refused", extra={"channel": channel})
        return ProviderResult(False, error_code="provider_error")


def live_endpoint(config, endpoint):
    if endpoint is not None and hasattr(endpoint, "refresh_from_db"):
        try:
            endpoint.refresh_from_db()
        except type(endpoint).DoesNotExist:
            raise ProviderFailure("invalid_endpoint") from None
    if (not config.enabled or not config.personal_enabled or not endpoint
            or endpoint.revoked_at or endpoint.verification_state != "verified"
            or not endpoint.consented_at or not endpoint.verified_at
            or endpoint.configuration_id != config.pk or endpoint.makerspace_id != config.makerspace_id
            or endpoint.channel != config.channel or endpoint.provider != config.provider
            or endpoint.integration_generation != config.generation
            or endpoint.integration_identity != config.integration_identity):
        raise ProviderFailure("invalid_endpoint")
    return endpoint.destination


def room(config, target, text):
    from .webhooks import send_webhook
    if (not config.enabled or not config.room_enabled
            or target is not None and (target.makerspace_id != config.makerspace_id
                or target.channel != config.channel or not target.is_active)):
        return ProviderResult(False, error_code="not_configured")
    return ProviderResult(bool(send_webhook(config.makerspace, channel=config.channel,
                                           text=text, destination=target)))


def message_text(rendered):
    # The contract renders a subject and a body; a DM without the subject loses its title.
    parts = (str(rendered.get(key) or "").strip() for key in ("subject", "text"))
    return "\n".join(part for part in parts if part)
