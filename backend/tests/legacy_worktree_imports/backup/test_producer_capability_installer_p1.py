import pytest as _legacy_pytest

_legacy_pytest.skip('Not in release 0.12.0: apps.backup.errors, apps.backup.recipient_selection', allow_module_level=True)

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from apps.backup.producer_capability import PRIVILEGED_SCRIPT_NAMES
from scripts.install_producer_capability import install_capability


BACKEND_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = BACKEND_ROOT / "scripts" / "install_producer_capability.py"


def _run_standalone(arguments, *, input_text=""):
    # Match the root installer: no Django configuration or application secrets.
    environment = {
        name: value for name, value in os.environ.items()
        if name.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG"}
    }
    result = subprocess.run(
        [sys.executable, *arguments], cwd=BACKEND_ROOT, env=environment,
        input=input_text, text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_installer_import_does_not_initialize_django():
    _run_standalone(["-c", "\n".join([
        "import sys",
        "from scripts.install_producer_capability import install_capability",
        "from django.conf import settings",
        "assert not settings.configured",
        "assert 'apps.backup.models' not in sys.modules",
        "assert 'apps.backup.recipient_selection' not in sys.modules",
    ])])


def test_producer_refusals_keep_existing_backup_error_compatibility():
    from apps.backup.errors import BackupBuildError
    from apps.backup.producer_capability import ProducerCapabilityRefused
    from apps.backup.recipient_selection import BackupBuildError as LegacyBackupBuildError

    assert LegacyBackupBuildError is BackupBuildError
    assert issubclass(ProducerCapabilityRefused, LegacyBackupBuildError)


@pytest.mark.skipif(os.name != "posix", reason="Host marker writes require POSIX fsync.")
@pytest.mark.parametrize("install_mode", [
    "function",
    "subprocess",
    pytest.param("cli", marks=pytest.mark.skipif(
        getattr(os, "geteuid", lambda: -1)() != 0,
        reason="The production installer CLI requires root.",
    )),
])
def test_installer_hashes_the_bytes_present_at_install_time(
    tmp_path, settings, install_mode
):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for index, name in enumerate(PRIVILEGED_SCRIPT_NAMES):
        (scripts / name).write_bytes(f"script-{index}:{name}\n".encode("ascii"))
    entrypoint = tmp_path / "entrypoint.py"
    entrypoint.write_bytes(b"entrypoint bytes independently hashed\n")
    migration = tmp_path / "apps" / "backup" / "migrations"
    migration.mkdir(parents=True)
    (migration / "0001_initial.py").write_bytes(b"migration bytes\n")
    marker = tmp_path / "host" / "public" / "producer-capability.json"

    inputs = {
        "marker": str(marker),
        "scripts_dir": str(scripts),
        "entrypoint": str(entrypoint),
        "migrations_dir": str(tmp_path / "apps"),
        "verification_key": settings.BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY,
    }
    if install_mode == "function":
        install_capability(**inputs, require_root_owned=False)
    elif install_mode == "subprocess":
        _run_standalone(["-c", "\n".join([
            "import json, sys",
            "from scripts.install_producer_capability import install_capability",
            "install_capability(**json.load(sys.stdin), require_root_owned=False)",
            "from django.conf import settings",
            "assert not settings.configured",
            "assert 'apps.backup.models' not in sys.modules",
        ])], input_text=json.dumps(inputs))
    else:
        _run_standalone([
            str(INSTALLER), "--marker", str(marker),
            "--scripts-dir", str(scripts), "--entrypoint", str(entrypoint),
            "--migrations-dir", str(tmp_path / "apps"),
        ], input_text=f"BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY={inputs['verification_key']}\n")
        assert marker.stat().st_uid == 0
        assert marker.parent.stat().st_uid == 0

    recorded = json.loads(marker.read_text(encoding="utf-8"))
    independently_hashed = {
        name: hashlib.sha256((scripts / name).read_bytes()).hexdigest()
        for name in PRIVILEGED_SCRIPT_NAMES
    }
    assert recorded["privileged_scripts"] == independently_hashed
    assert recorded["entrypoint_sha256"] == hashlib.sha256(
        entrypoint.read_bytes()
    ).hexdigest()
    assert recorded["signing_key_fingerprint"] == hashlib.sha256(
        base64.b64decode(inputs["verification_key"])
    ).hexdigest()
    assert marker.stat().st_mode & 0o777 == 0o444
    assert settings.BACKUP_ARCHIVE_SIGNING_PRIVATE_KEY not in marker.read_text(
        encoding="utf-8"
    )
