"""Provider outcomes contain only IDs/codes; never log addresses or response bodies."""
import errno
import json
import socket
from dataclasses import dataclass
from urllib import error, request


@dataclass(frozen=True)
class SendResult:
    message_id: str = ""
    provider_status: str = ""
    error_code: str = ""
    retryable: bool = False
    permanent: bool = False
    ambiguous: bool = False


def send_message(sender, *, to, delivery_id, body="", template_name="", language="", parameters=(), status_callback=None):
    """Single entry point for lane B; provider-specific transports share SendResult."""
    if sender.channel == "sms":
        from .twilio import send_message as send_sms
        return send_sms(sender, to=to, body=body, delivery_id=delivery_id, status_callback=status_callback)
    if sender.channel == "whatsapp":
        from .whatsapp import send_message as send_whatsapp
        return send_whatsapp(sender, to=to, delivery_id=delivery_id, template_name=template_name,
                             language=language, parameters=parameters)
    return SendResult(error_code="unsupported_channel", permanent=True)


def _json(response):
    try:
        value = json.loads(response.read(64 * 1024))
        return value if isinstance(value, dict) else {}
    except (ValueError, UnicodeError, OSError):
        return {}


def _code(value):
    value = str(value or "")
    return value if value.isdigit() and len(value) <= 16 else ""


def send_request(req, *, provider):
    try:
        with request.urlopen(req, timeout=10) as response:
            data = _json(response)
            message_id = data.get("sid", "") if provider == "twilio" else next(
                (item.get("id", "") for item in (data.get("messages") or []) if isinstance(item, dict)), "",
            )
            if not isinstance(message_id, str) or not message_id or len(message_id) > 255:
                return SendResult(error_code="invalid_response", retryable=True, ambiguous=True)
            status = data.get("status", "accepted")
            return SendResult(message_id=message_id, provider_status=status if status in {
                "queued", "accepted", "sending", "sent", "delivered", "read",
            } else "accepted")
    except error.HTTPError as exc:
        data = _json(exc)
        details = data.get("error", {}) if provider == "meta" else data
        code = _code(details.get("code")) if isinstance(details, dict) else ""
        retryable = exc.code == 429 or exc.code >= 500 or code in {"20429", "130429", "131048", "131056"}
        # A Meta 5xx without an explicit Graph rejection could follow acceptance.
        ambiguous = provider == "meta" and exc.code >= 500 and not code
        return SendResult(error_code=code or f"http_{exc.code}", retryable=retryable,
                          permanent=not retryable, ambiguous=ambiguous)
    except (error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        before_write = isinstance(reason, (socket.gaierror, ConnectionRefusedError)) or (
            isinstance(reason, OSError) and reason.errno in {errno.ECONNREFUSED, errno.ENETUNREACH, errno.EHOSTUNREACH}
        )
        return SendResult(error_code="connection_failed" if before_write else "ambiguous_timeout",
                          retryable=True, ambiguous=not before_write)

    except Exception:
        return SendResult(error_code="invalid_response", retryable=True, ambiguous=True)
