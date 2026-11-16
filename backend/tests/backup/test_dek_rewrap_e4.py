import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from apps.backup.dek_rewrap import StagedDekRow
from apps.backup.main_projection_registry import RowDisposition, table_rules
from apps.backup.build_errors import BackupBuildError
from apps.encryption.models import MakerspaceEncryptionKey
from apps.makerspaces.models import Makerspace


pytestmark = pytest.mark.django_db(transaction=True)


DEK = b"D" * 32
WRAPPED_ONE = b"immutable-wrapped-one"
WRAPPED_TWO = b"immutable-wrapped-two"
RECIPIENTS = ("age1tenant-e4-one", "age1tenant-e4-two")


def _row(row_id=1, version=1, wrapped=WRAPPED_ONE, **changes):
    value = StagedDekRow(
        row_identity=row_id,
        makerspace_id=41,
        version=version,
        status=MakerspaceEncryptionKey.Status.ACTIVE,
        broker_backend=MakerspaceEncryptionKey.BrokerBackend.LOCAL,
        broker_key_id="local:test",
        wrapped_dek=wrapped,
        wrapped_dek_sha256=hashlib.sha256(wrapped).hexdigest(),
    )
    return replace(value, **changes)


def _fake_age(commands):
    def run(command, *, input, **_kwargs):
        commands.append(tuple(command))
        output = Path(command[command.index("-o") + 1])
        # Model an opaque envelope so plaintext-leak assertions are meaningful.
        output.write_bytes(b"sealed:" + hashlib.sha256(input).digest())
    return run


def _record(row, root):
    path = root / f"{row.row_identity}.json.age"
    return {
        "row_identity": row.row_identity,
        "makerspace_id": row.makerspace_id,
        "version": row.version,
        "status": row.status,
        "source_broker_backend": row.broker_backend,
        "source_broker_key_id": row.broker_key_id,
        "source_wrapped_dek_sha256": row.wrapped_dek_sha256,
        "path": f"keys/deks/{row.row_identity}.json.age",
        "size_bytes": path.stat().st_size,
        "ciphertext_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def test_encryption_key_rows_are_slice_owned_in_projection_registry():
    rule = next(
        item for item in table_rules()
        if item.model._meta.label == "encryption.MakerspaceEncryptionKey"
    )
    assert rule.disposition == RowDisposition.COPY_TO_SLICE
    assert rule.predicate.any_paths == ("makerspace",)


