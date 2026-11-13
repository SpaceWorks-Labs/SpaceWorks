"""The space's brand kit for the Card Studio (decision 344(b)): its own colours, the logo slots a design of this kind
can place, and the allow-listed fonts. Read-only and derived; nothing new is stored.

Colours come from the space's theme (`theme_config.primary_color` / `accent_color`, the same values the public page
uses) and are offered only when they are valid `#RGB`/`#RRGGBB` (normalised to `#RRGGBB`), so a swatch can never carry
anything a document would refuse. Logos stay slots (space, organisation, event, symbol): a document never holds a URL.
"""
import re

from django.utils.translation import gettext

from .fonts import STUDIO_FONTS

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _hex(value):
    if not isinstance(value, str) or not _HEX.match(value.strip()):
        return None
    value = value.strip()
    if len(value) == 4:
        value = "#" + "".join(ch * 2 for ch in value[1:])
    return value.upper()


def build(design):
    space = design.makerspace
    theme = space.theme_config if isinstance(space.theme_config, dict) else {}
    colours, seen = [], set()
    for key, label in (("primary_color", gettext("Space colour")), ("accent_color", gettext("Space accent"))):
        value = _hex(theme.get(key))
        if value and value not in seen:
            seen.add(value)
            colours.append({"label": label, "hex": value})
    logos = [{"source": "space", "label": gettext("The space's logo")}]
    if design.organization_id or design.domain == "id_programme":
        logos.append({"source": "organisation", "label": gettext("The organisation's logo")})
    if design.event_id or design.domain in ("event_card", "event_ticket"):
        logos.append({"source": "event", "label": gettext("The event's logo")})
    logos.append({"source": "symbol", "label": gettext("Space Works symbol")})
    return {"colours": colours, "logos": logos, "fonts": list(STUDIO_FONTS)}
