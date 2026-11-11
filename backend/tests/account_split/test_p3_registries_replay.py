"""Boundary registries, OpenAPI, and deactivation's live offline-replay refusal."""
import pytest
from rest_framework.exceptions import APIException

from apps.accounts import staff_account_lifecycle as lifecycle
from apps.accounts.delegated_routes import route_class
from apps.accounts.claim_route_types import Refused
from apps.accounts.claim_routes import policy_for
from apps.apiclients.scope_registry import lookup
from apps.hardware_requests.replay_failures import ReplayFailure
from apps.makerspaces.origin_scope_routes import MAKERSPACE_KWARG_ROUTES
from tests.hardware_requests.replay_helpers import replay_env, identity
from .p3_helpers import context

pytestmark = pytest.mark.django_db(transaction=True)

ROUTES = ("admin-staff-accounts", "admin-staff-account-policy", "admin-staff-account-change",
          "admin-staff-account-deactivate", "admin-staff-account-reactivate",
          "admin-staff-account-set-password", "admin-staff-account-resend-invite")


@pytest.mark.parametrize("name", ROUTES)
def test_staff_account_routes_never_delegate_claim_or_api_client_authority(name):
    # U-B deleted these routes (staff roles on people replaced them); R2 tidy dropped their
    # registry rows. The names must stay unroutable, unclassified and unreachable.
    from django.urls import NoReverseMatch, reverse
    from apps.accounts.mfa_grace import STRICT_ROUTES
    from apps.accounts.surface_policy import _platform_route
    with pytest.raises(NoReverseMatch):
        reverse(name, args=[1])
    assert route_class(name) is None
    assert name not in MAKERSPACE_KWARG_ROUTES and name not in STRICT_ROUTES
    assert not _platform_route(name)
    for method in ("GET", "HEAD", "POST", "PATCH", "DELETE"):
        assert isinstance(policy_for(name, method), Refused)
        assert lookup(name, method) is None  # Includes legacy:v1 clients.


# R3: test_openapi_includes_all_contract_operations_and_typed_fields removed. It pinned the
# /staff-accounts/ operations that #63 (d55545d7) deleted; the staff-roles routes have their
# own contract tests (tests/admin_api/test_staff_roles_api.py).


def test_snapshot_fields_are_source_local_and_existing_user_edges_stay_classified():
    from apps.accounts.models import StaffInvitation
    from apps.data_export.classification_platform import OMITTED_MODELS
    from apps.tenant_migration.tenant_dump_catalog import FIELD_POLICIES
    from apps.tenant_migration.tenant_dump_types import AuthorityDisposition as D
    assert "accounts.StaffInvitation" in OMITTED_MODELS
    for field in ("account", "role_snapshot", "machine_scope_snapshot", "credential_generation"):
        assert FIELD_POLICIES["accounts.StaffInvitation", field].dispositions == (D.DROP,)


def test_deactivation_revokes_operator_lease_and_replay_never_resurrects(replay_env):
    from apps.accounts.models import User
    from tests.account_split.p1_helpers import staff
    env = replay_env
    root = User.objects.create_superuser("replay-p3-root", password="Root test password 72!")
    # Ensure two managers exist before deactivating the original station operator.
    staff(env.space, "replay-p3-manager", role="space_manager")
    principal = identity(env)
    principal.live("assign_box")
    # #63 (d55545d7): a whole account is now turned off by the superadmin's disable_account
    # (deactivate/reactivate went with staff accounts); the replay guarantee is unchanged.
    lifecycle.disable_account(root, env.user.pk)
    env.lease.refresh_from_db()
    assert env.lease.revoked_at
    with pytest.raises(ReplayFailure):
        principal.live("assign_box")
    lifecycle.enable_account(root, env.user.pk)
    with pytest.raises(ReplayFailure):
        principal.live("assign_box")


def test_inactive_actor_replay_refuses_even_with_an_unrevoked_lease(replay_env):
    from apps.accounts.models import User
    env = replay_env
    User.objects.filter(pk=env.user.pk).update(is_active=False)
    assert env.lease.revoked_at is None
    with pytest.raises(ReplayFailure) as refused:
        identity(env).live("assign_box")
    assert refused.value.code == "permission_revoked"
