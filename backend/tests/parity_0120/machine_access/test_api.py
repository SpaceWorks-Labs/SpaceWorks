"""Staff and member HTTP surfaces for machine access, and the retired certification routes (decision 319)."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.machines.models import MachineAccessGrant
from tests.machines.certification_helpers import _member
from tests.parity_0120.machine_access.helpers import machine_manager, world

pytestmark = pytest.mark.django_db


def client(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def test_space_manager_grants_lists_and_revokes_over_http():
    w = world()
    api = client(w.boss)
    url = reverse("admin-machine-access", args=[w.space.pk])
    created = api.post(url, {"member_ids": [w.member.pk], "machine_type_id": w.kind.pk,
                             "expires_at": (timezone.now() + timedelta(days=30)).isoformat(), "note": "ok"},
                       format="json")
    assert created.status_code == 201 and len(created.json()["granted"]) == 1
    listed = api.get(url).json()
    assert listed["count"] == 1 and listed["results"][0]["status"] == "live"
    pk = listed["results"][0]["id"]
    assert api.post(reverse("admin-machine-access-revoke", args=[pk])).status_code == 200
    assert api.get(url).json()["count"] == 0
    assert api.get(url, {"status": "revoked"}).json()["count"] == 1
    assert AuditLog.objects.filter(action__startswith="machine_access.").count() == 2


def test_machine_manager_only_sees_and_grants_inside_scope():
    w = world()
    MachineAccessGrant.objects.create(makerspace=w.space, member=w.member, machine=w.mill)
    manager = client(machine_manager(w, w.kind))
    url = reverse("admin-machine-access", args=[w.space.pk])
    assert manager.get(url).json()["count"] == 0
    assert manager.post(url, {"member_ids": [w.member.pk], "machine_id": w.mill.pk}, format="json").status_code == 403
    assert manager.post(url, {"member_ids": [w.member.pk], "machine_id": w.laser.pk}, format="json").status_code == 201


def test_cross_tenant_is_a_404_and_a_member_is_refused():
    w, elsewhere = world(), world("elsewhere")
    row = MachineAccessGrant.objects.create(makerspace=elsewhere.space, member=elsewhere.member, machine=elsewhere.laser)
    assert client(w.boss).get(reverse("admin-machine-access", args=[elsewhere.space.pk])).status_code == 404
    assert client(w.boss).post(reverse("admin-machine-access-revoke", args=[row.pk])).status_code == 404
    other, _ = _member(w.space, "plain")
    assert client(other).get(reverse("admin-machine-access", args=[w.space.pk])).status_code in (401, 403)


def test_open_to_all_toggle_is_audited_and_scoped():
    w = world()
    url = reverse("admin-machine-open-access", args=[w.laser.pk])
    assert client(w.boss).patch(url, {"open_to_all_members": True}, format="json").json() == {"open_to_all_members": True}
    w.laser.refresh_from_db()
    assert w.laser.open_to_all_members is True
    assert AuditLog.objects.filter(action="machine.open_access_changed").count() == 1
    scoped = client(machine_manager(w, w.other))
    assert scoped.patch(url, {"open_to_all_members": False}, format="json").status_code in (403, 404)


def test_member_sees_only_their_own_grants_and_open_machines():
    w = world()
    other, _ = _member(w.space, "neighbour")
    MachineAccessGrant.objects.create(makerspace=w.space, member=w.member, machine=w.laser, note="staff only")
    MachineAccessGrant.objects.create(makerspace=w.space, member=other, machine=w.mill)
    body = client(w.member).get(reverse("member-machine-access", args=[w.space.pk])).json()
    assert [g["machine_name"] for g in body["grants"]] == ["Laser 1"]
    assert "note" not in body["grants"][0] and body["open_machines"] == []


@pytest.mark.parametrize("name,args", [("admin-certification-types", [1]), ("member-certifications", [1])])
def test_certification_routes_are_retired_with_410(name, args):
    w = world()
    response = client(w.boss).get(reverse(name, args=args))
    assert response.status_code == 410 and response.json()["code"] == "certifications_retired"


def test_retired_switches_always_read_off():
    from apps.makerspaces.platform import feature_enabled
    w = world()
    w.space.enabled_features = sorted({*w.space.enabled_features, "machines.certifications",
                                       "machines.induction_events", "machines.certification_reminders"})
    w.space.save(update_fields=["enabled_features"])
    for key in ("machines.certifications", "machines.induction_events", "machines.certification_reminders"):
        assert feature_enabled(w.space, key) is False
