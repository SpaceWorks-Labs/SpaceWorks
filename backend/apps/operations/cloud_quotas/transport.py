"""Free-only raw S3 writer admission, including per-part physical reservations."""
import uuid
from urllib.parse import unquote

from django.conf import settings

from apps.storage_capabilities.contracts import CapabilityError
from .storage import reserve_upload, finalized_upload, clear_pending, identity_for, pending_key

WRITES = {"PutObject", "CopyObject", "CreateMultipartUpload", "UploadPart", "UploadPartCopy"}


def before(client, params, *, model, context):
    name = model.name
    if name not in WRITES or context.get("is_presign_request"):
        return
    bucket, key = params["Bucket"], params["Key"]
    physical_key = key
    if name in {"CopyObject", "UploadPartCopy"}:
        size = _copy_size(client, params)
    elif name == "CreateMultipartUpload":
        # No bytes yet; charge a conservative metadata slot. Parts acquire their
        # own durable capacity before upload, so an unknown TOTAL is never free.
        size = 1
        physical_key = f"multipart-create:{key}:{uuid.uuid4()}"
    else:
        size = _body_size(params)
    maximum = getattr(settings, "FREE_MAX_PROMOTION_BYTES", 16777216)
    if size > maximum:
        raise CapabilityError("storage_free_external_job_required")
    if name in {"UploadPart", "UploadPartCopy"}:
        # A replayed part can leave an old part in flight. Never recycle its
        # allowance from the part number or an Abort/Complete response alone.
        physical_key = f"multipart-part:{key}:{params['UploadId']}:{params['PartNumber']}:{uuid.uuid4()}"
    identity = identity_for(client, bucket)
    explicit = pending_key(identity, physical_key) is not None
    reservation = reserve_upload(client, bucket=bucket, key=physical_key, max_bytes=max(size, 1), ttl=60, server_owned=True)
    _claim(reservation)
    context["cloud_accounting"] = {"bucket": bucket, "key": physical_key, "size": size,
        "identity": identity, "operation": name, "explicit": explicit, "token": uuid.uuid4().hex,
        "reservation_id": reservation}


def after(client, *, parsed, http_response, context, **unused):
    entry = context.get("cloud_accounting")
    if entry is None:
        return
    success = 200 <= http_response.status_code < 300 and "Error" not in parsed
    if not success:
        _uncertain(entry)
    settled = False
    try:
        if success and entry["operation"] in {"PutObject", "CopyObject"}:
            finalized_upload(client, bucket=entry["bucket"], key=entry["key"], size=entry["size"],
                operation_key="s3-write:" + entry["token"], keep_pending=entry["explicit"], reservation_id=entry["reservation_id"])
            settled = True
        # Multipart reservations stay charged through successful parts, Complete
        # and Abort. Only drained physical inventory may reconcile them.
    finally:
        if not settled or not entry["explicit"]:
            clear_pending(entry["identity"], entry["key"])


def failed(*, context, **unused):
    entry = context.get("cloud_accounting")
    if entry:
        _uncertain(entry)
        clear_pending(entry["identity"], entry["key"])


def _uncertain(entry):
    from .database import accounting_transaction
    from apps.operations.models import CloudObjectReservation
    with accounting_transaction():
        CloudObjectReservation.objects.filter(pk=entry["reservation_id"], state__in=["reserved", "writing"]).update(state="uncertain")


def _claim(reservation_id):
    from .database import accounting_transaction
    from apps.operations.models import CloudObjectReservation
    with accounting_transaction():
        if CloudObjectReservation.objects.filter(pk=reservation_id, state="reserved").update(state="writing") != 1:
            raise CapabilityError("storage_write_reservation_already_claimed")


def _body_size(params):
    body = params.get("Body", b"")
    if isinstance(body, str):
        size = len(body.encode())
    elif isinstance(body, (bytes, bytearray, memoryview)):
        size = len(body)
    else:
        try:
            position = body.tell()
            body.seek(0, 2)
            size = body.tell() - position
            body.seek(position)
        except (AttributeError, OSError, ValueError):
            raise CapabilityError("storage_free_stream_size_unknown") from None
    declared = params.get("ContentLength", size)
    if type(declared) is not int or declared != size or size < 0:
        raise CapabilityError("storage_write_length_mismatch")
    return size


def _copy_size(client, params):
    source = params.get("CopySource")
    if isinstance(source, str):
        bucket, separator, key = unquote(source).lstrip("/").partition("/")
        if not separator or "?" in key:
            raise CapabilityError("storage_copy_source_invalid")
        source = {"Bucket": bucket, "Key": key}
    if not isinstance(source, dict) or set(source) - {"Bucket", "Key", "VersionId"} or not {"Bucket", "Key"} <= source.keys():
        raise CapabilityError("storage_copy_source_invalid")
    head = client.head_object(**source)
    size = head.get("ContentLength")
    if type(size) is not int or size < 0:
        raise CapabilityError("storage_copy_size_unknown")
    requested = params.get("CopySourceRange")
    if requested is not None:
        import re
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", requested)
        if match is None:
            raise CapabilityError("storage_copy_range_invalid")
        start, end = map(int, match.groups())
        if not 0 <= start <= end < size:
            raise CapabilityError("storage_copy_range_invalid")
        size = end - start + 1
    # Pin the actual measured source snapshot for the write that follows.
    if not source.get("VersionId"):
        if not head.get("ETag"):
            raise CapabilityError("storage_copy_snapshot_unavailable")
        params["CopySourceIfMatch"] = head["ETag"]
    return size
