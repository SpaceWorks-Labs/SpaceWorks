"""Actual PDF/JPEG/PNG/HEIC decoder and immutable S3 adapter acceptance.

Not runnable on the restricted host. G adds pillow-heif to backend requirements;
no decoder or HEIC test is silently skipped when it is missing.
"""
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
from unittest.mock import Mock
import pytest
from PIL import Image
from pypdf import PdfWriter
from pillow_heif import from_pillow
from botocore.exceptions import ClientError
from django.utils import timezone
from apps.payments.event_payouts.attachment_content import ContentError, validate
from apps.payments.event_payouts.attachment_storage import FinanceStorage
from apps.makerspaces.private_upload_transport import ObjectLocator, UploadRequest, PrivateTransportError


@pytest.mark.parametrize("kind,mime", [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("HEIC", "image/heic"), ("PDF", "application/pdf")])
def test_real_small_samples_and_declared_mime_binding(kind, mime):
    buffer = BytesIO()
    if kind == "PDF":
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(buffer)
    elif kind == "HEIC":
        from_pillow(Image.new("RGB", (4, 4), "blue")).save(buffer)
    else:
        Image.new("RGB", (4, 4), "blue").save(buffer, format=kind)
    data = buffer.getvalue()
    assert validate(data, declared_mime=mime, purpose="reimbursement_receipt") == mime
    with pytest.raises(ContentError):
        validate(data, declared_mime="image/png" if mime != "image/png" else "image/jpeg", purpose="reimbursement_receipt")
    if kind == "HEIC":
        with pytest.raises(ContentError):
            validate(data, declared_mime=mime, purpose="reimbursement_payee_document")


def test_extension_like_html_executable_archive_and_truncated_pdf_are_refused():
    for data in (b"<html>private</html>", b"MZ\x00\x00", b"PK\x03\x04archive", b"%PDF-1.7\n%%EOF"):
        with pytest.raises(ContentError):
            validate(data, declared_mime="application/pdf", purpose="reimbursement_receipt")


def test_presign_only_exact_sized_staging_and_at_most_fifteen_minutes():
    sdk, browser = Mock(), Mock()
    browser.generate_presigned_post.return_value = {"url": "http://minio/upload", "fields": {"key": "opaque/staging"}}
    storage = FinanceStorage(sdk=sdk, browser=browser, bucket_name="private")
    storage.initialize(UploadRequest(staging=ObjectLocator(bucket="private", key="opaque/staging"), generation=1,
        mime="application/pdf", size_bytes=100, not_after=timezone.now() + timedelta(hours=1)))
    args = browser.generate_presigned_post.call_args.kwargs
    assert args["Key"] == "opaque/staging" and args["ExpiresIn"] <= 900
    assert ["content-length-range", 100, 100] in args["Conditions"]
    assert not sdk.put_object.called


def test_promotion_never_overwrites_a_remaining_presign_or_different_final():
    sdk = Mock()
    sdk.put_object.side_effect = ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
    sdk.head_object.return_value = {"ETag": "etag", "VersionId": "final-1", "ContentLength": 3}
    body = Mock()
    body.read.return_value = b"old"
    sdk.get_object.return_value = {"Body": body}
    storage = FinanceStorage(sdk=sdk, bucket_name="private")
    with pytest.raises(PrivateTransportError):
        storage.promote(key="opaque/final", data=b"new", mime="application/pdf", digest=sha256(b"new").hexdigest())
    assert sdk.put_object.call_args.kwargs["IfNoneMatch"] == "*"
    assert sdk.get_object.call_args.kwargs["VersionId"] == "final-1"


def test_all_versions_and_markers_deleted_without_touching_prefix_neighbor():
    sdk = Mock()
    sdk.list_object_versions.side_effect = [
        {"Versions": [{"Key": "key", "VersionId": "v1"}, {"Key": "key-neighbor", "VersionId": "other"}],
         "IsTruncated": True, "NextKeyMarker": "key", "NextVersionIdMarker": "v1"},
        {"Versions": [{"Key": "key", "VersionId": "v2"}], "DeleteMarkers": [{"Key": "key", "VersionId": "marker"}]},
        # The shared deletion helper then proves the exact key is gone (cloud lane).
        {"Versions": [{"Key": "key-neighbor", "VersionId": "other"}]}]
    sdk.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")
    sdk.delete_objects.return_value = {}
    FinanceStorage(sdk=sdk, bucket_name="private").delete("key")
    # The shared helper deletes page by page; every exact version is removed, never the neighbor.
    deleted = [item for call in sdk.delete_objects.call_args_list for item in call.kwargs["Delete"]["Objects"]]
    assert deleted == [
        {"Key": "key", "VersionId": "v1"}, {"Key": "key", "VersionId": "v2"}, {"Key": "key", "VersionId": "marker"}]


def test_listing_unavailable_is_retried_not_silently_downgraded_to_latest_delete():
    sdk = Mock()
    sdk.list_object_versions.side_effect = ClientError({"Error": {"Code": "NotImplemented"}}, "ListObjectVersions")
    with pytest.raises(ClientError):
        FinanceStorage(sdk=sdk, bucket_name="private").delete("key")
    assert not sdk.delete_object.called
