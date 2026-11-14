"""The shared job creator cannot bypass printer capacity through a staff submission."""
import pytest
from django.db import connection
from rest_framework.exceptions import APIException

from apps.audit.models import AuditLog
from apps.machines.models import MachineServiceRequest
from apps.machines.public_printer_service import _kernel_payload
from apps.machines.service_workflow import submit
from apps.makerspaces.limits_usage import _COUNTERS
from apps.managed_hosting.extra_quotas import extra_used
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.machines.eta_helpers import world

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines, pytest.mark.area_machine_service]
KEYS = ["machine_service_open", "machine_service_submit", "machine_jobs_monthly", "print"]


def setup(key):
    w = world("cx7-submit-quota", printing=key == "print")
    w.space.resource_limit_overrides = {key: 1}
    w.space.save(update_fields=["resource_limit_overrides"])
    payload = _kernel_payload(w.queue, {}) if key == "print" else {}
    return w, payload


def create(w, payload, title):
    return submit(w.queue, w.staff, actor=w.staff, title=title, requester_name="Staff entry",
                  contact_email=w.staff.email, contact_phone="", capability_payload=payload)


def used(space, key):
    return extra_used(space, key) if key == "machine_jobs_monthly" else _COUNTERS[key](space)


@pytest.mark.parametrize("key", KEYS)
def test_shared_submit_accepts_max_and_refuses_next_before_job_or_audit(key, settings):
    settings.MANAGED_PLANS_ENABLED = False
    w, payload = setup(key)
    row = create(w, payload, "Last")
    assert row.status == "pending"
    assert used(w.space, key) == 1
    before = list(MachineServiceRequest.objects.filter(makerspace=w.space).values())
    audits = list(AuditLog.objects.filter(makerspace=w.space).order_by("pk").values())
    with pytest.raises(APIException) as raised:
        create(w, payload, "Excess")
    expected = (409, "machine_jobs_monthly_quota_reached") if key == "machine_jobs_monthly" else (400, "limit_reached")
    assert (raised.value.status_code, str(raised.value.detail["code"])) == expected
    assert list(MachineServiceRequest.objects.filter(makerspace=w.space).values()) == before
    assert list(AuditLog.objects.filter(makerspace=w.space).order_by("pk").values()) == audits


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("key", KEYS)
def test_shared_submit_creators_racing_for_last_slot_admit_one(key, settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    w, payload = setup(key)
    expected = (409, "machine_jobs_monthly_quota_reached") if key == "machine_jobs_monthly" else (400, "limit_reached")
    assert race_creators(lambda index: create(w, payload, str(index))) == [(201, "created"), expected]
    assert used(w.space, key) == 1
    assert MachineServiceRequest.objects.filter(makerspace=w.space).count() == 1
    assert AuditLog.objects.filter(makerspace=w.space, action="machine_service.submitted").count() == 1
