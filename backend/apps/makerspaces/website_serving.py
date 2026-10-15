"""Safe shared HTML/image projections; adapters supply authorized public data."""

from dataclasses import dataclass, asdict
import hashlib
import json

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.utils.html import escape

from apps.evidence import storage
from .website_origins import validate_origins


@dataclass(frozen=True)
class PublicCard:
    title: str
    description: str
    url: str
    image_url: str | None
    date: str
    location: str
    availability: str
    audience_label: str
    revision: str
    registration_count: int | None = None
    makerspace_name: str = ""


def private_image_response(key):
    from .website_assets import MAX_BYTES
    try:
        size = storage.object_size(key)
        if size is None or not 0 < size <= MAX_BYTES:
            raise Http404
        result = storage._client().get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
        with result["Body"] as body:
            data = body.read(MAX_BYTES + 1)
        if len(data) != size:
            raise storage.StorageUnavailable
    except (BotoCoreError, ClientError, OSError, storage.StorageUnavailable):
        return HttpResponse("Image storage is unavailable.", status=503)
    response = HttpResponse(data, content_type="image/webp")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def embed_response(card, origins):
    from rest_framework.exceptions import ValidationError
    try:
        origins = validate_origins(origins)
    except ValidationError as exc:
        raise Http404 from exc
    if not origins:
        raise Http404
    e = escape
    html = (f'<!doctype html><html lang="en"><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(card.title)}</title><main><h1>{e(card.title)}</h1>'
            f'<p>{e(card.date)}</p><p>{e(card.location)}</p>'
            f'<p>{e(card.availability)}</p><p>{e(card.audience_label)}</p>'
            f'<a href="{e(card.url)}" target="_blank" rel="noopener noreferrer">Register</a></main></html>')
    response = HttpResponse(html)
    response.xframe_options_exempt = True
    response["Content-Security-Policy"] = "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors " + " ".join(origins)
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


def share_response(card):
    # Always called AFTER live visibility/origin checks. A stale cache cannot revive a page.
    digest = hashlib.sha256(json.dumps(asdict(card), sort_keys=True).encode()).hexdigest()
    key = f"website-share:v1:{digest}"
    html = cache.get(key)
    if html is None:
        e = escape
        meta = {"og:type": "website", "og:title": card.title, "og:description": card.description,
                "og:url": card.url, "twitter:card": "summary_large_image" if card.image_url else "summary",
                "twitter:title": card.title, "twitter:description": card.description}
        if card.image_url:
            meta.update({"og:image": card.image_url, "twitter:image": card.image_url})
        tags = "".join(f'<meta {"name" if name.startswith("twitter:") else "property"}="{e(name)}" content="{e(value)}">' for name, value in meta.items())
        html = (f'<!doctype html><html lang="en"><meta charset="utf-8"><title>{e(card.title)}</title>'
                f'<meta name="robots" content="noindex">{tags}<a href="{e(card.url)}">{e(card.title)}</a></html>')
        cache.set(key, html, 600)
    response = HttpResponse(html)
    response["Cache-Control"] = "no-cache"
    response["X-Robots-Tag"] = "noindex"
    response["Referrer-Policy"] = "strict-origin"
    return response
