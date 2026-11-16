import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIRequestFactory
from apps.makerspaces.models import AccountProfile, AccountProject, Makerspace
from apps.makerspaces.profile_services import save_profile
from apps.makerspaces.public_profile_views import PublicProfileView, PublicProfileProjectsView
from apps.makerspaces.profile_serializers import ProfileWriteSerializer

pytestmark = pytest.mark.django_db


def read(handle="public.maker", **headers):
    request = APIRequestFactory().get(f"/api/v1/public/profiles/{handle}/", **headers)
    return PublicProfileView.as_view()(request, handle=handle)


def expected_card(**changes):
    # Decision 549: exact anonymous card, independent of owner/session/legacy consent.
    payload = {"display_name": "A Maker", "avatar_url": None, "handle": "public.maker",
               "bio": "", "projects": [], "memberships": [{"slug": "contract-profile",
                   "name": "Profile lab", "role_title": "Member", "started_on": "2025-01-02"}]}
    return {**payload, **changes}


def test_directory_consent_never_publishes_and_republication_needs_fresh_consent(membership):
    # Decision 549 supersedes whole-card opt-in; legacy stored state is preserved.
    from apps.makerspaces.public_profile_handles import claim_handle
    profile = save_profile(membership, {"is_visible": True})
    claim_handle(membership.user, "public.maker")
    for data in ({"public_visible": True}, {"public_visible": False},
                 {"public_visible": True, "publication_consent": True}):
        save_profile(membership, data)
        response = read()
        assert response.status_code == 200
        assert response.data == expected_card()
    profile.refresh_from_db()
    assert (profile.public_visible, profile.public_consented_at) == (False, None)


@pytest.mark.parametrize("change", ["revoked", "archived", "migrated", "module"])
def test_space_level_changes_shrink_the_listing_instead_of_hiding_the_profile(published, change):
    """Decision 304: the profile is the person's, so a revoked/archived/migrated space leaves the
    spaces list rather than 404ing the whole profile."""
    membership = published.membership
    space = membership.makerspace
    if change == "revoked":
        membership.status = "revoked"; membership.save()
    elif change == "archived":
        space.archived_at = timezone.now(); space.save()
    elif change == "migrated":
        space.lifecycle_state = "migrated_out"; space.save()
    else:
        space.enabled_modules = []; space.save()
    response = read()
    assert response.status_code == 200
    # Decision 336b (M13): an anonymous reader sees a space only while it is PUBLIC (public site on AND the
    # `membership` module installed), so switching the module off shrinks the list the same way.
    assert response.data == expected_card(memberships=[])  # decision 549


@pytest.mark.parametrize("change", ["invisible", "consent", "inactive", "restricted", "suspended"])
def test_every_predicate_returns_same_404(published, change):
    membership = published.membership
    space = membership.makerspace
    user = membership.user
    if change == "invisible":
        published.public_visible = False; published.save()
    elif change == "consent":
        published.public_consented_at = None; published.save()
    elif change == "inactive":
        user.is_active = False; user.save()
    elif change == "restricted":
        user.access_status = "restricted"; user.save()
    else:
        user.access_status = "suspended"; user.save()
    response = read()
    # Decision 549 changes only opt-out and restricted/suspended card presentation.
    missing = read("nonexistent.handle")
    assert missing.status_code == 404
    assert missing.data["code"] == "not_found"
    if change == "inactive":
        assert response.status_code == 404
        assert response.data == missing.data
    else:
        assert response.status_code == 200
        assert response.data == ({"display_name": "A Maker", "avatar_url": None}
                                 if change in {"restricted", "suspended"} else expected_card())


def test_explicit_public_allowlist_and_project_consent(published):
    published.skills = [{"name": "Python", "level": 2, "user_id": published.membership.user_id}]
    published.save(update_fields=["skills"])
    AccountProject.objects.create(profile=published, title="Private title", public_visible=False)
    AccountProject.objects.create(profile=published, title="Published title", public_visible=True)
    response = read()
    assert response.status_code == 200
    data = response.data
    assert data == expected_card(projects=[{"title": "Published title", "subtitle": "", "description": "",
                                          "tags": [], "image_url": None, "links": []}])  # decision 549
    assert [row["title"] for row in data["projects"]] == ["Published title"]
    assert "account_id" not in data  # the fixed card has no internal ids
    forbidden = {"id", "membership_id", "user_id", "user", "email", "phone", "payment", "avatar_key"}
    def inspect(value):
        if isinstance(value, dict):
            assert forbidden.isdisjoint(value)
            for item in value.values(): inspect(item)
        elif isinstance(value, list):
            for item in value: inspect(item)
    inspect(data)
    save_profile(published.membership, {"show_projects": True})
    response = PublicProfileProjectsView.as_view()(APIRequestFactory().get("/"), handle="public.maker")
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["title"] == "Published title"
    assert "id" not in response.data["results"][0]


