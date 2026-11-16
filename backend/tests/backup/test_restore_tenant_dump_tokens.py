"""Copied tenant-dump download bearers must not survive any database restore seam."""

import json
import uuid
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.backup.main_projection_registry import (
    BoundaryDisposition,
    boundary_rules,
    table_rules,
)
from apps.backup.models import RestoreOperation
from apps.backup.raw_projection import fixture_payload, raw_records
from apps.backup.restore_control_records import rehydrate_control_record
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.models import TenantDumpCapture
from apps.tenant_migration.restore_hooks import (
    invalidate_download_tokens_after_restore,
    strip_download_bearer,
)
from tests.backup.test_archive_expiry import _mid_build_archive

pytestmark = pytest.mark.django_db

BEARER = ("download_token_digest", "download_token_expires_at", "download_token_consumed_at")
CLEARED_BEARER = {
    "download_token_digest": "",
    "download_token_expires_at": None,
    "download_token_consumed_at": None,
}


def _capture(*, token=True):
    makerspace = Makerspace.objects.create(
        name="Restore dump tokens", slug=f"restore-dump-{uuid.uuid4().hex[:8]}"
    )
    requester = User.objects.create_user(username=f"dump-{uuid.uuid4().hex[:8]}")
    bearer = {
        "download_token_digest": "d" * 64,
        "download_token_expires_at": timezone.now() + timedelta(days=30),
        "download_token_consumed_at": timezone.now(),
    } if token else {}
    return TenantDumpCapture.objects.create(
        makerspace=makerspace,
        requested_by=requester,
        status=TenantDumpCapture.Status.PUBLISHED,
        source_makerspace_id=makerspace.pk,
        source_makerspace_slug=makerspace.slug,
        source_encryption_mode=False,
        catalog_digest="c" * 64,
        object_key=f"tenant-dumps/{uuid.uuid4()}.tar.age",
        **bearer,
    )


def _bearer(capture):
    return TenantDumpCapture.objects.values(*BEARER).get(pk=capture.pk)


def _non_bearer(capture):
    record, = raw_records(TenantDumpCapture.objects.filter(pk=capture.pk), TenantDumpCapture)
    return {key: value for key, value in record.items() if key not in BEARER}


@pytest.mark.parametrize("kind", list(RestoreOperation.Kind))
def test_classic_restore_clears_tenant_dump_bearer(kind, tmp_path):
    capture = _capture()
    before = _non_bearer(capture)
    restored = _mid_build_archive()
    control = tmp_path / "control.json"
    manifest = tmp_path / "manifest.json"
    control.write_text(json.dumps({"decision": "proceed"}), encoding="utf-8")
    manifest.write_text(json.dumps({"archive_id": str(restored.pk)}), encoding="utf-8")

    rehydrate_control_record(uuid.uuid4(), {
        "archive_id": str(restored.pk),
        "kind": kind,
        "control_record": str(control),
        "manifest": str(manifest),
    })

    assert _bearer(capture) == CLEARED_BEARER
    assert _non_bearer(capture) == before


def test_capture_makerspace_boundary_carries_the_whole_row_to_the_slice():
    dispositions = {
        rule.disposition
        for rule in boundary_rules(table_rules())
        if rule.source_model is TenantDumpCapture and rule.field.name == "makerspace"
    }
    assert dispositions == {BoundaryDisposition.DROP_ROW_TO_SLICE}


def test_tenant_dump_sweep_routes_to_default_database(monkeypatch):
    capture = _capture()
    manager = TenantDumpCapture.objects
    using = Mock(wraps=manager.using)
    monkeypatch.setattr(manager, "using", using)

    assert invalidate_download_tokens_after_restore(using="default") == 1

    using.assert_called_once_with("default")
    assert _bearer(capture) == CLEARED_BEARER


def test_tenant_dump_sweep_leaves_capture_without_token_unchanged():
    capture = _capture(token=False)
    queryset = TenantDumpCapture.objects.filter(pk=capture.pk)
    before = raw_records(queryset, TenantDumpCapture)

    assert invalidate_download_tokens_after_restore() == 0

    assert raw_records(queryset, TenantDumpCapture) == before
