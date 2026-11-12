"""Decision 336(k) / SECURITY-REVIEW M8, L-M1, L-M4: machine access grants belong to ONE makerspace.

Built-in machine types (makerspace NULL) are shared by every space, so a grant, its renewal, its uniqueness and
every lookup must carry the space. Plus: out-of-scope revoke and bulk grant leak nothing, and the expiry notice
sweep runs only for live spaces with machines on and sends each notice once.
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.machines import access_grants as ag
from apps.machines import notifications_machine_access as notices
from apps.machines.access_grants_services import grant_access
from apps.machines.models import Machine, MachineAccessGrant, MachineType
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from tests.machines.certification_helpers import _member
from tests.parity_0120.machine_access.helpers import machine_manager, world

pytestmark = pytest.mark.django_db


def client(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def builtin_type():
    return MachineType.objects.create(makerspace=None, slug=f"builtin-{uuid4().hex[:8]}", name="Shared laser", is_builtin=True)


def join(user, space):
    role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    return MakerspaceMembership.objects.create(user=user, makerspace=space, role=MakerspaceMembership.Role.CUSTOM,
                                               assigned_role=role)


def grant_url(space):
    return reverse("admin-machine-access", args=[space.pk])


# --- built-in types -------------------------------------------------------------------------------------------

def test_a_built_in_type_can_be_granted_over_http():
    w, shared = world("bi"), builtin_type()
    response = client(w.boss).post(grant_url(w.space), {"member_ids": [w.member.pk], "machine_type_id": shared.pk},
                                   format="json")
    assert response.status_code == 201, response.content
    assert MachineAccessGrant.objects.get().machine_type_id == shared.pk


def test_another_space_type_is_still_a_404():
    w, other = world("bi-own"), world("bi-other")
    response = client(w.boss).post(grant_url(w.space), {"member_ids": [w.member.pk], "machine_type_id": other.kind.pk},
                                   format="json")
    assert response.status_code == 404
    assert not MachineAccessGrant.objects.exists()


# --- one person, two spaces, one built-in type ---------------------------------------------------------------

def test_the_same_member_holds_separate_grants_in_two_spaces():
    a, b, shared = world("two-a"), world("two-b"), builtin_type()
    join(a.member, b.space)
    first = grant_access(a.boss, a.space, a.member, machine_type=shared, note="A's induction",
                         expires_at=timezone.now() + timedelta(days=10))
    second = grant_access(b.boss, b.space, a.member, machine_type=shared, note="B's note")
    assert first.pk != second.pk                         # B created its own row, it did not renew A's
    first.refresh_from_db()
    assert first.note == "A's induction" and first.expires_at is not None and first.makerspace_id == a.space.pk
    assert MachineAccessGrant.objects.filter(member=a.member, revoked_at__isnull=True).count() == 2


def test_space_b_response_never_shows_space_a_grant():
    a, b, shared = world("show-a"), world("show-b"), builtin_type()
    join(a.member, b.space)
    grant_access(a.boss, a.space, a.member, machine_type=shared, note="secret of A")
    created = client(b.boss).post(grant_url(b.space), {"member_ids": [a.member.pk], "machine_type_id": shared.pk},
                                  format="json").json()
    assert [row["note"] for row in created["granted"]] == [""]
    listed = client(b.boss).get(grant_url(b.space), {"status": "all"}).json()
    assert listed["count"] == 1 and "secret of A" not in str(listed)


def test_can_use_is_decided_per_space():
    a, b, shared = world("use-a"), world("use-b"), builtin_type()
    join(a.member, b.space)
    in_a = Machine.objects.create(makerspace=a.space, machine_type=shared, name="A laser")
    in_b = Machine.objects.create(makerspace=b.space, machine_type=shared, name="B laser")
    grant_access(a.boss, a.space, a.member, machine_type=shared)
    assert ag.can_use(a.member, in_a) == (True, None)
    assert ag.can_use(a.member, in_b) == (False, "no_machine_access")


def test_the_database_allows_one_live_type_grant_per_space_not_per_person():
    a, b, shared = world("db-a"), world("db-b"), builtin_type()
    MachineAccessGrant.objects.create(makerspace=a.space, member=a.member, machine_type=shared)
    MachineAccessGrant.objects.create(makerspace=b.space, member=a.member, machine_type=shared)
    with pytest.raises(IntegrityError), transaction.atomic():
        MachineAccessGrant.objects.create(makerspace=a.space, member=a.member, machine_type=shared)


# --- existence leaks (L-M4) -----------------------------------------------------------------------------------

def test_revoking_a_grant_outside_the_machine_scope_is_a_404_and_changes_nothing():
    w = world("rv")
    row = MachineAccessGrant.objects.create(makerspace=w.space, member=w.member, machine=w.mill)
    scoped = client(machine_manager(w, w.kind))
    assert scoped.post(reverse("admin-machine-access-revoke", args=[row.pk])).status_code == 404
    row.refresh_from_db()
    assert row.revoked_at is None
    mine = MachineAccessGrant.objects.create(makerspace=w.space, member=w.member, machine=w.laser)
    assert scoped.post(reverse("admin-machine-access-revoke", args=[mine.pk])).status_code == 200


def test_bulk_grant_answers_the_same_for_a_foreign_account_and_a_missing_id():
    w, elsewhere = world("oracle"), world("oracle-x")
    stranger = elsewhere.member                         # exists, but not in this space
    missing = MachineAccessGrant.objects.count() + 10_000_000
    response = client(w.boss).post(grant_url(w.space), {
        "member_ids": [w.member.pk, stranger.pk, missing], "machine_id": w.laser.pk}, format="json")
    assert response.status_code == 201
    body = response.json()
    assert len(body["granted"]) == 1
    details = {row["member_id"]: row["detail"] for row in body["failed"]}
    assert set(details) == {stranger.pk, missing}
    assert details[stranger.pk] == details[missing]
    assert not MachineAccessGrant.objects.filter(member=stranger).exists()


def test_bulk_grant_still_grants_every_active_member():
    w = world("bulk")
    second, _ = _member(w.space, f"second-{uuid4().hex[:6]}")
    response = client(w.boss).post(grant_url(w.space), {"member_ids": [w.member.pk, second.pk],
                                                        "machine_id": w.laser.pk}, format="json")
    assert response.status_code == 201 and len(response.json()["granted"]) == 2 and response.json()["failed"] == []


# --- expiry notice sweep (L-M1) -------------------------------------------------------------------------------

@pytest.fixture
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(notices, "notify_access", lambda grant, event: calls.append((grant.pk, event)))
    return calls


def _expiring(w, machine):
    return MachineAccessGrant.objects.create(makerspace=w.space, member=w.member, machine=machine,
                                             expires_at=timezone.now() + timedelta(days=2))


def test_the_expiry_notice_goes_out_once_even_when_the_sweep_runs_twice(sent):
    w = world("exp")
    row = _expiring(w, w.laser)
    assert notices.notify_expiring() == 1
    assert notices.notify_expiring() == 0
    assert sent == [(row.pk, "expiring")]
    row.refresh_from_db()
    assert row.expiry_notice_sent_at is not None


def test_a_space_with_machines_off_gets_no_expiry_notice(sent):
    on, off = world("exp-on"), world("exp-off")
    kept = _expiring(on, on.laser)
    quiet = _expiring(off, off.laser)
    off.space.enabled_modules = [key for key in off.space.enabled_modules if key != "machines"]
    off.space.save(update_fields=["enabled_modules"])
    notices.notify_expiring()
    assert sent == [(kept.pk, "expiring")]
    quiet.refresh_from_db()
    assert quiet.expiry_notice_sent_at is None             # still due once machines come back on
