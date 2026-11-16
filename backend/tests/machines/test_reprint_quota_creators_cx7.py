"""A reprint is a new job; retaining a prepaid charge does not waive job capacity."""
import pytest
from django.db import connection
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.machines.models import MachineServiceRequest
from apps.machines.service_workflow import create_reprint
from apps.makerspaces.limits_usage import _COUNTERS
from apps.managed_hosting.extra_quotas import extra_used
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.machines.eta_helpers import world

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines, pytest.mark.area_machine_service]
KEYS = ["machine_service_open", "machine_service_submit", "machine_jobs_monthly", "print"]


def setup(key, originals=1):
    w = world("cx7-reprint-quota", printing=key == "print")
    rows = [MachineServiceRequest.objects.create(makerspace=w.space, queue=w.queue,
            requester=w.staff, title=f"Original {index}", status="completed", estimated_minutes=1)
            for index in range(originals)]
    w.space.resource_limit_overrides = {key: 1 if key == "machine_service_open" else originals + 1}
    w.space.save(update_fields=["resource_limit_overrides"])
    return w, rows


def used(space, key):
    return extra_used(space, key) if key == "machine_jobs_monthly" else _COUNTERS[key](space)


def snapshot():
    return {model.__name__: list(model.objects.order_by("pk").values())
            for model in (MachineServiceRequest, AuditLog)}


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("key", KEYS)
def test_reprint_http_max_then_max_plus_one_has_exact_error_and_no_child(key, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    w, rows = setup(key)
    caller = callers(w.space, surface, settings, monkeypatch)[0]
    url = reverse("admin-machine-service-request-reprint", kwargs={"pk": rows[0].pk})
    maximum = caller.post(url, {}, format="json")
    assert maximum.status_code == 200
    assert used(w.space, key) == (1 if key == "machine_service_open" else 2)
    assert MachineServiceRequest.objects.filter(reprint_of=rows[0]).count() == 1
    before = snapshot()
    refused = caller.post(url, {}, format="json")
    expected = (409, "machine_jobs_monthly_quota_reached") if key == "machine_jobs_monthly" else (400, "limit_reached")
    assert (refused.status_code, refused.json()["code"]) == expected
    assert snapshot() == before


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("key", KEYS)
def test_reprints_from_different_originals_racing_for_last_slot_admit_one(key, settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    w, rows = setup(key, originals=2)
    expected = (409, "machine_jobs_monthly_quota_reached") if key == "machine_jobs_monthly" else (400, "limit_reached")
    assert race_creators(lambda index: create_reprint(rows[index], w.staff)) == [(201, "created"), expected]
    assert used(w.space, key) == (1 if key == "machine_service_open" else 3)
    assert MachineServiceRequest.objects.filter(reprint_of__in=rows).count() == 1
