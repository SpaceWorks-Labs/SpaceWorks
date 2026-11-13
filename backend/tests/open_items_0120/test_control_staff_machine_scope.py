"""0.12.0 (decision 282): the /control/ staff invite form offers individual machines.

Written for the consolidation run. The form feeds ``issue`` (snapshot on the invitation);
acceptance grants through ``grant_staff_role`` -> ``set_member_machine_scope``, so the
service's validation and audit apply. Never writes MembershipMachineScope directly.
"""
import pytest
from rest_framework.exceptions import ValidationError

from apps.accounts.models import StaffInvitation, User
from apps.accounts.services_staff_invitations import issue
from apps.accounts.staff_invitation_acceptance import _grant
from apps.audit.models import AuditLog
from apps.machines.member_scope_services import current_machine_scope, current_scope
from apps.machines.models import Machine
from apps.makerspaces.admin_staff_accounts import CreateStaffAccountForm
from apps.makerspaces.models import MakerspaceMembership
from tests.maintenance.l16_helpers import world

pytestmark = pytest.mark.django_db


def _root():
    return User.objects.create_superuser(username="ctl-root", email="ctl-root@example.test", password="x" * 20)


def _form(w, roles, **extra):
    return CreateStaffAccountForm(w.space, {"email": "invitee@example.test", "roles": roles, **extra})


def test_form_offers_only_this_spaces_machines():
    w = world("ctl-choices")
    foreign = world("ctl-foreign")
    form = CreateStaffAccountForm(w.space)
    offered = {pk for pk, _ in form.fields["machine_ids"].choices}
    assert {w.machine.pk, w.other.pk} <= offered
    assert foreign.machine.pk not in offered


def test_form_saves_types_and_machines_through_the_service():
    w = world("ctl-save")
    form = _form(w, ["machine_manager"], machine_type_ids=[w.kind.pk], machine_ids=[w.other.pk])
    assert form.is_valid(), form.errors
    row, _raw = issue(_root(), w.space.pk, **form.cleaned_data)
    assert row.machine_scope_snapshot == [w.kind.pk] and row.machine_ids_snapshot == [w.other.pk]
    invitee = User.objects.create_user(username="ctl-invitee", email="invitee@example.test",
                                       password="x" * 20)
    membership = _grant(invitee, StaffInvitation.objects.get(pk=row.pk))
    membership = MakerspaceMembership.staff_tracks.get(pk=membership.pk)
    assert current_scope(membership) == [w.kind.pk]
    assert current_machine_scope(membership) == [w.other.pk]
    assert AuditLog.objects.filter(action="staff.machine_scope_changed", makerspace=w.space).exists()


def test_cross_space_machine_is_rejected():
    w = world("ctl-mine")
    foreign = world("ctl-theirs")
    # The form refuses a machine that is not among this space's choices...
    form = _form(w, ["machine_manager"], machine_ids=[foreign.machine.pk])
    assert not form.is_valid() and "machine_ids" in form.errors
    # ...and the service layer refuses it too if the form is bypassed.
    with pytest.raises(ValidationError):
        issue(_root(), w.space.pk, email="invitee@example.test", roles=["machine_manager"],
              machine_ids=[foreign.machine.pk])
    assert not Machine.objects.filter(pk=foreign.machine.pk, makerspace=w.space).exists()


def test_machines_refused_for_a_role_that_is_not_scoped():
    w = world("ctl-role")
    form = _form(w, ["inventory_manager"], machine_ids=[w.machine.pk])
    assert form.is_valid(), form.errors
    with pytest.raises(ValidationError):
        issue(_root(), w.space.pk, **form.cleaned_data)
