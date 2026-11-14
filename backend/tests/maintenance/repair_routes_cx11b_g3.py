"""Repair lifecycle operation assertions, across all three subject parents."""
from decimal import Decimal
from datetime import timedelta
from types import SimpleNamespace

from django.utils import timezone

from apps.maintenance.models import IssueAssignment, IssueEvent, IssueReport, RepairPart, TechnicianDispatch, WorkOrder
from apps.maintenance.repairs import areas, services_issues as svc
from apps.payments.models_ledger_entries import LedgerEntry
from tests.maintenance.l16_helpers import external, world
from tests.maintenance.route_support_cx11b_g3 import foreign_client, foreign_refusal, isolation, prove, send
from tests.modules.switch_matrix_object_helpers import client_for
from tests.return_helpers import make_issued_request

OPS = ("detail", "triage", "reject", "assign", "unassign", "dispatch", "start", "work-log", "parts", "quote",
       "approve", "payout", "fix", "close")
SUBJECTS = {"machines": ("machine", "machine", "machines"),
            "inventory": ("inventory_product", "product", "loans.enabled"),
            "rooms": ("bookable_space", "room", "bookings")}


def cases(ops):
    return [(op, area, key, native) for op in ops for area, (_, _, parent) in SUBJECTS.items()
            for key in (areas.REPAIRS[area], areas.MAINTENANCE[area], parent) for native in (False, True)]


def reported(w, area, kind, subject):
    if area == "inventory":
        origin = make_issued_request(w.space, w.manager, [(subject, 1)])
        person, source = origin.requester, "loan"
    elif area == "machines":
        from apps.machines.models import MachineServiceRequest, ServiceQueue
        person, source = w.manager, "machine_job"
        queue = ServiceQueue.objects.create(makerspace=w.space, machine_type=subject.machine_type,
                                            name="Retained repair queue")
        origin = MachineServiceRequest.objects.create(queue=queue, makerspace=w.space, member=person, requester=person,
            assigned_machine=subject, title="Retained job", status="completed")
    else:
        from apps.bookings.models import Booking
        person, source = w.manager, "booking"
        origin = Booking.objects.create(space=subject, member=person, name="Retained booker", email=person.email,
            status="confirmed", starts_at=timezone.now(), ends_at=timezone.now() + timedelta(hours=1))
    return svc.file_report(w.space, reporter=person, source=source, origin=origin, subject_type=kind, subject=subject,
                           title="Broken", description="Retained repair", validated=[])


