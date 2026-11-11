from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.makerspaces.models_profiles import PublicHandle, PublicHandleRedirect
from apps.makerspaces.profile_github import refresh_calendar

from .conftest import enable, public_get

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("kind", ["github", "events"])
def test_tenant_host_and_browser_origin_both_narrow_scope(published, other_space, kind, settings):
    # Managed hosting requires verified DNS. Self-host intentionally trusts the
    # operator's saved domain and reconciles pending -> verified on every save.
    settings.PLATFORM_DOMAIN_SUFFIX = "platform.example.test"
    own = published.membership.makerspace
    own.frontend_domain = "own.example.test"; own.frontend_domain_status = "verified"; own.save()
    other_space.frontend_domain = "other.example.test"
    other_space.frontend_domain_status = "verified"; other_space.save()
    assert public_get(kind, HTTP_HOST="own.example.test").status_code == 200
    for headers in [
        {"HTTP_HOST": "other.example.test"}, {"HTTP_ORIGIN": "https://other.example.test"},
        {"HTTP_HOST": "own.example.test", "HTTP_ORIGIN": "https://other.example.test"},
        {"HTTP_ORIGIN": "https://untrusted.example.test"},
    ]:
        response = public_get(kind, **headers)
        assert response.status_code == 404
        assert response.data == public_get(kind, "not.a.profile").data
    own.frontend_domain_status = "pending"; own.save(update_fields=["frontend_domain_status"])
    assert public_get(kind, HTTP_HOST="own.example.test").status_code == 404


@pytest.mark.parametrize("kind", ["github", "events"])
@pytest.mark.parametrize("change", ["private", "consent", "inactive", "restricted", "revoked", "archived", "module", "owner"])
def test_same_404_for_all_frozen_predicates(published, other_user, kind, change):
    membership, user, space = published.membership, published.membership.user, published.membership.makerspace
    if change == "private":
        enable(published, public_visible=False)
    elif change == "consent":
        enable(published, public_consented_at=None)
    elif change == "inactive":
        user.is_active = False; user.save()
    elif change == "restricted":
        user.access_status = "restricted"; user.save()
    elif change == "revoked":
        membership.status = "revoked"; membership.save()
    elif change == "archived":
        space.archived_at = timezone.now(); space.save()
    elif change == "module":
        space.enabled_modules = []; space.save()
    else:
        PublicHandle.objects.filter(profile=published).update(user=other_user)
    response = public_get(kind)
    assert response.status_code == 404
    assert response.data == public_get(kind, "not.a.profile").data


def test_old_handle_redirect_requires_live_graph_consent(published):
    from datetime import timedelta
    PublicHandleRedirect.objects.create(profile=published, handle="former.maker", released_at=timezone.now(),
                                        expires_at=timezone.now() + timedelta(days=30))
    response = public_get("github", "former.maker")
    assert response.status_code == 302
    assert response["Location"] == "/api/v1/public/profiles/public.maker/github"
    enable(published, show_activity_graph=False)
    assert public_get("github", "former.maker").status_code == 404


def test_new_route_is_classified_and_target_resolves_through_frozen_predicate(published):
    from apps.accounts.claim_route_types import AnonymousRead
    from apps.accounts.claim_routes import policy_for
    from apps.apiclients.scope_registry import lookup, resolve_target
    from apps.apiclients.scope_registry_routes import PUBLIC_READ_SCOPES, TARGET_TENANT_TOKEN
    path = "/api/v1/public/profiles/public.maker/github"
    request = APIRequestFactory().get(path)
    request.resolver_match = resolve(path)
    assert request.resolver_match.view_name == "public-profile-github"
    entry = lookup("public-profile-github", "GET")
    assert entry.scopes == PUBLIC_READ_SCOPES and entry.target_mode == TARGET_TENANT_TOKEN
    assert resolve_target(request, entry) == (published.membership.makerspace, True)
    assert isinstance(policy_for("public-profile-github", "GET"), AnonymousRead)
    assert isinstance(policy_for("public-profile-github", "OPTIONS"), AnonymousRead)
    assert lookup("public-profile-github", "POST") is None
    enable(published, public_visible=False)
    assert resolve_target(request, entry) == (None, False)


def test_sweep_honors_tenant_fence_and_never_fetches_without_consent(published, settings, monkeypatch):
    from apps.makerspaces import profile_github_tasks as tasks
    settings.GITHUB_API_TOKEN = "token"
    fetch = MagicMock()
    monkeypatch.setattr(tasks, "refresh_calendar", fetch)
    observed = []
    @contextmanager
    def closed(tenant, *, operation, counts):
        observed.append((tenant, operation))
        yield False
    monkeypatch.setattr(tasks, "fanout_tenant_write", closed)
    tasks.refresh_public_calendars()
    assert observed == [(published.membership.makerspace_id, "github_contributions_refresh")]
    fetch.assert_not_called()
    enable(published, show_activity_graph=False)
    observed.clear()
    tasks.refresh_public_calendars()
    assert observed == []


def test_existing_scheduler_task_composes_calendar_sweep(published, settings, monkeypatch):
    from apps.makerspaces import github_contributions
    from apps.makerspaces import profile_github_tasks as calendars
    from apps.makerspaces.tasks import refresh_github_contributions_task
    settings.GITHUB_API_TOKEN = "token"
    monkeypatch.setattr(github_contributions, "due_for_sync", lambda profile: False)
    refresh = MagicMock()
    monkeypatch.setattr(calendars, "refresh_public_calendars", refresh)
    refresh_github_contributions_task()
    refresh.assert_called_once_with()


def test_cache_set_failure_does_not_escape_task_or_read(published, settings, monkeypatch):
    from django.core.cache import cache
    from apps.makerspaces import profile_github as service
    settings.GITHUB_API_TOKEN = "token"
    claim = PublicHandle.objects.get(profile=published)
    monkeypatch.setattr(service, "fetch_calendar", lambda username: [{"date": "2026-01-01", "count": 3}])
    original_set = cache.set
    def set_cache(key, value, *args, **kwargs):
        if key.startswith("public-profile:"):
            raise ConnectionError("private-redis")
        return original_set(key, value, *args, **kwargs)
    monkeypatch.setattr(service.cache, "set", set_cache)
    assert not refresh_calendar(claim.pk)
    assert public_get().status_code == 200 and public_get().data["days"] == []


@pytest.mark.parametrize("status", [401, 403, 405, 429])
@pytest.mark.parametrize("path", ["/api/v1/public/profiles/private.maker/",
    "/api/v1/public/profiles/private.maker/github", "/share/profiles/private.maker/"])
def test_profile_privacy_headers_cover_pre_handler_refusals(settings, status, path):
    from django.http import HttpResponse
    from apps.makerspaces.middleware import TenantHostValidationMiddleware
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    request = APIRequestFactory().get(path)
    middleware = TenantHostValidationMiddleware(lambda req: HttpResponse(status=status,
        headers={"Vary": "Accept, Authorization"}))
    response = middleware(request)
    assert response.status_code == status and response["Cache-Control"] == "no-store"
    assert {"Accept", "Authorization", "Origin", "Host"} <= set(response["Vary"].split(", "))
