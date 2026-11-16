"""`machines.access_grants.can_use` / `can_use_type`: the single decision (decision 319)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.machines import access_grants as ag
from apps.machines.models import Machine, MachineAccessGrant, MachineType
from tests.machines.certification_helpers import _member
from tests.parity_0120.machine_access.helpers import world

pytestmark = pytest.mark.django_db


def grant(w, member=None, **kwargs):
    return MachineAccessGrant.objects.create(makerspace=w.space, member=member or w.member, **kwargs)


def test_default_machine_needs_a_grant():
    w = world()
    assert w.laser.open_to_all_members is False
    assert ag.can_use(w.member, w.laser) == (False, "no_machine_access")


def test_machine_grant_allows_only_that_machine():
    w = world()
    grant(w, machine=w.laser)
    assert ag.can_use(w.member, w.laser) == (True, None)
    assert ag.can_use(w.member, w.laser2) == (False, "no_machine_access")


def test_type_grant_covers_every_machine_of_the_type_and_no_other_type():
    w = world()
    grant(w, machine_type=w.kind)
    assert ag.can_use(w.member, w.laser)[0] and ag.can_use(w.member, w.laser2)[0]
    assert ag.can_use(w.member, w.mill) == (False, "no_machine_access")
    assert ag.can_use_type(w.member, w.space, w.kind) == (True, None)
    assert ag.can_use_type(w.member, w.space, w.other) == (False, "no_machine_access")


def test_expired_grant_has_its_own_reason_and_a_live_one_wins():
    w = world()
    old = grant(w, machine=w.laser, expires_at=timezone.now() + timedelta(days=1))
    MachineAccessGrant.objects.filter(pk=old.pk).update(expires_at=timezone.now() - timedelta(days=1))
    assert ag.can_use(w.member, w.laser) == (False, "machine_access_expired")
    grant(w, machine_type=w.kind)
    assert ag.can_use(w.member, w.laser) == (True, None)


def test_revoked_grant_is_no_access():
    w = world()
    row = grant(w, machine=w.laser)
    MachineAccessGrant.objects.filter(pk=row.pk).update(revoked_at=timezone.now())
    assert ag.can_use(w.member, w.laser) == (False, "no_machine_access")


def test_open_to_all_members_needs_no_grant_but_does_not_admit_a_guest():
    w = world()
    Machine.objects.filter(pk=w.laser.pk).update(open_to_all_members=True)
    w.laser.refresh_from_db()
    assert ag.can_use(w.member, w.laser) == (True, None)
    assert ag.can_use(w.member, w.laser, include_open=False) == (False, "no_machine_access")
    assert ag.can_use_type(w.member, w.space, w.kind) == (True, None)


def test_a_grant_is_personal():
    w = world()
    other, _ = _member(w.space, "someone-else")
    grant(w, machine=w.laser)
    assert ag.can_use(other, w.laser) == (False, "no_machine_access")
    assert ag.can_use(None, w.laser) == (False, "no_machine_access")


def test_a_type_with_no_machine_has_nothing_to_gate():
    w = world()
    empty = MachineType.objects.create(makerspace=w.space, slug="empty-kind", name="Empty")
    assert ag.can_use_type(w.member, w.space, empty) == (True, None)


def test_require_access_raises_the_typed_refusal():
    w = world()
    with pytest.raises(ag.MachineAccessRefused) as caught:
        ag.require_access(w.member, w.laser)
    assert caught.value.detail["code"] == "no_machine_access"
    assert caught.value.status_code == 403
