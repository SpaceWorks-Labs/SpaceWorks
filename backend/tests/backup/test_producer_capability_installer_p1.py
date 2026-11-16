import hashlib
import json

from apps.backup.producer_capability import PRIVILEGED_SCRIPT_NAMES
from scripts.install_producer_capability import install_capability


def test_installer_hashes_the_bytes_present_at_install_time(
    tmp_path, settings
):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for index, name in enumerate(PRIVILEGED_SCRIPT_NAMES):
        (scripts / name).parent.mkdir(parents=True, exist_ok=True)
        (scripts / name).write_bytes(f"script-{index}:{name}\n".encode("ascii"))
    entrypoint = tmp_path / "entrypoint.py"
    entrypoint.write_bytes(b"entrypoint bytes independently hashed\n")
    migration = tmp_path / "apps" / "backup" / "migrations"
    migration.mkdir(parents=True)
    (migration / "0001_initial.py").write_bytes(b"migration bytes\n")
    marker = tmp_path / "host" / "public" / "producer-capability.json"

    install_capability(
        marker=marker,
        scripts_dir=scripts,
        entrypoint=entrypoint,
        migrations_dir=tmp_path / "apps",
        verification_key=settings.BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY,
        require_root_owned=False,
    )

    recorded = json.loads(marker.read_text(encoding="utf-8"))
    independently_hashed = {
        name: hashlib.sha256((scripts / name).read_bytes()).hexdigest()
        for name in PRIVILEGED_SCRIPT_NAMES
    }
    assert recorded["privileged_scripts"] == independently_hashed
    assert recorded["entrypoint_sha256"] == hashlib.sha256(
        entrypoint.read_bytes()
    ).hexdigest()
    assert marker.stat().st_mode & 0o777 == 0o444
    assert settings.BACKUP_ARCHIVE_SIGNING_PRIVATE_KEY not in marker.read_text(
        encoding="utf-8"
    )


def test_installer_imports_in_a_bare_container_without_django_settings():
    # setup runs it as `docker run --entrypoint python image .../install_producer_capability.py`
    # with no settings module and no environment file; it must not load any model.
    import os
    from pathlib import Path
    import subprocess
    import sys

    backend = Path(__file__).resolve().parents[2]
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"DJANGO_SETTINGS_MODULE", "PYTHONPATH"}}
    result = subprocess.run(
        [sys.executable, "-c", "import runpy, sys; runpy.run_path(sys.argv[1], run_name='imported')",
         str(backend / "scripts/install_producer_capability.py")],
        cwd="/", env=environment, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
