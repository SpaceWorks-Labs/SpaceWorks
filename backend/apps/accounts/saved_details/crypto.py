"""Explicit account envelope boundary. Never unwrap a broker key under domain locks."""
import json
from uuid import UUID

from apps.encryption import account_crypto
from apps.encryption.account_services import get_account_key
from apps.encryption.account_write_fence import AccountKeyChanged


def canonical(value):
    def encode(item):
        if isinstance(item, UUID):
            return str(item)
        raise TypeError("Use JSON values or UUID operation IDs.")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=encode)


def seal(value, row, field, key):
    return account_crypto.encrypt(
        canonical(value).encode(), key.dek, key_version=key.version,
        user_id=row.user_id, table=row._meta.db_table, pk=row.pk, field=field,
    )


def open_value(row, field, key=None):
    envelope = row.__dict__[field]
    if key is not None and account_crypto.envelope_version(envelope) != key.version:
        raise AccountKeyChanged("Account key changed. Retry this command.")
    if key is None:
        key = get_account_key(row.user_id, version=account_crypto.envelope_version(envelope))
    return json.loads(account_crypto.decrypt(
        envelope, key.dek, user_id=row.user_id,
        table=row._meta.db_table, pk=row.pk, field=field,
    ))
