"""HTTP range/HEAD adapter with per-chunk policy rechecks and no redirects."""
from urllib.parse import quote

from django.http import StreamingHttpResponse, HttpResponse
from django.utils import timezone

from apps.makerspaces.private_upload_transport import (
    resolve_range, stream_private, bounded_not_after, PrivateTransportError,
)


def download_response(*, request, reader, storage_reader, actor_id, asset_id, snapshot_id, purpose):
    def current():
        return reader.authorize_read(actor_id=actor_id, asset_id=asset_id,
                                     snapshot_id=snapshot_id, purpose=purpose)
    asset = current()  # Auth before range errors and before any storage, including HEAD.
    try:
        selected = resolve_range(request.headers.get("Range"), asset.size)
        not_after = bounded_not_after(now=timezone.now(), purpose_max_seconds=3600, limits=asset.limits)
    except PrivateTransportError as exc:
        response = HttpResponse(status=exc.status)
        if exc.status == 416:
            response["Content-Range"] = f"bytes */{asset.size}"
    else:
        status = 206 if selected.partial else 200
        def authorize():
            latest = current()
            # A row can never silently switch this response's immutable content.
            if latest.locator != asset.locator or latest.size != asset.size:
                raise PrivateTransportError("not_found", 404)
        response = HttpResponse(status=status) if request.method == "HEAD" else StreamingHttpResponse(
            stream_private(locator=asset.locator, byte_range=selected, reader=storage_reader,
                authorize=authorize, clock=timezone.now, not_after=not_after), status=status)
        response["Content-Type"], response["Content-Length"] = asset.mime, str(selected.length)
        response["Accept-Ranges"] = "bytes"
        if selected.partial:
            response["Content-Range"] = selected.content_range
        # All originals are attachments, including SVG/source/archives. Media
        # previews use an authenticated fetch/blob in a separate isolated viewer.
        response["Content-Disposition"] = "attachment; filename=download; filename*=UTF-8''" + quote(asset.filename, safe="")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox; default-src 'none'"
    return response
