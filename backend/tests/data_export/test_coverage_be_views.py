"""COVERAGE-BE: the staff data-export HTTP surface's list, PORTABLE and storage-outage answers."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.data_export import storage
from apps.data_export.models import DataExportJob
from apps.makerspaces.models import Makerspace
from tests.account_split.sweep_helpers import create_test_user
from tests.accounts.account_factories import make_staff

pytestmark = pytest.mark.django_db


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _job(space, owner, key, fidelity="REDACTED"):
    return DataExportJob.objects.create(
        makerspace=space, requested_by=owner, fidelity=fidelity, status="available",
        object_key=f"data-exports/{space.pk}/{key}.zip", expires_at=timezone.now() + timedelta(days=1))


@pytest.fixture
def world():
    space = Makerspace.objects.create(name="views-cov", slug="views-cov")
    manager = make_staff(space, username="views-cov-manager")
    superadmin = create_test_user(
        username="views-cov-super", email="views-cov-super@e.com", role=User.Role.SUPERADMIN,
        account_kind="platform", is_superuser=True)
    redacted = _job(space, manager, "red")
    portable = _job(space, manager, "port", fidelity="PORTABLE")
    subject = _job(space, manager, "subj", fidelity="SUBJECT")
    return space, manager, superadmin, redacted, portable, subject


def _list(space):
    return reverse("data-export-list-create", kwargs={"makerspace_id": space.pk})


def _detail(space, job):
    return reverse("data-export-detail", kwargs={"makerspace_id": space.pk, "job_id": job.pk})


def _download_url(space, job):
    return reverse("data-export-download-url", kwargs={"makerspace_id": space.pk, "job_id": job.pk})


def test_manager_list_shows_only_redacted_jobs_superadmin_sees_portable_too_never_subject(world):
    space, manager, superadmin, redacted, portable, subject = world
    as_manager = _client(manager).get(_list(space))
    assert as_manager.status_code == 200
    assert {row["id"] for row in as_manager.json()} == {str(redacted.pk)}
    as_super = _client(superadmin).get(_list(space))
    assert as_super.status_code == 200
    assert {row["id"] for row in as_super.json()} == {str(redacted.pk), str(portable.pk)}


def test_list_is_capped_at_twenty_newest_jobs(world):
    space, manager, *_ = world
    for i in range(22):
        _job(space, manager, f"bulk-{i}")
    response = _client(manager).get(_list(space))
    assert response.status_code == 200 and len(response.json()) == 20


def test_detail_returns_a_redacted_job_and_hides_subject_jobs_as_not_found(world):
    space, manager, _super, redacted, _portable, subject = world
    ok = _client(manager).get(_detail(space, redacted))
    assert ok.status_code == 200 and ok.json()["id"] == str(redacted.pk)
    missing = _client(manager).get(_detail(space, subject))
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"


def test_portable_job_detail_and_download_url_need_a_source_superadmin(world):
    space, manager, superadmin, _redacted, portable, _subject = world
    for response in (_client(manager).get(_detail(space, portable)),
                     _client(manager).post(_download_url(space, portable))):
        assert (response.status_code, response.json()["code"]) == (403, "forbidden")
        assert response.json()["detail"] == "Source superadmin access is required."
    assert DataExportJob.objects.get(pk=portable.pk).download_token_digest == ""
    allowed = _client(superadmin).get(_detail(space, portable))
    assert allowed.status_code == 200 and allowed.json()["id"] == str(portable.pk)


def test_download_returns_503_when_the_archive_store_is_unavailable(world, monkeypatch):
    space, manager, _super, redacted, _portable, _subject = world
    client = _client(manager)
    issued = client.post(_download_url(space, redacted))
    assert issued.status_code == 200
    from urllib.parse import unquote, urlparse
    token = unquote(urlparse(issued.json()["url"]).path.rstrip("/").rsplit("/", 1)[-1])

    def down(key):
        raise storage.ExportStorageError("minio down")
    monkeypatch.setattr(storage, "open_archive", down)
    response = APIClient().get(reverse("data-export-download", kwargs={"job_id": redacted.pk, "token": token}))
    assert response.status_code == 503
    assert response.json()["detail"] == "The export archive is temporarily unavailable."