def run(op, area, key, native, monkeypatch, settings):
    # A report can remain notify-only when repairs is off (decision 103). Isolate
    # this repair-only queue so each dependency can independently hide this row.
    w = world("g3-repair")
    kind, target, _ = SUBJECTS[area]
    subject = getattr(w, target)
    row = reported(w, area, kind, subject) if op == "triage" else svc.open_issue(
        w.manager, w.space, subject_type=kind, subject=subject, title="Broken", description="Retained repair")
    if op == "close":
        row = svc.fix(w.manager, row, resolution="Fixed fixture")
    isolation(w, area)
    contact = external(w)
    body, audit, event_kind = {}, None, None
    if op == "triage":
        body, audit, event_kind = {"priority": "urgent", "note": "Triage note"}, "issue.triaged", "triaged"
    elif op == "reject":
        body, audit, event_kind = {"reason": "Duplicate"}, "issue.rejected", "rejected"
    elif op == "assign":
        body, audit, event_kind = {"myself": True}, "issue.assigned", "assigned"
    elif op == "unassign":
        row = svc.assign(w.manager, row, myself=True)
        assignment = IssueAssignment.objects.get(issue=row, person=w.manager)
        body, audit, event_kind = {"assignment_id": assignment.pk}, "issue.unassigned", "unassigned"
    elif op == "dispatch":
        settings.NOTIFICATION_FANOUT_VIA_CELERY = False
        monkeypatch.setattr("apps.maintenance.repairs.channels._email", lambda *a, **k:
                            SimpleNamespace(delivered=True, failure_code="", message_id="g3-email"))
        body, audit, event_kind = {"contact_ids": [contact.pk], "channels": ["email"], "note": "Urgent"}, \
            "issue.dispatched", "dispatched"
    elif op == "start":
        audit, event_kind = "repair.started", "started"
    elif op == "work-log":
        body, audit, event_kind = {"kind": "remark", "note": "Replaced belt"}, "repair.remark_logged", "remark"
    elif op == "parts":
        body, audit, event_kind = {"kind": "used", "product_id": w.product.pk, "quantity": 2}, \
            "repair.parts_used", "parts_used"
    elif op == "quote":
        body, audit, event_kind = {"amount": "12.50", "currency": "inr", "contact_id": contact.pk,
                                  "note": "Labour"}, "repair.quote_recorded", "quote"
    elif op in {"approve", "payout"}:
        row.quote_state, row.quote_amount, row.quote_currency, row.quote_contact = (
            "pending" if op == "approve" else "approved", Decimal("12.50"), "inr", contact)
        row.save(update_fields=["quote_state", "quote_amount", "quote_currency", "quote_contact"])
        if op == "approve":
            body, audit, event_kind = {"approve": True, "note": "Proceed"}, "repair.quote_approved", "quote_approved"
        else:
            body, audit, event_kind = {"amount": "12.50", "method": "cash", "reference": "G3-CASH"}, \
                "repair.payout_recorded", "payout"
    elif op == "fix":
        body, audit, event_kind = {"resolution": "Belt replaced"}, "repair.fixed", "fixed"
    elif op == "close":
        body, audit, event_kind = {"note": "Verified"}, "issue.closed", "closed"
    client, outsider = client_for(w.manager, w.space, native), foreign_client(native)
    name = "admin-issue-detail" if op == "detail" else "admin-issue-" + op

    def check(response):
        row.refresh_from_db()
        assert response.data["id"] == row.pk
        if op == "detail":
            assert (response.data["title"], response.data["description"], response.data["state"]) == (
                "Broken", "Retained repair", "triaged")
            return
        events = IssueEvent.objects.filter(issue=row, kind=event_kind)
        assert events.count() == 1
        if op == "triage":
            assert (row.state, row.priority) == ("triaged", "urgent")
            order = WorkOrder.objects.get(pk=row.work_order_id)
            assert (order.title, order.priority, order.subject_type) == ("Broken", "urgent", kind)
            assert events.get().note == "Triage note"
        elif op == "reject":
            assert (row.state, row.resolution) == ("rejected", "Duplicate") and row.closed_at is not None
            assert WorkOrder.objects.get(pk=row.work_order_id).status == "cancelled"
        elif op == "assign":
            assert row.state == "assigned" and list(row.assignments.values_list("person_id", flat=True)) == [w.manager.pk]
            assert WorkOrder.objects.get(pk=row.work_order_id).assignee_id == w.manager.pk
        elif op == "unassign":
            assert row.assignments.count() == 0
        elif op == "dispatch":
            dispatch = TechnicianDispatch.objects.get(issue=row)
            assert (dispatch.contact_id, dispatch.channel, dispatch.status, dispatch.provider_message_id) == (
                contact.pk, "email", "delivered", "g3-email")
            assert list(row.assignments.values_list("contact_id", flat=True)) == [contact.pk]
            assert row.state == "assigned"
        elif op == "start":
            assert row.state == "in_progress"
            assert WorkOrder.objects.get(pk=row.work_order_id).status == "in_progress"
        elif op == "work-log":
            assert events.get().note == "Replaced belt"
        elif op == "parts":
            part = RepairPart.objects.get(issue=row)
            assert (part.product_id, part.quantity, part.kind) == (w.product.pk, 2, "used")
            w.product.refresh_from_db()
            assert (w.product.available_quantity, w.product.total_quantity) == (3, 3)
        elif op == "quote":
            assert (row.quote_state, row.quote_amount, row.quote_currency, row.quote_contact_id, row.quote_note) == (
                "pending", Decimal("12.50"), "inr", contact.pk, "Labour")
        elif op == "approve":
            assert row.quote_state == "approved" and events.get().note == "Proceed"
        elif op == "payout":
            entry = LedgerEntry.objects.get(pk=row.payout_entry_id)
            assert (entry.amount, entry.currency, entry.method, entry.reference, entry.counterparty) == (
                Decimal("12.50"), "inr", "cash", "G3-CASH", contact.name)
            assert (entry.kind, entry.domain, entry.source_kind, entry.source_id) == (
                "expense", areas.LEDGER_DOMAIN[area], "repairs.payout", str(row.pk))
            assert LedgerEntry.objects.filter(source_kind="repairs.payout").count() == 1
        elif op == "fix":
            assert (row.state, row.resolution) == ("fixed", "Belt replaced") and row.fixed_at is not None
            order = WorkOrder.objects.get(pk=row.work_order_id)
            assert (order.status, order.resolution, order.closed_by_id) == ("done", "Belt replaced", w.manager.pk)
            if area == "machines":
                from apps.maintenance.models import MaintenanceLog
                log = MaintenanceLog.objects.get(pk=order.log_id)
                assert (log.machine_id, log.summary, log.performed_by_id) == (subject.pk, "Belt replaced", w.manager.pk)
                assert MaintenanceLog.objects.filter(machine=subject).count() == 1
        elif op == "close":
            assert row.state == "closed" and row.closed_at is not None and events.get().note == "Verified"

    objects = {"issue": row, "subject": subject, "product": w.product}
    audits = {audit: 1} if audit else {}
    if op == "triage":
        audits["work_order.created"] = 1
    if op in {"start", "fix"}:
        audits["work_order.started"] = 1
    if op == "fix":
        audits["work_order.closed"] = 1
        if area == "machines":
            audits["maintenance.logged"] = 1
    if op == "reject":
        audits["work_order.cancelled"] = 1
    if op == "assign":
        audits["work_order.assigned"] = 1
    if op == "dispatch":
        audits["dispatch.sent"] = 1
    if op == "parts":
        audits["inventory.quantity_adjusted"] = 1
    if op == "payout":
        audits["ledger.expense_recorded"] = 1
    prove(w.space, objects, key, lambda c: send(c or client, name, [row.pk], "get" if op == "detail" else "post", body),
          check, outsiders=[(outsider, foreign_refusal(native))], audits=audits)
