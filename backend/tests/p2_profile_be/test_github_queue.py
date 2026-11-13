"""Decision 338: ownership is verified right after link / username save, not at the daily sweep."""
from unittest.mock import MagicMock

import pytest
from django.core.cache import cache

from apps.accounts.models_social import SocialIdentity
from apps.makerspaces import profile_github as service
from apps.makerspaces import tasks as makerspace_tasks
from apps.makerspaces.account_profile import save_profile
from apps.makerspaces.account_profile_read import build_payload
from apps.makerspaces.models_account_profile import AccountProfile

from .conftest import GITHUB_SUB, public_get

pytestmark = pytest.mark.django_db


@pytest.fixture
def delay(monkeypatch):
    call = MagicMock()
    monkeypatch.setattr(makerspace_tasks.verify_github_ownership_task, "delay", call)
    cache.clear()
    return call


def test_linking_github_queues_one_deduplicated_task_after_commit(published, delay, django_capture_on_commit_callbacks):
    SocialIdentity.objects.filter(user=published.user).delete()
    with django_capture_on_commit_callbacks(execute=True):
        SocialIdentity.objects.create(user=published.user, provider="github", provider_sub=GITHUB_SUB)
        assert delay.call_count == 0  # nothing before the commit
    delay.assert_called_once_with(published.user_id)
    with django_capture_on_commit_callbacks(execute=True):
        SocialIdentity.objects.filter(user=published.user).first().save()
    assert delay.call_count == 1  # the second request inside the dedupe window is dropped


def test_other_providers_and_unlinking_queue_nothing(published, delay, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        SocialIdentity.objects.create(user=published.user, provider="google", provider_sub="g-1")
        SocialIdentity.objects.filter(user=published.user, provider="github").delete()
    delay.assert_not_called()
    assert build_payload(AccountProfile.objects.get(pk=published.pk), "owner")["github_verified"] is False


def test_saving_a_new_username_queues_verification(published, delay, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        save_profile(published.user, {"github_username": "new-name"})
    delay.assert_called_once_with(published.user_id)
    delay.reset_mock()
    cache.clear()
    with django_capture_on_commit_callbacks(execute=True):
        save_profile(published.user, {"github_username": "new-name"})  # unchanged
        save_profile(published.user, {"github_username": ""})  # cleared: nothing to verify
    delay.assert_not_called()


def test_the_task_verifies_and_the_unlink_drops_the_badge(published, settings, monkeypatch):
    settings.GITHUB_API_TOKEN = "token"
    monkeypatch.setattr(service, "fetch_calendar", MagicMock(return_value=[{"date": "2026-01-01", "count": 3}]))
    assert build_payload(published, "public")["github_verified"] is False
    assert makerspace_tasks.verify_github_ownership_task(published.user_id) == {"verified": True}
    assert build_payload(published, "public")["github_verified"] is True
    assert public_get().data["days"] == [{"date": "2026-01-01", "count": 3}]
    SocialIdentity.objects.filter(user=published.user, provider="github").delete()
    assert build_payload(published, "public")["github_verified"] is False
    assert public_get().data["days"] == []


def test_the_task_has_time_limits_and_ignores_missing_profiles():
    task = makerspace_tasks.verify_github_ownership_task
    assert task.soft_time_limit and task.time_limit and task.soft_time_limit < task.time_limit
    assert task(0) == {"verified": False}


def test_directory_shape_carries_the_same_verified_flag(published, settings, monkeypatch):
    from apps.makerspaces.profile_directory import _empty
    from apps.makerspaces.profile_services import read_profile
    assert _empty(published.user)["github_verified"] is False
    membership = published.membership
    assert read_profile(membership, include_activity=False)["github_verified"] is False
    settings.GITHUB_API_TOKEN = "token"
    monkeypatch.setattr(service, "fetch_calendar", MagicMock(return_value=[]))
    service.verify_ownership(AccountProfile.objects.get(pk=published.pk))
    assert read_profile(membership, include_activity=False)["github_verified"] is True
