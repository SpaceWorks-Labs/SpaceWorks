"""Encrypt complete Lane D staging before crossing a process/container boundary."""
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from django.conf import settings

from apps.backup.managed import staging
from .import_staging import decrypted_archive


def persist(capture_id, root, label):
    recipient = settings.TENANT_MIGRATION_AGE_RECIPIENT
    if not recipient or not settings.TENANT_MIGRATION_AGE_IDENTITY_FILE:
        raise ValueError("Managed capture requires its configured private staging age identity.")
    with tempfile.TemporaryDirectory(prefix="spaceworks-capture-seal-") as directory:
        path = Path(directory, "capture.age")
        with path.open("xb") as output:
            process = subprocess.Popen(["age", "-r", recipient], stdin=subprocess.PIPE,
                                       stdout=output, stderr=subprocess.DEVNULL)
            try:
                with tarfile.open(fileobj=process.stdin, mode="w|") as archive:
                    for item in sorted(Path(root).rglob("*")):
                        if item.is_symlink():
                            raise ValueError("Capture staging contains a link.")
                        if item.is_file():
                            archive.add(item, arcname=item.relative_to(root).as_posix(), recursive=False)
                process.stdin.close()
                if process.wait() != 0:
                    raise ValueError("The private capture could not be sealed.")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        locator = staging.store(path, owner=capture_id, label=label)
        staging.select(locator)
    return locator


def hydrate(capture_id, destination):
    locator = staging.latest(capture_id, "derived") or staging.latest(capture_id, "source")
    if not locator:
        raise ValueError("The durable capture staging is unavailable.")
    with decrypted_archive(locator, require_carried_keys=False) as (root, _keys):
        shutil.copytree(root, destination, dirs_exist_ok=False)
    Path(destination).chmod(0o700)
