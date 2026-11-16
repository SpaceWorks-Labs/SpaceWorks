"""Per-event Open Graph / Twitter share image (L1, G5), rendered in the Space Works tokens.

`GET /api/v1/public/<slug>/events/<token>/share.png` serves a 1200x630 PNG for every
public event (each series occurrence is its own event). It runs the same access gate as
the event page, so a private, draft, ended or offline event is a 404, and an unlisted
one is served (people share unlisted links) with `noindex`. The PNG never carries the
join link, the venue address of an online event, or anything a public card hides.

Rendering is small, text-only Pillow work cached by the event's revision, so nothing
heavy happens per request (#133).
"""

from dataclasses import replace
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import textwrap

from django.core.cache import cache
from django.utils import timezone

WIDTH, HEIGHT = 1200, 630
FONTS = Path(__file__).resolve().parent / "certificates" / "fonts"
BG, PANEL, INK, MUTED, BRAND, ON_BRAND = (255, 244, 232), (255, 255, 255), (20, 44, 42), (91, 104, 99), \
    (0, 110, 99), (255, 255, 255)
MODE_LABELS = {"in_person": "In person", "online": "Online", "hybrid": "Hybrid"}
CACHE_SECONDS = 3600


def image_path(event):
    return f"/api/v1/public/{event.makerspace.slug}/events/{event.public_token}/share.png"


def with_share_image(card, event):
    """Give a cover-less share card the rendered event image instead of none."""
    if card.image_url:
        return card
    from apps.makerspaces.public_page_access import canonical_origin
    return replace(card, image_url=f"{canonical_origin(event.makerspace)}{image_path(event)}",
                   image_alt=f"{event.title} at {event.makerspace.name}")


def _font(name, size):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTS / name), size)


def _lines(event):
    from .online_delivery import public_mode
    zone = ZoneInfo(event.timezone_name)
    start = timezone.localtime(event.starts_at, zone)
    when = f"{start:%a %d %b %Y} · {start:%H:%M} {start.tzname()}"
    mode = public_mode(event)
    where = "Online" if mode == "online" else (event.location or event.makerspace.location or "")
    chip = MODE_LABELS.get(mode or "", "")
    return when, where[:80], chip


def revision(event):
    from .online_delivery import public_mode
    raw = "|".join(str(part) for part in (
        event.pk, event.title, event.starts_at.isoformat(), event.timezone_name, event.location,
        public_mode(event), event.makerspace.name, event.makerspace.location,
    ))
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def render_png(event):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((48, 48, WIDTH - 48, HEIGHT - 120), radius=28, fill=PANEL, outline=(213, 208, 198), width=2)
    draw.text((96, 92), event.makerspace.name[:60], font=_font("Outfit-600.ttf", 30), fill=MUTED)
    title_font = _font("Gilroy-ExtraBold.otf", 64)
    y = 150
    for line in textwrap.wrap(event.title, width=28)[:3]:
        draw.text((96, y), line, font=title_font, fill=INK)
        y += 76
    when, where, chip = _lines(event)
    detail_font = _font("Outfit-500.ttf", 32)
    draw.text((96, y + 18), when, font=detail_font, fill=INK)
    if where:
        draw.text((96, y + 66), where, font=detail_font, fill=MUTED)
    if chip:
        chip_font = _font("Outfit-600.ttf", 26)
        width = int(draw.textlength(chip, font=chip_font)) + 40
        draw.rounded_rectangle((WIDTH - 96 - width, 92, WIDTH - 96, 136), radius=22, fill=(224, 238, 236))
        draw.text((WIDTH - 96 - width + 20, 98), chip, font=chip_font, fill=INK)
    draw.rectangle((0, HEIGHT - 84, WIDTH, HEIGHT), fill=BRAND)
    # The layout's one Unbounded accent: the wordmark on the brand bar.
    draw.text((96, HEIGHT - 66), "SPACE WORKS", font=_font("Unbounded-700.ttf", 30), fill=ON_BRAND)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def share_png(event):
    """Cached PNG bytes for this event revision; a cache failure only costs a render."""
    key = f"event-share-png:v1:{revision(event)}"
    try:
        data = cache.get(key)
    except Exception:
        data = None
    if data is None:
        data = render_png(event)
        try:
            cache.set(key, data, CACHE_SECONDS)
        except Exception:
            pass
    return data
