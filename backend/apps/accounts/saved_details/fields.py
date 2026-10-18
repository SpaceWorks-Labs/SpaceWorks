"""F owns descriptors/normalization; G installs this small, explicit adapter.

No private vault value is accepted until the authoritative form registry is wired.
The registry cannot fall back to a second, subtly different list of field rules.
"""
from typing import Protocol

from .errors import SavedDetailsError, unavailable


class ProfileFields(Protocol):
    def descriptors(self) -> tuple[dict, ...]: ...
    def normalize(self, key: str, value: object) -> object: ...


_provider = None


def install_profile_fields(provider: ProfileFields):
    global _provider
    if _provider is not None and _provider is not provider:
        raise RuntimeError("Saved details profile fields already installed.")
    _provider = provider


def descriptor(key):
    if _provider is None:
        raise unavailable()
    item = next((d for d in _provider.descriptors() if d["field_key"] == key), None)
    if item is None or not item.get("persistable", True):
        raise SavedDetailsError("unknown_field_key", "Choose a supported saved detail.")
    return item


def normalize(key, value):
    descriptor(key)
    try:
        result = _provider.normalize(key, value)
    except (ValueError, TypeError) as exc:
        raise SavedDetailsError("invalid_field_type", "Check this saved detail.") from exc
    if result in (None, "", []):
        raise SavedDetailsError("invalid_field_type", "Use Delete to remove a saved detail.")
    return result
