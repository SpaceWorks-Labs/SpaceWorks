"""Versioned event-only extension seam. Hackathon workflows remain separate."""

from dataclasses import dataclass
from typing import Callable
from rest_framework.exceptions import ValidationError
from .event_permissions import EDIT_DETAILS, PUBLISH_SCHEDULE

REGISTRY_VERSION = 1
FUTURE_NAMES = frozenset({"prizes", "judges", "mentors", "project_gallery", "results"})


@dataclass(frozen=True)
class PublishedSectionContext:
    event_id: int
    series_id: int | None
    revision_id: str
    source_anchor_start: object


@dataclass(frozen=True)
class SectionProvider:
    key: str
    schema: type
    owner_kinds: tuple[str, ...]
    feature: str
    permission: str
    public_projection: Callable
    version: int = REGISTRY_VERSION


_providers: dict[str, SectionProvider] = {}


def register(provider):
    if (provider.version != REGISTRY_VERSION or not provider.key or provider.key in _providers
            or provider.permission not in {EDIT_DETAILS, PUBLISH_SCHEDULE}
            or not set(provider.owner_kinds) <= {"event", "series"}):
        raise ValueError("Invalid or duplicate event section provider.")
    _providers[provider.key] = provider


def validate_payload(key, payload):
    provider = _providers.get(key)
    if provider is None:
        raise ValidationError({"type": "This event section provider is not registered."})
    serializer = provider.schema(data=payload)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def project_provider(event, key, payload):
    # Resolve existing public/release gates before any provider can execute.
    from .website_visibility import visible_page
    from apps.makerspaces.platform import feature_enabled
    page = visible_page(event)
    provider = _providers.get(key)
    owner_kind = "series" if page.series_id else "event"
    if provider is None or owner_kind not in provider.owner_kinds or not feature_enabled(event.makerspace, provider.feature):
        return None
    context = PublishedSectionContext(event.pk, event.series_id, str(page.published_revision_id),
                                      page.published_revision.source_anchor_start)
    return provider.public_projection(context, payload)
