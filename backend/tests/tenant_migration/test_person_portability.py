"""One account per person in the PORTABLE tenant import (U-D; local only).

Staff-track rows travel with their person under the ordinary decision: a created person
keeps them as they were, a linked person gets them REVOKED unless the superadmin grants
them, and merged shells travel PII-free with their alias re-established when the survivor
travelled too.
"""

import json

import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.hardware_requests.models import HardwareRequest
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MembershipAdditionalRole
from apps.tenant_migration.materialization import materialize_tenant
from tests.accounts.account_factories import grant_staff_role, make_membership
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.materialization_helpers import portable_import_case

pytestmark = pytest.mark.django_db(transaction=True)


def _staff_person(space, username):
    person = make_user(username)
    make_membership(person, space)
    row = grant_staff_role(person, space, role_slug="inventory_manager")
    MembershipAdditionalRole.objects.create(membership=row, role=space.roles.get(slug="event_manager"))
    return person


def _target_rows(result, user):
    target = Makerspace.objects.get(pk=result.target_makerspace_id)
    return target, {(row.track, row.status, row.assigned_role.slug)
                    for row in MakerspaceMembership.all_tracks.filter(makerspace=target, user=user)}


def _run(case, slug):
    return materialize_tenant(case.root, case.job, case.carried, target_identity={"slug": slug})


def test_a_created_person_keeps_their_staff_roles_active():
    with enabled_encryption():
        owner = make_user("pp-create-owner")
        source = make_space("pp-create")
        state = {}

        def prepare(space, _user, _request):
            state["person"] = _staff_person(space, "pp-create-staff")

        with portable_import_case(source, owner, prepare_source=prepare) as case:
            case.decide_walk_in(owner)
            case.decide_walk_in(state["person"])
            result = _run(case, "pp-create-target")
        target = Makerspace.objects.get(pk=result.target_makerspace_id)
        created = MakerspaceMembership.staff_tracks.get(makerspace=target).user
        assert created.pk != state["person"].pk or created.username != state["person"].username
        target, rows = _target_rows(result, created)
        assert rows == {("community", "active", "member"), ("staff", "active", "inventory_manager")}
        staff_row = MakerspaceMembership.staff_tracks.get(makerspace=target, user=created)
        assert set(MembershipAdditionalRole.objects.filter(membership=staff_row)
                   .values_list("role__slug", flat=True)) == {"event_manager"}


@pytest.mark.parametrize("granted", [False, True])
def test_a_linked_person_gets_staff_roles_revoked_unless_granted(granted):
    with enabled_encryption():
        owner = make_user(f"pp-link-owner-{granted}")
        source = make_space(f"pp-link-{granted}")
        existing = make_user(f"pp-link-existing-{granted}")
        state = {}

        def prepare(space, _user, _request):
            state["person"] = _staff_person(space, f"pp-link-staff-{granted}")

        with portable_import_case(source, owner, prepare_source=prepare) as case:
            case.decide_walk_in(owner)
            decision = case.decide_link(state["person"], existing)
            decision.grant_staff_roles = granted
            decision.save(update_fields=["grant_staff_roles"])
            result = _run(case, f"pp-link-target-{granted}")
        target, rows = _target_rows(result, existing)
        status = "active" if granted else "revoked"
        assert rows == {("community", "active", "member"), ("staff", status, "inventory_manager")}
        audited = AuditLog.objects.filter(action="tenant_migration.staff_roles_granted", makerspace=target,
                                          target_id=str(existing.pk)).exists()
        assert audited is granted


def _merge(shell, survivor):
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.account_unification_run_id', 'pp-merge', true)")
        MakerspaceMembership.all_tracks.filter(user=shell).update(status="revoked", revoked_at=timezone.now())
        User._base_manager.filter(pk=shell.pk).update(
            account_kind="staff", merged_into=survivor, merged_at=timezone.now(), is_active=False)


@pytest.mark.parametrize("survivor_travels", [True, False])
def test_merged_shells_travel_pii_free_with_their_alias(survivor_travels):
    with enabled_encryption():
        owner = make_user(f"pp-shell-owner-{survivor_travels}")
        source = make_space(f"pp-shell-{survivor_travels}")
        state = {}

        def prepare(space, _user, _request):
            shell, survivor = make_user(f"pp-shell-{survivor_travels}"), make_user(f"pp-survivor-{survivor_travels}")
            HardwareRequest.objects.create(makerspace=space, requester=shell, requester_username=shell.username,
                                           requester_name="Shell history")
            if survivor_travels:
                make_membership(survivor, space)
            _merge(shell, survivor)
            state.update(shell=shell, survivor=survivor)

        with portable_import_case(source, owner, prepare_source=prepare) as case:
            users = (case.root / "global" / "users.csv").read_text(encoding="utf-8")
            assert f"pp-shell-{survivor_travels}@" not in users and f"merged-account-{state['shell'].pk}" in users
            aliases = json.loads((case.root / "global" / "user-aliases.json").read_text(encoding="utf-8"))
            assert bool(aliases["aliases"]) is survivor_travels
            case.decide_walk_in(owner)
            case.decide_walk_in(state["shell"])
            if survivor_travels:
                case.decide_walk_in(state["survivor"])
            result = _run(case, f"pp-shell-target-{survivor_travels}")
        target = Makerspace.objects.get(pk=result.target_makerspace_id)
        shell = HardwareRequest.objects.get(makerspace=target, requester__account_kind="staff").requester
        assert shell.account_kind == "staff" and not shell.is_active and shell.email == ""
        if survivor_travels:
            assert shell.merged_into is not None and shell.retired_at is None
            assert MakerspaceMembership.objects.filter(makerspace=target, user=shell.merged_into).exists()
        else:
            assert shell.merged_into is None and shell.retired_at is not None
