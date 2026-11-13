from tests.account_split.sweep_helpers import (
    create_test_user as _create_test_user,
)
import pytest
from django.contrib.auth import authenticate
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import audit_events, rbac
from apps.accounts.models import PasswordResetEnvelope, User
from apps.accounts.password_reset_crypto import new_dummy_digest
from apps.accounts.services_password_reset import normalize_email, request_password_reset
from apps.accounts.services_password_reset_drain import (
    claim_pending_envelopes,
    prepare_delivery,
)
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.handout_roles import make_handout_member


pytestmark = pytest.mark.django_db


def _edited_stub(username="edited-stub"):
    user = _create_test_user(
        username=username,
        is_tenant_dump_stub=True,
        is_active=False,
        access_status=User.AccessStatus.SUSPENDED,
    )
    # Simulate edits to mutable contact, password and legacy staff flags. Account kind stays immutable.
    user.email = f"{username}@example.test"
    user.set_password("Edited stub password 419!")
    user.is_active = True
    user.access_status = User.AccessStatus.ACTIVE
    user.is_staff = True
    user.role = User.Role.SPACE_MANAGER
    user.save()
    return user


def test_password_authentication_refuses_stub_after_security_fields_are_edited():
    user = _edited_stub("stub-password-login")

    assert authenticate(
        username=user.username, password="Edited stub password 419!"
    ) is None

    response = APIClient().post(
        reverse("auth-login"),
        {"username": user.username, "password": "Edited stub password 419!"},
        format="json",
    )

    assert response.status_code == 401
    assert "access" not in response.data


def test_password_reset_drain_refuses_stub_after_contact_and_status_are_edited():
    user = _edited_stub("stub-password-reset")
    # Account restore made issuance refuse stubs too (recovery_eligible), so a request
    # queues nothing...
    request_password_reset(user.email)
    assert not PasswordResetEnvelope.objects.filter(user=user).exists()
    # ...and the drain is the second wall: an envelope already queued for the account
    # (before it was stubbed and edited) must still be discarded at delivery.
    normalized = normalize_email(user.email)
    PasswordResetEnvelope.objects.create(
        user=user, context="member", credential_generation=user.credential_generation,
        email_normalized=normalized, email_fingerprint=audit_events.fingerprint(normalized),
        digest=new_dummy_digest(normalized), digest_is_live=False, generation=1,
        requested_at=timezone.now(),
    )
    claim = claim_pending_envelopes(owner="tenant-dump-stub-test")[0]

    outcome = prepare_delivery(claim)

    assert outcome == "discarded"
    envelope = PasswordResetEnvelope.objects.get(pk=claim.envelope_id)
    assert envelope.user_id == user.pk
    assert envelope.digest_is_live is False


def test_member_claim_path_refuses_stub_even_when_it_looks_like_a_walk_in():
    space = Makerspace.objects.create(name="Stub claim", slug="stub-claim")
    issuer = make_handout_member("stub-claim-issuer", space)
    target = User(
        username="stub-claim-target",
        is_tenant_dump_stub=True,
        is_walk_in=True,
        is_active=True,
        access_status=User.AccessStatus.ACTIVE,
    )
    target.set_unusable_password()
    target.save()
    membership = MakerspaceMembership.objects.create(
        makerspace=space,
        user=target,
        role=MakerspaceMembership.Role.CUSTOM,
    assigned_role=space.roles.get(slug="member"))
    client = APIClient()
    client.force_authenticate(issuer)

    response = client.post(
        f"/api/v1/admin/makerspaces/{space.pk}/member-claim-codes",
        {"membership_id": membership.pk},
        format="json",
    )

    assert response.status_code == 409


def test_rbac_refuses_stub_even_after_global_and_membership_grants_are_added():
    space = Makerspace.objects.create(name="Stub RBAC", slug="stub-rbac")
    user = _edited_stub("stub-rbac-user")
    MakerspaceMembership.objects.create(
        makerspace=space,
        user=user,
        assigned_role=space.roles.get(slug="member"),
        role="custom",
    )

    assert rbac.resolve_scope(user) == set()
    assert rbac.makerspaces_for_action(user, rbac.Action.MANAGE_MAKERSPACE) == set()
    assert rbac.effective_actions(user, space.pk) == set()
    assert rbac.can(user, rbac.Action.MANAGE_MAKERSPACE, space.pk) is False


def test_platform_provenance_stub_never_becomes_a_password_principal():
    user = User.objects.create_superuser(
        username="platform-provenance-stub", password="Edited platform stub 419!",
        is_tenant_dump_stub=True,
    )
    assert not user.makerspace_memberships.exists()
    assert authenticate(username=user.username, password="Edited platform stub 419!") is None
    response = APIClient().post(reverse("auth-login"), {
        "username": user.username, "password": "Edited platform stub 419!",
    }, format="json")
    assert response.status_code == 401
    assert "access" not in response.data
