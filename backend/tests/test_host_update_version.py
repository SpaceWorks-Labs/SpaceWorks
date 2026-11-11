"""Exact-release deployments validate GitHub metadata before backup or image changes."""
import json

import pytest

from tests.test_host_updater_behavior import NEW, OLD, host, run


def published(version=NEW, repository="SpaceWorks-Labs/SpaceWorks", **changes):
    return {"tag_name": f"v{version}", "draft": False, "prerelease": False,
            "published_at": "2026-10-10T10:00:00Z",
            "html_url": f"https://github.com/{repository}/releases/tag/v{version}", **changes}


def test_pinned_release_uses_exact_tag_endpoint_and_deploys_it(host):
    result, log = run(host, "--version", NEW)
    assert result.returncode == 0, result.stderr
    assert (host[0] / ".spaceworks-version").read_text().strip() == NEW
    assert "pg_dump" in log and "pull " in log
    assert f"/repos/SpaceWorks-Labs/SpaceWorks/releases/tags/v{NEW}" in (host[0] / "curl.log").read_text()
    assert "?per_page=" not in (host[0] / "curl.log").read_text()


@pytest.mark.parametrize("options", [
    ("--version",), ("--version", "latest"), ("--version", f"v{NEW}"),
    ("--version", "0.9.1-main.1.abc"), ("--version", "0.9.1-main.1.AAAAAAAAAAAA"),
    ("--version", "0.9.1-beta.1.aaaaaaaaaaaa"), ("--version", NEW + "/extra"),
    ("--version", NEW + "\n"), ("--version", NEW, "--version", OLD),
    ("--version", NEW, "--modules-only"),
])
def test_malformed_or_ignored_pin_is_refused_before_network(host, options):
    result, log = run(host, *options)
    assert result.returncode != 0
    assert not log and not (host[0] / "curl.log").exists()
    assert (host[0] / ".spaceworks-version").read_text().strip() == OLD


@pytest.mark.parametrize("changes", [
    {"draft": True}, {"prerelease": True}, {"published_at": None}, {"published_at": ""},
    {"draft": "false"}, {"prerelease": 0}, {"tag_name": f"v{OLD}"},
    {"html_url": f"https://github.com/Other/Repository/releases/tag/v{NEW}"},
    {"html_url": f"https://github.com/SpaceWorks-Labs/SpaceWorks.evil/releases/tag/v{NEW}"},
    {"html_url": None},
])
def test_ineligible_or_wrong_repository_pin_is_refused_without_changes(host, changes):
    result, log = run(host, "--version", NEW, TEST_RELEASE_JSON=json.dumps(published(**changes)))
    assert result.returncode != 0
    assert "pg_dump" not in log and "pull " not in log
    assert (host[0] / ".spaceworks-version").read_text().strip() == OLD
    assert not (host[0] / ".spaceworks-update.lock").exists()


def test_missing_pinned_release_is_refused_without_backup(host):
    result, log = run(host, "--version", NEW, TEST_FAILURE="github")  # curl --fail on 404
    assert result.returncode != 0
    assert "pg_dump" not in log and "pull " not in log
    assert (host[0] / ".spaceworks-version").read_text().strip() == OLD


def test_pin_uses_the_forks_repository(host):
    repository = "Example-Owner/MyFork"
    result, _ = run(host, "--version", NEW, SPACEWORKS_REPOSITORY=repository)
    assert result.returncode == 0, result.stderr
    assert f"/repos/{repository}/releases/tags/v{NEW}" in (host[0] / "curl.log").read_text()


def test_no_pin_keeps_newest_publication_selection(host):
    older = published(OLD)
    newest = published(NEW, published_at="2026-10-11T00:00:00Z")
    result, _ = run(host, TEST_RELEASE_JSON=json.dumps([older, newest]))
    assert result.returncode == 0, result.stderr
    assert (host[0] / ".spaceworks-version").read_text().strip() == NEW
    assert "/releases?per_page=100" in (host[0] / "curl.log").read_text()
