"""Explicit owner-scope declarations; no tenant resolver or blind indexes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountPiiField:
    model_label: str
    field_name: str
    owner_field: str = "user_id"
    max_bytes: int = 65536


ACCOUNT_FIELDS = (
    AccountPiiField("accounts.MemberSavedDetail", "value_envelope", max_bytes=16384),
    AccountPiiField("accounts.SavedDetailUpdateIntent", "encrypted_payload"),
)


def fields_for(model_or_instance):
    return tuple(item for item in ACCOUNT_FIELDS if item.model_label == model_or_instance._meta.label)


def registered_labels():
    return tuple(sorted({item.model_label for item in ACCOUNT_FIELDS}))


def all_fields():
    return ACCOUNT_FIELDS
