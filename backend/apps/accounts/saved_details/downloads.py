"""Authenticated stream gateways recheck live account/record status per chunk."""
from django.utils.translation import gettext
from django.http import StreamingHttpResponse
from django.utils import timezone

from apps.encryption.account_readiness import assert_ready
from apps.makerspaces.private_upload_transport import (
    ObjectLocator, PrivateTransportError, bounded_not_after, resolve_range, stream_private,
)

from . import storage
from .access import owner_read_gate, require_owner
from .assets import owned_asset
from .errors import SavedDetailsError
from .models import AccountSavedDetailsExportJob


def stream_response(request, *, key, version_id, size, mime, filename, authorize, expires_at=None):
    assert_ready()
    authorize()
    try:
        selected = resolve_range(request.headers.get("Range"), size)
        auth = getattr(request, "auth", None)
        token_deadline = None
        if auth is not None and hasattr(auth, "get") and auth.get("exp"):
            from datetime import UTC, datetime
            token_deadline = datetime.fromtimestamp(auth["exp"], UTC)
        deadline = bounded_not_after(now=timezone.now(), purpose_max_seconds=120,
                                     limits=(expires_at, token_deadline))
    except PrivateTransportError as exc:
        from rest_framework.response import Response
        response = Response({"code": exc.code, "detail": gettext("Check the requested byte range."), "fields": {}}, status=exc.status)
        if exc.status == 416:
            response["Content-Range"] = f"bytes */{size}"
        response["Cache-Control"] = "private, no-store"
        return response
    stream = () if request.method == "HEAD" else stream_private(
        locator=ObjectLocator(bucket=storage.bucket(), key=key, version_id=version_id or None),
        byte_range=selected, reader=storage.read_range, authorize=authorize,
        clock=timezone.now, not_after=deadline,
    )
    response = StreamingHttpResponse(stream, content_type=mime, status=206 if selected.partial else 200)
    response["Content-Length"] = selected.length
    response["Accept-Ranges"] = "bytes"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    if selected.partial:
        response["Content-Range"] = selected.content_range
    return response


def resume_download(request, asset_id):
    actor_id = request.user.pk
    authorize_owner = owner_read_gate(actor_id)
    asset = owned_asset(actor_id, asset_id)

    def authorize():
        authorize_owner()
        current = owned_asset(actor_id, asset_id)
        from .asset_policy import require_ready
        require_ready(current)
        if current.state != "ready" or current.version != asset.version:
            raise SavedDetailsError("asset_not_ready", "This résumé is no longer available.", 409)
    return stream_response(request, key=asset.object_key, version_id=asset.final_version_id,
        size=asset.size_bytes, mime="application/pdf", filename="resume.pdf", authorize=authorize)


def own_export(actor_id, job_uuid):
    require_owner(actor_id)
    job = AccountSavedDetailsExportJob.objects.filter(user_id=actor_id, job_uuid=job_uuid).first()
    if job is None:
        raise SavedDetailsError("not_found", "Export not found.", 404)
    if job.expires_at <= timezone.now() or job.state == "expired":
        raise SavedDetailsError("export_expired", "Create a fresh export.", 410)
    return job


def export_download(request, job_uuid):
    authorize_owner = owner_read_gate(request.user.pk)
    job = own_export(request.user.pk, job_uuid)

    def authorize():
        authorize_owner()
        if own_export(request.user.pk, job_uuid).state != "ready":
            raise SavedDetailsError("export_not_ready", "Your export is still being prepared.", 409)
    return stream_response(request, key=job.object_key, version_id=None, size=job.size_bytes,
        mime="application/zip", filename="saved-details.zip", authorize=authorize, expires_at=job.expires_at)
