"""Provider-neutral storage contracts. No provider is inferred from its hostname."""

from .contracts import CapabilityError, StorageCapabilities, StorageIdentity
from .runtime import capabilities_for, require_capability

__all__ = [
    "CapabilityError", "StorageCapabilities", "StorageIdentity",
    "capabilities_for", "require_capability",
]
