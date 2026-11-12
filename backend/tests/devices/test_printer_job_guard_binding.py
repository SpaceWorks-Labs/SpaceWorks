"""DB guard `devices_printer_job_guard` after migration 0010 (adapter placeholder id -> vendor id binding).

Only an unreported row whose id is a `pending-<hex>` placeholder may change `external_job_id`, once, to a real
(non-null, non-placeholder) id. Everything else about the job identity stays frozen by the trigger; the reverse
of the migration restores the fully frozen 0002 body. Real database, raw UPDATEs (the trigger is the subject, not
the service layer), each refusal inside its own savepoint so the transaction stays usable. Postgres DDL is
transactional, so the reverse-body test is rolled back with the test.
"""
import importlib
import uuid

import pytest
from django.db import InternalError, connection, transaction
from django.utils import timezone

from apps.devices.models import PrinterJob
from apps.devices.services_printer_bindings import create_binding
from apps.devices.services_printer_jobs import create_job
from tests.devices.helpers import create_device, enroll
from tests.devices.printer_helpers import printer_case
from tests.test_machine_service_workflow import in_progress, machine

pytestmark = pytest.mark.django_db

MIGRATION = importlib.import_module("apps.devices.migrations.0010_adapter_job_external_id_binding")


def _job(case, external_id):
    # A machine takes one in-progress request at a time and a device/machine pair binds once: use a fresh
    # machine AND a fresh enrolled device (the case already holds one binding).
    created = create_device(case["client"], case["space"])
    assert enroll(created["enrollment"])[0].status_code == 200
    target = machine(case["space"])
    row = in_progress(case["space"], actor=case["actor"], target=target)
    binding = create_binding(case["actor"], case["space"].pk, device_id=created["device"]["id"], machine_id=target.pk,
                             auto_apply_terminal=False)
    return create_job(case["actor"], case["space"].pk, binding_id=binding.pk,
                      service_request_id=row.pk, external_job_id=external_id)


def _update(job, **fields):
    with transaction.atomic():
        return PrinterJob.objects.filter(pk=job.pk).update(**fields)


def _refused(job, **fields):
    with pytest.raises(InternalError):
        _update(job, **fields)
    assert PrinterJob.objects.get(pk=job.pk).external_job_id == job.external_job_id


def _pending():
    return "pending-" + uuid.uuid4().hex


def test_pending_unreported_row_binds_once_to_a_real_vendor_id():
    case = printer_case("guard-bind-once")
    job = _job(case, _pending())
    _update(job, external_job_id="vendor-123")
    assert PrinterJob.objects.get(pk=job.pk).external_job_id == "vendor-123"
    job.external_job_id = "vendor-123"
    _refused(job, external_job_id="vendor-456")  # a real id is frozen once bound


def test_pending_cannot_move_to_another_placeholder_or_null():
    case = printer_case("guard-bind-refused")
    job = _job(case, _pending())
    _refused(job, external_job_id=_pending())
    with pytest.raises(InternalError):  # NULL is refused by the guard before NOT NULL could ever matter
        _update(job, external_job_id=None)


def test_non_pending_id_never_changes():
    case = printer_case("guard-non-pending")
    _refused(case["job"], external_job_id="vendor-other")
    _refused(case["job"], external_job_id=_pending())


def test_reported_pending_row_cannot_rebind():
    case = printer_case("guard-reported")
    job = _job(case, _pending())
    _update(job, terminal_operation_id=uuid.uuid4(), report_sha256="a" * 64, outcome="completed", actual_minutes=3,
            reported_at=timezone.now())
    _refused(job, external_job_id="vendor-late")


def test_other_identity_columns_stay_frozen_even_on_a_pending_row():
    case = printer_case("guard-identity")
    job = _job(case, _pending())
    for column, value in (("command_id", uuid.uuid4()), ("machine_name", "renamed"), ("service_request_name", "renamed"),
                          ("machine_id_snapshot", job.machine_id_snapshot + 1),
                          ("service_request_id_snapshot", job.service_request_id_snapshot + 1)):
        with pytest.raises(InternalError):
            _update(job, **{column: value})
    # a refused combined change must not slip the id through either
    with pytest.raises(InternalError):
        _update(job, external_job_id="vendor-combo", machine_name="renamed")
    assert PrinterJob.objects.get(pk=job.pk).external_job_id == job.external_job_id


def test_reverse_of_the_migration_restores_the_fully_frozen_body():
    case = printer_case("guard-reverse")
    job = _job(case, _pending())
    reverse_sql = MIGRATION.Migration.operations[0].reverse_sql
    forward_sql = MIGRATION.SQL
    with connection.cursor() as cursor:
        cursor.execute(reverse_sql)
    _refused(job, external_job_id="vendor-123")  # 0009 behaviour: even the placeholder is frozen
    with connection.cursor() as cursor:
        cursor.execute(forward_sql)
    _update(job, external_job_id="vendor-123")  # forward again: binding works
    assert PrinterJob.objects.get(pk=job.pk).external_job_id == "vendor-123"
