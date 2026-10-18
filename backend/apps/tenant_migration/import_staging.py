"""Ephemeral age decryption; carried DEKs are never written to plaintext disk."""

import base64
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

from django.conf import settings

from apps.backup.archive_builder import _require_binary

from .insertion_errors import ArchiveFormatError

MAX_MEMBER_BYTES = 2 * 1024 * 1024 * 1024
MAX_ARCHIVE_BYTES = 20 * 1024 * 1024 * 1024


def seal_rows_sidecar(root, output_fd):
    """Keep row-only request reads encrypted without copying the object payloads."""
    recipient = settings.TENANT_MIGRATION_AGE_RECIPIENT
    if not recipient:
        raise ArchiveFormatError("The target age recipient is not configured.")
    process = None
    try:
        _require_binary("age")
        process = subprocess.Popen(
            ["age", "-r", recipient], stdin=subprocess.PIPE,
            stdout=output_fd, stderr=subprocess.DEVNULL,
        )
        if process.stdin is None:
            raise OSError("age stdin pipe was not created")
        with tarfile.open(fileobj=process.stdin, mode="w|") as archive:
            for path in sorted(item for item in Path(root).rglob("*") if item.is_file()):
                relative = path.relative_to(root)
                if relative.parts[0] != "objects":
                    archive.add(path, arcname=relative.as_posix(), recursive=False)
        process.stdin.close()
        if process.wait() != 0:
            raise ArchiveFormatError("The encrypted rows archive could not be sealed.")
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        raise ArchiveFormatError("The encrypted rows archive could not be sealed.") from exc
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.wait()
            if process.stdin is not None:
                process.stdin.close()


@contextmanager
def decrypted_archive(encrypted_path, *, require_carried_keys=True):
    from apps.operations.cloud_jobs.admission import assert_ciphertext, assert_archive, free
    assert_ciphertext(encrypted_path)
    from apps.backup.managed.staging import is_locator, materialize
    if is_locator(encrypted_path):
        with materialize(encrypted_path) as local:
            with decrypted_archive(local, require_carried_keys=require_carried_keys) as result:
                yield result
        return
    identity = settings.TENANT_MIGRATION_AGE_IDENTITY_FILE
    if not identity:
        raise ArchiveFormatError("The target age identity is not configured.")
    try:
        _require_binary("age")
    except RuntimeError as exc:
        raise ArchiveFormatError("The age decryptor is unavailable.") from exc
    tempdir = tempfile.TemporaryDirectory(prefix="spaceworks-import-")
    root = Path(tempdir.name, "archive")
    root.mkdir()
    try:
        process = subprocess.Popen(
            ["age", "--decrypt", "-i", identity, str(encrypted_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        tempdir.cleanup()
        raise ArchiveFormatError("The age decryptor could not be started.") from exc
    carried = None
    seen, total_size = set(), 0
    try:
        if process.stdout is None:
            raise ArchiveFormatError("The age decrypt stream was not created.")
        with tarfile.open(fileobj=process.stdout, mode="r|") as bundle:
            for member in bundle:
                if not member.isfile():
                    if member.isdir():
                        continue
                    raise ArchiveFormatError("The migration archive contains a link or device.")
                relative = _safe_relative_path(member.name)
                key = relative.as_posix()
                if key in seen:
                    raise ArchiveFormatError("The migration archive contains a duplicate path.")
                seen.add(key)
                if free() and (len(seen) > 512 or member.size > 2 * 1024 * 1024):
                    raise ArchiveFormatError("This import exceeds the free archive limits; use an external full worker.")
                if member.size > MAX_MEMBER_BYTES:
                    raise ArchiveFormatError("A migration archive member is too large.")
                total_size += member.size
                if total_size > MAX_ARCHIVE_BYTES or (free() and total_size > 2 * 1024 * 1024):
                    raise ArchiveFormatError("The migration archive is too large.")
                source = bundle.extractfile(member)
                if source is None:
                    raise ArchiveFormatError("An archive member could not be read.")
                if key == "keys/deks.json":
                    carried = _decode_keys(source.read())
                    continue
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
        if process.wait() != 0:
            raise ArchiveFormatError("The encrypted migration archive could not be decrypted.")
        if carried is None and require_carried_keys:
            raise ArchiveFormatError("The migration archive has no carried-key payload.")
        assert_archive(root)
        yield root, carried
    except Exception:
        if process.poll() is None:
            process.kill()
            process.wait()
        raise
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        tempdir.cleanup()


def _safe_relative_path(name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ArchiveFormatError("The migration archive contains an unsafe path.")
    return path


def _decode_keys(payload):
    try:
        values = json.loads(payload)["keys"]
        from apps.operations.cloud_jobs.admission import free
        if free() and len(values) > 8:
            raise ArchiveFormatError("This import exceeds the free profile's eight-key limit; use an external full worker.")
        records = []
        for value in values:
            record = dict(value)
            if "dek_base64" in record:
                record["dek"] = base64.b64decode(
                    record.pop("dek_base64"), validate=True
                )
            records.append(record)
        return tuple(records)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ArchiveFormatError("The carried-key payload is invalid.") from exc
