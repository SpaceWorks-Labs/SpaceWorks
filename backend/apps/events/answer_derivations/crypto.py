"""Tenant-only source crypto. Preparation does broker work before event locks."""

from django.conf import settings
from django.db import connection

from apps.encryption.blind_index import active_generation
from apps.encryption.crypto import PiiUnavailable, decrypt_with_key_loader, encrypt
from apps.encryption.models import MakerspaceEncryptionKey
from apps.encryption.registry import field_for
from apps.encryption.services import get_dek, unwrap_dek

from .errors import pii_unavailable
from .models import EventAnswerDerivation
from apps.transaction_guards import in_domain_transaction


def require_preparation_boundary():
    if in_domain_transaction():
        raise RuntimeError("Prepare private DOB sources outside domain transactions.")


def prepared_key(makerspace_id):
    """Use an already provisioned host key; never lazily switch on tenant PII."""
    require_preparation_boundary()
    try:
        if not settings.PII_ENCRYPTION_ENABLED:
            raise PiiUnavailable()
        mapping = field_for(EventAnswerDerivation, "source_dob_envelope")
        if (mapping is None or mapping.makerspace_path != "event.makerspace_id"
                or mapping.classification != "source" or mapping.index_kind != "none"):
            raise PiiUnavailable()
        active_generation()  # The staged search readiness prerequisite remains binding.
        key = MakerspaceEncryptionKey.objects.get(makerspace_id=makerspace_id, status="active")
        return key.version, unwrap_dek(key)
    except (PiiUnavailable, MakerspaceEncryptionKey.DoesNotExist,
            MakerspaceEncryptionKey.MultipleObjectsReturned) as exc:
        raise pii_unavailable() from exc


def allocate_id():
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval(pg_get_serial_sequence(%s, %s))", [
            EventAnswerDerivation._meta.db_table, EventAnswerDerivation._meta.pk.column,
        ])
        return cursor.fetchone()[0]


def encrypt_source(plaintext, *, pk, makerspace_id, version, dek, field="source_dob_envelope"):
    return encrypt(
        plaintext.encode("utf-8"), dek, key_version=version, makerspace_id=makerspace_id,
        table=EventAnswerDerivation._meta.db_table, pk=pk, field=field,
    )


def decrypt_source(row, *, envelope=None, field="source_dob_envelope"):
    # Projection/export callers must run after transaction locks are released:
    # a cache miss can reach KMS even for an existing key.
    require_preparation_boundary()
    try:
        return decrypt_with_key_loader(
            envelope or row.source_dob_envelope,
            makerspace_id=row.event.makerspace_id, table=row._meta.db_table, pk=row.pk,
            field=field, load_dek=lambda version: get_dek(row.event.makerspace_id, version),
        ).decode("utf-8")
    except (PiiUnavailable, UnicodeDecodeError) as exc:
        raise pii_unavailable() from exc
