"""Copied export download bearers must not survive any database restore seam."""

import io
import json
import uuid
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from tests.accounts.account_factories import make_staff

from apps.backup.models import DeploymentRecoveryState, RestoreOperation
from apps.backup.raw_projection import fixture_payload, raw_records
from apps.backup.restore_control_records import rehydrate_control_record
from apps.data_export import services
from apps.data_export.models import DataExportJob
from apps.data_export.restore_hooks import (
    invalidate_download_tokens_after_restore,
    strip_download_bearer,
)
from tests.backup.test_archive_expiry import _mid_build_archive
from tests.data_export.test_api import (
    available_job, download_path, space, user,
)

pytestmark = pytest.mark.django_db

CLEARED_BEARER = {
    "download_token_digest": "",
    "download_token_expires_at": None,
    "download_token_consumed_at": None,
    "download_issued_to": None,
}


@pytest.fixture
def token_job(settings):
    settings.DATA_EXPORT_DOWNLOAD_TTL_SECONDS = 30 * 24 * 60 * 60
    makerspace = space("restore-export-tokens")
    actor = make_staff(makerspace, username="restore-export-manager")
    job = available_job(makerspace, actor)
    token, _ = services.issue_download_token(job, actor)
    return job, actor, token


def _job_fixture(job):
    record, = raw_records(DataExportJob.objects.filter(pk=job.pk), DataExportJob)
    return fixture_payload(DataExportJob, (record,))[0]


@pytest.fixture
def token_preimage(token_job):
    job, _actor, _token = token_job
    # Exercise clearing all four columns, including a historical consumption time.
    DataExportJob.objects.filter(pk=job.pk).update(
        download_token_consumed_at=timezone.now()
    )
    return job, _job_fixture(job)


def _assert_bearer_cleared(job):
    assert DataExportJob.objects.values(*CLEARED_BEARER).get(pk=job.pk) == CLEARED_BEARER


@pytest.mark.parametrize("kind", list(RestoreOperation.Kind))
def test_classic_restore_rejects_replayed_token_but_allows_new_token(
    kind, token_job, monkeypatch, tmp_path
):
    job, actor, token = token_job
    backup = DataExportJob.objects.values(*CLEARED_BEARER).get(pk=job.pk)
    assert backup["download_token_digest"]
    assert backup["download_token_consumed_at"] is None
    assert backup["download_token_expires_at"] > timezone.now() + timedelta(days=1)
    monkeypatch.setattr(
        "apps.data_export.storage.open_archive", lambda _key: io.BytesIO(b"zip")
    )
    anonymous = APIClient()
    downloaded = anonymous.get(download_path(job, token))
    assert downloaded.status_code == 200
    assert b"".join(downloaded.streaming_content) == b"zip"
    job.refresh_from_db()
    assert job.download_token_consumed_at is not None

    # pg_restore resurrects the captured, unused bearer after its live consumption.
    DataExportJob.objects.filter(pk=job.pk).update(**backup)
    archive = _mid_build_archive()
    control = tmp_path / "control.json"
    manifest = tmp_path / "manifest.json"
    control.write_text(json.dumps({"decision": "proceed"}), encoding="utf-8")
    manifest.write_text(json.dumps({"archive_id": str(archive.pk)}), encoding="utf-8")
    rehydrate_control_record(uuid.uuid4(), {
        "archive_id": str(archive.pk),
        "kind": kind,
        "control_record": str(control),
        "manifest": str(manifest),
    })
    state = DeploymentRecoveryState.load()
    state.mode = DeploymentRecoveryState.Mode.NORMAL
    state.save(update_fields=("mode", "updated_at"))

    assert anonymous.get(download_path(job, token)).status_code == 404
    _assert_bearer_cleared(job)
    fresh_token, _ = services.issue_download_token(job, actor)
    assert fresh_token != token
    downloaded = anonymous.get(download_path(job, fresh_token))
    assert downloaded.status_code == 200
    assert b"".join(downloaded.streaming_content) == b"zip"


def test_sweep_explicitly_routes_to_default_database(token_job, monkeypatch):
    job, _actor, _token = token_job
    DataExportJob.objects.filter(pk=job.pk).update(
        download_token_consumed_at=timezone.now()
    )
    manager = DataExportJob.objects
    using = Mock(wraps=manager.using)
    monkeypatch.setattr(manager, "using", using)

    assert invalidate_download_tokens_after_restore(using="default") == 1

    using.assert_called_once_with("default")
    _assert_bearer_cleared(job)


def test_sweep_leaves_job_without_token_unchanged():
    actor = user("restore-export-no-token")
    job = available_job(space("restore-export-no-token"), actor)
    queryset = DataExportJob.objects.filter(pk=job.pk)
    before = raw_records(queryset, DataExportJob)

    assert invalidate_download_tokens_after_restore() == 0

    assert raw_records(queryset, DataExportJob) == before
    job.refresh_from_db()
    assert job.status == before[0]["status"]
    assert job.object_key == before[0]["object_key"]
    assert job.expires_at == before[0]["expires_at"]
