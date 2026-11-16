"""Normalize authenticated Meta batch items without retaining arbitrary message bodies."""
import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

from .notification_ingress import accept_callback
from .notification_providers import CallbackEvent
from .notification_wa_meta_callbacks import callback_event, destination, destination_digest, message_text, STOP_WORDS
from .notification_wa_window import inbound_time
from .messaging.webhook_payloads import alias_hash, phone_hash


def accept_meta_item(config, request, index, item):
    proxy = SimpleNamespace(body=request.body, headers=request.headers,
        meta_route_kwargs=request.parser_context["kwargs"], meta_item_index=index)
    event = callback_event(config, proxy)
    kind, row = item
    recipient = row.get("recipient") if isinstance(row.get("recipient"), dict) else {}
    phone = row.get("from") if kind == "messages" else row.get("wa_id") if kind == "user_preferences" else row.get("recipient_id")
    phone = phone or recipient.get("wa_id")
    alias = row.get("from_user_id") or row.get("user_id") or row.get("recipient_user_id") or recipient.get("user_id")
    protection = {"phone_hash": phone_hash(phone), "alias_hash": alias_hash(alias),
        "stop": (kind == "messages" and message_text(row).casefold() in STOP_WORDS)
            or (kind == "user_preferences" and row.get("value") == "stop"),
        "timestamp": row.get("timestamp"),
        "context_id": str((row.get("context") or {}).get("id", ""))[:255]}
    errors = row.get("errors")
    code = str(errors[0].get("code", "")) if isinstance(errors, list) and errors and isinstance(errors[0], dict) else ""
    protection["error_code"] = code if code.isascii() and code.isdigit() and len(code) <= 16 else ""
    if code == "131050":
        protection["stop"] = True
    if kind == "user_preferences" and protection["stop"] and not (row.get("id") or row.get("timestamp")):
        protection["correlation_missing"] = True
    if event is None:
        # Alias-only STOP must still reach the sender barrier. Unsupported statuses
        # remain held facts; never acknowledge a discarded authenticated item.
        event = CallbackEvent(opt_out=bool(protection["stop"]))
    number = destination(phone)
    if number and not event.identity_digest:
        event = replace(event, identity_digest=destination_digest(config, number))
    moment = inbound_time(row.get("timestamp")) if kind == "messages" else None
    identity = [kind, row.get("id"), row.get("status"), row.get("timestamp"),
        hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()]
    extra = {"id": row.get("id"), "status": row.get("status"), "errors": [{"code": int(code)}] if code.isdigit() else []}
    return accept_callback(config, event, identity=identity, protection=protection,
        inbound_at=moment.isoformat() if moment else None, extra=extra)
