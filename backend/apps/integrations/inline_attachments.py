"""Confirmation-email attachments derived from the live source at send time (#169, lane L6).

A domain registers one callback per envelope `source_kind` (events registrations,
bookings). At every send and retry the callback rebuilds what the email carries:
`InlineAttachment` bytes made on the spot (a calendar invite; never stored) and typed
`AttachmentReference`s (a ticket PDF, rendered and re-authorized by its source). Email
only: chat channels never see these. A failing callback drops the extras, never the email.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)
INLINE_TYPES = frozenset({"text/calendar"})
_CALLBACKS = {}


@dataclass(frozen=True)
class InlineAttachment:
    filename: str
    content: bytes
    mimetype: str

    def __post_init__(self):
        if (self.mimetype.split(";", 1)[0] not in INLINE_TYPES or not isinstance(self.content, bytes)
                or len(self.content) > 256 * 1024 or not 1 <= len(self.filename) <= 80):
            raise ValueError("Unsupported inline attachment.")


def register_confirmation_attachments(source_kind, callback):
    if source_kind in _CALLBACKS and _CALLBACKS[source_kind] is not callback:
        raise ValueError("Duplicate confirmation attachment source.")
    _CALLBACKS[source_kind] = callback


def confirmation_attachments(envelope):
    callback = _CALLBACKS.get(envelope.source_kind)
    if callback is None:
        return ()
    try:
        return tuple(callback(envelope))
    except Exception as exc:
        logger.warning("confirmation_attachments_failed", extra={"envelope_id": envelope.pk,
                                                                  "failure_type": type(exc).__name__})
        return ()
