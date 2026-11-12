"""SECURITY-REVIEW H1, H4, H5, M13, L-P3, L-P5, L-F1 and hardening 13 on the global profile."""
import pytest
from django.utils import timezone

from apps.makerspaces import minors
from apps.makerspaces.account_profile import account_profile_for, save_profile
from apps.makerspaces.account_profile_spaces import organizations_for, spaces_for
from apps.makerspaces.account_profile_vouches import vouches_for
from apps.makerspaces.models import (
    AccountProject, GuardianConsent, MakerspaceMembership, MembershipRequest, MembershipVouch, MinorProfile,
    ProfileAchievement,
)
from apps.makerspaces.public_profile_handles import claim_for_signup
from apps.organizations.models import Organization, OrganizationMembership

from .conftest import client_for, make_person, make_space

pytestmark = pytest.mark.django_db
BY_ACCOUNT = "/api/v1/profiles/by-account/{}/"
PUBLIC = "/api/v1/public/profiles/{}/"


def directory_detail(viewer, space, subject):
    membership = MakerspaceMembership.all_tracks.get(user=subject, makerspace=space, track="community")
    return client_for(viewer).get(f"/api/v1/member/makerspaces/{space.pk}/directory/{membership.pk}")


# --- H1: the directory detail is the member audience, never the owner payload ---------------------


def test_directory_detail_honours_section_switches_and_hidden_projects(ada, grace, space_a):
    save_profile(ada, {"bio": "secret bio", "education": [{"institution": "Hidden U"}], "interests": ["Quiet"],
                       "links": [{"kind": "web", "url": "https://ada.test"}], "github_username": "ada-gh",
                       "show_about": False, "show_education": False, "show_interests": False, "show_links": False,
                       "show_activity_graph": False})
    profile = account_profile_for(ada)
    AccountProject.objects.create(profile=profile, title="Private build", public_visible=False)
    AccountProject.objects.create(profile=profile, title="Open build", public_visible=True,
                                  links=[{"label": "x", "url": "javascript:alert(1)"}, {"label": "y", "url": "https://ok.test"}])
    response = directory_detail(grace, space_a, ada)
    assert response.status_code == 200
    body = response.data
    assert body["bio"] == "" and body["education"] == [] and body["interests"] == [] and body["links"] == []
    assert body["github_username"] == ""
    assert [p["title"] for p in body["projects"]] == ["Open build"]
    assert [link["url"] for link in body["projects"][0]["links"]] == ["https://ok.test"]
    for owner_key in ("public_visible", "show_activity_graph", "show_speaking", "show_loans"):
        assert owner_key not in body
    assert body["public_consented_at"] is None


def test_directory_detail_still_shows_open_sections_and_closes_for_hidden_profiles(ada, grace, space_a):
    save_profile(ada, {"bio": "hello", "headline": "Welder"})
    body = directory_detail(grace, space_a, ada).data
    assert body["bio"] == "hello" and body["headline"] == "Welder"
    save_profile(ada, {"is_visible": False})
    assert directory_detail(grace, space_a, ada).status_code == 404


def test_directory_hides_a_tenant_dump_stub_like_any_unlistable_account(ada, grace, space_a):
    account_profile_for(ada)
    type(ada).objects.filter(pk=ada.pk).update(is_tenant_dump_stub=True)
    assert directory_detail(grace, space_a, ada).status_code == 404  # L-P5: the one listability rule


# --- H4: minors ------------------------------------------------------------------------------------


def mark_minor(user, space):
    return MinorProfile.objects.create(makerspace=space, user=user, declared_under_age=True)


def test_a_minor_is_readable_only_by_people_who_share_a_space(grace, space_a):
    child = make_person("child", space_a)
    account_profile_for(child)
    mark_minor(child, space_a)
    stranger = make_person("far-away", make_space("elsewhere"))
    assert client_for(grace).get(BY_ACCOUNT.format(child.pk)).status_code == 200
    assert client_for(stranger).get(BY_ACCOUNT.format(child.pk)).status_code == 404
    assert client_for(child).get(BY_ACCOUNT.format(child.pk)).status_code == 200


def test_a_minor_cannot_open_the_web_alone_and_a_guardian_consent_unlocks_it(grace, space_a):
    child = make_person("child-web", space_a)
    claim_for_signup(child, "child-web")
    profile = mark_minor(child, space_a)
    with pytest.raises(Exception):
        save_profile(child, {"public_visible": True, "publication_consent": True})
    assert account_profile_for(child).public_visible is False
    minors.publish_terms(grace, space_a, "I consent.", "v1")
    minors.sign_consent(grace, profile, "A Guardian", accepted=True, method=GuardianConsent.Method.STAFF_RECORDED)
    save_profile(child, {"public_visible": True, "publication_consent": True})
    assert client_for().get(PUBLIC.format("child-web")).status_code == 200
    GuardianConsent.objects.filter(profile=profile).update(revoked_at=timezone.now())
    assert client_for().get(PUBLIC.format("child-web")).status_code == 404  # consent lapsed: off the web


