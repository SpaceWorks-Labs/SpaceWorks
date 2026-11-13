"""E HTTP adapter over G's shared range/revocation transport, never a redirect."""
from django.utils.translation import gettext
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from rest_framework.response import Response
from apps.makerspaces.private_upload_transport import (
    ObjectLocator, PrivateTransportError, resolve_range, stream_private,
)


def private_bytes(request, content, *, authorize, expires_at, mime, locator_key, filename=None):
    authorize()
    try:
        selected = resolve_range(request.headers.get("Range"), len(content))
    except PrivateTransportError as exc:
        response = Response({"detail": gettext("Requested range cannot be satisfied."), "code": exc.code}, status=exc.status)
        response["Content-Range"] = f"bytes */{len(content)}"
    else:
        iterator = stream_private(locator=ObjectLocator(bucket="prepared-event-render", key=locator_key),
            byte_range=selected, reader=lambda locator, start, length, timeout_seconds: content[start:start+length],
            authorize=authorize, clock=timezone.now, not_after=expires_at)
        response = (HttpResponse(content_type=mime) if request.method == "HEAD" else
                    StreamingHttpResponse(iterator, content_type=mime))
        response.status_code = 206 if selected.partial else 200
        response["Content-Length"] = str(selected.length)
        response["Accept-Ranges"] = "bytes"
        if selected.partial:
            response["Content-Range"] = selected.content_range
        if filename:
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
