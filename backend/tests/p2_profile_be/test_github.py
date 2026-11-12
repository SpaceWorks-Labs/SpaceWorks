import json
from unittest.mock import MagicMock

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.makerspaces import profile_github as service
from apps.makerspaces import profile_github_fetch as provider
from apps.makerspaces.models_account_profile import AccountProfile
from apps.makerspaces.models_profiles import PublicHandle

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
    claim = published  # the calendar is keyed by the ACCOUNT profile now (decision 304c)
    assert public_get().data == {"source": "github", "days": []}
    fetch.assert_not_called()
    assert service.refresh_calendar(claim.pk)
    assert public_get().data == {"source": "github", "days": DAYS}
    assert public_get()["Cache-Control"] == "no-store"
    assert not service.refresh_calendar(claim.pk)
    assert fetch.call_count == 1
    # Daily refresh becomes due BEFORE the body expires, avoiding every-other-day gaps.
    key = service.calendar_key(service.current_profile(claim.pk))
    cache.delete_many([f"{key}:due", f"{key}:fetch"])
    assert service.refresh_calendar(claim.pk)
    assert fetch.call_count == 2
    cache.delete(key)
    assert public_get().data["days"] == []


@pytest.mark.parametrize("change", ["username", "handle", "profile", "withdraw", "generation", "aba"])
def test_stale_fetch_cannot_publish_into_new_generation(published, settings, monkeypatch, change):
    settings.GITHUB_API_TOKEN = "token"
    claim = published  # the calendar is keyed by the ACCOUNT profile now (decision 304c)
    old_key = service.calendar_key(service.current_profile(claim.pk))
    def fetch(username):
        assert username == "octocat"
        if change == "username":
            AccountProfile.objects.filter(pk=published.pk).update(github_username="new-user")
        elif change == "handle":
            PublicHandle.objects.filter(user=published.user).update(handle="new.handle", changed_at=timezone.now())
        elif change == "withdraw":
            AccountProfile.objects.filter(pk=published.pk).update(is_visible=False)
        elif change == "profile":
            # A released handle can never read the original profile's body.
            PublicHandle.objects.filter(user=published.user).delete()
        elif change == "generation":
            cache.set(f"public-profile:generation:acct:{published.user_id}", "new-generation", timeout=None)
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
    claim = published  # the calendar is keyed by the ACCOUNT profile now (decision 304c)
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
    claim = published  # the calendar is keyed by the ACCOUNT profile now (decision 304c)
    old_key = service.calendar_key(service.current_profile(claim.pk))
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
    claim = published  # the calendar is keyed by the ACCOUNT profile now (decision 304c)
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
    claim = published  # the calendar is keyed by the ACCOUNT profile now (decision 304c)
    monkeypatch.setattr(service, "fetch_calendar", MagicMock(return_value=None))
    assert not service.refresh_calendar(claim.pk)
    assert public_get().data["days"] == []
    assert cache.get(f"{service.calendar_key(service.current_profile(claim.pk))}:due")
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
    claim = published  # the calendar is keyed by the ACCOUNT profile now (decision 304c)
    fetch = MagicMock(return_value=DAYS)
    monkeypatch.setattr(service, "fetch_calendar", fetch)
    assert service.refresh_calendar(claim.pk)
    enable(published, show_activity_graph=False)
    assert public_get().status_code == 404
    assert not service.refresh_calendar(claim.pk)
    enable(published, show_activity_graph=True, public_visible=False)
    # The open web is closed, so a logged-out reader gets the 404 ...
    assert public_get().status_code == 404
    # ... but signed-in readers still may see the calendar, so the refresh is NOT blocked by it.
    assert service.refresh_calendar(claim.pk) and fetch.call_count == 2
    # Hiding the whole profile blocks the fetch.
    enable(published, public_visible=True, is_visible=False)
    key = service.calendar_key(service.current_profile(claim.pk))
    cache.delete_many([f"{key}:due", f"{key}:fetch"])
    assert not service.refresh_calendar(claim.pk)
    assert fetch.call_count == 2


def test_unconfigured_skips_even_cached_calendar(published, settings, monkeypatch):
    settings.GITHUB_API_TOKEN = "token"
    claim = published  # the calendar is keyed by the ACCOUNT profile now (decision 304c)
    monkeypatch.setattr(service, "fetch_calendar", MagicMock(return_value=DAYS))
    assert service.refresh_calendar(claim.pk)
    settings.GITHUB_API_TOKEN = ""
    assert public_get().data["days"] == []
    assert not service.refresh_calendar(claim.pk)


def test_calendar_and_badge_need_a_linked_github_sign_in_owning_the_username(published, settings, monkeypatch):
    """Decision 338 (L-P4): an unlinked or mismatched username is a plain link; no calendar, no token spend."""
    from apps.accounts.models_social import SocialIdentity
    from apps.makerspaces.account_profile_read import build_payload
    settings.GITHUB_API_TOKEN = "token"
    fetch = MagicMock(return_value=DAYS)
    monkeypatch.setattr(service, "fetch_calendar", fetch)
    claim = published
    assert build_payload(claim, "owner")["github_verified"] is False  # nothing proven yet
    assert service.refresh_calendar(claim.pk)
    for audience in ("owner", "public"):
        assert build_payload(claim, audience)["github_verified"] is True
    # Another person's GitHub account: the id does not match, so nothing is fetched or shown.
    AccountProfile.objects.filter(pk=claim.pk).update(github_username="someone-else")
    monkeypatch.setattr(service, "fetch_database_id", lambda username: 999)
    fetch.reset_mock()
    assert not service.refresh_calendar(claim.pk)
    fetch.assert_not_called()
    claim.refresh_from_db()
    assert build_payload(claim, "owner")["github_verified"] is False
    assert build_payload(claim, "public")["github_contributions"] is None
    # No linked sign-in at all.
    AccountProfile.objects.filter(pk=claim.pk).update(github_username="octocat")
    SocialIdentity.objects.filter(user=claim.user).delete()
    claim.refresh_from_db()
    assert not service.refresh_calendar(claim.pk)
    assert build_payload(claim, "owner")["github_verified"] is False
    assert public_get().data["days"] == []


def test_rename_cannot_inherit_a_verification(published, settings, monkeypatch):
    """The verified flag is keyed by (profile, username, immutable id): a changed username starts unverified."""
    from apps.makerspaces.account_profile_read import build_payload
    settings.GITHUB_API_TOKEN = "token"
    monkeypatch.setattr(service, "fetch_calendar", MagicMock(return_value=DAYS))
    assert service.refresh_calendar(published.pk)
    AccountProfile.objects.filter(pk=published.pk).update(github_username="renamed-login")
    published.refresh_from_db()
    assert build_payload(published, "owner")["github_verified"] is False
