"""COVERAGE-BE: archive release on row deletion (signals.py), tenant predicates (types.py), subject boundary."""
from contextlib import contextmanager
from datetime import timedelta

import pytest
from django.db.models import Q
from django.utils import timezone

from apps.data_export import storage
from apps.data_export.models import DataExportJob
from apps.data_export.subject_boundary import subject_boundary, subject_write
from apps.data_export.types import TenantPredicate
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
from tests.accounts.account_factories import make_staff

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def job():
    space = Makerspace.objects.create(name="sig-cov", slug="sig-cov")
    Makerspace.objects.filter(pk=space.pk).update(storage_bytes_used=1000)
    owner = make_staff(space, username="sig-cov-owner")
    return DataExportJob.objects.create(
        makerspace=space, requested_by=owner, fidelity="REDACTED", status="available",
        object_key="data-exports/sig/a.zip", accounted_size_bytes=400,
        expires_at=timezone.now() + timedelta(days=1))


def used(space_id):
    return Makerspace.objects.get(pk=space_id).storage_bytes_used


def test_deleting_a_job_deletes_the_archive_and_releases_its_bytes(job, monkeypatch):
    deleted = []
    monkeypatch.setattr(storage, "delete_object", lambda key: deleted.append(key) or True)
    space_id = job.makerspace_id
    job.delete()
    assert deleted == ["data-exports/sig/a.zip"] and used(space_id) == 600


def test_bytes_stay_charged_when_the_bucket_refuses_deletion(job, monkeypatch):
    monkeypatch.setattr(storage, "delete_object", lambda key: False)
    space_id = job.makerspace_id
    job.delete()
    assert used(space_id) == 1000


def test_a_job_without_an_object_key_releases_nothing(job, monkeypatch):
    called = []
    monkeypatch.setattr(storage, "delete_object", lambda key: called.append(key) or True)
    DataExportJob.objects.filter(pk=job.pk).update(object_key="")
    job.refresh_from_db()
    space_id = job.makerspace_id
    job.delete()
    assert called == [] and used(space_id) == 1000


def test_closed_source_gate_skips_release_and_storage_errors_never_break_the_delete(job, monkeypatch):
    @contextmanager
    def closed(makerspace_id):
        raise SourceMigrationGateClosed("closed")
        yield
    monkeypatch.setattr("apps.tenant_migration.gate_runtime.tenant_write", closed)
    deleted = []
    monkeypatch.setattr(storage, "delete_object", lambda key: deleted.append(key) or True)
    space_id, pk = job.makerspace_id, job.pk
    job.delete()
    assert not DataExportJob.objects.filter(pk=pk).exists()
    assert deleted == [] and used(space_id) == 1000

    owner = make_staff(Makerspace.objects.get(pk=space_id), username="sig-cov-owner-2")
    second = DataExportJob.objects.create(
        makerspace_id=space_id, requested_by=owner, fidelity="REDACTED", status="available",
        object_key="data-exports/sig/b.zip", accounted_size_bytes=100,
        expires_at=timezone.now() + timedelta(days=1))

    def boom(key):
        raise RuntimeError("bucket exploded")
    monkeypatch.undo()
    monkeypatch.setattr(storage, "delete_object", boom)
    second.delete()  # the failure is logged, never raised into the request
    assert not DataExportJob.objects.filter(pk=second.pk).exists()


# ------------------------------------------------------------------- predicates
def test_tenant_predicate_queryset_and_fixture_semantics_agree():
    plain = TenantPredicate(("makerspace",))
    assert plain.as_q(5) == Q(makerspace_id=5)
    assert plain.includes({"makerspace": 5}, 5) and not plain.includes({"makerspace": 6}, 5)
    assert not plain.includes({"makerspace": None}, 5)

    by_pk = TenantPredicate(("pk",))
    assert by_pk.as_q(5) == Q(pk=5)

    glob = TenantPredicate(("makerspace",), include_global_if_unowned=True)
    assert glob.as_q(5) == Q(makerspace_id=5) | Q(makerspace__isnull=True)
    assert glob.includes({"makerspace": None}, 5) and glob.includes({"makerspace": 5}, 5)
    assert not glob.includes({"makerspace": 6}, 5)

    local = TenantPredicate(("makerspace",), local_or_global_paths=("space",))
    assert local.includes({"makerspace": 5, "space": None}, 5)
    assert local.includes({"makerspace": 5, "space": 5}, 5)
    assert not local.includes({"makerspace": 5, "space": 6}, 5)


# ---------------------------------------------------------------- subject_boundary
def test_subject_boundary_reuses_a_held_lock_and_otherwise_opens_one(monkeypatch):
    from apps.tenant_migration import gate_runtime
    opened = []

    @contextmanager
    def fake_boundary(makerspace_id):
        opened.append(("boundary", makerspace_id))
        yield

    @contextmanager
    def fake_write(makerspace_id):
        opened.append(("write", makerspace_id))
        yield
    monkeypatch.setattr("apps.data_export.subject_boundary.boundary_tenant_write", fake_boundary)
    monkeypatch.setattr("apps.data_export.subject_boundary.tenant_write", fake_write)
    with subject_boundary(3):
        pass
    with subject_write(3):
        pass
    assert opened == [("boundary", 3), ("write", 3)]

    token = gate_runtime._boundary_shared_locks.set((3,))
    try:
        with subject_boundary(3):
            pass
        with subject_write(3):  # held lock: only a savepoint, no second boundary
            pass
    finally:
        gate_runtime._boundary_shared_locks.reset(token)
    assert opened == [("boundary", 3), ("write", 3)]
