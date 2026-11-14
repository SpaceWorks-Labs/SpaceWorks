"""Bucket submissions/reprints and pooled jobs cannot each claim the last print slot."""
import pytest
from django.db import connection
from rest_framework.exceptions import APIException

from apps.audit.models import AuditLog
from apps.machines.models import MachineServiceRequest, ServiceBucket, get_or_create_default_bucket
from apps.machines.public_printer_service import _kernel_payload
from apps.machines.service_workflow import submit, create_reprint
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.machines.eta_helpers import world

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines, pytest.mark.area_machine_service]


def create(w, index, pooled=False):
    return submit(w.queue if pooled else w.machines[index], w.staff, actor=w.staff,
        title=f"Part {index}", requester_name="Staff", contact_email=w.staff.email, contact_phone="",
        capability_payload=_kernel_payload(w.queue, {}))


def snapshot():
    return [list(model.objects.order_by("pk").values()) for model in (MachineServiceRequest, ServiceBucket, AuditLog)]


def setup(reprints=False):
    w = world("cx7-p4b-bucket-print", printing=True)
    originals = []
    if reprints:
        # Seed retained completed jobs, as the reprint boundary suite does; no status UPDATE.
        originals = [MachineServiceRequest.objects.create(makerspace=w.space,
            bucket=get_or_create_default_bucket(w.machines[index]), requester=w.staff,
            title=f"Original {index}", status="completed", estimated_minutes=1,
            capability_payload=_kernel_payload(w.queue, {})) for index in range(2)]
    w.space.resource_limit_overrides = {"print": 3 if reprints else 1}
    w.space.save(update_fields=["resource_limit_overrides"])
    return w, originals


@pytest.mark.parametrize("reprints", [False, True])
def test_bucket_creator_max_next_print_refusal_keeps_jobs_and_buckets(reprints, settings):
    settings.MANAGED_PLANS_ENABLED = False
    w, originals = setup(reprints)
    make = lambda index: create_reprint(originals[index], w.staff) if reprints else create(w, index)
    assert make(0).pk
    before = snapshot()
    with pytest.raises(APIException) as failure:
        make(1)
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (400, "limit_reached")
    assert snapshot() == before


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["buckets", "mixed", "reprints"])
def test_bucket_and_queue_creators_share_the_last_print_slot(kind, settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    w, originals = setup(kind == "reprints")
    def make(index):
        return create_reprint(originals[index], w.staff) if kind == "reprints" else \
            create(w, index, pooled=kind == "mixed" and index == 1)
    assert race_creators(make) == [(201, "created"), (400, "limit_reached")]
    assert MachineServiceRequest.objects.filter(makerspace=w.space).count() == (3 if kind == "reprints" else 1)
    action = "machine_service.reprint_created" if kind == "reprints" else "machine_service.submitted"
    assert AuditLog.objects.filter(makerspace=w.space, action=action).count() == 1
