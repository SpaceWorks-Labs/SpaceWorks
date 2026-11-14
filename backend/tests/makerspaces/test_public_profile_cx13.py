"""Decision 549: exact public cards, publication retirement and tenant fences."""
from datetime import date, datetime, timedelta, timezone as dt_timezone

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.apiclients.throttling import ClientTierRateThrottle
from apps.makerspaces.account_profile import account_profile_for, save_profile
from apps.makerspaces.account_profile_serializers import AccountProfileWriteSerializer
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MinorProfile
from apps.makerspaces.models_account_profile import AccountProfile, AccountProject
from apps.makerspaces.models_profiles import PublicHandle, PublicHandleRedirect
from apps.makerspaces.profile_serializers import ProfileReadSerializer, ProfileWriteSerializer
from apps.makerspaces.public_profile_serializers import PublicAccountCardSerializer

pytestmark = pytest.mark.django_db
BASE = "/api/v1/public/profiles/cx13.maker/"
RETIRED = {"is_visible", "public_visible", "publication_consent", "public_consented_at",
           "public_reconfirm_pending"}


@pytest.fixture
def person(settings):
    settings.INFRA_HOSTS = ["testserver", "localhost"]
    settings.PUBLIC_APP_BASE_URL = "http://testserver"
    settings.ALLOWED_HOSTS = ["testserver", ".example.test"]
    user = User.objects.create_user(username="cx13.maker", email="secret@example.test",
                                    display_name="Maker 名", phone="+12025550123")
    profile = account_profile_for(user)
    PublicHandle.objects.update_or_create(user=user, defaults={"handle": "cx13.maker", "changed_at": timezone.now()})
    # Old opt-outs remain stored; they cannot hide the public card.
    AccountProfile.objects.filter(pk=profile.pk).update(
        is_visible=False, public_visible=False, public_consented_at=None,
        bio="Builds useful things", public_reconfirm_pending=True, show_spaces=False)
    return user


def add_membership(person, slug="cx13-lab", **space_fields):
    space = Makerspace.objects.create(name=slug, slug=slug, public_site_enabled=True,
                                      enabled_modules=["member_accounts", "membership"], timezone="Asia/Kolkata", **space_fields)
    membership = MakerspaceMembership.objects.create(
        makerspace=space, user=person, role="custom", assigned_role=space.roles.get(slug="member"),
        activated_at=datetime(2025, 1, 1, 20, 0, tzinfo=dt_timezone.utc))
    return space, membership


def card(client=None, handle="cx13.maker", **headers):
    response = (client or APIClient()).get(f"/api/v1/public/profiles/{handle}/", **headers)
    assert response.status_code == 200, response.data
    return response


def test_exact_payload_and_no_pii_for_every_viewer(person):
    add_membership(person)
    profile = person.account_profile
    AccountProject.objects.create(profile=profile, title="Public robot", description="Built it",
                                   links=[{"label": "Code", "url": "https://example.test/code"}], tags=["robot"])
    AccountProject.objects.create(profile=profile, title="Secret project", public_visible=False)
    expected = {
        "display_name": "Maker 名", "avatar_url": None, "handle": "cx13.maker",
        "bio": "Builds useful things",
        "projects": [{"title": "Public robot", "subtitle": "", "description": "Built it", "tags": ["robot"],
                      "image_url": None, "links": [{"kind": "Code", "url": "https://example.test/code"}]}],
        "memberships": [{"slug": "cx13-lab", "name": "cx13-lab", "role_title": "Member", "started_on": "2025-01-02"}],
    }
    other = User.objects.create_user(username="cx13-other", email="other@example.test")
    for viewer in (None, person, other):
        client = APIClient()
        if viewer:
            client.force_authenticate(viewer)
        response = card(client)
        assert response.data == expected
        assert response["Cache-Control"] == "no-store"
        assert {"Host", "Origin"} <= set(response["Vary"].split(", "))
    # Exact equality above excludes contacts, internal row IDs, loans, money, evidence and audit.
    profile.refresh_from_db()
    assert (profile.is_visible, profile.public_visible, profile.public_consented_at,
            profile.public_reconfirm_pending) == (False, False, None, True)


@pytest.mark.parametrize("status", ["restricted", "suspended"])
def test_restricted_and_suspended_are_exactly_minimal(person, status):
    add_membership(person)
    AccountProject.objects.create(profile=person.account_profile, title="Never exposed")
    User.objects.filter(pk=person.pk).update(access_status=status)
    assert card().data == {"display_name": "Maker 名", "avatar_url": None}
    owner = APIClient()
    owner.force_authenticate(person)
    assert card(owner).data == {"display_name": "Maker 名", "avatar_url": None}


@pytest.mark.parametrize("modules,features", [([], []), (["member_accounts", "membership"], []),
                                            (["member_accounts", "membership"], ["membership.minors"])])
