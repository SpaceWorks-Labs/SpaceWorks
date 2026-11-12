"""The `machine-access-grants` report follows machine scope (SECURITY-REVIEW L-M3, decision 319).

A Machine Manager handed one machine type counts only the grants they could manage on the staff list;
the Space Manager counts everything. Preview, export and the scheduled path all forward the actor.
"""
import pytest
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.machines.models import MachineAccessGrant
from apps.operations import reports
from tests.machines.certification_helpers import _member
from tests.parity_0120.machine_access.helpers import machine_manager, world

pytestmark = pytest.mark.django_db


def _metrics(matrix):
    header, *rows = matrix
    return {row[header.index("metric")]: row[header.index("value")] for row in rows}


def _grants():
    w = world()
    MachineAccessGrant.objects.create(makerspace=w.space, member=w.member, machine=w.laser)
    MachineAccessGrant.objects.create(makerspace=w.space, member=w.member, machine=w.mill)
    other, _ = _member(w.space, "other-member")
    MachineAccessGrant.objects.create(makerspace=w.space, member=other, machine_type=w.other)
    return w


def test_space_manager_counts_every_grant_in_the_preview_and_export():
    w = _grants()
    preview = _metrics(reports.report_data("machine-access-grants", w.space.pk, actor=w.boss)["rows"])
    export = _metrics(reports.report_rows("machine-access-grants", w.space.pk, actor=w.boss))
    assert preview["live_grants"] == export["live_grants"] == 3


def test_machine_manager_counts_only_their_machine_scope():
    w = _grants()
    manager = machine_manager(w, w.kind)
    preview = _metrics(reports.report_data("machine-access-grants", w.space.pk, actor=manager)["rows"])
    export = _metrics(reports.report_rows("machine-access-grants", w.space.pk, actor=manager))
    # Only the laser grant is inside a laser-type manager's scope: not the mill, not the mill type.
    assert preview["live_grants"] == export["live_grants"] == 1
    assert preview["live_machine_type_grants"] == 0


def test_a_member_without_machine_authority_is_refused():
    w = _grants()
    with pytest.raises(PermissionDenied):
        reports.report_data("machine-access-grants", w.space.pk, actor=w.member)


def test_scheduled_export_uses_the_schedule_owner_scope(monkeypatch):
    """`_build_and_deliver` calls report_rows with `actor=schedule.created_by`; the builder must see it."""
    w = _grants()
    manager = machine_manager(w, w.kind)
    seen = {}
    from apps.operations import reports_r2_devices
    original = reports_r2_devices._grant_rows

    def spy(space, start, end, *, actor=None):
        seen["actor"] = actor
        return original(space, start, end, actor=actor)
    monkeypatch.setattr(reports_r2_devices, "_grant_rows", spy)
    reports.report_rows("machine-access-grants", w.space.pk, actor=manager)
    assert seen["actor"] == manager


def test_review_converted_grants_list_filters_on_source():
    """Decision 335(a): the Space Manager reviews grants carried over from certifications."""
    w = world()
    MachineAccessGrant.objects.create(makerspace=w.space, member=w.member, machine=w.laser, source="migration",
                                      note="Converted")
    other, _ = _member(w.space, "staff-given")
    MachineAccessGrant.objects.create(makerspace=w.space, member=other, machine=w.laser)
    api = APIClient()
    api.force_authenticate(w.boss)
    url = reverse("admin-machine-access", args=[w.space.pk])
    converted = api.get(url, {"source": "migration"}).json()
    assert converted["count"] == 1 and converted["results"][0]["source"] == "migration"
    assert api.get(url).json()["count"] == 2
    assert api.get(url, {"source": "bogus"}).status_code == 400
