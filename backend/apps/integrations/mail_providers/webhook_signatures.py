"""Native Resend/Svix and Mailgun verification; bounded input, no raw persistence."""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class MailEvent:
    event_id: str
    message_id: str
    status: str | None


def recent(stamp):
    return isinstance(stamp, str) and stamp.isascii() and stamp.isdigit() and len(stamp) <= 12 and abs(time.time() - int(stamp)) <= 300


def verify(provider, raw, headers, credentials):
    if len(raw) > 16384:
        raise ValueError("Invalid webhook.")
    body = json.loads(raw)
    if provider == "resend":
        event_id, stamp = headers.get("svix-id", ""), headers.get("svix-timestamp", "")
        if not recent(stamp) or not event_id.isascii() or not 1 <= len(event_id) <= 200:
            raise ValueError("Invalid webhook.")
        secret = credentials.get("webhook_secret", "")
        if not secret.startswith("whsec_"):
            raise ValueError("Invalid webhook.")
        key = base64.b64decode(secret[6:], validate=True)
        expected = base64.b64encode(hmac.new(key, event_id.encode() + b"." + stamp.encode() + b"." + raw,
                                           hashlib.sha256).digest()).decode()
        signatures = headers.get("svix-signature", "")
        if len(signatures) > 4096 or not signatures.isascii() or not any(
                hmac.compare_digest(expected, part[3:]) for part in signatures.split() if part.startswith("v1,")):
            raise ValueError("Invalid webhook.")
        status = {"email.delivered": "delivered", "email.bounced": "bounce", "email.complained": "complaint"}.get(body.get("type"))
        message_id = body.get("data", {}).get("email_id", "")
    elif provider == "mailgun":
        signature = body.get("signature", {})
        stamp, token = signature.get("timestamp", ""), signature.get("token", "")
        key = credentials.get("webhook_signing_key", "")
        if not key or not recent(stamp) or not isinstance(token, str) or not 1 <= len(token) <= 200:
            raise ValueError("Invalid webhook.")
        expected = hmac.new(key.encode(), (stamp + token).encode(), hashlib.sha256).hexdigest()
        supplied = signature.get("signature", "")
        if not isinstance(supplied, str) or not supplied.isascii() or not hmac.compare_digest(expected, supplied):
            raise ValueError("Invalid webhook.")
        event = body.get("event-data", {})
        event_id = event.get("id", "")
        message_id = event.get("message", {}).get("headers", {}).get("message-id", "")
        status = {"delivered": "delivered", "complained": "complaint"}.get(event.get("event"))
        if event.get("event") == "failed" and event.get("severity") == "permanent":
            status = "bounce"
    else:
        raise ValueError("Invalid webhook.")
    if not all(isinstance(value, str) and 1 <= len(value) <= 200 for value in (event_id, message_id)):
        raise ValueError("Invalid webhook.")
    return MailEvent(event_id, message_id, status)