def test_minor_is_minimal_even_when_minors_module_is_off(person, modules, features):
    space, _ = add_membership(person)
    space.enabled_modules = modules
    space.enabled_features = features
    space.save(update_fields=["enabled_modules", "enabled_features"])
    MinorProfile.objects.create(makerspace=space, user=person, declared_under_age=True,
                                guardian_email="guardian-secret@example.test")
    assert card().data == {"display_name": "Maker 名", "avatar_url": None}


@pytest.mark.parametrize("field,value", [
    ("public_site_enabled", False), ("hidden_from_central_directory", True),
    ("lifecycle_state", "suspended"), ("archived_at", "now"), ("enabled_modules", []),
])
def test_nonpublic_spaces_are_omitted_and_restored_without_data_loss(person, field, value):
    space, membership = add_membership(person)
    original = getattr(space, field)
    setattr(space, field, timezone.now() if value == "now" else value)
    space.save(update_fields=[field])
    assert card().data["memberships"] == []
    assert MakerspaceMembership.objects.get(pk=membership.pk).status == "active"
    setattr(space, field, original)
    space.save(update_fields=[field])
    assert card().data["memberships"] == [
        {"slug": space.slug, "name": space.name, "role_title": "Member", "started_on": "2025-01-02"}]


def test_revoked_membership_is_omitted(person):
    _, membership = add_membership(person)
    membership.status = "revoked"
    membership.save(update_fields=["status"])
    assert card().data["memberships"] == []


def test_section_choices_keep_content_and_do_not_hide_memberships(person):
    add_membership(person)
    profile = person.account_profile
    AccountProject.objects.create(profile=profile, title="Retained")
    AccountProfile.objects.filter(pk=profile.pk).update(show_about=False, show_projects=False)
    response = card()
    assert response.data["bio"] == ""
    assert response.data["projects"] == []
    assert response.data["memberships"] == [
        {"slug": "cx13-lab", "name": "cx13-lab", "role_title": "Member", "started_on": "2025-01-02"}]
    AccountProfile.objects.filter(pk=profile.pk).update(show_about=True, show_projects=True)
    assert card().data["projects"][0]["title"] == "Retained"
    assert card().data["bio"] == "Builds useful things"


def test_missing_profile_row_still_serves_a_handle_without_writes(person):
    AccountProfile.objects.filter(user=person).delete()
    assert card().data == {"display_name": "Maker 名", "avatar_url": None,
                           "handle": "cx13.maker", "bio": "", "projects": [], "memberships": []}
    assert AccountProfile.objects.filter(user=person).count() == 0


@pytest.mark.parametrize("handle", ["unknown-cx13", "bad!handle", "ab"])
def test_unknown_handle_has_exact_not_found(person, handle):
    response = APIClient().get(f"/api/v1/public/profiles/{handle}/")
    assert response.status_code == 404
    assert response.data["code"] == "not_found"


def test_inactive_account_keeps_existing_security_refusal(person):
    User.objects.filter(pk=person.pk).update(is_active=False)
    response = APIClient().get(BASE)
    assert response.status_code == 404
    assert response.data["code"] == "not_found"


def test_retired_handle_redirects_only_during_its_reservation(person):
    redirect = PublicHandleRedirect.objects.create(
        handle="cx13.old", user=person, released_at=timezone.now(), expires_at=timezone.now() + timedelta(days=1))
    response = APIClient().get("/api/v1/public/profiles/cx13.old/")
    assert response.status_code == 302
    assert response["Location"] == BASE
    redirect.expires_at = timezone.now() - timedelta(seconds=1)
    redirect.save(update_fields=["expires_at"])
    response = APIClient().get("/api/v1/public/profiles/cx13.old/")
    assert response.status_code == 404
    assert response.data["code"] == "not_found"


def test_public_rate_limit_has_exact_error(person, monkeypatch):
    key = "cx13-public-profile-throttle"
    cache.delete(key)
    monkeypatch.setattr(ClientTierRateThrottle, "get_rate", lambda self: "1/min")
    monkeypatch.setattr(ClientTierRateThrottle, "get_cache_key", lambda *args: key)
    try:
        card()
        response = APIClient().get(BASE)
        assert response.status_code == 429
        assert response.data["code"] == "throttled"
    finally:
        cache.delete(key)


def test_no_publication_toggle_in_any_profile_schema_or_owner_response(person):
    from apps.makerspaces.account_profile_serializers import AccountProfileSerializer
    for serializer in (AccountProfileWriteSerializer, AccountProfileSerializer,
                       ProfileWriteSerializer, ProfileReadSerializer, PublicAccountCardSerializer):
        assert RETIRED & set(serializer().fields) == set()
    client = APIClient()
    client.force_authenticate(person)
    response = client.get("/api/v1/member/profile")
    assert response.status_code == 200
    assert RETIRED & set(response.data) == set()
    assert RETIRED & set(response.data["toggles"]) == set()
    # Even direct service callers cannot turn publication off; storage is untouched.
    save_profile(person, {"is_visible": True, "public_visible": True})
    person.account_profile.refresh_from_db()
    assert person.account_profile.is_visible is False
    assert person.account_profile.public_visible is False
    assert card().data["display_name"] == "Maker 名"


