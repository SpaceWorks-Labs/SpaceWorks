"""Immutable source-DEK enumeration shared with the Lane D tenant-exit envelope."""

from dataclasses import dataclass

from apps.backup.digests import sha256_bytes
from apps.backup.build_errors import BackupBuildError
from apps.encryption.models import MakerspaceEncryptionKey


@dataclass(frozen=True)
class StagedDekRow:
    row_identity: int
    makerspace_id: int
    version: int
    status: str
    broker_backend: str
    broker_key_id: str
    wrapped_dek: bytes
    wrapped_dek_sha256: str


SUPPORTED_STATUSES = frozenset(MakerspaceEncryptionKey.Status.values)
SUPPORTED_BACKENDS = frozenset(MakerspaceEncryptionKey.BrokerBackend.values)


def enumerate_staged_deks(makerspace_id, *, using="default"):
    """Freeze exact raw key rows while the caller owns the snapshot transaction."""
    fields = (
        "pk", "makerspace_id", "version", "status", "broker_backend",
        "broker_key_id", "wrapped_dek",
    )
    rows = MakerspaceEncryptionKey._base_manager.using(using).filter(
        makerspace_id=makerspace_id
    ).order_by("pk").values_list(*fields)
    result = []
    for values in rows:
        row_id, owner, version, status, backend, key_id, wrapped = values
        immutable_wrapped = bytes(wrapped)
        result.append(StagedDekRow(
            row_identity=row_id,
            makerspace_id=owner,
            version=version,
            status=status,
            broker_backend=backend,
            broker_key_id=key_id,
            wrapped_dek=immutable_wrapped,
            wrapped_dek_sha256=sha256_bytes(immutable_wrapped),
        ))
    return tuple(result)


def validate_staged_deks(staged):
    """Validate immutable source-key identity and wrapped-byte integrity."""
    identities = set()
    versions = set()
    for row in staged:
        identity = (row.row_identity, row.makerspace_id)
        if identity in identities or row.version in versions:
            raise BackupBuildError("W8 staging contains a duplicate key row.")
        identities.add(identity)
        versions.add(row.version)
        valid = (
            # Positive, not merely int-typed: these are database primary keys, so
            # 0 or a negative value is a substituted row, not a real one.
            type(row.row_identity) is int
            and row.row_identity > 0
            and type(row.makerspace_id) is int
            and row.makerspace_id > 0
            and type(row.version) is int
            and row.version > 0
            and row.status in SUPPORTED_STATUSES
            and row.broker_backend in SUPPORTED_BACKENDS
            and isinstance(row.broker_key_id, str)
            and bool(row.broker_key_id)
            and isinstance(row.wrapped_dek, bytes)
            and bool(row.wrapped_dek)
            and sha256_bytes(row.wrapped_dek) == row.wrapped_dek_sha256
        )
        if not valid:
            raise BackupBuildError("W8 staging contains an unsupported or substituted key row.")
