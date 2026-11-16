"""Decision 308: everyone needs a username. Availability, every sign-up path, the gate, token clients."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts import services_registration
from apps.accounts.models import User
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.makerspaces import handle_gate
from apps.makerspaces.models import PublicHandle
from apps.makerspaces.public_profile_handles import (
    check_handle, claim_default_handle, claim_for_signup, suggest_handle, suggestion_for,
)

from .conftest import client_for, make_person

pytestmark = pytest.mark.django_db
CHECK = "/api/v1/handles/check"
SIGNUP = "/api/v1/auth/member-sign-up"
ME = "/api/v1/auth/me"
PASSWORD = "Safe member password 947!"


def jwt_client(user):
    token = SpaceWorksRefreshToken.for_user(user).access_token
    token["surface"] = "member"
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api


def handleless(username="no-handle-yet", **fields):
    user = make_person(username, **fields)
    PublicHandle.objects.filter(user=user).delete()
    return user


# --- availability + suggestion -------------------------------------------------------------------


def test_check_reports_grammar_reserved_taken_and_free():
    make_person("taken-name")
    claim_default_handle(User.objects.get(username="taken-name"))
    client = APIClient()
    assert client.get(CHECK, {"handle": "free-name"}).data["available"] is True
    # Decision 336d: a reserved word answers "taken" exactly like a claimed name.
    for value, reason in (("ab", "invalid"), ("admin", "taken"), ("Taken-Name", "taken"), ("-bad", "invalid")):
        body = client.get(CHECK, {"handle": value}).data
        assert (body["available"], body["reason"]) == (False, reason), value
    assert client.get(CHECK).data["available"] is None  # no handle asked: suggestion only


def test_suggestion_order_username_then_name_slug_then_digits():
    assert suggest_handle(username="ada.l", display_name="Ada Lovelace") == "ada.l"
    assert suggest_handle(username="member_" + "a" * 32, display_name="Ada Lovelace") == "ada-lovelace"
    make_person("taken1")
    claim_default_handle(User.objects.get(username="taken1"))
    taken_slug = make_person("slug-owner")
    claim_for_signup(taken_slug, "ada-lovelace")
    digits = suggest_handle(username="admin", display_name="Ada Lovelace")
    assert digits.startswith("ada-lovelace") and digits != "ada-lovelace" and check_handle(digits)[0]
    assert APIClient().get(CHECK, {"username": "ada.l", "display_name": "x"}).data["suggestion"] == "ada.l"


def test_check_is_throttled_like_other_public_reads():
    from apps.makerspaces.handle_views import HandleCheckView
    # Decision 336c/M15: the shared public budget plus the tighter per-account / per-IP handle-check budgets.
    assert [c.__name__ for c in HandleCheckView.throttle_classes] == [
        "ClientTierRateThrottle", "HandleCheckThrottle", "HandleCheckDailyThrottle"]
    assert HandleCheckView.authentication_classes == []


# --- sign-up paths -------------------------------------------------------------------------------


def post_signup(client, email, **extra):
    return client.post(SIGNUP, {"display_name": "Ada Lovelace", "email": email, "password": PASSWORD, **extra},
                       format="json")


def confirm_email(user, code):
    token = SpaceWorksRefreshToken.for_user(user).access_token
    token["surface"] = "verification_only"
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api.post("/api/v1/auth/email-verification/confirm", {"code": code}, format="json")


def test_email_signup_claims_the_chosen_handle_only_when_the_email_is_confirmed(monkeypatch):
    """SECURITY-REVIEW M14: claiming at sign-up made "taken" mean "this address is new"."""
    codes = []
    monkeypatch.setattr(services_registration, "send_email_verification_otp", lambda _, code: codes.append(code) or 1)
    response = post_signup(APIClient(), "ada@example.test", handle="Ada-L")
    assert response.status_code == 200
    user = User.objects.get(email="ada@example.test")
    assert not PublicHandle.objects.filter(user=user).exists()
    assert check_handle("ada-l") == (True, "")
    assert confirm_email(user, codes[0]).status_code == 200
    assert PublicHandle.objects.get(user=user).handle == "ada-l"


@pytest.mark.parametrize("bad", ["ab", "admin", "bad name"])
def test_signup_with_an_invalid_or_reserved_handle_is_refused_and_creates_nothing(monkeypatch, bad):
    monkeypatch.setattr(services_registration, "send_email_verification_otp", lambda *a: 1)
    response = post_signup(APIClient(), "nobody@example.test", handle=bad)
    assert response.status_code == 400 and "handle" in response.data
    assert not User.objects.filter(email="nobody@example.test").exists()


def test_signup_with_a_taken_handle_is_refused_and_a_lost_race_rolls_the_account_back(monkeypatch):
    monkeypatch.setattr(services_registration, "send_email_verification_otp", lambda *a: 1)
    claim_for_signup(make_person("owner"), "wanted-name")
    assert post_signup(APIClient(), "late@example.test", handle="wanted-name").status_code == 400
    assert not User.objects.filter(email="late@example.test").exists()
    # The name is only CLAIMED at email confirmation (M14). Lost between sign-up and confirmation, the
    # account gets the best suggestion instead and can change it once for free.
    from apps.makerspaces import public_profile_handles as handles
    codes = []
    monkeypatch.setattr(services_registration, "send_email_verification_otp", lambda _, code: codes.append(code) or 1)
    monkeypatch.setattr("apps.accounts.serializers_registration.MemberSignUpSerializer.validate_handle",
                        lambda self, value: value.lower())
    assert post_signup(APIClient(), "race@example.test", handle="wanted-name").status_code == 200
    racer = User.objects.get(email="race@example.test")
    assert confirm_email(racer, codes[-1]).status_code == 200
    assert PublicHandle.objects.get(user=racer).handle == "ada-lovelace"
    assert handles.check_handle("wanted-name") == (False, "taken")


def test_signup_without_a_handle_still_gets_the_best_suggestion(monkeypatch):
    codes = []
    monkeypatch.setattr(services_registration, "send_email_verification_otp", lambda _, code: codes.append(code) or 1)
    post_signup(APIClient(), "plain@example.test")
    user = User.objects.get(email="plain@example.test")
    assert confirm_email(user, codes[0]).status_code == 200
    assert PublicHandle.objects.get(user=user).handle == "ada-lovelace"  # username is a placeholder -> name slug


def test_otp_confirmation_keeps_the_handle_chosen_at_signup(monkeypatch):
    codes = []
    monkeypatch.setattr(services_registration, "send_email_verification_otp", lambda _, code: codes.append(code) or 1)
    post_signup(APIClient(), "otp@example.test", handle="otp-person")
    user = User.objects.get(email="otp@example.test")
    token = SpaceWorksRefreshToken.for_user(user).access_token
    token["surface"] = "verification_only"
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert api.post("/api/v1/auth/email-verification/confirm", {"code": codes[0]}, format="json").status_code == 200
    assert PublicHandle.objects.get(user=user).handle == "otp-person"


def test_social_account_creation_claims_a_handle_with_the_account():
    from apps.accounts import services_social_identity as social
    source = Path(social.__file__).read_text(encoding="utf-8")
    assert "claim_for_signup(user)" in source.split("user.set_unusable_password()")[1].split("outcome = ")[0]


def test_walk_in_upgrade_claims_a_chosen_or_suggested_handle():
    from apps.accounts.transition_services import transition_walk_in_to_account
    staff = make_person("front-desk")
    walk_in = User.objects.create_user(username="member_" + "b" * 32, display_name="Walk In", is_walk_in=True)
    transition_walk_in_to_account(walk_in, actor=staff, handle="walked-in")
    assert PublicHandle.objects.get(user=walk_in).handle == "walked-in"
    second = User.objects.create_user(username="member_" + "c" * 32, display_name="Second Walker", is_walk_in=True)
    transition_walk_in_to_account(second, actor=staff)
    assert PublicHandle.objects.get(user=second).handle == "second-walker"


def test_invitation_and_organization_invitation_accounts_come_through_the_same_signup_paths():
    """Invitations redeem for an EXISTING signed-in account, so they create none: the account was made by
    one of the paths above (or has the gate below). Pin that no other creation site exists."""
    from apps.accounts import services_registration as signup, services_social_identity as social
    root = Path(signup.__file__).parents[1]
    sites = {str(path.relative_to(root)).replace("\\", "/") for path in root.rglob("*.py")
             if "User(" in path.read_text(encoding="utf-8", errors="ignore")
             and "tests" not in path.parts and "migrations" not in path.parts}
    assert {"accounts/services_registration.py", "accounts/services_social_identity.py"} <= sites
    assert social and signup


# --- migration + existing accounts ---------------------------------------------------------------


def test_default_claim_for_existing_accounts_is_username_only():
    free = make_person("free-user-name")
    claim_default_handle(free)
    assert PublicHandle.objects.get(user=free).handle == "free-user-name"
    bad = make_person("x")
    bad.username = "ab"
    bad.display_name = "Name Only"
    bad.save()
    assert claim_default_handle(bad) is None and not PublicHandle.objects.filter(user=bad).exists()
    assert suggestion_for(bad) == "name-only"  # ... who then sees the blocking step with this suggestion


# --- the gate ------------------------------------------------------------------------------------


def test_auth_payload_flags_a_missing_handle_with_a_suggestion():
    user = handleless("needs-one", display_name="Needs One")
    body = jwt_client(user).get(ME).data
    assert body["handle_required"] is True and body["handle"] is None and body["handle_suggestion"]
    claim_for_signup(user, body["handle_suggestion"])
    body = jwt_client(user).get(ME).data
    assert body["handle_required"] is False
    assert body["handle"]


def test_state_changing_member_routes_return_typed_handle_required_until_chosen():
    user = handleless("blocked")
    api = jwt_client(user)
    response = api.put("/api/v1/member/profile", {"headline": "x"}, format="json")
    assert response.status_code == 403
    assert response.data["code"] == "handle_required"
    assert api.get(ME).status_code == 200  # reading your own account stays open
    assert api.get("/api/v1/member/profile").status_code == 200  # reads are never blocked


def test_allow_list_sign_out_choose_handle_and_availability():
    user = handleless("allowed")
    api = jwt_client(user)
    assert api.post("/api/v1/member/profile/handle", {"handle": "chosen-one"}, format="json").status_code == 200
    unblocked = api.put("/api/v1/member/profile", {"headline": "now fine"}, format="json")
    assert unblocked.status_code == 200
    again = handleless("allowed-two")
    assert jwt_client(again).get(CHECK, {"handle": "free-one"}).status_code == 200
    assert {"auth-logout", "auth-logout-all", "auth-refresh", "member-global-profile-handle",
            "member-profile-handle", "handle-check"} <= handle_gate.ALLOWED_URL_NAMES


def test_the_gate_ignores_safe_methods_walk_ins_and_platform_accounts():
    factory = APIRequestFactory()
    get = factory.get("/x")
    get.resolver_match = MagicMock(url_name="anything")
    handle_gate.assert_handle_chosen(get, handleless("reader"))
    post = factory.post("/x")
    post.resolver_match = MagicMock(url_name="anything")
    walk_in = User.objects.create_user(username="walk-in-gate", is_walk_in=True)
    handle_gate.assert_handle_chosen(post, walk_in)
    platform = User.objects.create_superuser(username="platform-gate", email="p@example.test", password=PASSWORD)
    handle_gate.assert_handle_chosen(post, platform)
    with pytest.raises(handle_gate.HandleRequired):
        handle_gate.assert_handle_chosen(post, handleless("gated"))


# --- token clients are unaffected ----------------------------------------------------------------


def test_machine_and_station_principals_never_reach_the_gate():
    """The gate lives ONLY in the human bearer class: HMAC API clients and kiosk/station/display
    tokens authenticate through other classes, so they cannot be blocked by a missing handle."""
    from apps.accounts import authentication
    root = Path(authentication.__file__).parents[1]
    users = [str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*.py")
             if "assert_handle_chosen" in p.read_text(encoding="utf-8", errors="ignore")
             and "tests" not in p.parts]
    assert sorted(users) == ["accounts/authentication.py", "makerspaces/handle_gate.py"]


def test_a_non_bearer_principal_can_write_without_a_handle():
    """force_authenticate stands in for any non-JWT principal: the gate is not in their path."""
    user = handleless("kiosk-like")
    response = client_for(user).put("/api/v1/member/profile", {"headline": "ok"}, format="json")
    assert response.status_code == 200


def test_public_signup_and_availability_routes_need_no_handle():
    # The anonymous availability check never authenticates, so it cannot be gated.
    assert APIClient().get(CHECK, {"handle": "anything-free"}).status_code == 200
