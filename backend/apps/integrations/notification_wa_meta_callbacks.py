"""Authenticate raw bytes before JSON and bind every item to this installation."""
import hashlib
import hmac
import json
import re
from datetime import timedelta

from django.utils.crypto import salted_hmac

from apps.accounts import rbac
from .models_endpoints import NotificationEndpointChallenge
from .notification_proofs import digest
from .notification_providers import CallbackEvent, EndpointProof
from .notification_wa_meta_http import PHONE, credentials, error_result
from .notification_wa_window import inbound_time
from .notification_wa_meta_reference import referenced_delivery
from .messaging.webhook_payloads import timestamp

MAX_BODY = 262144
MAX_ITEMS = 200
STOP_WORDS = {"stop", "unsubscribe", "cancel", "end", "quit", "stopall", "opt out", "opt-out", "block"}


def route_kwargs(request):
    # Browser proof requests deliberately lack this provider-only route binding.
    context = getattr(request, "parser_context", None) or {}
    return (getattr(request, "meta_route_kwargs", None)
            or context.get("kwargs") or getattr(getattr(request, "resolver_match", None), "kwargs", {}))


def verified_payload(configuration, request):
    values = credentials(configuration)
    kwargs = route_kwargs(request)
    if (not values or kwargs.get("makerspace_id") != configuration.makerspace_id
            or kwargs.get("generation") != configuration.generation
            or kwargs.get("phone_number_id") != values["phone_number_id"]
            or configuration.channel != "whatsapp" or configuration.provider != "meta"):
        return None
    raw = request.body
    signature = request.headers.get("X-Hub-Signature-256", "")
    if (not isinstance(raw, bytes) or len(raw) > MAX_BODY or not isinstance(signature, str)
            or not re.fullmatch(r"sha256=[a-fA-F0-9]{64}", signature)):
        return None
    expected = "sha256=" + hmac.new(values["app_secret"].encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature.lower()):
        return None
    # No JSON parser (including DRF request.data) is consulted until authentication.
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError):
        return None
    return payload if isinstance(payload, dict) and payload.get("object") == "whatsapp_business_account" else None


def items(configuration, payload):
    """A webhook may carry unrelated tenants using the same Meta app secret."""
    values = credentials(configuration)
    entries = payload.get("entry")
    if not values or not isinstance(entries, list) or len(entries) > MAX_ITEMS:
        raise ValueError("invalid_payload")
    result = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("id") != values["business_account_id"]:
            continue
        changes = entry.get("changes")
        if not isinstance(changes, list) or len(changes) > MAX_ITEMS:
            raise ValueError("invalid_payload")
        for change in changes:
            if (not isinstance(change, dict) or not isinstance(change.get("field"), str)
                    or change["field"] not in {"messages", "user_preferences"}):
                continue
            value = change.get("value")
            if not isinstance(value, dict) or value.get("messaging_product") != "whatsapp":
                continue
            metadata = value.get("metadata", {})
            if not isinstance(metadata, dict) or metadata.get("phone_number_id") != values["phone_number_id"]:
                continue
            kinds = ("statuses", "messages") if change["field"] == "messages" else ("user_preferences",)
            for kind in kinds:
                rows = value.get(kind, [])
                if not isinstance(rows, list) or len(rows) > MAX_ITEMS:
                    raise ValueError("invalid_payload")
                for row in rows:
                    if not isinstance(row, dict):
                        raise ValueError("invalid_payload")
                    result.append((kind, row))
                    if len(result) > MAX_ITEMS:
                        raise ValueError("invalid_payload")
    return result


def destination(value):
    if not isinstance(value, str):
        return None
    number = value if value.startswith("+") else "+" + value
    return number if PHONE.fullmatch(number) else None


def destination_digest(configuration, number):
    if not number:
        return ""
    return salted_hmac("notification.endpoint.identity.v1",
        f"{configuration.pk}:{configuration.generation}:{number}", algorithm="sha256").hexdigest()


def message_text(row):
    kind = row.get("type")
    if kind == "text" and isinstance(row.get("text"), dict):
        value = row["text"].get("body")
    elif kind == "button" and isinstance(row.get("button"), dict):
        value = row["button"].get("payload") or row["button"].get("text")
    else:
        value = ""
    return value.strip() if isinstance(value, str) and len(value) <= 4096 else ""


def callback_event(configuration, request):
    payload = verified_payload(configuration, request)
    if payload is None:
        return None
    try:
        rows = items(configuration, payload)
        selected = getattr(request, "meta_item_index", 0)
        if type(selected) is not int or not 0 <= selected < len(rows):
            return None
        kind, row = rows[selected]
    except ValueError:
        return None
    if kind == "statuses":
        state, provider_id = row.get("status"), row.get("id")
        if (not isinstance(state, str) or state not in {"sent", "delivered", "read", "failed"}
                or not isinstance(provider_id, str) or not 0 < len(provider_id) <= 255):
            return None
        identity = destination_digest(configuration, destination(row.get("recipient_id")))
        errors = row.get("errors", [])
        stopped = state == "failed" and isinstance(errors, list) and any(
            isinstance(error, dict) and error.get("code") == 131050 for error in errors)
        error = errors[0] if isinstance(errors, list) and errors and isinstance(errors[0], dict) else {}
        if state == "failed" and error_result(400, {"error": error}).retryable:
            # The frozen failed callback releases email fallback immediately.
            # Defer that state until the lane's bounded retry handler decides it
            # is terminal. verified_callback still authenticates this event.
            state = "retrying"
        delivery_id, attempt = referenced_delivery(configuration, row.get("biz_opaque_callback_data"))
        return CallbackEvent(provider_id=provider_id, state=state,
            delivery_id=delivery_id, delivery_attempt=attempt,
            identity_digest=identity if stopped else "", opt_out=stopped,
            provider_timestamp=timestamp(row.get("timestamp")))
    number = destination(row.get("from") if kind == "messages" else row.get("wa_id"))
    if not number:
        return None
    identity = destination_digest(configuration, number)
    if kind == "user_preferences":
        if row.get("value") in {"stop", "start"}:
            return CallbackEvent(identity_digest=identity, opt_out=row["value"] == "stop",
                                 opt_in=row["value"] == "start", provider_timestamp=timestamp(row.get("timestamp")))
        return None
    text = message_text(row)
    # A signed opt-out is honoured even when its timestamp is missing or skewed.
    if text.casefold() in STOP_WORDS:
        return CallbackEvent(identity_digest=identity, opt_out=True, provider_timestamp=timestamp(row.get("timestamp")))
    moment = inbound_time(row.get("timestamp"))
    if moment is None or not isinstance(row.get("id"), str) or not row["id"]:
        return None
    challenge = None
    if re.fullmatch(r"[A-Za-z0-9_-]{43}", text):
        challenge = rbac.scope_notification_policy(NotificationEndpointChallenge.objects.all(),
            makerspace_id=configuration.makerspace_id).filter(configuration=configuration,
            integration_generation=configuration.generation, code_digest=digest(text),
            consumed_at=None, created_at__lt=moment + timedelta(seconds=1)).first()
    # Timestamp advancement belongs to the HTTP batch handler, using signed event time.
    # Keep inbound=False here so the frozen handler cannot substitute receipt time.
    if challenge:
        return CallbackEvent(proof=EndpointProof(code=text, destination=number,
            integration_identity=configuration.integration_identity, subject=number, private=True))
    return CallbackEvent(identity_digest=identity, opt_in=text.casefold() in {"start", "unstop", "yes"})
