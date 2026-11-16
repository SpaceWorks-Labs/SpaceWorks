"""Technician directory and item/room schedule routes; folded OR-gates, 481/494 standing."""
from datetime import date, timedelta

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.utils import timezone

from apps.maintenance.models import SubjectMaintenanceLog, SubjectMaintenanceSchedule
from apps.maintenance.repairs import areas, optin
from tests.maintenance.l16_helpers import external, world
from tests.maintenance.route_support_cx11b_g3 import foreign_client, foreign_refusal, isolation, prove, send
from tests.modules.switch_matrix_object_helpers import client_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory,
              pytest.mark.area_machines, pytest.mark.area_bookings]
DIRECTORY = [(op, area, key, native) for op in ("get", "patch", "delete", "link", "consent")
             for area, parent in (("machines", "machines"), ("inventory", "loans.enabled"), ("rooms", "bookings"))
             for key in (areas.REPAIRS[area], areas.MAINTENANCE[area], parent) for native in (False, True)]


@pytest.mark.parametrize("op,area,key,native", DIRECTORY)
def test_technician_directory_effect_standing_and_switch(op, area, key, native, monkeypatch):
    w = world("g3-directory")
    isolation(w, area)
    row = external(w, sms_opted_in_at=timezone.now())
    # Email delivery is a boundary; link minting, signed digest and audit are real.
    monkeypatch.setattr("apps.maintenance.repairs.optin._email_link", lambda *a: True)
    client, outsider = client_for(w.manager, w.space, native), foreign_client(native)
    name, method, body, status, audit = "admin-technician-detail", op, {}, 200, None
    if op == "patch":
        body, audit = {"name": "Updated technician", "notes": "Retained specialist"}, "technician.updated"
    elif op == "delete":
        audit = "technician.archived"
    elif op == "link":
        name, method, status, audit = "admin-technician-opt-in-link", "post", 201, "technician.opt_in_link_created"
    elif op == "consent":
        name, method, body, audit = "admin-technician-consent", "post", {"channel": "sms"}, "technician.consent_withdrawn"

    def check(response):
        row.refresh_from_db()
        if op == "get":
            assert (response.data["id"], response.data["name"]) == (row.pk, "Ravi Repairs")
        elif op == "patch":
            assert (row.name, row.notes) == ("Updated technician", "Retained specialist")
        elif op == "delete":
            assert row.is_archived is True
        elif op == "link":
            token = response.data["telegram_start"].split()[-1]
            assert row.opt_in_digest == optin.digest(token)
            assert optin.contact_for_token(token).pk == row.pk and response.data["emailed"] is True
        else:
            assert row.sms_opted_in_at is None and row.phone == "+919800000000"

    prove(w.space, {"contact": row}, key,
          lambda c: send(c or client, name, [row.pk], method, body), check, status=status,
          off=(404, "capability_disabled"), outsiders=[(outsider, foreign_refusal(native))],
          audits={audit: 1} if audit else {})


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("area,kind,target,parent", [
    ("inventory", "inventory_product", "product", "loans.enabled"),
    ("rooms", "bookable_space", "room", "bookings")])
@pytest.mark.parametrize("gate", ["capability", "parent"])
@pytest.mark.parametrize("op", ["patch", "run"])
def test_subject_schedule_effect_standing_and_switch(native, area, kind, target, parent, gate, op):
    w = world("g3-subject-schedule")
    subject = getattr(w, target)
    row = SubjectMaintenanceSchedule.objects.create(makerspace=w.space, subject_type=kind,
        **{areas.SUBJECT_FIELD[kind]: subject}, description="Retained schedule", interval_days=14,
        next_due=date(2099, 1, 1))
    client, outsider = client_for(w.manager, w.space, native), foreign_client(native)
    key = areas.MAINTENANCE[area] if gate == "capability" else parent
    body = {"description": "Updated schedule"} if op == "patch" else {"summary": "Checked handle"}

    def check(response):
        row.refresh_from_db()
        if op == "patch":
            assert row.description == "Updated schedule" and row.interval_days == 14
        else:
            log = SubjectMaintenanceLog.objects.get(pk=response.data["id"])
            assert (log.schedule_id, log.summary, log.performed_by_id) == (row.pk, "Checked handle", w.manager.pk)
            assert SubjectMaintenanceLog.objects.filter(schedule=row).count() == 1
            from apps.makerspaces.local_time import to_local
            assert row.next_due == to_local(w.space, log.performed_at).date() + timedelta(days=14)

    prove(w.space, {"schedule": row, "subject": subject}, key,
          lambda c: send(c or client, "admin-subject-maintenance-detail" if op == "patch" else
                         "admin-subject-maintenance-run", [row.pk], "patch" if op == "patch" else "post", body),
          check, status=200 if op == "patch" else 201, off=(404, "capability_disabled"),
          outsiders=[(outsider, foreign_refusal(native))], audits={
              "maintenance.subject_schedule_updated" if op == "patch" else "maintenance.subject_logged": 1})

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
