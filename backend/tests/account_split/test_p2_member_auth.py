"""Member identity methods never resolve a staff or platform principal."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.exceptions import TokenError

from apps.accounts import services_phone, services_phone_login, services_registration
from apps.accounts.claim_tokens import mint_claim_tokens
from apps.accounts.claim_sessions import ClaimSessionInvalid, validated_claim_session
from apps.accounts.models import User
from apps.accounts.models_phone import PhoneChallengePurpose, PhoneVerificationChallenge
from apps.accounts.models_social import SocialIdentity
from apps.accounts.oidc_browser_attempts import OidcAttemptRejected, start_attempt, _transition_binding
from apps.accounts.oidc_browser_resolution import resolve_browser_identity
from apps.accounts.services_social_identity import SocialResolutionError, resolve_social_identity
from apps.accounts.services_social_login import issue_social_session
from apps.accounts.social_nonces import SocialNonceRejected, create_social_nonce
from apps.makerspaces.import_adoption import adopt_pending_memberships_for_user, _validate_address_proof
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.walk_in_services import _new_user
from tests.account_split.p1_helpers import staff

pytestmark = pytest.mark.django_db
PASSWORD = "Safe account split password 947!"
EMAIL = "same@example.test"
PHONE = "+15550123456"


@pytest.fixture
def principals():
    space = Makerspace.objects.create(name="Identity", slug="identity")
    employee, membership = staff(space, "identity.staff", email="identity.staff@example.test", password=PASSWORD)
    platform = User.objects.create_superuser("identity.platform", email="identity.platform@example.test", password=PASSWORD)
    return space, employee, platform


def claims(subject="subject", email=EMAIL):
    return {"sub": subject, "email": email, "email_verified": True}


@pytest.mark.skip(reason="U-A1 (decision 308 family): staff and members share ONE account; there is no separate staff "
                  "namespace sharing an email with a member, so 'signup ignores the staff row' has no premise")
def test_signup_and_duplicate_only_use_member_identity(principals, monkeypatch):
    _, employee, platform = principals
    monkeypatch.setattr(services_registration, "send_email_verification_otp", lambda *_: 0)
    member = services_registration.register_member(
        email=EMAIL, password=PASSWORD, display_name="Member", phone=""
    )
    duplicate = services_registration.register_member(
        email=EMAIL.upper(), password=PASSWORD, display_name="Duplicate", phone=""
    )
    assert member.account_kind == "member" and member.pk == duplicate.pk
    assert member.pk not in {employee.pk, platform.pk}
    assert services_registration.issue_challenge(employee) is None
    assert services_registration.issue_challenge(platform) is None
    assert not employee.email_challenges.exists() and not platform.email_challenges.exists()


@pytest.mark.skip(reason="U-A1: one account per person; a provider email matching a staff-track holder asks to link "
                  "to that person (account_link_required): there is no separate staff namespace to ignore")
@pytest.mark.parametrize("provider", ["google", "apple", "github", "oidc:campus"])
def test_provider_email_matching_ignores_staff_and_platform(principals, provider):
    _, employee, platform = principals
    member, outcome = resolve_social_identity(provider=provider, claims=claims(), surface="member")
    assert outcome == "created" and member.account_kind == "member"
    assert member.pk not in {employee.pk, platform.pk}


@pytest.mark.parametrize("provider", ["google", "apple", "github", "oidc:campus"])
@pytest.mark.parametrize("target", [2])  # platform only: a staff-track holder is a person (U-A1)
def test_preexisting_nonmember_provider_identity_is_refused(principals, provider, target):
    account = principals[target]
    SocialIdentity.objects.create(user=account, provider=provider, provider_sub="subject")
    with pytest.raises(SocialResolutionError) as exc:
        resolve_social_identity(provider=provider, claims=claims(), surface="member")
    assert exc.value.code == "social_invalid"
    with pytest.raises(SocialResolutionError) as exc:
        resolve_social_identity(provider=provider, claims=claims("other"),
                                surface="member", explicit_user=account)
    assert exc.value.code == "social_invalid"


@pytest.mark.parametrize("target", [2])  # platform only: a staff-track holder is a person (U-A1)
def test_social_session_and_oidc_resolution_refuse_nonmembers(principals, target):
    account = principals[target]
    with pytest.raises(SocialResolutionError):
        issue_social_session(account, surface="member", delivery="web", nonce_row=None)
    attempt = SimpleNamespace(surface="staff", intended_user_id=None)
    with pytest.raises(SocialResolutionError):
        resolve_browser_identity(attempt, claims(), allow_user_creation=True)


def test_staff_social_attempts_refused_before_provider_or_origin_work():
    request = APIRequestFactory().post("/")
    with pytest.raises(SocialNonceRejected):
        create_social_nonce(request, provider="google", surface="staff",
                            delivery="web", client_platform="web")
    with pytest.raises(OidcAttemptRejected):
        start_attempt(request, None, None, redirect_uri="https://example.test/callback",
                      surface="staff")
    with pytest.raises(SocialResolutionError) as exc:
        resolve_social_identity(provider="google", claims=claims(), surface="staff")
    assert exc.value.code == "social_invalid"


@pytest.mark.parametrize("target", [2])  # platform only: a staff-track holder is a person (U-A1)
def test_phone_login_and_linking_refuse_nonmembers(principals, target, monkeypatch):
    account = principals[target]
    User.objects.filter(pk=account.pk).update(phone_e164=PHONE, phone_verified_at=timezone.now())
    account.refresh_from_db()
    monkeypatch.setattr(services_phone_login, "sms_configured", lambda: True)
    monkeypatch.setattr(services_phone, "sms_configured", lambda: True)
    assert services_phone_login.start_login(PHONE) is None
    with pytest.raises(ValidationError):
        services_phone.start_link(account, PHONE)
    with pytest.raises(ValidationError):
        services_phone.confirm_link(account, PHONE, "123456")
    assert not PhoneVerificationChallenge.objects.filter(user=account).exists()
    PhoneVerificationChallenge.objects.create(
        user=account, purpose=PhoneChallengePurpose.LOGIN, phone_e164=PHONE,
        code_digest=services_phone._digest("123456", PHONE),
        expires_at=timezone.now() + timedelta(minutes=5), last_sent_at=timezone.now(),
    )
    with pytest.raises(ValidationError) as exc:
        services_phone_login.confirm_login(PHONE, "123456")
    assert exc.value.detail["detail"] == services_phone.GENERIC_CONFIRM_ERROR


@pytest.mark.skip(reason="U-A1: a verified phone belongs to exactly ONE account (uniq_member_phone_e164); a staff-track "
                  "holder and a member can no longer share one contact, so there is nothing to disambiguate")
def test_phone_login_resolves_member_with_shared_staff_contact(principals, monkeypatch):
    _, employee, _ = principals
    member = User.objects.create_user("phone.member", email=EMAIL, password=PASSWORD)
    User.objects.filter(pk__in=[employee.pk, member.pk]).update(
        phone_e164=PHONE, phone_verified_at=timezone.now()
    )
    monkeypatch.setattr(services_phone_login, "sms_configured", lambda: True)
    monkeypatch.setattr(services_phone, "send_sms", lambda **_: True)
    monkeypatch.setattr(services_phone, "_generate_otp", lambda: "123456")
    challenge = services_phone_login.start_login(PHONE)
    assert challenge.user_id == member.pk
    assert services_phone_login.confirm_login(PHONE, "123456").pk == member.pk


@pytest.mark.skip(reason="U-A1: a walk-in whose email belongs to a staff-track holder is the same person; the "
                  "add-from-members-list refusal replaces 'ignore the staff row'")
def test_walk_in_and_oidc_transition_email_lookup_ignore_staff(principals):
    space, _, _ = principals
    walk_in = _new_user("Walk In", EMAIL, "")
    assert walk_in.account_kind == "member"
    membership = MakerspaceMembership.objects.create(
        user=walk_in, makerspace=space, assigned_role=space.roles.get(slug="member")
    )
    request = APIRequestFactory().post("/")
    assert _transition_binding(request, email=EMAIL, makerspace_slug=space.slug) == (
        walk_in.pk, membership.pk
    )


@pytest.mark.parametrize("target", [2])  # platform only: a staff-track holder is a person (U-A1)
def test_import_adoption_and_claim_issuance_refuse_nonmembers(principals, target):
    account = principals[target]
    User.objects.filter(pk=account.pk).update(email_verified_at=timezone.now())
    account.refresh_from_db()
    assert adopt_pending_memberships_for_user(account) == []
    with pytest.raises(ValidationError):
        _validate_address_proof(account, SimpleNamespace(email=EMAIL))
    with pytest.raises(TokenError):
        mint_claim_tokens(SimpleNamespace(membership=SimpleNamespace(user=account)))


@pytest.mark.parametrize("kind", [None, "staff", "platform"])
def test_claim_session_requires_member_kind_claim(kind):
    with pytest.raises(ClaimSessionInvalid):
        validated_claim_session({"kind": kind})


def test_signup_unique_race_recovery_is_member_scoped(principals, monkeypatch):
    from django.db.models.query import QuerySet

    member = User.objects.create_user("race.member", email=EMAIL, password=PASSWORD)
    original = QuerySet.first
    hidden = False

    def miss_once(rows):
        nonlocal hidden
        # Simulate the initial read preceding a competing member insert. The real
        # unique index rejects our insert; recovery must ignore the staff row.
        if rows.model is User and not hidden:
            hidden = True
            return None
        return original(rows)

    monkeypatch.setattr(QuerySet, "first", miss_once)
    monkeypatch.setattr(services_registration, "send_email_verification_otp", lambda *_: 0)
    recovered = services_registration.register_member("Race", EMAIL, "", PASSWORD)
    assert recovered.pk == member.pk and recovered.account_kind == "member"


@pytest.mark.parametrize("winner_is_target", [True, False])
def test_provider_identity_unique_race_recovers_after_savepoint(monkeypatch, winner_is_target):
    from django.db.models.query import QuerySet

    target = User.objects.create_user("social.target", email=EMAIL, password=PASSWORD,
                                      email_verified_at=timezone.now())
    winner = target if winner_is_target else User.objects.create_user("social.winner")
    identity = SocialIdentity.objects.create(user=winner, provider="google", provider_sub="race")
    original = QuerySet.first
    hidden = False

    def miss_once(rows):
        nonlocal hidden
        if rows.model is SocialIdentity and not hidden:
            hidden = True
            return None
        return original(rows)

    monkeypatch.setattr(QuerySet, "first", miss_once)
    if winner_is_target:
        resolved, _ = resolve_social_identity(provider="google", claims=claims("race"), surface="member")
        assert resolved.pk == target.pk
    else:
        with pytest.raises(SocialResolutionError) as exc:
            resolve_social_identity(provider="google", claims=claims("race"), surface="member")
        assert exc.value.code == "identity_conflict"
    assert SocialIdentity.objects.get(pk=identity.pk).user_id == winner.pk


def test_provider_member_creation_unique_race_is_typed_and_rolls_back(monkeypatch):
    from django.db.models.query import QuerySet

    member = User.objects.create_user("social.email.winner", email=EMAIL, password=PASSWORD,
                                      email_verified_at=timezone.now())
    original = QuerySet.first
    hidden = False

    def miss_once(rows):
        nonlocal hidden
        if rows.model is User and not hidden:
            hidden = True
            return None
        return original(rows)

    monkeypatch.setattr(QuerySet, "first", miss_once)
    with pytest.raises(SocialResolutionError) as exc:
        resolve_social_identity(provider="google", claims=claims("new-race"), surface="member")
    assert exc.value.code == "identity_conflict"
    assert not SocialIdentity.objects.filter(provider_sub="new-race").exists()
    assert User.objects.get(email=EMAIL).pk == member.pk


def test_explicit_link_unique_race_returns_typed_conflict(monkeypatch):
    from django.db.models.query import QuerySet

    target = User.objects.create_user("explicit.target")
    winner = User.objects.create_user("explicit.winner")
    SocialIdentity.objects.create(user=winner, provider="google", provider_sub="explicit-race")
    original = QuerySet.first
    hidden = False

    def miss_once(rows):
        nonlocal hidden
        if rows.model is SocialIdentity and not hidden:
            hidden = True
            return None
        return original(rows)

    monkeypatch.setattr(QuerySet, "first", miss_once)
    with pytest.raises(SocialResolutionError) as exc:
        resolve_social_identity(provider="google", claims=claims("explicit-race"),
                                surface="member", explicit_user=target)
    assert exc.value.code == "identity_conflict"
    assert not SocialIdentity.objects.filter(user=target).exists()
