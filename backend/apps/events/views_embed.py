"""Backend-rendered event card for third-party pages: `GET /embed/<slug>/<token>/`.

Served from the API origin (no SPA, no rewrite on static frontend hosts). It is framable
only by the space's exact allow-list (`Content-Security-Policy: frame-ancestors`), off by
default, and never carries the join link. Sign-up and checkout always open the SPA in a
new tab; the card itself has no form.
"""

from zoneinfo import ZoneInfo

from django.http import Http404
from django.template.loader import render_to_string
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.http import HttpResponse

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.inventory import public_image_storage
from apps.makerspaces.public_page_access import canonical_origin

from .capacity import availability_label
from .embed_policy import framing_origins
from .website_visibility import resolve

MODE_LABELS = {"in_person": "In person", "online": "Online", "hybrid": "Hybrid"}


def _when(event):
    zone = ZoneInfo(event.timezone_name)
    start, end = timezone.localtime(event.starts_at, zone), timezone.localtime(event.ends_at, zone)
    same_day = start.date() == end.date()
    return (f"{start:%a %d %b %Y, %H:%M}–{end:%H:%M} {start:%Z}" if same_day
            else f"{start:%d %b %Y %H:%M} – {end:%d %b %Y %H:%M} {start:%Z}")


def embed_context(event):
    from .online_delivery import public_mode
    image_key = event.image_key
    if event.series_id and "image_key" not in (event.series_override_fields or []):
        image_key = event.series.image_key
    mode = public_mode(event)
    return {"title": event.title, "when": _when(event), "space": event.makerspace.name,
            "location": "" if mode == "online" else event.location,
            "mode": MODE_LABELS.get(mode or "", ""),
            "availability": availability_label(event) if event.capacity else "",
            "image_url": public_image_storage.public_url(image_key) or "",
            "event_url": f"{canonical_origin(event.makerspace)}/e/{event.public_token}"}


class EventEmbedView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(tags=["Public events"], auth=[], summary="Framable event card (HTML, not JSON)",
                   description="Self-contained HTML. 404 unless the space enabled embeds and the event is live.",
                   responses={(200, "text/html"): OpenApiResponse(str, description="Event card HTML."),
                              404: OpenApiResponse(ErrorSerializer, description="Unknown or unavailable."),
                              429: OpenApiResponse(ErrorSerializer, description="Rate limit exceeded.")})
    def get(self, request, makerspace_slug, public_token):
        event = resolve(makerspace_slug, public_token)
        origins = framing_origins(event.makerspace)
        if not origins:
            raise Http404
        html = render_to_string("events/embed.html", embed_context(event))
        response = HttpResponse(html, content_type="text/html; charset=utf-8")
        response.xframe_options_exempt = True
        response["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; img-src https: data:; base-uri 'none'; "
            "form-action 'none'; frame-ancestors " + " ".join(origins))
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        response["X-Robots-Tag"] = "noindex, nofollow"
        response["X-Content-Type-Options"] = "nosniff"
        return response
