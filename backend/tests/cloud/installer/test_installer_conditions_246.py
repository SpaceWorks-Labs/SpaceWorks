"""Decision 246 (lane T4): installer and hybrid-setup conditions (232 release installer, 239 outside services).

Real bash/sh with a fake `curl`, `uname` and `docker` (the `host` fixture of the release-asset test), and
the real questionnaire (the helpers of the host-setup tests). No Docker daemon, no network.
Covers: unsupported OS and CPU refusal, a missing checksum entry, an unreachable download, forward-only
version rules (older refused, same and newer allowed), a cosign signature that cannot be fetched, and the
outside-service prompts refusing bad input (same bucket twice, bad port, bad e-mail, bad Redis URL,
transaction pooler) and asking again.
"""
import pytest

from tests.test_host_setup_outside_services import SUPABASE_DIRECT, SUPABASE_TRANSACTION
from tests.test_host_setup_questions_behavior import BASH, questionnaire, question_tail
from tests.test_release_asset_installer import (  # noqa: F401  (host is a pytest fixture)
    SH, VERSION, host, install,
)

pytestmark = pytest.mark.skipif(not BASH or not SH, reason="requires bash and sh")


def fake_uname(host, system, machine):
    bins = host[2]
    (bins / "uname").write_text(f'#!/bin/sh\n[ "$1" = -m ] && echo {machine} || echo {system}\n')
    (bins / "uname").chmod(0o755)


@pytest.mark.parametrize("system,machine,fragment", [
    ("FreeBSD", "x86_64", "Unsupported operating system"),
    ("MINGW64_NT-10.0", "x86_64", "WSL2"),
    ("Linux", "i686", "Unsupported architecture"),
    ("Linux", "armv7l", "Unsupported architecture"),
])
def test_unsupported_host_is_refused_before_any_download(host, system, machine, fragment):
    fake_uname(host, system, machine)
    result = install(host)
    assert result.returncode != 0 and fragment in result.stderr
    assert not (host[0] / "entry.log").exists()
    assert not (host[0] / "curl.log").exists()


@pytest.mark.parametrize("machine", ["x86_64", "aarch64", "arm64"])
def test_supported_cpus_reach_the_hand_off(host, machine):
    fake_uname(host, "Linux", machine)
    result = install(host)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (host[0] / "entry.log").exists()


def test_a_checksum_file_without_the_bundle_entry_is_refused(host):
    _tmp, served, _bins, _env = host
    sums = [line for line in (served / "SHA256SUMS").read_text().splitlines() if "release.json" in line]
    (served / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    result = install(host)
    assert result.returncode != 0 and "has no entry" in result.stderr
    assert not (host[0] / "entry.log").exists()


def test_an_altered_release_json_is_refused_even_when_the_bundle_is_intact(host):
    (host[1] / "release.json").write_text('{"version": "9.9.9", "commit": "' + "0" * 40 + '"}')
    result = install(host)
    assert result.returncode != 0 and "Checksum mismatch for release.json" in result.stderr
    assert not (host[0] / "entry.log").exists()


def test_a_missing_download_names_the_file_and_installs_nothing(host):
    (host[1] / f"spaceworks-{VERSION}.tar.gz").unlink()
    result = install(host)
    assert result.returncode != 0 and "Could not download" in result.stderr
    assert not (host[0] / "entry.log").exists()


def test_cosign_present_but_signature_files_missing_refuses(host):
    tmp, _served, bins, _env = host
    (bins / "cosign").write_text("#!/bin/sh\nexit 0\n")
    (bins / "cosign").chmod(0o755)
    result = install(host)
    assert result.returncode != 0 and "unsigned or its signature assets are missing" in result.stderr
    assert not (tmp / "entry.log").exists()


@pytest.mark.parametrize("installed,allowed", [
    ("0.12.0-main.7.abcdef012345", True),    # the same release: a re-run, not a downgrade
    ("0.12.0-main.1.aaaaaaaaaaaa", True),    # an earlier build of the same version
    ("0.11.0", True),                        # an older version upgrades forward
    ("0.12.0-main.99.aaaaaaaaaaaa", False),  # a later build of the same version
    ("0.12.1", False),
    ("1.0.0", False),
])
def test_upgrades_are_forward_only(host, installed, allowed):
    root = host[0] / "installed"
    root.mkdir()
    (root / ".spaceworks-version").write_text(installed + "\n")
    result = install(host)
    if allowed:
        assert result.returncode == 0, result.stdout + result.stderr
        assert (host[0] / "entry.log").exists()
    else:
        assert result.returncode != 0 and "forward-only" in result.stderr
        assert not (host[0] / "entry.log").exists()


# --- Outside services: each prompt refuses bad input and asks again ---------------------------------

def hybrid(*, buckets=("sw-private", "sw-public"), smtp_port=("587",), db=("2", SUPABASE_DIRECT),
           redis=("2", "rediss://default:tok@x.upstash.io:6379"), email_tail=("resend", "re_key", "Y",
                                                                           "noreply@example.org", "N")):
    return (["", "", "3", "api.example.org",
             "2", "https://acc.r2.cloudflarestorage.com", "", "auto", *buckets, "AKIA", "r2-secret",
             "https://img.example.org", "limited", "y", *db, *redis,
             "2", "smtp.resend.com", *smtp_port, *email_tail,
             "", "Test Organization", "My Lab", "", ""] + question_tail())


def test_the_same_bucket_for_evidence_and_images_is_refused_and_asked_again(tmp_path):
    answers = hybrid(buckets=("sw-private", "sw-private", "sw-public"))
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    assert "must use different buckets" in result.stdout


def test_a_bad_smtp_port_is_refused_and_the_corrected_one_is_written(tmp_path):
    result = questionnaire(tmp_path, hybrid(smtp_port=("70000", "587")), write=True)
    assert result.returncode == 0, result.stderr
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "EMAIL_PORT='587'" in env and "70000" not in env


def test_a_bad_sender_address_is_refused_and_asked_again(tmp_path):
    answers = hybrid(email_tail=("resend", "re_key", "Y", "not-an-address", "noreply@example.org", "N"))
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    assert "Enter an email address." in result.stdout
    assert "not-an-address" not in (tmp_path / ".env").read_text(encoding="utf-8")


def test_a_plain_redis_url_off_the_private_network_is_refused_and_a_tls_one_taken(tmp_path):
    answers = hybrid(redis=("2", "redis://default:tok@x.upstash.io:6379", "rediss://default:tok@x.upstash.io:6379"))
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "CELERY_BROKER_URL='rediss://default:tok@x.upstash.io:6379?ssl_cert_reqs=required'" in env
    # The saved URL always carries the certificate mode (normalize_redis_url), so the bare URL never appears.
    assert "tok@x.upstash.io:6379'" not in env and "redis://default" not in env.replace("rediss://", "")


def test_a_transaction_pooler_is_refused_for_the_owner_url_too(tmp_path):
    answers = hybrid(db=("2", SUPABASE_TRANSACTION, SUPABASE_DIRECT))
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    assert "transaction-pooler address" in result.stdout
    assert "6543" not in (tmp_path / ".env").read_text(encoding="utf-8")
