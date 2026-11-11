"""The release verifier must check both published architectures, including failures."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")


@pytest.mark.parametrize("failure", ["", "linux/arm64", "linux/amd64"])
def test_every_package_platform_is_checked_and_any_missing_image_fails(failure):
    result = subprocess.run([BASH, "-c", '''
docker() { printf 'PULL %s\n' "$*"; [[ "$*" != *"${FAIL_PLATFORM:-no-failure}"* ]]; }
set -- 0.5.0-main.2.bbbbbbbbbbbb
source "$VERIFIER"
'''], env={**os.environ, "GHCR_OWNER": "example", "FAIL_PLATFORM": failure,
          "VERIFIER": (ROOT / "scripts/verify-release-images.sh").as_posix()},
        text=True, capture_output=True, timeout=10)
    assert result.returncode == (1 if failure else 0)
    for package in ("backend", "frontend"):
        for platform in ("linux/amd64", "linux/arm64"):
            assert f"PULL pull --platform {platform} ghcr.io/example/spaceworks-{package}:" in result.stdout