def test_a_minor_is_never_on_the_sitemap_or_a_share_card(space_a):
    from apps.makerspaces.public_profile_share import sitemap_profile_urls
    from rest_framework.test import APIRequestFactory

    adult = make_person("adult-web", space_a)
    claim_for_signup(adult, "adult-web")
    save_profile(adult, {"public_visible": True, "publication_consent": True})
    child = make_person("child-card", space_a)
    claim_for_signup(child, "child-card")
    save_profile(child, {"public_visible": True, "publication_consent": True})
    mark_minor(child, space_a)
    urls = list(sitemap_profile_urls(APIRequestFactory().get("/sitemap.xml"), spaces=[space_a]))
    assert any(url.endswith("/adult-web") for url in urls)
    assert not any(url.endswith("/child-card") for url in urls)
    assert client_for().get("/share/profiles/child-card/").status_code == 404


# --- M13 / 336b: spaces, organisations, roles and vouches by audience -------------------------------


def test_non_co_members_see_only_public_spaces_without_titles_and_no_vouches(ada, grace, space_a, space_b):
    type(space_b).objects.filter(pk=space_b.pk).update(public_site_enabled=False)
    for space in (space_a, space_b):
        space.refresh_from_db()
    account_profile_for(ada)
    stranger = make_person("outsider", make_space("space-x"))
    full = spaces_for(ada, full=True)
    assert {row["slug"] for row in full} == {"space-a", "space-b"}
    public = client_for(stranger).get(BY_ACCOUNT.format(ada.pk)).data
    assert "space-b" not in {row["slug"] for row in public["spaces"]}
    assert all(row["role_title"] is None for row in public["spaces"])
    assert public["vouched_by"] == [] and public["vouched_count"] == 0
    co_member = client_for(grace).get(BY_ACCOUNT.format(ada.pk)).data
    assert any(row["role_title"] for row in co_member["spaces"])


def test_private_organisations_are_listed_only_to_the_owner(ada):
    hidden = Organization.objects.create(name="Quiet Org", slug="quiet", is_active=True, review_status="approved")
    shown = Organization.objects.create(name="Open Org", slug="open", is_active=True, review_status="approved",
                                        public_profile_enabled=True)
    for org in (hidden, shown):
        OrganizationMembership.objects.create(organization=org, user=ada, status="active")
    assert {row["slug"] for row in organizations_for(ada, full=True)} == {"quiet", "open"}
    assert {row["slug"] for row in organizations_for(ada)} == {"open"}


# --- L-P3: a named voucher must still belong and show their spaces --------------------------------


def _vouch(space, member, voucher):
    from datetime import timedelta

    request = MembershipRequest.objects.create(makerspace=space, user=member, kind="request", state="active")
    return MembershipVouch.objects.create(makerspace=space, request=request, voucher=voucher,
                                          expires_at=timezone.now() + timedelta(days=30))


def test_voucher_is_named_only_while_a_member_showing_their_spaces(ada, space_a):
    voucher = make_person("voucher-l", space_a)
    claim_for_signup(voucher, "voucher-l")
    _vouch(space_a, ada, voucher)
    assert len(vouches_for(ada, "member")["vouched_by"]) == 1
    save_profile(voucher, {"show_spaces": False})
    assert vouches_for(ada, "member")["vouched_by"] == []
    save_profile(voucher, {"show_spaces": True})
    MakerspaceMembership.all_tracks.filter(user=voucher, makerspace=space_a).update(status="revoked")
    assert vouches_for(ada, "member")["vouched_by"] == []


def test_a_minor_voucher_is_never_named(ada, space_a):
    voucher = make_person("young-voucher", space_a)
    claim_for_signup(voucher, "young-voucher")
    _vouch(space_a, ada, voucher)
    mark_minor(voucher, space_a)
    assert vouches_for(ada, "member")["vouched_by"] == []


# --- H5: everyone is told once that their profile is open -------------------------------------------


def test_a_backfilled_or_new_profile_is_queued_for_the_one_time_notice(ada):
    assert account_profile_for(ada).open_notice_pending is True


# --- L-F1: self-reported achievement links are filtered on read too --------------------------------


def test_a_non_https_achievement_url_never_reaches_a_reader(ada, grace):
    profile = account_profile_for(ada)
    ProfileAchievement.objects.create(profile=profile, title="Imported", url="javascript:alert(1)")
    ProfileAchievement.objects.create(profile=profile, title="Fine", url="https://award.test/x")
    rows = client_for(grace).get(BY_ACCOUNT.format(ada.pk)).data["achievements"]["self_reported"]
    assert {row["title"]: row["url"] for row in rows} == {"Imported": "", "Fine": "https://award.test/x"}


# --- hardening 13: an account merge keeps the stricter visibility -----------------------------------


def test_account_merge_takes_the_stricter_switches(ada, grace):
    from apps.makerspaces.account_profile_account_merge import merge_profiles

    save_profile(ada, {"show_about": False, "bio": "private"})
    save_profile(grace, {"public_visible": True, "publication_consent": True})
    assert merge_profiles(ada.pk, grace.pk) is True
    survivor = account_profile_for(grace)
    assert survivor.show_about is False and survivor.bio == "private"
    assert survivor.public_visible is False and survivor.public_consented_at is None
