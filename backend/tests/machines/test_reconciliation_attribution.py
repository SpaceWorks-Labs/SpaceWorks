"""Manual usage must never attribute member activity to another account kind."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.machines.usage_attribution import validate_attribution
from apps.makerspaces.models import MakerspaceMembership
from tests.account_split.p1_helpers import staff
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db


def setup_member(suffix):
    space = make_space(f"recon-usage-{suffix}")
    user = make_user(f"recon-usage-{suffix}", access_status="active")
    membership = MakerspaceMembership.objects.create(
        makerspace=space, user=user, role="custom", assigned_role=space.roles.get(slug="member"))
    return SimpleNamespace(makerspace_id=space.pk), user, membership


def test_current_same_tenant_member_is_attributed_by_pk_or_instance():
    machine, user, _ = setup_member("valid")
    past = timezone.now() - timedelta(hours=1)
    assert validate_attribution(machine, user.pk, past).pk == user.pk
    assert validate_attribution(machine, user, past).pk == user.pk
    assert validate_attribution(machine) is None


@pytest.mark.parametrize("changes", [
    {"is_active": False}, {"access_status": "restricted"},
    {"is_tenant_dump_stub": True}, {"deletion_requested_at": timezone.now()},
    {"account_purged_at": timezone.now()},
])
def test_live_database_standing_beats_a_stale_selected_instance(changes):
    machine, user, _ = setup_member(next(iter(changes)))
    User.objects.filter(pk=user.pk).update(**changes)
    with pytest.raises(ValidationError, match="active member"):
        validate_attribution(machine, user)


def test_staff_and_foreign_and_revoked_members_are_refused():
    machine, member, membership = setup_member("scope")
    space = membership.makerspace
    staff_user, _ = staff(space, "recon-usage-staff", "machine_manager", access_status="active")
    with pytest.raises(ValidationError):
        validate_attribution(machine, staff_user)
    with pytest.raises(ValidationError):
        validate_attribution(SimpleNamespace(makerspace_id=make_space("recon-usage-other").pk), member)
    membership.status = "revoked"
    membership.save(update_fields=["status"])
    with pytest.raises(ValidationError):
        validate_attribution(machine, member)


@pytest.mark.parametrize("started", [timezone.now() + timedelta(days=1), timezone.datetime(2020, 1, 1)])
def test_invalid_attribution_time_is_refused(started):
    with pytest.raises(ValidationError, match="past time"):
        validate_attribution(SimpleNamespace(), started_at=started)


@pytest.mark.parametrize("identity", [True, False, 0, -1, "1", [], {}])
def test_malformed_member_identifiers_are_validation_errors(identity):
    with pytest.raises(ValidationError, match="active member"):
        validate_attribution(SimpleNamespace(makerspace_id=1), identity)


@pytest.mark.parametrize("started", ["2026-10-17", 1, True, {}])
def test_non_datetime_attribution_times_are_validation_errors(started):
    with pytest.raises(ValidationError, match="past time"):
        validate_attribution(SimpleNamespace(), started_at=started)
