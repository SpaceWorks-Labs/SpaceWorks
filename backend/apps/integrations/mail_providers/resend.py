"""Anymail transport with Resend's HTTP idempotency header (not a mail header)."""

from anymail.backends.resend import EmailBackend as ResendBackend


class EmailBackend(ResendBackend):
    def build_message_payload(self, message, defaults):
        payload = super().build_message_payload(message, defaults)
        key = getattr(message, "spaceworks_idempotency_key", "")
        if key:
            payload.headers["Idempotency-Key"] = key
        return payload
