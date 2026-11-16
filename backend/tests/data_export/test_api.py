import io
import json
from datetime import timedelta
from urllib.parse import unquote, urlparse

import pytest
from django.conf import settings as django_settings
from django.core.cache import cache
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from tests.accounts.account_factories import make_staff

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.data_export import services
from apps.data_export.models import DataExportJob
from apps.data_export.throttles import DataExportCreateThrottle
from apps.inventory.models import InventoryProduct
from apps.makerspaces import limits
from apps.makerspaces.models import Makerspace, MakerspaceMembership

pytestmark = pytest.mark.django_db


def user(username):
    return User.objects.create_user(
        username=username,
        access_status=User.AccessStatus.ACTIVE,
    )


def space(slug):
    return Makerspace.objects.create(name=slug, slug=slug)



def client_for(actor):
    client = APIClient()
    client.force_authenticate(actor)
    return client

def available_job(makerspace, actor, *, suffix="archive", manifest=None):
    return DataExportJob.objects.create(
        makerspace=makerspace,
        requested_by=actor,
        fidelity="REDACTED",
        status=DataExportJob.Status.AVAILABLE,
        object_key=f"data-exports/{makerspace.pk}/{suffix}.zip",
        manifest=manifest or {},
        expires_at=timezone.now() + timedelta(days=1),
    )

def list_url(makerspace):
    return reverse("data-export-list-create", kwargs={"makerspace_id": makerspace.pk})

def detail_url(makerspace, job):
    return reverse(
        "data-export-detail",
        kwargs={"makerspace_id": makerspace.pk, "job_id": job.pk},
    )

def download_url_endpoint(makerspace, job):
    return reverse(
        "data-export-download-url",
        kwargs={"makerspace_id": makerspace.pk, "job_id": job.pk},
    )


def token_from(response):
    return unquote(urlparse(response.data["url"]).path.rstrip("/").rsplit("/", 1)[-1])


def download_path(job, token):
    return reverse("data-export-download", kwargs={"job_id": job.pk, "token": token})


def test_staff_endpoints_require_manage_makerspace_in_the_target_tenant():
    target = space("export-permission-target")
    manager = make_staff(target, username="export-permission-owner")
    job = available_job(target, manager)

    underprivileged = make_staff(target, username="export-permission-inventory",
                                role_slug="inventory_manager")
    foreign_manager = make_staff(space("export-permission-other-space"), username="export-permission-foreign")

    calls = (
        ("get", list_url(target), None),
        ("post", list_url(target), {"fidelity": "REDACTED"}),
        ("get", detail_url(target, job), None),
        ("post", download_url_endpoint(target, job), None),
    )
    # Decision 481(1): staff of the space lacking the action get 403; another space's manager gets the
    # answer a missing space gets, so the tenant's existence is not confirmed.
    for actor, refusal in ((underprivileged, 403), (foreign_manager, 404)):
        client = client_for(actor)
        for method, url, payload in calls:
            response = getattr(client, method)(url, payload, format="json")
            assert response.status_code == refusal
            if refusal == 404:
                # 481(1): the exact missing-space answer, code included.
                assert response.json()["code"] == "not_found"


