import pytest
from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.links import normalize_link
from apps.events.submissions.integrity import github_request_url
from datetime import datetime, UTC


@pytest.mark.parametrize("value", ["http://github.com/a/b", "https://user:pass@example.com", "javascript:alert(1)",
    "https://localhost/x", "https://127.0.0.1/x", "https://example.com\\@evil.com/x", "https://example.com/%0aevil",
    "https://example.com:8080/x", "https://example.com/\u202ex", "https://example.com/ x"])
def test_invalid_link_is_refused_without_network(value):
    with pytest.raises(SubmissionError):
        normalize_link(value, "repo")


def test_known_and_unknown_https_links_remain_navigation_only():
    assert normalize_link("https://GitHub.com/team/project", "repo") == ("https://github.com/team/project", "github")
    assert normalize_link("https://unlisted.example/demo", "demo")[1] == "external"


def test_github_integrity_api_host_is_fixed_and_arbitrary_path_is_refused():
    url = github_request_url("https://github.com/example/project", datetime.now(UTC))
    assert url.startswith("https://api.github.com/repos/example/project/commits?")
    for value in ("https://github.com.evil.example/a/b", "https://github.com/a/b/commits", "https://github.com/a/%2F.."):
        with pytest.raises(SubmissionError):
            github_request_url(value, datetime.now(UTC))
