"""Server-side fetch of an open-catalogue font family into private storage (Q-I2).

Runs as a Celery task, never in a request. The server asks the catalogue's CSS
endpoint for static TrueType faces, downloads each, checks it parses as a font, and
stores it under `card-fonts/`. The browser only ever loads fonts from this app.
A deployment can point CARD_FONT_SOURCE_URL at a mirror, or switch downloads off
(CARD_FONT_DOWNLOADS_ENABLED=false) and keep to the bundled faces.
"""
import hashlib
import io
import logging
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .fonts import catalogue, is_bundled

logger = logging.getLogger(__name__)
MAX_FONT_BYTES = 40 * 1024 * 1024
_FACE = re.compile(r"font-weight:\s*(\d+);[^}]*?src:\s*url\((https://[^)]+\.ttf)\)", re.S)


def downloads_enabled():
    return bool(getattr(settings, "CARD_FONT_DOWNLOADS_ENABLED", True))


def request_family(family):
    """Queue every missing weight of a catalogue family; returns the weights now pending."""
    from .models import CardFont
    row = catalogue().get(family)
    if row is None or not downloads_enabled():
        return []
    pending = []
    for weight in row["weights"]:
        if is_bundled(family, weight):
            continue
        font, created = CardFont.objects.get_or_create(family=family, weight=weight)
        if created or font.state == CardFont.State.FAILED:
            if font.state == CardFont.State.FAILED:
                CardFont.objects.filter(pk=font.pk).update(state=CardFont.State.PENDING, error="")
            pending.append(weight)
    if pending:
        from .tasks import fetch_card_font_task
        transaction.on_commit(lambda: _dispatch(fetch_card_font_task, family), robust=True)
    return pending


def _dispatch(task, family):
    try:
        task.delay(family)
    except Exception:
        logger.warning("card_font_dispatch_failed", extra={"family": family})


def _css(family, weights):
    import httpx
    source = getattr(settings, "CARD_FONT_SOURCE_URL", "https://fonts.googleapis.com/css2")
    query = f"family={family.replace(' ', '+')}:wght@{';'.join(str(w) for w in sorted(weights))}"
    # A plain client asks for TrueType: the faces reportlab can embed.
    response = httpx.get(f"{source}?{query}", headers={"User-Agent": "SpaceWorks-card-fonts/1"}, timeout=20)
    response.raise_for_status()
    return {int(weight): url for weight, url in _FACE.findall(response.text)}


def _download(url):
    import httpx
    with httpx.stream("GET", url, timeout=60, follow_redirects=True) as response:
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > MAX_FONT_BYTES:
                raise ValueError("font_too_large")
            chunks.append(chunk)
    data = b"".join(chunks)
    from fontTools.ttLib import TTFont
    TTFont(io.BytesIO(data), lazy=True).close()
    return data


def fetch_family(family):
    from .font_store import object_key
    from .models import CardFont
    from .storage import put_bytes
    rows = list(CardFont.objects.filter(family=family, state=CardFont.State.PENDING))
    if not rows or not downloads_enabled():
        return 0
    try:
        urls = _css(family, [row.weight for row in rows])
    except Exception:
        CardFont.objects.filter(pk__in=[row.pk for row in rows]).update(state=CardFont.State.FAILED,
                                                                      error="catalogue_unreachable")
        return 0
    ready = 0
    for row in rows:
        url = urls.get(row.weight)
        try:
            if url is None:
                raise ValueError("weight_not_offered")
            data = _download(url)
            key = object_key(family, row.weight)
            put_bytes(key, data, "font/ttf")
        except Exception as exc:
            code = str(exc) if str(exc) in ("weight_not_offered", "font_too_large") else "download_failed"
            CardFont.objects.filter(pk=row.pk).update(state=CardFont.State.FAILED, error=code)
            continue
        CardFont.objects.filter(pk=row.pk).update(state=CardFont.State.READY, font_key=key, error="",
            sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data), fetched_at=timezone.now())
        ready += 1
    return ready


def state_of(family):
    """`ready`, `preparing`, `unavailable` or `bundled` for the designer's font picker."""
    from .fonts import family_weights
    from .models import CardFont
    weights = family_weights(family)
    if weights and all(is_bundled(family, weight) for weight in weights):
        return "bundled"
    states = set(CardFont.objects.filter(family=family).values_list("state", flat=True))
    if CardFont.State.PENDING in states:
        return "preparing"
    if CardFont.State.READY in states:
        return "ready"
    if any(is_bundled(family, weight) for weight in weights):
        return "bundled"
    return "unavailable" if CardFont.State.FAILED in states else "not_fetched"
