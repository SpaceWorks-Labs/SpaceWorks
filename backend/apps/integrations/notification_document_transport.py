"""Bounded PDF multipart encoding and personal-delivery guards for chat adapters."""
import json
import re
from uuid import uuid4

from .notification_slack_http import ProviderFailure, live_endpoint

MAX_DOCUMENT_BYTES = 5 * 1024 * 1024


def validate_document(filename, pdf_bytes):
    if (not isinstance(filename, str) or not filename.endswith(".pdf")
            or not 1 <= len(filename) <= 255 or re.search(r'[\x00-\x1f\x7f"\\/]', filename)
            or not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b"%PDF-")):
        raise ProviderFailure("provider_error")
    if len(pdf_bytes) > MAX_DOCUMENT_BYTES:
        raise ProviderFailure("document_too_large", retryable=True)


def personal_destination(config, delivery):
    config.refresh_from_db()
    if (not getattr(delivery, "endpoint_id", None) or not getattr(delivery, "envelope_id", None)
            or delivery.makerspace_id != config.makerspace_id
            or delivery.envelope.makerspace_id != config.makerspace_id
            or delivery.envelope.recipient_id != delivery.endpoint.user_id
            or delivery.integration_generation != config.generation
            or delivery.integration_identity != config.integration_identity
            or delivery.channel != config.channel or delivery.provider != config.provider):
        raise ProviderFailure("invalid_endpoint")
    return live_endpoint(config, delivery.endpoint)


def multipart(fields, *, filename, pdf_bytes, field="file"):
    validate_document(filename, pdf_bytes)
    boundary = "spaceworks-" + uuid4().hex
    chunks = []
    for name, value in fields.items():
        if not re.fullmatch(r"[A-Za-z0-9_\[\]]+", name):
            raise ProviderFailure("provider_error")
        value = value if isinstance(value, str) else json.dumps(value)
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
                      + value.encode() + b"\r\n")
    if not re.fullmatch(r"[A-Za-z0-9_\[\]]+", field):
        raise ProviderFailure("provider_error")
    chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                  'Content-Type: application/pdf\r\n\r\n'.encode() + pdf_bytes + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"
