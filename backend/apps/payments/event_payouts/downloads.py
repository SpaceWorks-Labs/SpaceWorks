"""Finance-only originals, no reusable download URL or owner byte-read route."""
from urllib.parse import quote
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.accounts.models import User
from apps.audit.services import record
from apps.makerspaces.models import Makerspace
from apps.makerspaces.private_upload_transport import ObjectLocator, resolve_range, stream_private, bounded_not_after, PrivateTransportError
from apps.tenant_migration.gate_runtime import assert_write_allowed, boundary_tenant_write
from .attachment_models import FinanceAttachment
from .attachment_policy import PURPOSES
from .attachment_storage import FinanceStorage, asset_bucket
from .authority import authorize
from .errors import require


def authorized(request, *, makerspace_id, asset_id):
    # Re-fetch on EVERY stream authorization. No actor/host/role positive cache.
    request.user = User.objects.get(pk=request.user.pk)
    space = get_object_or_404(Makerspace, pk=makerspace_id)
    authorize(request, space)
    assert_write_allowed(space.pk)
    row = get_object_or_404(FinanceAttachment, pk=asset_id, makerspace=space)
    require(row.purpose in PURPOSES, "not_found", status=404)
    require(row.state not in ("expired", "deleting", "deleted") and row.expired_at is None,
            "asset_expired", status=410)
    held = bool(row.legal_hold_reason_code or row.legal_hold_until)
    if row.obligation_id:
        from .eligibility_workflow import retention_held
        held = held or retention_held(row.obligation)
    require(held or row.expires_at is None or timezone.now() < row.expires_at, "asset_expired", status=410)
    require(row.state in ("ready", "attached") and row.scan_status in ("clean", "skipped")
        and row.actual_bytes == row.expected_bytes and row.sha256, "asset_not_ready")
    return row, held


def response(*, request, makerspace_id, asset_id, storage=None):
    row, held = authorized(request, makerspace_id=makerspace_id, asset_id=asset_id)
    bucket_name = asset_bucket(row.pk)
    storage = storage or FinanceStorage(bucket_name=bucket_name)
    # Audit is a write with the same source boundary, even for GET and HEAD.
    with boundary_tenant_write(makerspace_id):
        authorized(request, makerspace_id=makerspace_id, asset_id=asset_id)
        record(request.user, "finance.attachment.opened", makerspace=row.makerspace, target=row,
               meta={"asset_id": row.pk, "purpose": PURPOSES[row.purpose].value, "generation": row.generation})
    locator = ObjectLocator(bucket=bucket_name, key=row.object_key, version_id=row.final_version_id or None)
    try:
        selected = resolve_range(request.headers.get("Range"), row.actual_bytes)
        not_after = bounded_not_after(now=timezone.now(), purpose_max_seconds=3600,
                                      limits=(() if held else (row.expires_at,)))
    except PrivateTransportError as exc:
        result = HttpResponse(status=exc.status)
        if exc.status == 416:
            result["Content-Range"] = f"bytes */{row.actual_bytes}"
    else:
        def recheck():
            fresh, _ = authorized(request, makerspace_id=makerspace_id, asset_id=asset_id)
            require((fresh.object_key, fresh.final_version_id, fresh.sha256, fresh.generation, fresh.actual_bytes) == (
                row.object_key, row.final_version_id, row.sha256, row.generation, row.actual_bytes), "attachment_changed")
        result = HttpResponse(status=206 if selected.partial else 200) if request.method == "HEAD" else StreamingHttpResponse(
            stream_private(locator=locator, byte_range=selected, reader=storage.reader, authorize=recheck,
                clock=timezone.now, not_after=not_after), status=206 if selected.partial else 200)
        result["Content-Type"], result["Content-Length"] = row.canonical_mime, str(selected.length)
        result["Accept-Ranges"] = "bytes"
        if selected.partial:
            result["Content-Range"] = selected.content_range
        result["Content-Disposition"] = "attachment; filename=finance-document; filename*=UTF-8''" + quote(row.original_filename, safe="")
    result["Cache-Control"] = "private, no-store"
    result["X-Content-Type-Options"] = "nosniff"
    result["Content-Security-Policy"] = "sandbox; default-src 'none'"
    return result
