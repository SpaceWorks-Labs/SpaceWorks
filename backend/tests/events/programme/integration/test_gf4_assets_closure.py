"""Runtime regressions for the actual GF4 asset, default and purge seams."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from django.db import connection, transaction, IntegrityError
from django.utils import timezone
from apps.events.submissions.policy_adapter import require_policy
from apps.events.submissions.errors import SubmissionError


def test_unknown_or_unversioned_upload_policy_refuses():
    require_policy("hackathon-maker-v1", 1)
    for name, version in (("maker", 1), ("future", 1), ("hackathon-maker-v1", 2), ("hackathon-maker-v1", True)):
        with pytest.raises(SubmissionError):
            require_policy(name, version)


def test_gallery_http_delegates_exact_opaque_identity_for_get_head_and_range(monkeypatch):
    from apps.events.submissions import views_downloads, gallery_projection
    from rest_framework.test import APIRequestFactory
    from django.http import HttpResponse
    calls = []
    def download(token, opaque_id, *, request):
        calls.append((token, opaque_id, request.method, request.headers.get("Range")))
        return HttpResponse(b"ok")
    monkeypatch.setattr(gallery_projection, "asset_download", download)
    # The numeric public reader is intentionally unavailable. The view must not
    # resolve through it even if another publication later consents the same asset.
    monkeypatch.setattr(views_downloads, "runtime", Mock(side_effect=AssertionError("numeric gallery bypass")))
    factory = APIRequestFactory()
    for method, headers in (("get", {}), ("head", {}), ("get", {"HTTP_RANGE": "bytes=0-1"})):
        request = getattr(factory, method)("/", **headers)
        response = views_downloads.GalleryAssetView.as_view()(request, public_token=uuid4(), public_asset_id=uuid4())
        assert response.status_code == 200
    assert [c[2] for c in calls] == ["GET", "HEAD", "GET"]
    assert calls[-1][3] == "bytes=0-1"


@pytest.mark.django_db(transaction=True)
def test_print_cleanup_custody_survives_actual_tenant_delete_and_repeats(monkeypatch):
    from apps.events.certificates import print_custody
    from apps.events.certificates.print_models import BadgePrintCleanupReceipt
    from tests.events.programme.uploads.test_retained_recovery import normal
    from tests.events.ticketing_helpers import event_space
    from apps.makerspaces.models import Makerspace
    normal()
    space = event_space("gf4-print-purge")
    tenant_id = space.pk
    row = BadgePrintCleanupReceipt.objects.create(makerspace_id_snapshot=tenant_id,
        event_id_snapshot=999, object_key="events/badge-print/purged.pdf", size_bytes=100,
        not_before=timezone.now()-timedelta(minutes=1), next_attempt_at=timezone.now()-timedelta(minutes=1))
    # This receipt has no FK and survives deletion of the tenant itself. The tenant
    # fence is PROTECTed; delete it the way the purge path does (scoped GUC).
    from apps.encryption.models import PiiMakerspaceWriteFence
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        PiiMakerspaceWriteFence.objects.filter(makerspace_id=tenant_id).delete()
        space.delete()
    assert not Makerspace.objects.filter(pk=tenant_id).exists()
    calls = []
    def delete(key):
        assert not connection.in_atomic_block
        calls.append(key)
    monkeypatch.setattr(print_custody.print_storage, "delete", delete)
    monkeypatch.setattr(print_custody.limits, "free_storage", Mock(side_effect=AssertionError("tenant already absent")))
    assert print_custody.cleanup_receipt(row.pk)
    row.refresh_from_db()
    assert row.released and row.cleaned_at
    BadgePrintCleanupReceipt.objects.filter(pk=row.pk).update(next_attempt_at=timezone.now()-timedelta(minutes=1))
    assert print_custody.cleanup_receipt(row.pk)
    assert calls == [row.object_key, row.object_key]
    with pytest.raises(Exception), transaction.atomic():
        BadgePrintCleanupReceipt.objects.filter(pk=row.pk).delete()


@pytest.mark.django_db(transaction=True)
def test_page_programme_kinds_have_closed_persisted_options():
    from apps.events.serializers_website import WebsiteSectionInput
    valid = {"kind": "prizes", "slug": "prizes", "title": "Awards", "options": {"ids": [7], "layout": "grid", "limit": 10}}
    serializer = WebsiteSectionInput(data=valid)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["options"]["ids"] == [7]
    for options in ({"secret_query": "users"}, {"ids": [7, 7]}, {"layout": "unsafe"}, {"limit": 101}):
        assert not WebsiteSectionInput(data={**valid, "options": options}).is_valid()


def test_print_cleanup_refuses_unsupported_version_listing_and_surviving_versions(monkeypatch):
    from apps.events.certificates import print_storage
    from botocore.exceptions import ClientError
    client = Mock()
    client.get_paginator.side_effect = ClientError({"Error": {"Code": "NotImplemented"}}, "ListObjectVersions")
    monkeypatch.setattr(print_storage, "_client", lambda endpoint: client)
    with pytest.raises(print_storage.PrintStorageUnavailable):
        print_storage.delete("print/key")
    client.delete_object.assert_not_called()
    client.get_paginator.side_effect = None
    versions = Mock()
    versions.paginate.return_value = [{"Versions": [{"Key": "print/key", "VersionId": "still-live"}]}]
    uploads = Mock()
    uploads.paginate.return_value = []
    client.get_paginator.side_effect = lambda operation: versions if operation == "list_object_versions" else uploads
    client.delete_objects.return_value = {}
    with pytest.raises(print_storage.PrintStorageUnavailable):
        print_storage.delete("print/key")
