"""Query-free source registry shared by campaigns, reminders and digest delivery."""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class DeliverySource:
    prepare: Callable  # reload authority/eligibility and set transient delivery_content
    finished: Callable = lambda log: None
    digestible: bool = True
    retry: Callable = lambda log, actor: None


SOURCES = {}


def register(kind, source):
    if kind in SOURCES and SOURCES[kind] != source:
        raise RuntimeError(f"Duplicate delivery source: {kind}")
    SOURCES[kind] = source


def has_retry_content(log):
    # Registered sources rebuild content and recheck live authority at delivery.
    # Redacted credential mail has no source and must remain unretriable.
    return bool(log.text_body or log.html_body or SOURCES.get(log.source_kind))


def digestible(log):
    if not getattr(log, "source_kind", ""):
        return True
    source = SOURCES.get(log.source_kind)
    return bool(source and source.digestible)


def prepare(log):
    # Reusing an instance for a retry must never reuse an earlier rendering.
    log.__dict__.pop("_rendered_email", None)
    if not getattr(log, "source_kind", ""):
        return True
    source = SOURCES.get(log.source_kind)
    # Unknown (including tombstoned) sources cannot send old content.
    return bool(source and source.prepare(log))


def finished(log):
    source = SOURCES.get(getattr(log, "source_kind", ""))
    if source:
        source.finished(log)


def retry(log, actor):
    """Restore domain retry state inside the caller's locked outbox transaction."""
    source = SOURCES.get(getattr(log, "source_kind", ""))
    if source:
        source.retry(log, actor)