def test_tenant_host_and_custom_origin_never_cross_tenants(published):
    own = published.membership.makerspace
    own.frontend_domain = "own.example.test"; own.frontend_domain_status = "verified"; own.save()
    other = Makerspace.objects.create(name="Other", slug="other-domain", frontend_domain="other.example.test",
                                     frontend_domain_status="verified")
    own_response = read(HTTP_HOST="own.example.test")
    assert own_response.status_code == 200
    assert own_response.data == expected_card()
    for headers in ({"HTTP_HOST": "other.example.test"}, {"HTTP_ORIGIN": "https://other.example.test"},
                    {"HTTP_HOST": "own.example.test", "HTTP_ORIGIN": "https://other.example.test"},
                    {"HTTP_ORIGIN": "https://untrusted.example.test"}):
        response = read(**headers)
        assert response.status_code == 404
        assert response.data["code"] == "not_found"


def test_withdrawal_invalidates_share_and_sitemap_after_commit(published, django_capture_on_commit_callbacks):
    cache.set(f"public-profile:share:acct:{published.user_id}", "stale card")
    cache.set("public-profile:sitemap", "stale sitemap")
    with django_capture_on_commit_callbacks(execute=True):
        save_profile(published.membership, {"bio": "Updated bio"})  # 549: content invalidation remains
    assert cache.get(f"public-profile:share:acct:{published.user_id}") is None
    assert cache.get("public-profile:sitemap") is None
    response = read()
    assert response.status_code == 200
    assert response.data == expected_card(bio="Updated bio")
    assert response["Cache-Control"] == "no-store"


def test_share_and_sitemap_always_recheck_live_consent(published, django_capture_on_commit_callbacks):
    # Decision 549: share/sitemap recheck live account standing, not retired publication consent.
    from apps.makerspaces.public_profile_share import PublicProfileShareView, sitemap_profile_urls
    request = APIRequestFactory().get("/share/profiles/public.maker/")
    assert PublicProfileShareView.as_view()(request, handle="public.maker").status_code == 200
    body_key = cache.get(f"public-profile:share:acct:{published.user_id}")
    assert body_key.startswith("website-share:v1:") and cache.get(body_key)
    assert set(sitemap_profile_urls(request)) == {"http://testserver/@public.maker"}
    with django_capture_on_commit_callbacks(execute=True):
        user = published.membership.user
        user.is_active = False
        user.save(update_fields=["is_active"])
    assert cache.get(body_key) is None
    response = PublicProfileShareView.as_view()(request, handle="public.maker")
    assert response.status_code == 404
    assert response.data["code"] == "not_found"
    assert list(sitemap_profile_urls(request)) == []


@pytest.mark.parametrize("payload", [
    {"skills": [{"name": "Python", "level": 0}]}, {"skills": [{"name": "Python", "level": 4}]},
    {"domains": ["x"] * 21}, {"links": [{"kind": "web", "url": "http://example.test"}]},
    {"links": [{"kind": "web", "url": "javascript:alert(1)"}]},
    {"links": [{"kind": "web", "url": "https://user:password@example.test"}]},
])
def test_content_bounds(payload):
    assert not ProfileWriteSerializer(data=payload).is_valid()


def test_vouch_projection_omits_unpublished_vouchers_and_vouchees(published):
    from datetime import timedelta
    from apps.accounts.models import User
    from apps.makerspaces.models import MakerspaceMembership, MembershipRequest, MembershipVouch
    from apps.makerspaces.public_profile_handles import claim_handle
    space = published.membership.makerspace
    other = User.objects.create_user(username="public-voucher", display_name="Visible voucher")
    membership = MakerspaceMembership.objects.create(user=other, makerspace=space, assigned_role=space.roles.get(slug="member"), role="custom")
    request = MembershipRequest.objects.create(makerspace=space, user=published.membership.user,
                                              kind="request", state="active")
    MembershipVouch.objects.create(makerspace=space, request=request, voucher=other,
                                   expires_at=timezone.now() + timedelta(days=30))
    from apps.makerspaces.account_profile_vouches import vouches_for
    subject = published.membership.user
    save_profile(membership, {"is_visible": True})
    assert vouches_for(subject, "public")["vouched_by"] == []
    # Decision 549 removed publication writes; seed legacy consent for the retained voucher gate.
    AccountProfile.objects.filter(user=other).update(public_visible=True, public_consented_at=timezone.now())
    claim_handle(membership.user, "public.voucher")
    assert vouches_for(subject, "public")["vouched_by"] == [
        {"handle": "public.voucher", "display_name": "Visible voucher", "space_name": space.name}]
    AccountProfile.objects.filter(user=other).update(public_visible=False)
    assert vouches_for(subject, "public")["vouched_by"] == []
    # Decision 336b (M13): the anonymous profile read never names vouchers; only co-members see them.
    response = read()
    assert response.status_code == 200
    assert response.data == expected_card()  # 549: vouchers are absent from the entire card
