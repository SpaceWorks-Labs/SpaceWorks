"""Space Works broadcast designs: one fixed HTML frame per design, brand tokens only.

Every design receives already-escaped HTML fragments. The only per-campaign values a frame
adds are the escaped organiser name (letter signature) and an escaped public cover URL
(photo header); neither is a placeholder an author can type.
"""

from django.utils.translation import gettext
import html

DESIGNS = ("classic", "bold", "minimal", "accent_band", "photo_header", "letter")
# The three newer designs ride `events.broadcast_templates`; saved campaigns keep rendering.
TEMPLATE_DESIGNS = frozenset({"accent_band", "photo_header", "letter"})


def require_design_allowed(makerspace, design):
    from rest_framework.exceptions import ValidationError
    from apps.makerspaces.platform import feature_enabled
    if design in TEMPLATE_DESIGNS and not feature_enabled(makerspace, "events.broadcast_templates"):
        raise ValidationError({"design": gettext("This design needs broadcast templates switched on.")})

# Brand colours (docs/brand/README.md): Deep Ink, Maker Teal, Workshop Orange, Citron,
# Sky Blue and Warm Cream. Light/dark pairs keep the documented contrast pairs.
ACCENTS = {"classic": "#006E63", "bold": "#FF7447", "minimal": "#142C2A",
           "accent_band": "#006E63", "photo_header": "#B5CDFF", "letter": "#142C2A"}

FRAMES = {
    "classic": "main{border-top:6px solid var(--accent);padding-top:24px;}",
    "bold": "main{border:3px solid var(--accent);padding:24px;}",
    "minimal": "main{border-bottom:2px solid var(--accent);padding-bottom:24px;}",
    "accent_band": (".band{background:var(--accent);color:var(--on-accent);padding:24px;border-radius:16px 16px 0 0;}"
                    ".band h1{margin:0;color:var(--on-accent);}.band header{color:var(--on-accent);}"
                    ".body{padding:24px;border:2px solid var(--accent);border-top:0;border-radius:0 0 16px 16px;}"),
    "photo_header": (".cover{display:block;width:100%;height:auto;max-height:280px;object-fit:cover;"
                     "border-radius:16px;}.cover-fallback{height:96px;border-radius:16px;background:var(--accent);}"
                     ".body{padding-top:16px;}"),
    "letter": ("main{padding:32px 8px;}.salutation{font-weight:600;}"
               ".signature{margin-top:32px;padding-top:16px;border-top:1px solid var(--ink);font-weight:600;}"),
}

DARK = {"accent_band": "--accent:#DFFF8F;--on-accent:#142C2A;",
        "photo_header": "--accent:#B5CDFF;"}


def _body(design, *, title_html, message_html, links_html, organization, cover_url):
    brand = "<header>Space Works</header>"
    if design == "accent_band":
        return (f'<div class="band">{brand}<h1>{title_html}</h1></div>'
                f'<div class="body">{message_html}{links_html}</div>')
    if design == "photo_header":
        media = (f'<img class="cover" alt="" src="{html.escape(cover_url, quote=True)}">' if cover_url
                 else '<div class="cover-fallback" aria-hidden="true"></div>')
        return f'{media}<div class="body">{brand}<h1>{title_html}</h1>{message_html}{links_html}</div>'
    if design == "letter":
        signature = html.escape(organization or "Space Works")
        return (f'<header>{signature}</header><h1>{title_html}</h1>{message_html}{links_html}'
                f'<p class="signature">{signature}</p>')
    return f"{brand}<h1>{title_html}</h1>{message_html}{links_html}"


def document(design, *, fonts, width, title_html, message_html, links_html, organization="", cover_url=""):
    if design not in DESIGNS:
        raise ValueError("Unsupported broadcast design")
    if width not in {360, 640}:
        raise ValueError("Unsupported composer preview width")
    dark = DARK.get(design, "--accent:#DFFF8F;")
    content = _body(design, title_html=title_html, message_html=message_html, links_html=links_html,
                    organization=organization, cover_url=cover_url)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<style>' + fonts + ':root{color-scheme:light dark;--paper:#FFF4E8;--ink:#142C2A;--accent:'
        + ACCENTS[design] + ';--on-accent:#FFF4E8;}'
        '@media(prefers-color-scheme:dark){:root{--paper:#142C2A;--ink:#FFF4E8;' + dark + '}}'
        'body{margin:0;padding:24px;background:var(--paper);color:var(--ink);font:400 16px Gilroy;}'
        'main{max-width:' + str(width) + 'px;margin:auto;}'
        'h1{font-weight:700;font-size:24px;}p{line-height:1.6;overflow-wrap:anywhere;}'
        'a{color:var(--ink);text-decoration:underline;font-weight:600;}'
        'header{font-weight:700;}' + FRAMES[design] + '</style></head><body><main>' + content
        + '</main></body></html>')
