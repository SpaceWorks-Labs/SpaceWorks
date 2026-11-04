"""Domain lanes register live authority, source validity and audience checks here."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class NotificationSource:
    # Must reload the subject, source revision, owner/campaign audience and original
    # sender authority. Runs at send, retry, deferred release AND digest rendering.
    eligible: Callable
    render: Callable | None = None


SOURCES = {}


def register_source(kind, source):
    if kind in SOURCES and SOURCES[kind] != source:
        raise ValueError("Duplicate notification source")
    SOURCES[kind] = source


def source_eligible(envelope):
    if envelope.source_kind == "notification.digest":
        from .notification_digest import eligible_digest
        return eligible_digest(envelope)
    source = SOURCES.get(envelope.source_kind)
    return bool(source and source.eligible(envelope))


def render(envelope):
    if envelope.source_kind == "notification.digest":
        from .notification_digest import render_digest
        return render_digest(envelope)
    source = SOURCES.get(envelope.source_kind)
    if source and source.render:
        return source.render(envelope)
    import json
    return json.loads(envelope.message_body or "{}")
