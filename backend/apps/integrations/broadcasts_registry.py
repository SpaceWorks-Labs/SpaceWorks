"""Domain adapters declare policy; the common worker owns batching and outbox writes."""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class BroadcastAdapter:
    campaign_model: type
    delivery_model: type
    authorize: Callable
    recipients: Callable
    eligible: Callable
    render: Callable
    feature: str
    audit_prefix: str


ADAPTERS = {}


def register(kind, adapter):
    if kind in ADAPTERS and ADAPTERS[kind] != adapter:
        raise RuntimeError(f"Duplicate broadcast adapter: {kind}")
    ADAPTERS[kind] = adapter
    from .delivery_sources import DeliverySource, register as register_source
    from .broadcasts_delivery import prepare, finished, retry
    register_source(kind, DeliverySource(prepare, finished, digestible=False, retry=retry))
