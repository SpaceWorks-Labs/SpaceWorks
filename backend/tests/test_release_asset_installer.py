"""The release-asset installer (decision 232): build script, workflow wiring and install.sh behaviour.

`install.sh` runs on a user's server under plain `sh`. Here its network edge is a fake `curl`
that serves local files, so checksum/signature handling, forward-only refusal and the hand-off
to the verified bundle are exercised without GitHub. The Docker rehearsal covers the real flow.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
STANDALONE = ROOT / "scripts/installer/standalone-install.sh"
VERSION = "0.12.0-main.7.abcdef012345"
COMMIT = "abcdef012345" + "0" * 28
REPO = "SpaceWorks-Labs/SpaceWorks"
SH = shutil.which("sh")
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not SH or not BASH, reason="requires sh and bash")


def test_standalone_installer_is_posix_sh_wrapped_in_main():
    text = STANDALONE.read_text()
    assert text.startswith("#!/bin/sh\n") and text.rstrip().endswith('main "$@"')
    assert len(text.splitlines()) < 300
    for bashism in ("[[", "${!", "<<<", "mapfile"):
        assert bashism not in text, bashism
    # Keywords are only bashisms as commands; "local volumes" appears in the help prose.
    assert not re.search(r"(?m)^\s*(local|declare|function)\s", text)
    assert subprocess.run([SH, "-n", str(STANDALONE)]).returncode == 0
    # Helpers arrive in the verified bundle: this file never fetches or sources unverified code.
    assert "release-fetch" not in text and "raw.githubusercontent" not in text
    assert "token.actions.githubusercontent.com" in text and "release\\\\.yml" in text


def test_legacy_raw_main_install_sh_is_a_stub_for_the_release_asset():
    stub = (ROOT / "install.sh").read_text()
    assert stub.startswith("#!/bin/sh\n") and len(stub.splitlines()) < 40
    assert "releases/latest/download/install.sh" in stub and 'sh "$tmp" "$@"' in stub
    assert subprocess.run([SH, "-n", str(ROOT / "install.sh")]).returncode == 0


def test_release_workflow_publishes_signed_installer_assets():
    workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    assets = workflow["jobs"]["assets"]
    assert assets["permissions"] == {"contents": "read", "id-token": "write"}
    uses = [step.get("uses", "") for step in assets["steps"]]
    assert any(item.startswith("sigstore/cosign-installer@") for item in uses)
    script = "\n".join(step.get("run", "") for step in assets["steps"])
    assert "scripts/release-assets.sh" in script and "cosign sign-blob --yes" in script
    assert "SHA256SUMS.sig" in script and "SHA256SUMS.pem" in script
    release = workflow["jobs"]["github-release"]
    assert "assets" in release["needs"]
    create = next(step for step in release["steps"] if step.get("name") == "Create GitHub Release")
    assert create["with"]["files"] == "release-assets/*"
    assert "id-token" not in workflow["permissions"]  # only the signing job may mint OIDC tokens


def test_release_assets_script_builds_a_checksummed_bundle(tmp_path):
    out = tmp_path / "out"
    run = subprocess.run([BASH, str(ROOT / "scripts/release-assets.sh"), VERSION, COMMIT, str(out)],
                         capture_output=True, text=True, timeout=120)
    if run.returncode != 0 and "VERSION differs" in run.stderr:
        pytest.skip("repository VERSION is not the fixture series")
    assert run.returncode == 0, run.stderr
    assert sorted(path.name for path in out.iterdir()) == sorted(
        ["install.sh", f"spaceworks-{VERSION}.tar.gz", "release.json", "SHA256SUMS"])
    sums = dict(line.split(None, 1)[::-1] for line in (out / "SHA256SUMS").read_text().splitlines())
    for name, digest in ((n.strip().lstrip("*"), d) for n, d in sums.items()):
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
    assert json.loads((out / "release.json").read_text()) == {"version": VERSION, "commit": COMMIT}
    manifest = subprocess.run([BASH, "-c", 'source "$H"; host_bundle_files; printf "%s\\n" "${HOST_BUNDLE_FILES[@]}"'],
                              env={**os.environ, "H": str(ROOT / "scripts/install-host-bundle.sh")},
                              capture_output=True, text=True, check=True).stdout.split()
    with tarfile.open(out / f"spaceworks-{VERSION}.tar.gz") as archive:
        names = {m.name.split("/", 1)[1] for m in archive if m.isfile()}
    assert set(manifest) <= names and "scripts/installer/install-entry.sh" in names


def test_release_assets_script_refuses_a_commit_that_does_not_match_the_version(tmp_path):
    run = subprocess.run([BASH, str(ROOT / "scripts/release-assets.sh"), VERSION, "f" * 40, str(tmp_path)],
                         capture_output=True, text=True, timeout=30)
    assert run.returncode == 64


@pytest.fixture
def host(tmp_path):
    """A fake network (curl) and host (uname, docker) around the real install.sh."""
    bins, served, tree = tmp_path / "bin", tmp_path / "served", tmp_path / "tree"
    bins.mkdir(); served.mkdir()
    entry = tree / f"spaceworks-{VERSION}/scripts/installer/install-entry.sh"
    entry.parent.mkdir(parents=True)
    entry.write_text('#!/usr/bin/env bash\nprintf "%s|%s|%s|%s\\n" "$SPACEWORKS_STAGED_VERSION" '
                     '"$SPACEWORKS_STAGED_COMMIT" "$SPACEWORKS_STAGED_SHA256" "$*" > "$ENTRY_LOG"\n')
    tarball = served / f"spaceworks-{VERSION}.tar.gz"
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(tree / f"spaceworks-{VERSION}", arcname=f"spaceworks-{VERSION}")
    (served / "release.json").write_text(json.dumps({"version": VERSION, "commit": COMMIT}))
    sums = "".join(f"{hashlib.sha256((served / n).read_bytes()).hexdigest()} *{n}\n"
                   for n in (tarball.name, "release.json"))
    (served / "SHA256SUMS").write_text(sums)
    (bins / "curl").write_text(f'''#!/bin/sh
out=''; fmt=''; url=''
while [ $# -gt 0 ]; do case $1 in -o) out=$2; shift ;; -w) fmt=$2; shift ;; http*) url=$1 ;; esac; shift; done
echo "$url" >> "$CURL_LOG"
case $fmt in *redirect_url*) printf 'https://github.com/{REPO}/releases/tag/v{VERSION}'; exit 0 ;; esac
f="$SERVED/${{url##*/}}"; [ -f "$f" ] || exit 22
cp "$f" "$out"
''')
    (bins / "uname").write_text('#!/bin/sh\n[ "$1" = -m ] && echo x86_64 || echo Linux\n')
    (bins / "docker").write_text("#!/bin/sh\nexit 0\n")
    for tool in bins.iterdir():
        tool.chmod(0o755)
    env = {**os.environ, "PATH": f"{bins}{os.pathsep}{os.environ['PATH']}", "SERVED": str(served),
           "CURL_LOG": str(tmp_path / "curl.log"), "ENTRY_LOG": str(tmp_path / "entry.log"),
           "SPACEWORKS_DIR": str(tmp_path / "installed"), "TMPDIR": str(tmp_path), "SPACEWORKS_MIN_FREE_KB": "1"}
    for name in ("SPACEWORKS_VERSION", "SPACEWORKS_REPOSITORY", "SPACEWORKS_FRONTEND"):
        env.pop(name, None)
    return tmp_path, served, bins, env


def install(host, *args, **env):
    tmp, _, _, base = host
    return subprocess.run([SH, str(STANDALONE), *args], env={**base, **env}, capture_output=True,
                          text=True, timeout=60, cwd=tmp)


def test_verified_bundle_is_handed_to_the_entry_with_its_facts(host):
    result = install(host, "--frontend", "api-only")
    assert result.returncode == 0, result.stdout + result.stderr
    version, commit, digest, args = (host[0] / "entry.log").read_text().strip().split("|")
    assert (version, commit, args) == (VERSION, COMMIT, "--frontend api-only")
    assert digest == hashlib.sha256((host[1] / f"spaceworks-{VERSION}.tar.gz").read_bytes()).hexdigest()
    assert "Only the checksum was verified" in result.stdout
    assert "\033[" not in result.stdout  # no colour when not a terminal
    assert not list(host[0].glob(".spaceworks-stage.*"))


def test_tampered_bundle_is_refused_before_anything_runs(host):
    (host[1] / f"spaceworks-{VERSION}.tar.gz").write_bytes(b"tampered")
    result = install(host)
    assert result.returncode != 0 and "Checksum mismatch" in result.stderr
    assert not (host[0] / "entry.log").exists()


def test_cosign_present_but_signature_assets_missing_is_refused_with_a_clear_message(host):
    tmp, _served, bins, _ = host  # decision 253(d): no .sig/.pem is served
    cosign = bins / "cosign"
    cosign.write_text("#!/bin/sh\nexit 0\n"); cosign.chmod(0o755)
    result = install(host)
    assert result.returncode != 0 and "unsigned or its signature assets are missing" in result.stderr
    assert not (tmp / "entry.log").exists()


def test_cosign_failure_refuses_and_success_is_reported(host):
    tmp, served, bins, _ = host
    (served / "SHA256SUMS.sig").write_text("sig"); (served / "SHA256SUMS.pem").write_text("pem")
    cosign = bins / "cosign"
    cosign.write_text('#!/bin/sh\nprintf "%s\\n" "$*" > "$COSIGN_LOG"\nexit "${COSIGN_EXIT:-0}"\n'); cosign.chmod(0o755)
    env = {"COSIGN_LOG": str(tmp / "cosign.log")}
    bad = install(host, COSIGN_EXIT="1", **env)
    assert bad.returncode != 0 and "cosign signature" in bad.stderr and not (tmp / "entry.log").exists()
    good = install(host, **env)
    assert good.returncode == 0 and "cosign signature ok" in good.stdout
    call = (tmp / "cosign.log").read_text()
    assert "verify-blob" in call and "https://token.actions.githubusercontent.com" in call
    assert "SpaceWorks-Labs/SpaceWorks" in call and "release" in call


def test_downgrade_is_refused_before_download(host):
    root = host[0] / "installed"
    root.mkdir()
    (root / ".spaceworks-version").write_text("0.13.0-main.9.aaaaaaaaaaaa\n")
    result = install(host)
    assert result.returncode != 0 and "forward-only" in result.stderr
    assert not (host[0] / "entry.log").exists()
    assert not any(line.endswith(".tar.gz") for line in (host[0] / "curl.log").read_text().splitlines())


@pytest.mark.parametrize("args", [("--version", "latest"), ("--repo", "not a repo"), ("--repo",)])
def test_invalid_options_fail_before_any_network_use(host, args):
    result = install(host, *args)
    assert result.returncode != 0
    assert not (host[0] / "curl.log").exists()


def test_uninstall_without_an_install_and_help_have_no_effects(host):
    assert install(host, "--help").returncode == 0
    result = install(host, "--uninstall")
    assert result.returncode != 0 and "No SpaceWorks install" in result.stderr
    assert not (host[0] / "curl.log").exists()


def test_rehearsal_fixture_serves_installer_assets():
    text = (ROOT / "scripts/ci/install_rehearsal_fixture.py").read_text()
    assert "releases/latest/download/" in text and "releases/download/" in text
    assert re.search(r"release-assets\.sh", text)
