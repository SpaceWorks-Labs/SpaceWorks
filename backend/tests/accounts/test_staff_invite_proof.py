"""U-B: staff invitations are redeemed signed in, with a fresh emailed code (local test)."""

import pytest
from cryptography.fernet import Fernet
from rest_framework.test import APIClient

from apps.accounts import services_staff_invitations as invitations, staff_invitation_acceptance as acceptance
from apps.accounts.models import EmailVerificationChallenge, StaffInvitation, User
from apps.accounts.models_mfa_grace import StaffMfaGrace
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.accounts.account_factories import make_staff

pytestmark = pytest.mark.django_db
PASSWORD = "Invite proof password 19!"
URL = "/api/v1/auth/staff-invitations/accept"


@pytest.fixture(autouse=True)
def keys(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()


@pytest.fixture
def space():
    row = Makerspace.objects.create(name="Invite A", slug="invite-a")
    row.enabled_modules = sorted({*(row.enabled_modules or []), "email"})
    row.save(update_fields=["enabled_modules"])
    return row


@pytest.fixture
def codes(monkeypatch):
    sent = []
    monkeypatch.setattr(acceptance, "_send_code", lambda address, code, name: sent.append((address, code)))
    return sent


def invite(space, email="invitee@example.com", roles=("event_manager",)):
    manager = make_staff(space, username=f"inv-manager-{space.slug}", password=PASSWORD)
    return invitations.issue(manager, space.pk, email=email, roles=list(roles))


def signed_in(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {SpaceWorksRefreshToken.for_user(user).access_token}")
    return api


def person(username, email):
    return User.objects.create_user(username=username, password=PASSWORD, email=email)


def test_requires_sign_in(space):
    _row, raw = invite(space)
    response = APIClient().post(URL, {"token": raw, "makerspace_slug": space.slug}, format="json")
    assert response.status_code == 401


def test_email_must_match_the_invitation(space, codes):
    _row, raw = invite(space)
    other = person("inv-other", "someone-else@example.com")
    response = signed_in(other).post(URL, {"token": raw, "makerspace_slug": space.slug}, format="json")
    assert response.status_code == 403 and response.data["code"] == "invite_email_mismatch"
    assert codes == []


def test_fresh_code_then_grant(space, codes, django_capture_on_commit_callbacks):
    row, raw = invite(space)
    invitee = person("inv-invitee", "Invitee@Example.com")
    api = signed_in(invitee)
    with django_capture_on_commit_callbacks(execute=True):
        first = api.post(URL, {"token": raw, "makerspace_slug": space.slug}, format="json")
    assert first.status_code == 200, first.data
    assert first.data["challenge_required"] is True
    assert not MakerspaceMembership.staff_tracks.filter(user=invitee).exists()
    (address, code), = codes
    assert address == "invitee@example.com"
    wrong = api.post(URL, {"token": raw, "makerspace_slug": space.slug, "code": "000000" if code != "000000" else "111111"},
                     format="json")
    assert wrong.status_code == 400 and wrong.data["code"] == "proof_failed"
    row.refresh_from_db()
    assert row.failed_attempts == 1
    with django_capture_on_commit_callbacks(execute=True):
        done = api.post(URL, {"token": raw, "makerspace_slug": space.slug, "code": code}, format="json")
    assert done.status_code == 200, done.data
    assert done.data["challenge_required"] is False and done.data["makerspace"]["slug"] == space.slug
    staff = MakerspaceMembership.staff_tracks.get(user=invitee, makerspace=space)
    assert staff.status == "active" and staff.assigned_role.slug == "event_manager"
    invitee.refresh_from_db()
    assert invitee.email_verified_at is None  # the code proved this acceptance only
    row.refresh_from_db()
    assert row.accepted_by_id == invitee.pk and row.account_id is None
    assert StaffMfaGrace.objects.get(user=invitee).source == "invite"
    assert AuditLog.objects.filter(action="staff_invitation.accepted").exists()
    reused = api.post(URL, {"token": raw, "makerspace_slug": space.slug, "code": code}, format="json")
    assert reused.status_code == 400


@pytest.mark.parametrize(("field", "key", "kind"), [
    ("enabled_features", "staff.invitations", "feature"),
    ("enabled_modules", "email", "module"),
])
def test_pending_invitation_obeys_live_switches(space, codes, django_capture_on_commit_callbacks, field, key, kind):
    row, raw = invite(space)
    invitee = person("inv-invitee", "invitee@example.com")
    api = signed_in(invitee)
    payload = {"token": raw, "makerspace_slug": space.slug}
    with django_capture_on_commit_callbacks(execute=True):
        assert api.post(URL, payload, format="json").status_code == 200
    (_address, code), = codes
    original = getattr(space, field)
    setattr(space, field, [value for value in original if value != key])
    space.save(update_fields=[field])

    for request_payload in (payload, {**payload, "code": code}):
        with django_capture_on_commit_callbacks(execute=True):
            refused = api.post(URL, request_payload, format="json")
        assert refused.status_code == 404, refused.data
        assert refused.data["code"] == f"{kind}_disabled"
        assert refused.data[kind] == key
    assert len(codes) == 1
    assert EmailVerificationChallenge.objects.filter(user=invitee, consumed_at__isnull=True).count() == 1
    assert not MakerspaceMembership.staff_tracks.filter(user=invitee).exists()
    row.refresh_from_db()
    assert row.accepted_at is None and row.failed_attempts == 0

    invalid = api.post(URL, {**payload, "token": "invalid-invitation-token"}, format="json")
    assert invalid.status_code == 400
    other = person("inv-other", "other@example.com")
    mismatch = signed_in(other).post(URL, payload, format="json")
    assert mismatch.status_code == 403 and mismatch.data["code"] == "invite_email_mismatch"

    setattr(space, field, original)
    space.save(update_fields=[field])
    assert api.post(URL, {**payload, "code": code}, format="json").status_code == 200


def test_invitation_challenge_obeys_the_resolved_source_gate(space, codes, monkeypatch,
                                                          django_capture_on_commit_callbacks):
    from apps.tenant_migration import gate_runtime
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed

    _row, raw = invite(space)
    invitee = person("inv-frozen", "invitee@example.com")
    original = gate_runtime.assert_write_allowed

    def refuse_target(makerspace_id):
        if makerspace_id == space.pk:
            raise SourceMigrationGateClosed("Tenant writes are frozen.")
        return original(makerspace_id)

    monkeypatch.setattr(gate_runtime, "assert_write_allowed", refuse_target)
    with django_capture_on_commit_callbacks(execute=True):
        response = signed_in(invitee).post(URL, {"token": raw, "makerspace_slug": space.slug}, format="json")
    assert response.status_code == 423 and response.data["code"] == "tenant_gated"
    assert codes == []
    assert not EmailVerificationChallenge.objects.filter(user=invitee).exists()
    assert not MakerspaceMembership.staff_tracks.filter(user=invitee).exists()


def test_demoted_inviter_link_stops_working(space, codes, django_capture_on_commit_callbacks):
    row, raw = invite(space)
    MakerspaceMembership.staff_tracks.filter(user_id=row.created_by_id).update(status="revoked")
    invitee = person("inv-late", "invitee@example.com")
    api = signed_in(invitee)
    with django_capture_on_commit_callbacks(execute=True):
        api.post(URL, {"token": raw, "makerspace_slug": space.slug}, format="json")
    (_address, code), = codes
    response = api.post(URL, {"token": raw, "makerspace_slug": space.slug, "code": code}, format="json")
    assert response.status_code == 403
    assert not MakerspaceMembership.staff_tracks.filter(user=invitee).exists()


def test_platform_account_cannot_redeem(space):
    _row, raw = invite(space, email="root@example.com")
    root = User.objects.create_superuser("inv-root", password=PASSWORD, email="root@example.com")
    response = signed_in(root).post(URL, {"token": raw, "makerspace_slug": space.slug}, format="json")
    assert response.status_code in {401, 403}


def test_revoked_and_resent_links(space):
    row, raw = invite(space)
    manager = User.objects.get(pk=row.created_by_id)
    new, new_raw = invitations.resend(manager, space.pk, row.pk)
    row.refresh_from_db()
    assert row.revoked_at is not None and new.email == "invitee@example.com" and new_raw != raw
    invitations.revoke(manager, space.pk, new.pk)
    assert StaffInvitation.objects.filter(revoked_at__isnull=True).count() == 0


def test_delivery_returns_no_link(space, monkeypatch):
    from apps.accounts import staff_invitation_delivery as delivery
    row, raw = invite(space)
    result = delivery.deliver(row, raw)
    assert set(result) == {"delivery_status"}
