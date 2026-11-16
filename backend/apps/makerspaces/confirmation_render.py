"""Render already-authorized fields. Domain adapters enforce visibility and ownership."""

from datetime import timezone
from io import BytesIO
from urllib.parse import urlencode

import segno
from PIL import Image, ImageDraw, ImageFont


def google_calendar_url(*, title, starts_at, ends_at, description="", location=""):
    def stamp(value):
        if value.tzinfo is None:
            raise ValueError("Calendar dates must be timezone-aware.")
        return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "https://calendar.google.com/calendar/render?" + urlencode({
        "action": "TEMPLATE", "text": title[:200],
        "dates": f"{stamp(starts_at)}/{stamp(ends_at)}",
        "details": description[:4000], "location": location[:255],
    })


def render_confirmation_png(*, qr_value, title, lines=()):
    if len(qr_value) > 512 or len(lines) > 8:
        raise ValueError("Confirmation render bounds exceeded.")
    qr_bytes = BytesIO()
    segno.make(qr_value, micro=False).save(qr_bytes, kind="png", scale=8, border=4)
    qr_bytes.seek(0)
    with Image.open(qr_bytes) as qr:
        qr = qr.convert("RGB")
        width = max(640, qr.width + 64)
        header_height = 100 + len(lines) * 24
        result = Image.new("RGB", (width, qr.height + header_height + 32), "white")
        result.paste(qr, ((width - qr.width) // 2, header_height))
    draw = ImageDraw.Draw(result)
    font = ImageFont.load_default(size=20)
    def label(value):
        text = " ".join(str(value).split())[:200]
        while text and draw.textlength(text, font=font) > width - 64:
            text = text[:-1]
        return text
    draw.text((32, 24), label(title), fill="black", font=font)
    for index, line in enumerate(lines):
        draw.text((32, 60 + index * 24), label(line), fill="black", font=font)
    output = BytesIO()
    result.save(output, format="PNG")
    return output.getvalue()
