"""Small, deliberately raw adapters used only by fenced PII maintenance."""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import connection

from apps.encryption.blind_index import canonical_email
from apps.encryption.crypto import decrypt_with_key_loader, is_envelope
from apps.encryption.registry import field_for, makerspace_id_for
from apps.encryption.services import get_dek


def decrypted_values(row, fields):
    """Authenticate every mapped envelope without invoking mapper dual-read."""
    values = {}
    for item in fields:
        raw = row.__dict__.get(item.field_name, "")
        if raw in ("", None) or not is_envelope(raw):
            values[item.field_name] = None
            continue
        makerspace_id = makerspace_id_for(row, item)
        values[item.field_name] = decrypt_with_key_loader(
            raw,
            makerspace_id=makerspace_id,
            table=row._meta.db_table,
            pk=row.pk,
            field=item.field_name,
            load_dek=lambda version: get_dek(makerspace_id, version, mandatory=item.encryption_required),
        ).decode("utf-8")
    return values


def validate_legacy_values(row, fields, values):
    """Validate rollback values before the legacy-only raw update is issued."""
    for item in fields:
        value = values.get(item.field_name)
        if value is None:
            continue
        model_field = row._meta.get_field(item.field_name)
        if item.max_length is not None and len(value) > item.max_length:
            raise ValidationError({item.field_name: gettext("Value exceeds the legacy maximum length.")})
        model_field.clean(value, row)
        if "email" in item.field_name and value:
            validate_email(value)
            if item.model_label in {"events.EventRegistration", "bookings.Booking"}:
                values[item.field_name] = canonical_email(value)
    required = {
        "hardware_requests.HardwareRequest": {"requester_username"},
        "events.EventRegistration": {"name", "email", "phone"},
        "bookings.Booking": {"name", "email", "phone"},
    }.get(row._meta.label, set())
    for name in required:
        value = values.get(name)
        if value in (None, ""):
            raise ValidationError({name: gettext("This field may not be blank.")})


def write_legacy_values(row, values, *, operation_kind="decrypt_rollback"):
    """Update source columns directly, so enabled mappers cannot re-encrypt them."""
    changed = {name: value for name, value in values.items() if value is not None}
    if any(item and item.encryption_required for item in (field_for(row, name) for name in changed)):
        raise ValidationError(gettext("Mandatory encrypted fields cannot be restored to plaintext."))
    if not changed:
        return False
    from .maintenance_programme import assert_immutable_maintenance
    assert_immutable_maintenance(row, changed, operation_kind)
    columns = [row._meta.get_field(name).column for name in changed]
    assignments = ", ".join(f'"{column}" = %s' for column in columns)
    params = [changed[name] for name in changed] + [row.pk]
    with connection.cursor() as cursor:
        cursor.execute(
            f'UPDATE "{row._meta.db_table}" SET {assignments} WHERE "{row._meta.pk.column}" = %s',
            params,
        )
    return True


# Compatibility name retained for maintenance callers from the G2 checkpoint.
from .maintenance_programme import encrypt_immutable as encrypt_immutable_snapshot
