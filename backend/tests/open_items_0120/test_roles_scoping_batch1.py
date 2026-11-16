"""Open items A14, B1-B5, B7, B11, F1 (batch 1): scoping and notice fixes. Written for the consolidation run."""
import ast
import pathlib
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.accounts import rbac
from tests.fixed_roles.helpers import staff_account
from tests.maintenance.l16_helpers import in_house, world
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def test_a14_machine_manager_sees_only_their_types_due_schedules():
    from apps.maintenance.models import MaintenanceSchedule
    w = world("oi-a14")
    mine = MaintenanceSchedule.objects.create(machine=w.machine, description="Mirror", interval_days=30,
                                              next_due=timezone.localdate())
    MaintenanceSchedule.objects.create(machine=w.other, description="Spindle", interval_days=30,
                                       next_due=timezone.localdate())
    manager = staff_account(w.space, "oi-a14-mm", "machine_manager", machine_types=(w.kind,))
    data = authenticated_client(manager).get(f"/api/v1/admin/makerspaces/{w.space.pk}/my-maintenance").json()
    assert [row["id"] for row in data["machine_schedules"]] == [mine.pk]


def test_b1_request_timeline_audit_rows_go_through_the_area_scope(monkeypatch):
    from apps.audit import area_scope
    from apps.hardware_requests.timeline_service_audit import request_audit_rows
    from tests.return_helpers import make_issued_request
    w = world("oi-b1")
    request = make_issued_request(w.space, w.manager, [(w.product, 1)])
    seen = []
    monkeypatch.setattr(area_scope, "scope_audit_rows", lambda actor, rows: seen.append(actor) or rows.none())
    assert list(request_audit_rows(request, w.manager)) == [] and seen == [w.manager]
    request_audit_rows(request)  # no actor: the caller already scoped the request itself
    assert seen == [w.manager]


def test_b2_foreign_space_reads_as_not_found_not_forbidden():
    from django.urls import reverse
    from rest_framework.test import APIClient
    from tests.operations.test_related_facts_item13 import world as facts_world
    w, other = facts_world(), facts_world()
    client = APIClient()
    client.force_authenticate(other.manager)
    for name, kwargs in (("admin-related-facts-event", {"event_id": w.event.pk}),
                         ("admin-related-facts-booking", {"booking_id": w.booking.pk})):
        assert client.get(reverse(name, kwargs={"makerspace_id": w.space.pk, **kwargs})).status_code == 404


def test_b3_unlinking_a_link_with_no_booking_needs_tenant_wide_machine_authority():
    from rest_framework.exceptions import NotFound
    from apps.events.machine_booking_links import _require_tenant_wide_machine_authority as require
    w = world("oi-b3")
    scoped = staff_account(w.space, "oi-b3-scoped", "machine_manager", machine_types=(w.kind,))
    boss = staff_account(w.space, "oi-b3-boss", "space_manager")
    with pytest.raises(NotFound):
        require(scoped, w.space)
    require(boss, w.space)


def test_b4_a_technician_recipient_must_cover_the_creators_coverage():
    from apps.operations.report_schedule_reach import _coverage_covers
    w = world("oi-b4")
    creator = staff_account(w.space, "oi-b4-a", "technician")
    wide = staff_account(w.space, "oi-b4-b", "technician")
    narrow = staff_account(w.space, "oi-b4-c", "technician")
    in_house(w, creator, coverage=[{"kind": "machine_type", "machine_type": w.kind}])
    in_house(w, wide, coverage=[{"kind": "machine_type", "machine_type": w.kind},
                                {"kind": "machine_type", "machine_type": w.other_kind}])
    in_house(w, narrow, coverage=[{"kind": "machine_type", "machine_type": w.other_kind}])
    assert _coverage_covers(wide, creator, w.space.pk) is True
    assert _coverage_covers(narrow, creator, w.space.pk) is False


def test_b5_report_definitions_name_their_action_and_the_default_fails_closed():
    from apps.operations.report_types import ReportDefinition
    assert ReportDefinition.__dataclass_fields__["required_action"].default == rbac.Action.MANAGE_MAKERSPACE
    missing = []
    for path in pathlib.Path(__file__).resolve().parents[2].joinpath("apps").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "ReportDefinition(" not in text:
            continue
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "ReportDefinition":
                names = {kw.arg for kw in node.keywords}
                if "required_action" not in names and None not in names:
                    missing.append(f"{path.name}:{node.lineno}")
    assert missing == []


def test_b7_machine_service_rows_narrow_by_request_provenance(monkeypatch):
    from apps.notifications import legacy_feed_scope as scope
    assert scope._request_id("/admin/machine-service/requests/42") == 42
    assert scope._request_id("/admin/machine-service/requests/x") is None
    monkeypatch.setattr(scope, "reader_areas", lambda actor, space: {"machines"})
    monkeypatch.setattr(scope, "_machine_scoped", lambda actor, space: True)
    monkeypatch.setattr(scope, "_in_machine_scope", lambda actor, space, ids: {1} & set(ids))
    assert scope.event_visible(None, 1, "machine_service.accepted", url_path="/admin/machine-service/requests/1")
    assert not scope.event_visible(None, 1, "machine_service.accepted", url_path="/admin/machine-service/requests/2")
    assert not scope.event_visible(None, 1, "machine_service.accepted", url_path="")  # fails closed


def test_b11_event_linked_loan_notices_carry_the_event_window_and_desk_link():
    from apps.hardware_requests.loan_event_notice import annotate, context_for
    start = timezone.now()
    event = {"id": 5, "title": "Open night", "starts_at": start, "ends_at": start + timedelta(hours=2),
             "desk_link": "/admin/events/5"}
    out = annotate({"subject": "Loan issued", "text": "Body", "link": ""}, event)
    assert "(for Open night)" in out["subject"] and "Event window:" in out["text"] and out["link"] == "/admin/events/5"
    ctx = context_for(event)
    assert ctx["notice_kind"] == "event_loan" and ctx["event_id"] == 5 and ctx["event_desk_link"] == "/admin/events/5"


def test_f1_incident_alerts_also_reach_the_area_owner(monkeypatch):
    from apps.integrations import staff_notifications
    from apps.maintenance.incidents import notify
    calls = []
    monkeypatch.setattr(staff_notifications, "staff_user_ids_for_feature",
                        lambda space, feature, *a, **k: calls.append(feature) or [7])
    space = SimpleNamespace()
    assert notify._area_staff_ids(SimpleNamespace(area="events", makerspace=space)) == [7]
    assert notify._area_staff_ids(SimpleNamespace(area="bookings", makerspace=space)) == [7]
    assert notify._area_staff_ids(SimpleNamespace(area="lending", makerspace=space)) == [7]
    assert notify._area_staff_ids(SimpleNamespace(area="machines", makerspace=space)) == []
    assert calls == ["events", "bookings", "hardware_requests"]
