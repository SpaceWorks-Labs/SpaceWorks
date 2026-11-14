"""Queued imports count products at execution, never when merely accepting a job."""
from unittest.mock import Mock

import pytest
from django.db import connection
from django.urls import reverse
from rest_framework.exceptions import APIException

from apps.admin_api import bulk_import, tasks, views_bulk
from apps.admin_api.models import BulkImportJob
from apps.inventory.models import InventoryProduct
from tests.inventory.test_alternative_creators_cx7_p4a import state, world
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.creator_races_cx7 import race_creators

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory]


def jobs(surface, settings, monkeypatch):
    space = world(settings)
    caller = callers(space, surface, settings, monkeypatch)[0]
    dispatch = Mock()
    monkeypatch.setattr(views_bulk, "dispatch", dispatch)
    rows = []
    for name in ["First", "Second"]:
        response = caller.post(reverse("inventory-import-jobs", args=[space.pk]), {"mode": "apply",
            "rows": [{"name": name, "total_quantity": 1, "available_quantity": 1}]}, format="json")
        assert response.status_code == 201
        rows.append(BulkImportJob.objects.get(pk=response.json()["id"]))
    assert dispatch.call_count == 2
    assert all(row.status == "pending" and row.upload.name == "" for row in rows)
    errors = []
    original = bulk_import.apply_import
    def observe(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        except APIException as exc:
            errors.append((exc.status_code, str(exc.detail["code"])))
            raise
    monkeypatch.setattr(bulk_import, "apply_import", observe)
    return space, rows, errors


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_async_import_max_next_has_typed_quota_and_no_domain_writes(surface, settings, monkeypatch):
    space, rows, errors = jobs(surface, settings, monkeypatch)
    tasks.process_bulk_import_job.run(rows[0].pk)
    rows[0].refresh_from_db()
    assert (rows[0].status, rows[0].created_count, rows[0].error) == ("completed", 1, "")
    before = state()
    tasks.process_bulk_import_job.run(rows[1].pk)
    assert errors == [(400, "limit_reached")]
    assert state() == before
    rows[1].refresh_from_db()
    assert (rows[1].status, rows[1].created_count) == ("failed", 0)
    assert InventoryProduct.objects.filter(makerspace=space).count() == 1
    failed = dict(BulkImportJob.objects.filter(pk=rows[1].pk).values().get())
    tasks.process_bulk_import_job.run(rows[1].pk)
    assert BulkImportJob.objects.filter(pk=rows[1].pk).values().get() == failed
    assert state() == before


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_async_import_workers_racing_at_last_slot_create_one_product(surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, rows, errors = jobs(surface, settings, monkeypatch)
    race_creators(lambda index: tasks.process_bulk_import_job.run(rows[index].pk))
    assert sorted(BulkImportJob.objects.filter(makerspace=space).values_list("status", flat=True)) == ["completed", "failed"]
    assert errors == [(400, "limit_reached")]
    assert InventoryProduct.objects.filter(makerspace=space).count() == 1


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_queued_import_module_off_keeps_domain_and_failed_job_does_not_replay(surface, settings, monkeypatch):
    space, rows, errors = jobs(surface, settings, monkeypatch)
    original = list(space.enabled_modules)
    space.enabled_modules.remove("bulk_import")
    space.save(update_fields=["enabled_modules"])
    before = state()
    tasks.process_bulk_import_job.run(rows[0].pk)
    rows[0].refresh_from_db()
    assert (rows[0].status, rows[0].error) == ("failed", "Bulk import is switched off.")
    assert state() == before
    assert errors == []
    space.enabled_modules = original
    space.save(update_fields=["enabled_modules"])
    tasks.process_bulk_import_job.run(rows[0].pk)
    assert state() == before
    tasks.process_bulk_import_job.run(rows[1].pk)
    rows[1].refresh_from_db()
    assert (rows[1].status, rows[1].created_count) == ("completed", 1)
    assert InventoryProduct.objects.filter(makerspace=space).count() == 1
