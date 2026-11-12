"""Closing the PROFILE-2 'not done' list: claim sessions, storage recompute, admin, vouches, account graph."""
import pytest
from django.contrib import admin
from django.utils import timezone

from apps.accounts.claim_route_types import Refused
from apps.accounts.claim_routes import policy_for
from apps.makerspaces.account_profile import account_profile_for, save_profile
from apps.makerspaces.account_profile_vouches import vouches_for
from apps.makerspaces.management.commands.recompute_storage import Command
from apps.makerspaces.models import AccountProfile, AccountProject, MembershipRequest, MembershipVouch
from apps.makerspaces.profile_activity_public import daily_activity

from .conftest import client_for, make_person

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("name,method", [
    ("member-profile", "PUT"), ("member-profile", "PATCH"), ("member-profile-image", "POST"),
    ("member-profile-image", "PUT"), ("member-profile-image", "DELETE"),
    ("member-profile-timeline", "POST"), ("member-profile-achievements", "POST"),
])
def test_claim_sessions_cannot_write_the_global_profile_through_the_old_routes(name, method):
    assert isinstance(policy_for(name, method), Refused)


def test_recompute_storage_counts_account_level_avatars_and_project_images(space_a, ada):
    profile = account_profile_for(ada)
    avatar, project_key = f"member/{space_a.pk}/a.png", f"member/{space_a.pk}/p.png"
    AccountProfile.objects.filter(pk=profile.pk).update(avatar_key=avatar)
    AccountProject.objects.create(profile=profile, title="P", image_key=project_key)
    AccountProfile.objects.create(user=make_person("elsewhere"), avatar_key="member/999999/other.png")
    keys = set(Command._public_image_keys(space_a))
    assert {avatar, project_key} <= keys and "member/999999/other.png" not in keys


def test_account_profile_has_a_read_only_control_admin():
    model_admin = admin.site._registry[AccountProfile]

    class Request:
        method = "POST"
        user = type("U", (), {"is_active": True, "is_superuser": True, "is_staff": True,
                              "has_perm": lambda *a: True})()

    assert model_admin.has_add_permission(Request()) is False
    assert model_admin.has_change_permission(Request()) is False


def test_vouches_are_named_only_for_readable_vouchers_and_open_web_needs_their_consent(space_a, ada):
    from datetime import timedelta
    voucher = make_person("voucher-v", space_a)
    request = MembershipRequest.objects.create(makerspace=space_a, user=ada, kind="request", state="active")
    MembershipVouch.objects.create(makerspace=space_a, request=request, voucher=voucher,
                                   expires_at=timezone.now() + timedelta(days=30))
    from apps.makerspaces.public_profile_handles import claim_for_signup
    claim_for_signup(voucher, "voucher-v")
    assert vouches_for(ada, "member")["vouched_by"] == [
        {"handle": "voucher-v", "display_name": "Voucher-V", "space_name": space_a.name}]
    assert vouches_for(ada, "public")["vouched_by"] == []  # voucher has not opened to the open web
    save_profile(voucher, {"public_visible": True, "publication_consent": True})
    assert len(vouches_for(ada, "public")["vouched_by"]) == 1
    save_profile(voucher, {"is_visible": False})
    assert vouches_for(ada, "member")["vouched_by"] == []


def test_activity_graph_and_github_work_for_an_account_with_no_legacy_profile(space_a, ada):
    from apps.makerspaces.models import MemberProfile
    account_profile_for(ada)
    # Pointer rows exist (decision 305) but carry no content: the account row is the only source.
    assert not MemberProfile.objects.filter(membership__user=ada).exclude(headline="", github_username="").exists()
    save_profile(ada, {"github_username": "octocat", "show_activity_graph": True})
    account = AccountProfile.objects.get(user=ada)
    assert account.github_username == "octocat" and account.github_contributions is None
    assert len(daily_activity(account, {})["days"]) == 120
    save_profile(ada, {"github_username": "someone-else"})
    assert AccountProfile.objects.get(user=ada).github_synced_at is None  # a new username clears the cache
    handle = client_for(ada).get("/api/v1/member/profile").data["handle"]
    assert client_for(ada).get(f"/api/v1/public/profiles/{handle}/github").data == {"source": "github", "days": []}