def test_both_host_and_origin_keep_foreign_tenant_fence(person):
    add_membership(person, "cx13-foreign", frontend_domain="foreign.example.test", frontend_domain_status="verified")
    other = Makerspace.objects.create(name="Other", slug="cx13-other", frontend_domain="other.example.test",
                                      frontend_domain_status="verified")
    for headers in ({"HTTP_HOST": other.frontend_domain}, {"HTTP_ORIGIN": f"https://{other.frontend_domain}"}):
        response = APIClient().get(BASE, **headers)
        assert response.status_code == 404
        assert response.data["code"] == "not_found"
    assert card(HTTP_HOST="foreign.example.test").data["display_name"] == "Maker 名"


def test_staff_title_wins_and_earliest_local_membership_date_is_kept(person):
    space, community = add_membership(person)
    MakerspaceMembership.staff_tracks.create(
        makerspace=space, user=person, track="staff", role="custom",
        assigned_role=space.roles.get(slug="inventory_manager"),
        activated_at=datetime(2026, 1, 1, tzinfo=dt_timezone.utc))
    assert card().data["memberships"] == [
        {"slug": space.slug, "name": space.name, "role_title": "Inventory Manager", "started_on": "2025-01-02"}]
    # Legacy rows without activation metadata use their actual creation day.
    community.activated_at = None
    community.save(update_fields=["activated_at"])
    MakerspaceMembership.objects.filter(pk=community.pk).update(
        created_at=datetime(2024, 12, 1, 20, tzinfo=dt_timezone.utc))
    assert card().data["memberships"][0]["started_on"] == "2024-12-02"


def test_shared_resolver_and_share_use_the_always_on_card(person):
    response = APIClient().get("/api/v1/public/page-handles/cx13.maker/")
    assert response.status_code == 200
    assert response.data == {
        "kind": "member", "handle": "cx13.maker", "canonical_url": "http://testserver/@cx13.maker",
        "redirected": False, "content_url": BASE,
    }
    response = APIClient().get("/share/profiles/cx13.maker/")
    assert response.status_code == 200
    assert b"Builds useful things" in response.content
    User.objects.filter(pk=person.pk).update(access_status="restricted")
    response = APIClient().get("/share/profiles/cx13.maker/")
    assert response.status_code == 200
    assert b"Builds useful things" not in response.content
    assert b"secret@example.test" not in response.content


def test_minimal_card_keeps_only_the_chosen_avatar(person, monkeypatch):
    from apps.makerspaces import public_profile_card
    AccountProfile.objects.filter(user=person).update(avatar_key="chosen-avatar")
    monkeypatch.setattr(public_profile_card, "public_url", lambda key: "https://example.test/avatar.png" if key else "")
    User.objects.filter(pk=person.pk).update(access_status="suspended")
    assert card().data == {"display_name": "Maker 名", "avatar_url": "https://example.test/avatar.png"}


def test_public_project_links_drop_unsafe_schemes_and_credentials(person):
    AccountProject.objects.create(profile=person.account_profile, title="Safe text <script>", links=[
        {"label": "Bad", "url": "javascript:alert(1)"},
        {"label": "Credentials", "url": "https://user:secret@example.test"},
        {"label": "Code", "url": "https://example.test/code"},
    ])
    assert card().data["projects"] == [{
        "title": "Safe text <script>", "subtitle": "", "description": "", "tags": [], "image_url": None,
        "links": [{"kind": "Code", "url": "https://example.test/code"}],
    }]


def test_blank_display_name_never_falls_back_to_a_private_login(person):
    User.objects.filter(pk=person.pk).update(
        username="login-secret@example.test", display_name="", first_name="", last_name="")
    assert card().data["display_name"] == "cx13.maker"


def test_minor_card_changes_at_the_spaces_local_age_boundary(person, monkeypatch):
    from apps.makerspaces import minors
    space, _ = add_membership(person)
    monkeypatch.setattr(minors, "_local_today", lambda makerspace: date(2026, 11, 14))
    minor = MinorProfile.objects.create(makerspace=space, user=person, date_of_birth="2008-11-15")
    assert card().data == {"display_name": "Maker 名", "avatar_url": None}
    minor.date_of_birth = "2008-11-14"
    minor.save(update_fields=["date_of_birth"])
    assert card().data["memberships"] == [
        {"slug": space.slug, "name": space.name, "role_title": "Member", "started_on": "2025-01-02"}]
