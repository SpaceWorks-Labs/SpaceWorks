"""Discard body/contact PII before inserting the durable callback inbox."""
import re
from email.utils import parsedate_to_datetime

from django.utils.dateparse import parse_datetime

from .protections import recipient_hash
from .stops import SMS_STOP, WHATSAPP_STOP


def code(value):
    value = str(value or "")
    return value if value.isascii() and value.isdigit() and len(value) <= 16 else ""


def phone_hash(value):
    value = str(value or "")
    if value.startswith("whatsapp:"):
        value = value[9:]
    if not value.startswith("+"):
        value = "+" + value
    return recipient_hash("phone", value) if re.fullmatch(r"\+[1-9]\d{6,14}", value) else ""


def alias_hash(value):
    return recipient_hash("alias", str(value)) if isinstance(value, str) and 0 < len(value) <= 255 else ""


def timestamp(value):
    """Normalize only an explicit provider timestamp, never the receipt time."""
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    value = str(value)
    if len(value) > 64:
        return None
    if value.isdigit() and len(value) <= 12:
        return value
    try:
        parsed = parse_datetime(value) or parsedate_to_datetime(value)
        return str(int(parsed.timestamp())) if parsed and parsed.tzinfo is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def twilio_payload(params, kind):
    message_id = params.get("MessageSid", "")
    if not isinstance(message_id, str) or not re.fullmatch(r"[A-Za-z0-9]{1,255}", message_id):
        return None
    if kind == "inbound":
        opt_out = params.get("OptOutType", "").upper()
        stop = opt_out == "STOP" if opt_out else params.get("Body", "").strip().upper() in SMS_STOP
        return message_id, {"message_id": message_id, "phone_hash": phone_hash(params.get("From")), "stop": stop,
                            "opt_out_type": opt_out if opt_out in {"STOP", "START", "HELP"} else "",
                            "timestamp": timestamp(params.get("Timestamp"))}
    status = params.get("MessageStatus") or params.get("SmsStatus", "")
    if status not in {"queued", "accepted", "sending", "sent", "delivered", "read", "failed", "undelivered"}:
        return None
    segments = params.get("NumSegments", "")
    billed = int(segments) if len(segments) <= 5 and segments.isascii() and segments.isdigit() and 0 <= int(segments) <= 32767 else None
    return f"{message_id}:{status}", {"message_id": message_id, "status": status,
        "error_code": code(params.get("ErrorCode")), "billed_segments": billed,
        "timestamp": timestamp(params.get("Timestamp") or params.get("DateSent"))}


def meta_payloads(document, phone_number_id):
    if not isinstance(document, dict) or not isinstance(document.get("entry", []), list):
        return
    for entry in document.get("entry", []):
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes", [])
        if not isinstance(changes, list):
            continue
        for change in changes:
            value = change.get("value", {}) if isinstance(change, dict) else {}
            metadata = value.get("metadata", {}) if isinstance(value, dict) else {}
            if not isinstance(metadata, dict) or str(metadata.get("phone_number_id", "")) != phone_number_id:
                continue
            statuses = value.get("statuses") or []
            if not isinstance(statuses, list):
                statuses = []
            for item in statuses:
                if not isinstance(item, dict):
                    continue
                message_id, status = item.get("id"), item.get("status")
                if not isinstance(message_id, str) or not message_id or len(message_id) > 255:
                    continue
                if status not in {"accepted", "sent", "delivered", "read", "failed"}:
                    continue
                errors = item.get("errors") or [{}]
                if not isinstance(errors, list):
                    errors = [{}]
                recipient = item.get("recipient", {})
                recipient = recipient if isinstance(recipient, dict) else {}
                yield "status", f"{message_id}:{status}", {
                    "message_id": message_id, "status": status, "timestamp": timestamp(item.get("timestamp")),
                    "error_code": code(errors[0].get("code")) if isinstance(errors[0], dict) else "",
                    "delivery_id": str(item.get("biz_opaque_callback_data", ""))[:64],
                    "alias_hash": alias_hash(item.get("user_id") or item.get("recipient_user_id") or recipient.get("user_id")),
                    "phone_hash": phone_hash(item.get("recipient_id") or recipient.get("wa_id")),
                }
            contacts = value.get("contacts") or []
            if not isinstance(contacts, list):
                contacts = []
            messages = value.get("messages") or []
            if not isinstance(messages, list):
                messages = []
            for item in messages:
                if not isinstance(item, dict):
                    continue
                message_id = item.get("id")
                if not isinstance(message_id, str) or not message_id or len(message_id) > 255:
                    continue
                contact = next((c for c in contacts if isinstance(c, dict) and
                    ((item.get("from") and c.get("wa_id") == item["from"]) or
                     (item.get("from_user_id") and c.get("user_id") == item["from_user_id"]))), {})
                # Meta may identify username users solely by from_user_id/user_id.
                alias = item.get("from_user_id") or item.get("user_id") or contact.get("user_id")
                phone = item.get("from") or contact.get("wa_id")
                text = item.get("text", {})
                body = text.get("body", "") if isinstance(text, dict) else ""
                keyword = body.strip().upper() if isinstance(body, str) else ""
                context = item.get("context") or {}
                context = context if isinstance(context, dict) else {}
                yield "inbound", message_id, {"message_id": message_id,
                    "phone_hash": phone_hash(phone), "alias_hash": alias_hash(alias),
                    "context_id": str(context.get("id", ""))[:255],
                    "stop": keyword in WHATSAPP_STOP, "timestamp": timestamp(item.get("timestamp"))}
