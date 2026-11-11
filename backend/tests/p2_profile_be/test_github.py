import json
from unittest.mock import MagicMock

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.makerspaces import profile_github as service
from apps.makerspaces import profile_github_fetch as provider
from apps.makerspaces.models_profiles import MemberProfile, PublicHandle

from .conftest import enable, public_get

pytestmark = pytest.mark.django_db
DAYS = [{"date": "2026-01-01", "count": 3}]


def response_body(days=DAYS):
    return {"data": {"user": {"contributionsCollection": {"contributionCalendar": {
        "weeks": [{"contributionDays": [{"date": day["date"], "contributionCount": day["count"]}
                                        for day in days]}],
    }}}}}


def mock_http(monkeypatch, body):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(body).encode()
    call = MagicMock(return_value=response)
    monkeypatch.setattr(provider.urllib.request, "urlopen", call)
    return call


def test_graphql_fetch_is_bounded_and_uses_platform_token(settings, monkeypatch):
    settings.GITHUB_API_TOKEN = "platform-token"
    call = mock_http(monkeypatch, response_body())
    assert provider.fetch_calendar("octocat") == DAYS
    request = call.call_args.args[0]
    assert request.full_url == provider.GRAPHQL_URL
    assert request.headers["Authorization"] == "Bearer platform-token"
    assert json.loads(request.data)["variables"] == {"login": "octocat"}
    assert "contributionDays" in json.loads(request.data)["query"]
    assert call.call_args.kwargs["timeout"] == provider.REQUEST_TIMEOUT


@pytest.mark.parametrize("body", [
    {"errors": [{"message": "secret body"}], **response_body()}, {"data": {"user": None}},
    response_body([{"date": "invalid", "count": 3}]),
    response_body([{"date": "2026-01-01", "count": -1}]),
    response_body([{"date": "2026-01-01", "count": True}]), response_body(DAYS * 2),
])
def test_invalid_or_partial_graphql_fails_empty(settings, monkeypatch, body, caplog):
    settings.GITHUB_API_TOKEN = "secret-token"
    mock_http(monkeypatch, body)
    assert provider.fetch_calendar("octocat") is None
    assert "github_fetch_failed" in caplog.text
    assert "secret-token" not in caplog.text and "secret body" not in caplog.text


def test_provider_timeout_has_no_private_exception_in_log(settings, monkeypatch, caplog):
    settings.GITHUB_API_TOKEN = "secret-token"
    monkeypatch.setattr(provider.urllib.request, "urlopen", MagicMock(side_effect=TimeoutError("private-destination")))
    assert provider.fetch_calendar("octocat") is None
    assert "private-destination" not in caplog.text


def test_response_size_is_bounded(settings, monkeypatch):
    settings.GITHUB_API_TOKEN = "token"
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b" " * (provider.MAX_RESPONSE_BYTES + 1)
    monkeypatch.setattr(provider.urllib.request, "urlopen", MagicMock(return_value=response))
    assert provider.fetch_calendar("octocat") is None


def test_unconfigured_and_invalid_username_never_fetch(settings, monkeypatch):
    call = mock_http(monkeypatch, {})
    settings.GITHUB_API_TOKEN = ""
    assert provider.fetch_calendar("octocat") is None
    settings.GITHUB_API_TOKEN = "token"
    assert provider.fetch_calendar("https://attacker.test") is None
    call.assert_not_called()


def test_cache_only_read_and_ttl_refresh(published, settings, monkeypatch):
    settings.GITHUB_API_TOKEN = "token"
    fetch = MagicMock(return_value=DAYS)
    monkeypatch.setattr(service, "fetch_calendar", fetch)
    claim = PublicHandle.objects.get(profile=published)
    assert public_get().data == {"source": "github", "days": []}
    fetch.assert_not_called()
    assert service.refresh_calendar(claim.pk)
    assert public_get().data == {"source": "github", "days": DAYS}
    assert public_get()["Cache-Control"] == "no-store"
    assert not service.refresh_calendar(claim.pk)
    assert fetch.call_count == 1
    # Daily refresh becomes due BEFORE the body expires, avoiding every-other-day gaps.
    key = service.calendar_key(service.current_claim(claim.pk))
    cache.delete_many([f"{key}:due", f"{key}:fetch"])
    assert service.refresh_calendar(claim.pk)
    assert fetch.call_count == 2
    cache.delete(key)
    assert public_get().data["days"] == []


@pytest.mark.parametrize("change", ["username", "handle", "profile", "withdraw", "generation", "aba"])
def test_stale_fetch_cannot_publish_into_new_generation(published, settings, monkeypatch, change):
    settings.GITHUB_API_TOKEN = "token"
    claim = PublicHandle.objects.get(profile=published)
    old_key = service.calendar_key(service.current_claim(claim.pk))
    def fetch(username):
        assert username == "octocat"
        if change == "username":
            MemberProfile.objects.filter(pk=published.pk).update(github_username="new-user")
        elif change == "handle":
            PublicHandle.objects.filter(pk=claim.pk).update(handle="new.handle", changed_at=timezone.now())
        elif change == "withdraw":
            MemberProfile.objects.filter(pk=published.pk).update(public_visible=False)
        elif change == "profile":
            # A moved claim can never read the original profile's body.
            claim.delete()
        elif change == "generation":
            cache.set(f"public-profile:generation:{published.pk}", "new-generation", timeout=None)
        else:
            enable(published, github_username="new-user")
            enable(published, github_username="octocat")
        return DAYS
    monkeypatch.setattr(service, "fetch_calendar", fetch)
    assert not service.refresh_calendar(claim.pk)
    assert cache.get(old_key) is None
    if change != "profile":
        assert service.calendar_for(claim)["days"] == []


