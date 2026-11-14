"""The export creator reserves capacity before enqueueing its background worker."""
from unittest.mock import Mock

import pytest
from django.db import connection
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.data_export.models import DataExportJob
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.concurrency_helpers_cx7 import race_posts
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_data_export]


def scenario(monkeypatch):
    space = make_space("cx7-export-creator")
    space.resource_limit_overrides = {"data_exports": 1}
    space.save(update_fields=["resource_limit_overrides"])
    enqueue = Mock()
    monkeypatch.setattr("apps.data_export.views.dispatch", enqueue)
    return space, reverse("data-export-list-create", kwargs={"makerspace_id": space.pk}), enqueue


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_export_creator_max_then_exact_refusal_preserves_job_and_enqueues_once(surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, url, enqueue = scenario(monkeypatch)
    caller = callers(space, surface, settings, monkeypatch)[0]
    maximum = caller.post(url, {}, format="json")
    assert maximum.status_code == 201
    job = DataExportJob.objects.get(makerspace=space)
    assert job.status == "pending"
    before = list(DataExportJob.objects.filter(makerspace=space).values())
    refused = caller.post(url, {}, format="json")
    assert refused.status_code == 400
    assert refused.json()["code"] == "limit_reached"
    assert list(DataExportJob.objects.filter(makerspace=space).values()) == before
    assert AuditLog.objects.filter(makerspace=space, action="data_export.requested").count() == 1
    assert enqueue.call_count == 1
    assert enqueue.call_args.args[1] == str(job.pk)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_two_export_creators_at_last_slot_admit_and_enqueue_one(surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, url, enqueue = scenario(monkeypatch)
    results = race_posts(callers(space, surface, settings, monkeypatch), url, [{}, {}])
    assert sorted(status for status, _ in results) == [201, 400]
    assert [body["code"] for status, body in results if status == 400] == ["limit_reached"]
    assert DataExportJob.objects.filter(makerspace=space, status="pending").count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="data_export.requested").count() == 1
    assert enqueue.call_count == 1
