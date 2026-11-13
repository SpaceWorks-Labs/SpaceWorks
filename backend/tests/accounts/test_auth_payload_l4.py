from tests.fixed_roles.helpers import roles_for_actions
import pytest
from django.db import connection, IntegrityError, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.serializers import user_payload
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from tests.return_helpers import make_space, make_user


pytestmark = pytest.mark.django_db

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


def seeded(makerspace, legacy_role):
    return MakerspaceRole.objects.get(makerspace=makerspace, legacy_role=legacy_role)


def active_staff(username, makerspace):
    return make_user(
        username,
        role=User.Role.SPACE_MANAGER,
        password="pw-strong-123",
        access_status=User.AccessStatus.ACTIVE,
    )


def membership_payload(user, makerspace):
    return next(
        item for item in user_payload(user)["makerspaces"] if item["id"] == makerspace.id
    )


def test_seeded_default_role_includes_metadata_and_effective_actions():
    makerspace = make_space("auth-payload-default")
    user = active_staff("auth-payload-default-user", makerspace)
    membership = MakerspaceMembership.staff_tracks.create(track="staff",
        user=user,
        makerspace=makerspace,
        role=MakerspaceMembership.Role.INVENTORY_MANAGER,
        assigned_role=seeded(makerspace, MakerspaceMembership.Role.INVENTORY_MANAGER),
    )

    payload = membership_payload(user, makerspace)

    assert payload == {
        "id": makerspace.id,
        "slug": makerspace.slug,
        "role": membership.role,
        "role_id": membership.assigned_role_id,
        "role_ids": [membership.assigned_role_id],
        "role_slugs": [membership.assigned_role.slug],
        "role_names": [membership.assigned_role.name],
        "role_name": membership.assigned_role.name,
        "role_slug": membership.assigned_role.slug,
        "actions": sorted(rbac.effective_actions(user, makerspace.id)),
        "can_configure_machine_types": False,
        # An Inventory Manager holds no MANAGE_MACHINES, so machine scoping has nothing to
        # say about it and every console surface stays.
        "is_machine_only": False,
        "can_refer": True,
        "can_verify": False,
        "verified_at": None,
        "referrals_enabled": False,
        "source": "membership",
        "tracks": ["staff"],
    }
    assert payload["actions"] == sorted(membership.assigned_role.granted_actions)


def test_builtin_role_actions_follow_assigned_role_despite_stale_legacy_mirror():
    makerspace = make_space("auth-payload-custom")
    user = active_staff("auth-payload-custom-user", makerspace)
    role = roles_for_actions(makerspace, [rbac.Action.VIEW_INVENTORY, rbac.Action.ISSUE_REQUEST])[0]
    MakerspaceMembership.staff_tracks.create(track="staff",
        user=user,
        makerspace=makerspace,
        role=MakerspaceMembership.Role.CUSTOM,
        assigned_role=role,
    )

    payload = membership_payload(user, makerspace)

    assert payload["role"] == MakerspaceMembership.Role.CUSTOM
    assert payload["role_id"] == role.id
    assert payload["role_name"] == role.name
    assert payload["role_slug"] == role.slug
    assert payload["actions"] == sorted(role.granted_actions)


