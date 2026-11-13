"""SECURITY-REVIEW M14-M17, L-P1 and L-P2: usernames, the handle gate, purge reservations and the export."""
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts import services_registration
from apps.accounts.models import User
from apps.makerspaces import handle_gate
from apps.makerspaces.account_profile import account_profile_for, save_profile
from apps.makerspaces.account_profile_purge import purge_account_profile
from apps.makerspaces.models import AccountProject, ProfileAchievement, PublicHandle, PublicHandleRedirect
from apps.makerspaces.public_profile_handles import (
    check_handle, claim_default_handle, claim_for_signup, claim_handle, name_available, release_handle,
    suggestion_for,
)

from .conftest import make_person

pytestmark = pytest.mark.django_db
SIGNUP = "/api/v1/auth/member-sign-up"
PASSWORD = "Safe member password 947!"


def signup(email, handle):
    return APIClient().post(SIGNUP, {"display_name": "New Person", "email": email, "password": PASSWORD,
                                     "handle": handle}, format="json")


# --- M14: sign-up never reveals whether an email is registered --------------------------------------


def test_the_handle_check_answers_the_same_for_a_new_and_a_registered_email(monkeypatch):
    monkeypatch.setattr(services_registration, "send_email_verification_otp", lambda *a: 1)
    User.objects.create_user(username="existing", email="known@example.test", password=PASSWORD)
    assert signup("known@example.test", "probe-one").status_code == 200
    assert signup("fresh@example.test", "probe-two").status_code == 200
    assert check_handle("probe-one") == check_handle("probe-two") == (True, "")


def test_an_invalid_handle_is_refused_the_same_way_for_known_and_unknown_emails(monkeypatch):
    monkeypatch.setattr(services_registration, "send_email_verification_otp", lambda *a: 1)
    User.objects.create_user(username="existing2", email="known2@example.test", password=PASSWORD)
    known = signup("known2@example.test", "ab")
    unknown = signup("unknown2@example.test", "ab")
    assert known.status_code == unknown.status_code == 400


# --- M15: a sign-in username is never published automatically --------------------------------------


def test_a_password_login_username_is_never_auto_claimed_or_suggested():
    staff = User.objects.create_user(username="night-shift", email="n@example.test", password=PASSWORD,
                                     display_name="Night Shift Lead")
    assert claim_default_handle(staff) is None
    assert not PublicHandle.objects.filter(user=staff).exists()
    assert suggestion_for(staff) == "night-shift-lead"
    # ... but the person may still choose it on purpose.
    claim_for_signup(staff, "night-shift")
    assert PublicHandle.objects.get(user=staff).handle == "night-shift"


def test_a_passwordless_account_keeps_the_username_first_default():
    social = make_person("social-only")  # no usable password: the username signs nobody in
    claim_default_handle(social)
    assert PublicHandle.objects.get(user=social).handle == "social-only"


def test_the_check_never_distinguishes_reserved_from_taken():
    assert check_handle("admin") == (False, "taken")
    assert check_handle("support") == (False, "taken")  # L-P1 brand/operational name
    from .conftest import client_for
    assert client_for(make_person("asker")).get("/api/v1/handles/check", {"handle": "admin"}).data["reason"] == "taken"


# --- M16: releasing a handle blocks only handle changes ---------------------------------------------


def _post(url_name):
    request = APIRequestFactory().post("/x")
    request.resolver_match = MagicMock(url_name=url_name)
    return request


def test_release_cooldown_never_blocks_other_writes_and_the_own_name_can_come_back():
    person = make_person("cooling")
    claim_for_signup(person, "cooling")
    release_handle(person)
    handle_gate.assert_handle_chosen(_post("anything"), person)  # no 403 while in the 30-day wait
    with pytest.raises(Exception):
        claim_handle(person, "something-else")
    assert claim_handle(person, "cooling").handle == "cooling"


def test_safety_and_erasure_routes_are_never_gated():
    for name in ("auth-account-deletion", "auth-change-password", "auth-mfa-disable", "auth-passkeys",
                 "auth-reauth", "auth-email-verification-confirm"):
        assert name in handle_gate.ALLOWED_URL_NAMES
    blocked = make_person("still-blocked")
    PublicHandle.objects.filter(user=blocked).delete()
    handle_gate.assert_handle_chosen(_post("auth-account-deletion"), blocked)
    with pytest.raises(handle_gate.HandleRequired):
        handle_gate.assert_handle_chosen(_post("anything"), blocked)


# --- L-P1: an abandoned sign-up frees its username --------------------------------------------------


def test_releasing_a_stale_signup_frees_its_handle():
    from apps.accounts.services_registration import _release_self_registration

    stale = User.objects.create_user(username="stale-signup", email="s@example.test", password=PASSWORD,
                                     self_registered_at=timezone.now() - timedelta(days=2))
    claim_for_signup(stale, "squatted-name")
    _release_self_registration(stale, timezone.now())
    assert check_handle("squatted-name") == (True, "")


# --- L-P2: a purged person's handle stays reserved for 30 days --------------------------------------


def test_a_purged_handle_is_reserved_not_freed():
    person = make_person("leaving-soon")
    claim_for_signup(person, "leaving-soon")
    account_profile_for(person)
    purge_account_profile(person)
    assert not PublicHandle.objects.filter(user=person).exists()
    assert name_available("leaving-soon") is False
    reservation = PublicHandleRedirect.objects.get(handle="leaving-soon")
    assert reservation.expires_at > timezone.now() + timedelta(days=29)
    newcomer = make_person("newcomer")
    with pytest.raises(Exception):
        claim_for_signup(newcomer, "leaving-soon")


# --- M17: the member's own export contains their global profile -------------------------------------


def test_the_subject_export_carries_the_requesters_own_profile_only(ada, grace):
    from apps.data_export.subject_account_profile import account_profile_records

    save_profile(ada, {"bio": "about me", "public_visible": True, "publication_consent": True})
    profile = account_profile_for(ada)
    AccountProject.objects.create(profile=profile, title="Mine", image_key="account/1/x.png")
    ProfileAchievement.objects.create(profile=profile, title="Award")
    save_profile(grace, {"bio": "someone else"})
    records = account_profile_records(ada)
    assert records["profile"][0]["bio"] == "about me" and records["profile"][0]["public_consented_at"]
    assert "avatar_key" not in records["profile"][0] and "user" not in records["profile"][0]
    assert [row["title"] for row in records["projects"]] == ["Mine"] and "image_key" not in records["projects"][0]
    assert [row["title"] for row in records["achievements"]] == ["Award"]
    assert "someone else" not in str(records)
    assert account_profile_records(make_person("no-profile-yet")) == {
        "profile": [], "projects": [], "timeline": [], "achievements": []}


def test_the_subject_archive_writes_the_profile_section():
    from apps.data_export import subject_archive

    source = Path(subject_archive.__file__).read_text(encoding="utf-8")
    assert "account_profile_records(job.requested_by)" in source and "account_profile/" in source
