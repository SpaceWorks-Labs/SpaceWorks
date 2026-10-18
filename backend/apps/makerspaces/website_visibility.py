"""Query-free registration of typed public domain adapters. No separable imports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, Protocol, TypeVar, TYPE_CHECKING
from uuid import UUID

from django.http import Http404

from .platform import feature_enabled, module_enabled
from .servability import is_servable

if TYPE_CHECKING:
    from .website_serving import PublicCard


class PublicSubject(Protocol):
    makerspace: Any
    public_token: Any


Subject = TypeVar("Subject", bound=PublicSubject)


@dataclass(frozen=True)
class WebsiteAdapter(Generic[Subject]):
    kind: str
    module: str
    resolve: Callable[[str | None, UUID], Subject]
    discover: Callable[[Any, dict[str, Any]], Any]
    card: Callable[[Subject], PublicCard]
    page: Callable[[Subject], Any]
    filters: type | None = None
    cards: Callable[[list[Subject]], list[PublicCard]] | None = None
    action_label: str = "Register"
    share_card: Callable[[Subject], PublicCard] | None = None


_adapters: dict[str, WebsiteAdapter] = {}


def register(adapter: WebsiteAdapter):
    if adapter.kind in _adapters and _adapters[adapter.kind] != adapter:
        raise RuntimeError(f"Duplicate public website adapter: {adapter.kind}")
    _adapters[adapter.kind] = adapter


def adapters():
    from .module_registry import module_available
    from .editions import public_surface_available
    return tuple(adapter for adapter in _adapters.values()
                 if module_available(adapter.module) and public_surface_available(adapter.module))


def adapter_for(kind):
    adapter = _adapters.get(kind)
    if adapter is None or adapter not in adapters():
        raise Http404
    return adapter


def website_enabled(subject: PublicSubject, module: str):
    space = subject.makerspace
    return (is_servable(space) and module_enabled(space, module)
            and feature_enabled(space, f"{module}.website"))


def released_page(subject: PublicSubject, module: str, page):
    """The domain resolves its core gate first; release never broadens it."""
    if not website_enabled(subject, module) or page is None or not page.released:
        raise Http404
    return page
