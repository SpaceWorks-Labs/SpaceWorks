"""Owner decision #107: SpaceWorks-HQ became SpaceWorks-Labs.

An existing install's saved repository and image names migrate automatically the next
time the updater, installer re-run or compose wrapper configures the release; forks and
any other owner are never touched.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts" / "spaceworks-repository.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required")


def configure(tmp_path, saved, env=None):
    settings = tmp_path / "settings.conf"
    settings.write_text(saved, encoding="utf-8")
    settings.chmod(0o600)
    script = (
        f'ROOT="{tmp_path}"; source "{HELPER}"; '
        "configure_release_repository && "
        'printf "%s\\n%s\\n%s\\n" "$SPACEWORKS_REPOSITORY" "$MAKERSPACE_BACKEND_IMAGE" "$MAKERSPACE_FRONTEND_IMAGE"'
    )
    clean = {"PATH": "/usr/bin:/bin", "SPACEWORKS_STATIC_ENV_FILE": str(settings), **(env or {})}
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=clean, check=True)
    return result.stdout.splitlines(), result.stderr, settings.read_text(encoding="utf-8"), settings


def test_old_org_names_are_migrated_persisted_and_logged(tmp_path):
    values, log, saved, settings = configure(tmp_path, (
        "A=1\n"
        "SPACEWORKS_REPOSITORY=SpaceWorks-HQ/SpaceWorks\n"
        'MAKERSPACE_BACKEND_IMAGE="ghcr.io/spaceworks-hq/spaceworks-backend"\n'
        "MAKERSPACE_FRONTEND_IMAGE=ghcr.io/spaceworks-hq/spaceworks-frontend\n"
    ))
    assert values == ["SpaceWorks-Labs/SpaceWorks", "ghcr.io/spaceworks-labs/spaceworks-backend",
                      "ghcr.io/spaceworks-labs/spaceworks-frontend"]
    assert saved == (
        "A=1\n"
        "SPACEWORKS_REPOSITORY=SpaceWorks-Labs/SpaceWorks\n"
        "MAKERSPACE_BACKEND_IMAGE=ghcr.io/spaceworks-labs/spaceworks-backend\n"
        "MAKERSPACE_FRONTEND_IMAGE=ghcr.io/spaceworks-labs/spaceworks-frontend\n"
    )
    assert log.count("NOTICE:") == 3 and "SpaceWorks-Labs" in log
    assert settings.stat().st_mode & 0o777 == 0o600
    assert sorted(p.name for p in tmp_path.iterdir()) == ["settings.conf"]


def test_defaults_follow_the_migrated_repository_owner(tmp_path):
    values, _, saved, _ = configure(tmp_path, "SPACEWORKS_REPOSITORY=spaceworks-hq/SpaceWorks\n")
    assert values == ["SpaceWorks-Labs/SpaceWorks", "ghcr.io/spaceworks-labs/spaceworks-backend",
                      "ghcr.io/spaceworks-labs/spaceworks-frontend"]
    assert saved == "SPACEWORKS_REPOSITORY=SpaceWorks-Labs/SpaceWorks\n"


def test_an_exported_old_name_is_switched_without_a_saved_value(tmp_path):
    values, log, saved, _ = configure(tmp_path, "A=1\n", {"SPACEWORKS_REPOSITORY": "SpaceWorks-HQ/SpaceWorks"})
    assert values[0] == "SpaceWorks-Labs/SpaceWorks"
    assert saved == "A=1\n" and "NOTICE:" in log


@pytest.mark.parametrize("saved", [
    "SPACEWORKS_REPOSITORY=my-fork/SpaceWorks\n",
    "SPACEWORKS_REPOSITORY=SpaceWorks-HQ-fork/SpaceWorks\n",
    "SPACEWORKS_REPOSITORY=SpaceWorks-Labs/SpaceWorks\nMAKERSPACE_BACKEND_IMAGE=registry.example.org/spaceworks-hq/backend\n",
])
def test_forks_and_other_owners_are_left_untouched(tmp_path, saved):
    _, log, after, _ = configure(tmp_path, saved)
    assert after == saved
    assert "NOTICE:" not in log