def test_null_assigned_role_fails_closed_and_is_refused_at_commit():
    makerspace = make_space("auth-payload-fallback")
    user = active_staff("auth-payload-fallback-user", makerspace)
    membership = MakerspaceMembership.staff_tracks.create(track="staff",
        user=user, makerspace=makerspace, role="space_manager",
        assigned_role=seeded(makerspace, "space_manager"),
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.staff_tracks.filter(pk=membership.pk).update(assigned_role=None)
        # Release 2: an invalid staff row is not a staff role at all; the space is absent.
        assert all(item["id"] != makerspace.id for item in user_payload(user)["makerspaces"])
        assert user_payload(user)["staff_roles"] == []
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_login_and_me_return_identical_membership_shapes():
    makerspace = make_space("auth-payload-parity")
    user = active_staff("auth-payload-parity-user", makerspace)
    MakerspaceMembership.staff_tracks.create(track="staff",
        user=user,
        makerspace=makerspace,
        role=MakerspaceMembership.Role.SPACE_MANAGER,
        assigned_role=seeded(makerspace, MakerspaceMembership.Role.SPACE_MANAGER),
    )

    login = APIClient().post(
        LOGIN,
        {"username": user.username, "password": "pw-strong-123"},
        format="json",
    )
    client = APIClient()
    client.force_authenticate(user=user)
    me = client.get(ME)

    assert login.status_code == 200
    assert me.status_code == 200
    assert login.data["user"]["makerspaces"] == me.data["makerspaces"]


def test_archived_makerspace_membership_is_excluded():
    visible = make_space("auth-payload-visible")
    archived = make_space("auth-payload-archived")
    archived.archived_at = timezone.now()
    archived.save(update_fields=["archived_at"])
    user = make_user("auth-payload-archived-user")
    for makerspace in (visible, archived):
        MakerspaceMembership.objects.create(
            user=user,
            makerspace=makerspace,
            role=MakerspaceMembership.Role.CUSTOM,
            assigned_role=makerspace.roles.get(slug="member"),
        )

    assert {row["id"] for row in user_payload(user)["makerspaces"]} == {visible.id}


def test_platform_account_cannot_gain_membership():
    hidden = make_space("auth-payload-hidden")
    superadmin = make_user(
        "auth-payload-hidden-root",
        role=User.Role.SUPERADMIN,
        is_superuser=True,
        access_status=User.AccessStatus.ACTIVE,
    )

    assert hidden.id not in {row["id"] for row in user_payload(superadmin)["makerspaces"]}

    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.objects.create(
            user=superadmin, makerspace=hidden, role="custom",
            assigned_role=hidden.roles.get(slug="inventory_manager"),
        )
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_branded_origin_scopes_memberships_and_actions_exclude_superadmin_only_values():
    makerspace_a = make_space("auth-payload-origin-a")
    makerspace_a.frontend_domain = "auth-payload-a.example"
    makerspace_a.frontend_domain_status = Makerspace.DomainStatus.VERIFIED
    makerspace_a.save(update_fields=["frontend_domain", "frontend_domain_status"])
    makerspace_b = make_space("auth-payload-origin-b")
    user = make_user("auth-payload-origin-user")
    for makerspace in (makerspace_a, makerspace_b):
        MakerspaceMembership.objects.create(
            user=user,
            makerspace=makerspace,
            role=MakerspaceMembership.Role.CUSTOM,
            assigned_role=makerspace.roles.get(slug="member"),
        )

    request = APIRequestFactory().get(ME, HTTP_ORIGIN="https://auth-payload-a.example")
    payload = user_payload(user, request=request)

    assert [row["id"] for row in payload["makerspaces"]] == [makerspace_a.id]
    for membership in payload["makerspaces"]:
        assert rbac.Action.TRANSFER_STOCK not in membership["actions"]
        assert rbac.Action.MANAGE_STAFF not in membership["actions"]


def _payload_query_count(user):
    with CaptureQueriesContext(connection) as ctx:
        user_payload(user)
    return len(ctx)


def test_auth_payload_query_count_does_not_scale_with_memberships():
    # Regression guard: actions are derived from the already select_related-loaded rows, so
    # /auth/me + /auth/login stay O(1) queries instead of the old 1+2N (one effective_actions
    # call per membership).
    one_user = make_user("auth-payload-q1")
    one_space = make_space("auth-payload-q1-space")
    MakerspaceMembership.objects.create(
        user=one_user,
        makerspace=one_space,
        role=MakerspaceMembership.Role.CUSTOM,
        assigned_role=one_space.roles.get(slug="member"),
    )
    many_user = make_user("auth-payload-q4")
    for i in range(4):
        space = make_space(f"auth-payload-q4-space-{i}")
        MakerspaceMembership.objects.create(
            user=many_user,
            makerspace=space,
            role=MakerspaceMembership.Role.CUSTOM,
            assigned_role=space.roles.get(slug="member"),
        )

    assert len(user_payload(many_user)["makerspaces"]) == 4
    # Same query count for 1 vs 4 memberships => no per-membership query.
    assert _payload_query_count(many_user) == _payload_query_count(one_user)