def test_stale_worker_cannot_overwrite_new_username_result(published, settings, monkeypatch):
    settings.GITHUB_API_TOKEN = "token"
    claim = PublicHandle.objects.get(profile=published)
    newer = [{"date": "2026-01-01", "count": 9}]
    def fetch(username):
        if username == "octocat":
            enable(published, github_username="new-user")
            assert service.refresh_calendar(claim.pk)
            return DAYS
        return newer
    monkeypatch.setattr(service, "fetch_calendar", fetch)
    assert not service.refresh_calendar(claim.pk)
    assert public_get().data["days"] == newer


def test_change_after_final_check_still_writes_only_old_key(published, settings, monkeypatch):
    settings.GITHUB_API_TOKEN = "token"
    claim = PublicHandle.objects.get(profile=published)
    old_key = service.calendar_key(service.current_claim(claim.pk))
    newer = [{"date": "2026-01-01", "count": 9}]
    original_set = cache.set
    writes = []
    def set_cache(key, value, timeout=None, **kwargs):
        writes.append((key, timeout))
        if key == old_key:
            enable(published, github_username="new-user")
            assert service.refresh_calendar(claim.pk)
        return original_set(key, value, timeout=timeout, **kwargs)
    monkeypatch.setattr(service.cache, "set", set_cache)
    monkeypatch.setattr(service, "fetch_calendar", lambda username: DAYS if username == "octocat" else newer)
    assert service.refresh_calendar(claim.pk)
    assert public_get().data["days"] == newer
    assert (old_key, service.CALENDAR_TTL) in writes


def test_success_body_outlives_due_marker_and_failure_backs_off(published, settings, monkeypatch):
    settings.GITHUB_API_TOKEN = "token"
    claim = PublicHandle.objects.get(profile=published)
    setter = MagicMock(wraps=cache.set)
    monkeypatch.setattr(service.cache, "set", setter)
    monkeypatch.setattr(service, "fetch_calendar", lambda username: DAYS)
    assert service.refresh_calendar(claim.pk)
    timeouts = [call.kwargs["timeout"] for call in setter.call_args_list]
    assert service.CALENDAR_TTL in timeouts and service.REFRESH_INTERVAL in timeouts
    assert service.CALENDAR_TTL > 24 * 3600 > service.REFRESH_INTERVAL
    enable(published, github_username="failing-user")
    monkeypatch.setattr(service, "fetch_calendar", lambda username: None)
    setter.reset_mock()
    assert not service.refresh_calendar(claim.pk)
    assert all(call.kwargs["timeout"] == service.FAILURE_TTL for call in setter.call_args_list)


def test_cache_and_provider_failure_are_empty(published, settings, monkeypatch):
    settings.GITHUB_API_TOKEN = "token"
    claim = PublicHandle.objects.get(profile=published)
    monkeypatch.setattr(service, "fetch_calendar", MagicMock(return_value=None))
    assert not service.refresh_calendar(claim.pk)
    assert public_get().data["days"] == []
    assert cache.get(f"{service.calendar_key(service.current_claim(claim.pk))}:due")
    original_get = cache.get
    def get_cache(key, *args, **kwargs):
        if key.startswith("public-profile:"):
            raise ConnectionError("private-redis-url")
        return original_get(key, *args, **kwargs)
    monkeypatch.setattr(service.cache, "get", get_cache)
    assert public_get().status_code == 200
    assert public_get().data["days"] == []
    assert not service.refresh_calendar(claim.pk)


def test_publication_and_consent_block_fetch_and_cached_body(published, settings, monkeypatch):
    settings.GITHUB_API_TOKEN = "token"
    claim = PublicHandle.objects.get(profile=published)
    fetch = MagicMock(return_value=DAYS)
    monkeypatch.setattr(service, "fetch_calendar", fetch)
    assert service.refresh_calendar(claim.pk)
    enable(published, show_activity_graph=False)
    assert public_get().status_code == 404
    assert not service.refresh_calendar(claim.pk)
    enable(published, show_activity_graph=True, public_visible=False)
    assert public_get().status_code == 404
    assert not service.refresh_calendar(claim.pk)
    assert fetch.call_count == 1


def test_unconfigured_skips_even_cached_calendar(published, settings, monkeypatch):
    settings.GITHUB_API_TOKEN = "token"
    claim = PublicHandle.objects.get(profile=published)
    monkeypatch.setattr(service, "fetch_calendar", MagicMock(return_value=DAYS))
    assert service.refresh_calendar(claim.pk)
    settings.GITHUB_API_TOKEN = ""
    assert public_get().data["days"] == []
    assert not service.refresh_calendar(claim.pk)
