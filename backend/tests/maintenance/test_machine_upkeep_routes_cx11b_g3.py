"""Machine upkeep, documents and due projection; folded gates 97/128, standing 481/494."""
from datetime import timedelta
from unittest.mock import Mock

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.utils import timezone

from apps.maintenance import storage
from apps.maintenance.models import MaintenanceLog, MaintenanceLogDocument, MaintenanceSchedule
from tests.maintenance.l16_helpers import world
from tests.maintenance.route_support_cx11b_g3 import foreign_client, foreign_refusal, prove, send
from tests.modules.switch_matrix_object_helpers import client_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory, pytest.mark.area_machines]
OPS = ("schedules", "create", "patch", "deactivate", "run", "logs", "log", "presign", "finalize", "url", "delete", "overdue")


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["machines", "machines.maintenance"])
@pytest.mark.parametrize("op", OPS)
def test_machine_upkeep_effect_standing_and_switch(op, key, native, monkeypatch):
    w = world("g3-upkeep")
    from apps.makerspaces.local_time import to_local
    today = to_local(w.space, timezone.now()).date()
    schedule = MaintenanceSchedule.objects.create(machine=w.machine, description="Retained inspection",
        interval_days=30, next_due=today - timedelta(days=1), created_by=w.manager)
    log = MaintenanceLog.objects.create(machine=w.machine, summary="Retained log", performed_by=w.manager)
    object_key = storage.log_document_object_key(w.space.pk, w.machine.pk, "pdf")
    doc = MaintenanceLogDocument.objects.create(log=log, object_key=object_key, size_bytes=87, uploaded_by=w.manager)
    w.space.storage_bytes_used = 87
    w.space.save(update_fields=["storage_bytes_used"])
    new_key = storage.log_document_object_key(w.space.pk, w.machine.pk, "pdf")
    upload = {"url": "https://storage.example.test/staging", "method": "PUT", "headers": {"Content-Type": "application/pdf"}}
    mocks = {
        "presigned_upload": Mock(return_value=upload), "finalize_upload": Mock(),
        "validate_log_document_object": Mock(return_value=storage.LogDocumentValidationResult(87, "application/pdf")),
        "presigned_get_url": Mock(return_value="https://storage.example.test/private"), "delete_object": Mock(),
    }
    for attr, mock in mocks.items():
        monkeypatch.setattr(storage, attr, mock)
    client, outsider = client_for(w.manager, w.space, native), foreign_client(native)
    args, method, body, status, audit = [w.space.pk, w.machine.pk], "get", {}, 200, None
    names = {"schedules": "admin-maintenance-schedule-list-create", "create": "admin-maintenance-schedule-list-create",
        "patch": "admin-maintenance-schedule-detail", "deactivate": "admin-maintenance-schedule-deactivate",
        "run": "admin-machine-maintenance-run", "logs": "admin-maintenance-log-list-create",
        "log": "admin-maintenance-log-list-create", "presign": "admin-maintenance-log-document-presign",
        "finalize": "admin-maintenance-log-document-finalize", "url": "admin-maintenance-log-document-url",
        "delete": "admin-maintenance-log-document-detail", "overdue": "admin-maintenance-overdue"}
    if op == "create":
        method, status, audit = "post", 201, "maintenance.schedule_created"
        body = {"description": "New inspection", "interval_days": 14, "next_due": "2099-01-01"}
    elif op in {"patch", "deactivate", "run"}:
        args = [schedule.pk]
        if op == "patch":
            method, audit, body = "patch", "maintenance.schedule_updated", {"description": "Updated inspection"}
        elif op == "deactivate":
            method, audit = "post", "maintenance.schedule_deactivated"
        else:
            method, status, audit, body = "post", 201, "maintenance.schedule_completed", {"summary": "Inspection done"}
    elif op == "log":
        method, status, audit, body = "post", 201, "maintenance.logged", {"summary": "New log", "parts_note": "New belt"}
    elif op in {"presign", "finalize"}:
        args, method = [log.pk], "post"
        body = {"filename": "inspection.pdf", "content_type": "application/pdf"} if op == "presign" else {"object_key": new_key}
        if op == "finalize":
            status, audit = 201, "maintenance.document_added"
    elif op in {"url", "delete"}:
        args = [doc.pk]
        if op == "delete":
            method, status, audit = "delete", 204, "maintenance.document_deleted"
    elif op == "overdue":
        args = [w.space.pk]

    def call(c):
        before = {k: m.call_count for k, m in mocks.items()}
        response = send(c or client, names[op], args, method, body)
        if response.status_code == 404:
            assert {k: m.call_count for k, m in mocks.items()} == before
        return response

    def check(response):
        data = response.data
        if op in {"schedules", "overdue"}:
            records = data["results"] if isinstance(data, dict) else data
            assert [(r["id"], r["description"]) for r in records] == [(schedule.pk, "Retained inspection")]
        elif op == "logs":
            assert [(r["id"], r["summary"]) for r in data["results"]] == [(log.pk, "Retained log")]
            assert [r["id"] for r in data["results"][0]["documents"]] == [doc.pk]
        elif op == "create":
            saved = MaintenanceSchedule.objects.get(pk=data["id"])
            assert (saved.description, saved.interval_days, saved.next_due.isoformat(), saved.machine_id) == (
                "New inspection", 14, "2099-01-01", w.machine.pk)
            assert MaintenanceSchedule.objects.filter(machine=w.machine).count() == 2
        elif op in {"patch", "deactivate"}:
            schedule.refresh_from_db()
            assert schedule.description == ("Updated inspection" if op == "patch" else "Retained inspection")
            assert schedule.is_active is (op != "deactivate")
        elif op in {"log", "run"}:
            saved = MaintenanceLog.objects.get(pk=data["id"])
            assert (saved.machine_id, saved.performed_by_id, saved.summary) == (
                w.machine.pk, w.manager.pk, "Inspection done" if op == "run" else "New log")
            assert MaintenanceLog.objects.filter(machine=w.machine).count() == 2
            if op == "run":
                schedule.refresh_from_db()
                assert schedule.next_due == to_local(w.space, saved.performed_at).date() + timedelta(days=30)
        elif op == "presign":
            assert data["upload"] == upload
            storage.assert_log_document_object_key(data["object_key"], w.space.pk, w.machine.pk)
            mocks["presigned_upload"].assert_called_with(data["object_key"], "application/pdf")
            assert MaintenanceLogDocument.objects.filter(log=log).count() == 1
        elif op == "finalize":
            saved = MaintenanceLogDocument.objects.get(pk=data["id"])
            assert (saved.log_id, saved.object_key, saved.size_bytes, saved.uploaded_by_id) == (
                log.pk, new_key, 87, w.manager.pk)
            assert MaintenanceLogDocument.objects.filter(log=log).count() == 2
            w.space.refresh_from_db()
            assert w.space.storage_bytes_used == 174
            mocks["finalize_upload"].assert_called_with(new_key)
            mocks["validate_log_document_object"].assert_called_with(new_key)
        elif op == "url":
            assert data == {"url": "https://storage.example.test/private"}
            mocks["presigned_get_url"].assert_called_with(object_key)
        else:
            assert not MaintenanceLogDocument.objects.filter(pk=doc.pk).exists()
            w.space.refresh_from_db()
            assert w.space.storage_bytes_used == 0
            mocks["delete_object"].assert_called_with(object_key)

    audits = {audit: 1} if audit else {}
    if op == "run":
        audits["maintenance.logged"] = 1
    prove(w.space, {"schedule": schedule, "log": log, "doc": doc}, key, call, check, status=status,
          off=(404, "capability_disabled"), outsiders=[(outsider, foreign_refusal(native, space_path=op in {"schedules", "create", "logs", "log", "overdue"}))], audits=audits,
          after_off=((403, "permission_denied") if native else (404, "not_found")) if op == "delete" else None)

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
