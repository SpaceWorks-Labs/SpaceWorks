"""Invitation routes: pending rows, exact effects, and per-route standing contracts."""
import pytest
from django.urls import reverse

from apps.accounts.models import EmailVerificationChallenge, StaffInvitation, User
from apps.accounts.services_staff_invitations import issue
from tests.accounts.account_factories import make_staff
from tests.modules.switch_matrix_object_helpers import client_for, object_world
from tests.modules.test_switch_matrix_objects_rest_additional_support import PASSWORD, reauthenticate
from tests.operations.route_support_cx11b_g4 import cleanup_cycle, contains, cycle, outsider, send

pytestmark = [pytest.mark.django_db, pytest.mark.area_auth]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,key", [("admin-staff-invitations", "staff.invitations"),
    ("admin-staff-invitation-revoke", "staff.invitations"), ("admin-staff-invitation-revoke", "email"),
    ("admin-staff-invitation-resend", "staff.invitations"), ("admin-staff-invitation-resend", "email")])
def test_staff_invitation_management_effect_and_switch(native, name, key, monkeypatch):
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    actor.set_password(PASSWORD)
    actor.save(update_fields=["password"])
    if native:
        reauthenticate(client, actor)
    foreign = outsider(native)
    if native:
        stranger = User.objects.get(username="g4-foreign-manager")
        stranger.set_password(PASSWORD)
        stranger.save(update_fields=["password"])
        reauthenticate(foreign, stranger)
    row, _ = issue(actor, space.pk, email="g4-invited@example.test", roles=["event_manager"])
    untouched = None
    if name.endswith("revoke"):
        untouched, _ = issue(actor, space.pk, email="g4-kept@example.test", roles=["event_manager"])
    # Only the outbound delivery port is substituted. The invitation service and its token rotation stay real.
    deliveries = []
    monkeypatch.setattr("apps.accounts.views_staff_invitations.deliver",
                        lambda invite, raw: deliveries.append((invite.pk, raw)) or {"delivery_status": "sent"})
    kwargs = {"makerspace_id": space.pk}
    method = "GET" if name == "admin-staff-invitations" else "POST"
    if method == "POST":
        kwargs["invitation_id"] = row.pk
    url = reverse(name, kwargs=kwargs)

    def check(response):
        row.refresh_from_db()
        if method == "GET":
            contains(response, row.pk)
            assert response.data["results"][0]["roles"] == ["event_manager"]
            assert row.revoked_at is None
        elif name.endswith("revoke"):
            assert response.data["id"] == row.pk
            assert row.revoked_at is not None
            assert StaffInvitation.objects.filter(makerspace=space).count() == 2
            untouched.refresh_from_db()
            assert untouched.revoked_at is None and untouched.accepted_at is None
            assert deliveries == []
        else:
            new = StaffInvitation.objects.get(pk=response.data["id"])
            assert row.revoked_at is not None
            assert (new.email, new.role_snapshot, new.revoked_at) == (row.email, ["event_manager"], None)
            assert new.token_digest != row.token_digest
            assert StaffInvitation.objects.filter(makerspace=space).count() == 2
            assert deliveries[-1][0] == new.pk
            assert response.data["delivery_status"] == "sent"

    # 537: revoke is cleanup, with unchanged staff authority, MFA and step-up.
    if name.endswith("revoke"):
        peer = make_staff(space, username="g4-invitation-non-manager", role_slug="inventory_manager",
                          password=PASSWORD, access_status="active")
        peer_client = client_for(peer, space, native)
        if native:
            reauthenticate(peer_client, peer)
        cleanup_cycle(space, key, lambda: send(client, method, url), check, on=(200, None),
            foreign=[(lambda: send(foreign, method, url), (403, "permission_denied") if native else (404, "not_found")),
                     (lambda: send(peer_client, method, url), (403, "permission_denied"))],
            audit=("staff_invitation.revoked",))
        return
    actions = () if method == "GET" else ("staff_invitation.revoked",) if name.endswith("revoke") else ("staff_invitation.sent",)
    cycle(space, key, lambda: send(client, method, url), check,
          off=(404, "feature_disabled" if "." in key else "module_disabled"), audit=actions,
          foreign=lambda: send(foreign, method, url), foreign_native=native)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["staff.invitations", "email"])
@pytest.mark.parametrize("phase", ["challenge", "grant"])
def test_invitation_acceptance_challenge_requires_its_own_email_before_gate(native, key, phase):
    from apps.accounts.login_codes import digest
    from apps.accounts.staff_invitation_acceptance import PURPOSE
    from unittest.mock import patch
    space, _, _ = object_world(native)
    creator = User.objects.get(username="sx-real-object-manager")
    # Isolate the role grant from optional automatic card production. MFA remains enrolled.
    space.enabled_features = [key for key in space.enabled_features if key != "membership.staff_cards_auto_issue"]
    space.save(update_fields=["enabled_features"])
    from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
    other = live_space("g4-invite-person-home", MODULE_KEYS)
    invitee = make_staff(other, username="g4-invitee", email="g4-invitee@example.test", access_status="active")
    client = client_for(invitee, other, native)
    row, raw = issue(creator, space.pk, email=invitee.email, roles=["event_manager"])
    foreign = outsider(native)
    if native:
        client._credentials.pop("HTTP_X_MAKERSPACE_ID", None)
        foreign._credentials.pop("HTTP_X_MAKERSPACE_ID", None)
    url = reverse("auth-staff-invitation-accept")
    body = {"token": raw, "makerspace_slug": space.slug}
    if phase == "grant":
        from datetime import timedelta
        from django.utils import timezone
        now = timezone.now()
        EmailVerificationChallenge.objects.create(user=invitee, email=f"staff-invite:{row.pk}",
            code_digest=digest("123456", PURPOSE, f"{row.pk}:{invitee.pk}"),
            expires_at=now + timedelta(minutes=10), last_sent_at=now)
        body["code"] = "123456"

    def check(response):
        assert response.data["challenge_required"] is (phase == "challenge")
        proof = EmailVerificationChallenge.objects.get(user=invitee, email=f"staff-invite:{row.pk}")
        assert proof.code_digest == digest("123456", PURPOSE, f"{row.pk}:{invitee.pk}")
        assert proof.failed_attempts == 0
        row.refresh_from_db()
        if phase == "challenge":
            assert (proof.consumed_at, row.accepted_at) == (None, None)
        else:
            from apps.makerspaces.models import MakerspaceMembership
            grant = MakerspaceMembership.staff_tracks.get(makerspace=space, user=invitee)
            assert (grant.assigned_role.slug, grant.status, row.accepted_by_id) == ("event_manager", "active", invitee.pk)
            assert proof.consumed_at is not None and row.accepted_at is not None
            assert response.data["makerspace"]["id"] == space.pk

    # Email ownership is the decided standing contract here, not 481's staff-space 404.
    with patch("apps.accounts.login_codes.new_code", return_value="123456"):
        cycle(space, key, lambda: send(client, "POST", url, body), check,
              off=(404, "feature_disabled" if "." in key else "module_disabled"),
              foreign=lambda: send(foreign, "POST", url, body), foreign_pair=(403, "invite_email_mismatch"),
              audit=("staff_role.granted", "staff_invitation.accepted") if phase == "grant" else ())
