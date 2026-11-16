"""Export selectors and projections under one account per person (U-D; local only)."""

import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.data_export.datasets import DATASETS
from apps.data_export.fields import USER_PROJECTIONS
from apps.data_export.guards import validate_user_projection
from apps.data_export.runner_users import scrub_shell_identities, staff_track_user_ids
from apps.data_export.subject_selectors import subject_query
from apps.data_export.types import Fidelity
from apps.hardware_requests.models import HardwareRequest
from apps.makerspaces.models import MakerspaceMembership
from tests.accounts.account_factories import grant_staff_role, make_membership
from tests.data_export.portable_helpers import make_space, make_user

pytestmark = pytest.mark.django_db(transaction=True)


def _merge(shell, survivor):
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.account_unification_run_id', 'mf-merge', true)")
        MakerspaceMembership.all_tracks.filter(user=shell).update(status="revoked", revoked_at=timezone.now())
        User._base_manager.filter(pk=shell.pk).update(
            account_kind="staff", merged_into=survivor, merged_at=timezone.now(), is_active=False)


def test_portable_user_projection_has_no_staff_tenant_and_the_guard_agrees():
    assert "staff_makerspace" not in USER_PROJECTIONS[Fidelity.PORTABLE]
    assert "account_kind" in USER_PROJECTIONS[Fidelity.PORTABLE]
    columns = {column.name for column in DATASETS[(Fidelity.PORTABLE, "global/users.csv")].columns}
    assert "staff_makerspace_id" not in columns
    validate_user_projection()


def test_subject_export_reads_history_recorded_against_a_merged_shell():
    space = make_space("mf-subject")
    survivor, shell = make_user("mf-survivor"), make_user("mf-shell")
    make_membership(survivor, space)
    make_membership(shell, space)
    old = HardwareRequest.objects.create(makerspace=space, requester=shell, requester_username=shell.username,
                                         requester_name="Before the merge")
    _merge(shell, survivor)
    rows = set(subject_query(HardwareRequest, survivor, space.pk).values_list("pk", flat=True))
    assert old.pk in rows
    memberships = set(subject_query(MakerspaceMembership, survivor, space.pk).values_list("user_id", flat=True))
    assert memberships == {survivor.pk, shell.pk}


def test_staff_closure_and_shell_scrub():
    space = make_space("mf-closure")
    staff, member = make_user("mf-staff"), make_user("mf-member")
    grant_staff_role(staff, space, role_slug="inventory_manager")
    make_membership(member, space)
    assert staff_track_user_ids(space.pk) == {staff.pk}
    shell = make_user("mf-scrub-shell")
    _merge(shell, member)
    scrubbed = scrub_shell_identities([User._base_manager.get(pk=shell.pk), User._base_manager.get(pk=member.pk)])
    assert (scrubbed[0].email, scrubbed[0].username) == ("", f"merged-account-{shell.pk}")
    assert scrubbed[1].email == member.email
