"""The lifecycle policy supplies every editor lookup within its authorized tenant."""
import pytest

from apps.accounts.models import User
from apps.machines.models import MachineType
from apps.makerspaces.role_catalog import BUILTIN_ROLE_SLUGS
from tests.account_split.p3_helpers import context
from tests.accounts.account_factories import make_membership
from .helpers import bearer_client

pytestmark = pytest.mark.django_db(transaction=True)


def base(space):
    """Decisions 63/66 (U-B): staff are roles on people; `staff-accounts/` became `staff-roles/`."""
    return f"/api/v1/admin/makerspaces/{space.pk}/staff-roles/"


@pytest.fixture
def ctx(settings):
    return context(settings)


@pytest.mark.parametrize("actor", ["root", "manager"])
def test_policy_choices_match_assignable_types_and_create_machine_scope(ctx, actor):
    local = MachineType.objects.create(makerspace=ctx.space, slug="s4-local", name="Local laser")
    builtin = MachineType.objects.create(is_builtin=True, slug="s4-global", name="Global built-in")
    foreign = MachineType.objects.create(makerspace=ctx.other, slug="s4-foreign", name="Foreign laser")
    api = bearer_client(getattr(ctx, actor), recent=True)
    response = api.get(base(ctx.space))
    assert response.status_code == 200, response.data
    policy = response.data["policy"]
    choices = policy["machine_types"]
    ids = {row["id"] for row in choices}
    assert {local.pk, builtin.pk} <= ids and foreign.pk not in ids
    assert all(set(row) == {"id", "name"} for row in choices)
    seeded = set(ctx.space.roles.values_list("slug", flat=True))
    expected = {slug for slug in BUILTIN_ROLE_SLUGS if slug in seeded and slug != "member" and (slug != "space_manager" or actor == "root")}
    assert {row["slug"] for row in policy["grantable_roles"]} == expected
    assert "no-store" in response["Cache-Control"]
    scoped, refused = (User.objects.create_user(f"s4-{kind}-{actor}") for kind in ("scoped", "foreign"))
    for person in (scoped, refused):
        make_membership(person, ctx.space)
    created = api.post(base(ctx.space), {"user_id": scoped.pk, "roles": ["machine_manager"],
        "machine_type_ids": [local.pk, builtin.pk]}, format="json")
    assert created.status_code == 201, created.data
    assert set(created.data["staff_role"]["machine_type_ids"]) == {local.pk, builtin.pk}
    assert api.post(base(ctx.space), {"user_id": refused.pk, "roles": ["machine_manager"],
        "machine_type_ids": [foreign.pk]}, format="json").status_code == 400


def test_policy_keeps_recent_proof_and_tenant_boundaries(ctx):
    assert bearer_client(ctx.root).get(base(ctx.space) ).status_code == 403
    assert bearer_client(ctx.manager, recent=True).get(base(ctx.other) ).status_code in {403, 404}
    assert bearer_client(ctx.worker, recent=True).get(base(ctx.space) ).status_code in {403, 404}
    # The retired per-space switch no longer hides a space from the platform superadmin.
    assert bearer_client(ctx.root, recent=True).get(base(ctx.space) ).status_code == 200
    assert bearer_client(ctx.manager, recent=True).get(base(ctx.space) ).status_code == 200