def test_download_token_is_job_bound_expires_and_is_single_use(monkeypatch):
    makerspace = space("export-token-scope")
    actor = make_staff(makerspace, username="export-token-manager")
    first = available_job(makerspace, actor, suffix="first")
    second = available_job(makerspace, actor, suffix="second")
    client = client_for(actor)
    monkeypatch.setattr(
        "apps.data_export.storage.open_archive",
        lambda _key: io.BytesIO(b"archive"),
    )

    issued = client.post(download_url_endpoint(makerspace, first))
    assert issued.status_code == 200
    token = token_from(issued)
    assert client.get(download_path(second, token)).status_code == 404

    DataExportJob.objects.filter(pk=first.pk).update(
        download_token_expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert client.get(download_path(first, token)).status_code == 404

    reissued = client.post(download_url_endpoint(makerspace, first))
    fresh_token = token_from(reissued)
    assert reissued.status_code == 200
    assert fresh_token != token
    successful = client.get(download_path(first, fresh_token))
    assert successful.status_code == 200
    assert successful["Cache-Control"] == "private, no-store"
    assert client.get(download_path(first, fresh_token)).status_code == 404


def test_export_lifecycle_audits_counts_never_rows_or_download_token(
    monkeypatch, tmp_path
):
    makerspace = space("export-audit")
    actor = make_staff(makerspace, username="export-audit-manager")
    row_sentinel = "PRIVATE-ROW-CONTENT-MUST-NOT-ENTER-AUDIT"
    InventoryProduct.objects.create(
        makerspace=makerspace,
        name=row_sentinel,
        total_quantity=1,
        available_quantity=1,
    )
    queued = []
    monkeypatch.setattr(
        "apps.data_export.views.run_data_export_task.delay", queued.append
    )

    response = client_for(actor).post(
        list_url(makerspace), {"fidelity": "REDACTED"}, format="json"
    )
    assert response.status_code == 201
    job = DataExportJob.objects.get(pk=response.data["id"])
    assert queued == [str(job.pk)]

    archive_path = tmp_path / "export.zip"
    archive_path.write_bytes(b"zip")
    manifest = {
        "snapshot_at": timezone.now().isoformat(),
        "row_counts": {"inventory/products.csv": 1},
        "total_rows": 1,
    }
    cleanup_calls = []
    monkeypatch.setattr(
        services,
        "build_archive",
        lambda _job: (archive_path, manifest, type(
            "TempDir", (), {"cleanup": lambda _self: cleanup_calls.append(True)}
        )()),
    )
    monkeypatch.setattr("apps.data_export.storage.upload_archive", lambda *_args: None)
    services.run_export_job(job.pk)
    assert cleanup_calls == [True]

    client = client_for(actor)
    issued = client.post(download_url_endpoint(makerspace, job))
    assert issued.status_code == 200
    raw_token = token_from(issued)
    monkeypatch.setattr(
        "apps.data_export.storage.open_archive",
        lambda _key: io.BytesIO(b"archive"),
    )
    assert client.get(download_path(job, raw_token)).status_code == 200

    logs = list(
        AuditLog.objects.filter(target_id=str(job.pk)).order_by("created_at", "pk")
    )
    assert [entry.action for entry in logs] == [
        "data_export.requested",
        "data_export.completed",
        "data_export.download_url_issued",
        "data_export.downloaded",
    ]
    expected_counts = {
        "row_counts": {"inventory/products.csv": 1},
        "total_rows": 1,
    }
    for entry in logs:
        assert entry.actor_id == actor.pk
        assert entry.makerspace_id == makerspace.pk
        assert entry.target_type == "data_export.dataexportjob"
        assert set(entry.meta) <= {"fidelity", "row_counts", "total_rows"}
        assert "row_counts" in entry.meta
        assert "total_rows" in entry.meta
    assert logs[0].meta == {
        "fidelity": "REDACTED",
        "row_counts": {},
        "total_rows": 0,
    }
    assert logs[1].meta == {"fidelity": "REDACTED", **expected_counts}
    assert logs[2].meta == expected_counts
    assert logs[3].meta == expected_counts

    persisted = json.dumps(
        list(
            AuditLog.objects.filter(target_id=str(job.pk)).values(
                "actor_id", "makerspace_id", "action", "target_type", "target_id", "meta"
            )
        ),
        sort_keys=True,
    )
    assert raw_token not in persisted
    assert row_sentinel not in persisted


def test_create_checks_quota_inside_the_job_transaction(monkeypatch):
    makerspace = space("export-quota-transaction")
    actor = make_staff(makerspace, username="export-quota-manager")
    calls = []
    original = limits.check_quota

    def observe_quota(locked, key, *, adding=1):
        assert connection.in_atomic_block
        assert not DataExportJob.objects.filter(makerspace=makerspace).exists()
        calls.append((locked.pk, key, adding))
        return original(locked, key, adding=adding)

    monkeypatch.setattr(limits, "check_quota", observe_quota)
    monkeypatch.setattr("apps.data_export.views.run_data_export_task.delay", lambda _pk: None)

    response = client_for(actor).post(
        list_url(makerspace), {"fidelity": "REDACTED"}, format="json"
    )

    assert response.status_code == 201
    assert calls == [(makerspace.pk, "data_exports", 1)]
    assert DataExportJob.objects.filter(makerspace=makerspace).count() == 1


def test_export_creation_is_rate_limited(settings, monkeypatch):
    cache.clear()
    throttle_rates = {
        **django_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        "data_export_create": "1/hour",
    }
    rest_framework_settings = dict(django_settings.REST_FRAMEWORK)
    rest_framework_settings["DEFAULT_THROTTLE_RATES"] = throttle_rates
    settings.REST_FRAMEWORK = rest_framework_settings
    monkeypatch.setattr(DataExportCreateThrottle, "THROTTLE_RATES", throttle_rates)
    monkeypatch.setattr("apps.data_export.views.run_data_export_task.delay", lambda _pk: None)
    makerspace = space("export-throttle")
    actor = make_staff(makerspace, username="export-throttle-manager")
    client = client_for(actor)

    first = client.post(list_url(makerspace), {}, format="json")
    second = client.post(list_url(makerspace), {}, format="json")

    assert first.status_code == 201
    assert second.status_code == 429


def test_openapi_documents_every_data_export_endpoint():
    paths = SchemaGenerator().get_schema(request=None, public=True)["paths"]
    expected = {
        "/api/v1/admin/makerspace/{makerspace_id}/data-exports": {"get", "post"},
        "/api/v1/admin/makerspace/{makerspace_id}/data-exports/{job_id}": {"get"},
        "/api/v1/admin/makerspace/{makerspace_id}/data-exports/{job_id}/download-url": {
            "post"
        },
        "/api/v1/data-exports/download/{job_id}/{token}": {"get"},
    }
    for path, methods in expected.items():
        assert path in paths
        assert methods <= set(paths[path])
