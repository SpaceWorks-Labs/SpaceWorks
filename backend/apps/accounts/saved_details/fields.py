"""F owns descriptors/normalization; G installs this small, explicit adapter.

No private vault value is accepted until the authoritative form registry is wired.
The registry cannot fall back to a second, subtly different list of field rules.
"""
from typing import Protocol
import re
from uuid import UUID

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


def selected_values(validated_form, choices, base_versions):
    """Normalize only explicitly chosen visible mappings using F's registry."""
    if not isinstance(choices, dict) or any(type(v) is not bool for v in choices.values()):
        raise SavedDetailsError("invalid_save_choices", "Check save choices.")
    if set(choices) - set(validated_form.mapped_values):
        raise SavedDetailsError("invalid_save_choices", "Choose visible mapped answers only.")
    stage = str(validated_form.subject.kind) == "stage_response"
    if stage and set(validated_form.mapped_values) & {"date_of_birth", "age_at_event"}:
        raise SavedDetailsError("stage_age_question_unsupported", "Stage forms cannot ask for date of birth or age.")
    selected = {k: normalize(k, validated_form.mapped_values[k]) for k, save in choices.items() if save}
    if not isinstance(base_versions, dict) or any(type(base_versions.get(k)) is not int or base_versions[k] < 0 for k in selected):
        raise SavedDetailsError("saved_version_required", "Review saved detail versions before submitting.")
    return selected


def require_form_slot(slot):
    if not isinstance(slot, str) or re.fullmatch(r"base|stage:[1-9][0-9]*", slot) is None:
        raise SavedDetailsError("invalid_form_slot", "Choose a canonical form slot.")


def require_form_operation(outer_operation_id, slot, subject):
    if outer_operation_id is None and slot is None:
        return  # standalone one-form commands keep their own operation UUID
    require_form_slot(slot)
    if not isinstance(outer_operation_id, UUID) or (slot != "base") != (str(subject.kind) == "stage_response"):
        raise SavedDetailsError("invalid_form_slot", "Choose a matching form slot and outer operation.")
