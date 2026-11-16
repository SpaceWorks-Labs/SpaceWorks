"""Query-free registration of runtime resource authority sources.

Only active separable apps register. Discovery evaluates callbacks against live rows;
neither credentials nor tenant actions are cached in this registry.
"""


from apps.accounts.staff_identity import is_person
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ResourceGrantSource:
    key: str
    has_authority: Callable
    entries: Callable
    payload_serializer: type | None = None


_sources = {}


def register(source):
    existing = _sources.get(source.key)
    if existing is not None and existing != source:
        raise ValueError(f"Duplicate resource grant source: {source.key}")
    _sources[source.key] = source


def registered_sources():
    return tuple(_sources.values())


def has_authority(actor, *, makerspace_ids=None):
    if not is_person(actor):
        return False
    return any(source.has_authority(actor, makerspace_ids=makerspace_ids)
               for source in registered_sources())


def payload_entries(actor, *, makerspace_ids=None):
    if not is_person(actor):
        return {source.key: [] for source in registered_sources()}
    return {source.key: source.entries(actor, makerspace_ids=makerspace_ids)
            for source in registered_sources()}
