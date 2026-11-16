"""Compile badge settings (`badge_v1`) into front-side free-canvas layers (E-B1).

`compile_front(settings)` is the only way `badge_v1` layers come to exist: the server recompiles on every
save, so a client cannot smuggle layers in. Each Events item becomes one or more v2 layers; the maths is
`badge_geometry.py`. Layer ids are stable `uuid5` values (same settings -> byte-identical layers), which is
what lets the TypeScript twin be checked against `fixtures/badge_compile_cases.json`.

Mapping notes (see the lane report): the name is a shrink-to-fit `{{name}}` field (one line down to 60 %, as
in Events); answers are label/value layer pairs; the QR is the `checkin_qr` kind and is never smaller than the
stock's scan minimum; sponsors are `logo` layers `sponsor_1..sponsor_6` on a white strip.
"""
from uuid import NAMESPACE_URL, uuid5

from django.utils.translation import gettext

from . import badge_geometry as geo
from . import badge_palette
from . import stocks
from .badge_format import CREW_KIND_FIELD_KEY, TEAM_FIELD_KEY
from .data_fields import ANSWER_PREFIX, valid_tag

PHOTO_SYMBOL_ASPECT = 136 / 126
SPONSOR_GAP_MM = 2.0
_NS = "spaceworks:badge_v1:"


def stock_for(width, height):
    """A named stock when the size matches one, else custom (dimensions rounded to 0.1 mm)."""
    for key, (w, h) in stocks.STOCKS.items():
        if abs(w - width) < 0.05 and abs(h - height) < 0.05:
            return key, w, h
    return stocks.CUSTOM, geo.r1(width), geo.r1(height)


def field_tag(key):
    """A settings field key (`registration:<k>`, `<k>`, `attendee:team`) -> a data-field tag, or None."""
    if key == TEAM_FIELD_KEY:
        return "team"
    if key == CREW_KIND_FIELD_KEY:
        return "crew_kind"
    tag = ANSWER_PREFIX + (key[len("registration:"):] if key.startswith("registration:") else key)
    return tag if valid_tag(tag) else None


def default_label(key):
    if key == TEAM_FIELD_KEY:
        return gettext("Team")
    if key == CREW_KIND_FIELD_KEY:
        return gettext("Role")
    name = key.split(":", 1)[-1].replace("_", " ").strip()
    return name[:1].upper() + name[1:]


def _braceless(value):
    return str(value).replace("{", "").replace("}", "")


class _Builder:
    def __init__(self, width, height):
        self.width, self.height, self.layers = width, height, []

    def add(self, kind, key, name, x, y, w, h, **extra):
        w = geo.clamp(w, 0.5, self.width)
        h = geo.clamp(h, 0.3, self.height)
        x = geo.clamp(x, 0.0, self.width - w)
        y = geo.clamp(y, 0.0, self.height - h)
        self.layers.append({"id": str(uuid5(NAMESPACE_URL, _NS + key)), "kind": kind, "name": name[:40],
                            "x_mm": round(x, 2), "y_mm": round(y, 2), "w_mm": round(w, 2), "h_mm": round(h, 2),
                            "rotation": 0, "opacity": 100, "locked": False, "hidden": False, **extra})

    def text(self, key, name, x, y, w, h, *, pt, colour, text=None, field=None, bold=False, align="left",
             tracking_em=0.0, upper=False, shrink=True):
        size = geo.clamp(pt, 6.0, 96.0)
        row = {"font_family": "Outfit", "font_weight": 700 if bold else 400, "font_size_pt": size, "align": align,
               "valign": "top", "colour": colour, "uppercase": upper,
               "tracking_pt": geo.clamp(round(tracking_em * size, 2), -2.0, 10.0),
               "line_height": geo.LINE_HEIGHT["body"], "shrink_to_fit": shrink}
        if field:
            self.add("data_field", key, name, x, y, w, h, field=field, **row)
        else:
            self.add("text", key, name, x, y, w, h, text=text, **row)


def _line(pt, kind="body"):
    return pt * geo.PT_TO_MM * geo.LINE_HEIGHT[kind]


def _header(build, settings, palette, at, size, pt, bold, decor):
    label = settings["badgeLabel"] if settings["showBadgeLabel"] else ""
    heading = settings["heading"]
    if not (label.strip() or heading.strip()):
        return
    band = decor["band"]
    x = at["header"]["xMm"] + (band["padX"] if band else 0)
    width = size["header"] - (2 * band["padX"] if band else 0)
    cursor = at["header"]["yMm"] + (band["padY"] if band else 0)
    colour = palette["on_accent"] if band else palette["heading"]
    label_pt = geo.badge_label_pt(pt["header"])
    label_h, heading_h = _line(label_pt, "label"), _line(pt["header"], "heading")
    top = cursor
    cursor += (label_h + decor["labelGap"] if label.strip() else 0) + (heading_h if heading.strip() else 0)
    if band:
        build.add("band", "header-band", "Heading band", at["header"]["xMm"], at["header"]["yMm"], size["header"],
                  cursor + band["padY"] - at["header"]["yMm"], fill=palette["accent"], radius_mm=band["radius"])
    if label.strip():
        build.text("header-label", "Badge label", x, top, width, label_h, pt=label_pt, colour=colour, text=label,
                   bold=bold["header"], tracking_em=0.16, shrink=False)
        top += label_h + decor["labelGap"]
    if heading.strip():
        build.text("header-heading", "Heading", x, top, width, heading_h, pt=pt["header"], colour=colour,
                   text=heading, bold=bold["header"], tracking_em=-0.01)
    if decor["headerRule"]:
        build.add("shape", "header-rule", "Heading rule", at["header"]["xMm"], cursor + decor["headerRule"]["gap"],
                  size["header"], max(0.3, decor["headerRule"]["rule"]), shape="rect", fill=palette["rule"],
                  stroke=None, stroke_mm=0.3, radius_mm=0.0)


def _details(build, settings, palette, at, size, pt, bold, labels):
    cursor = at["details"]["yMm"]
    row_h = _line(pt["details"])
    for index, key in enumerate(settings["printFieldKeys"]):
        tag = field_tag(key)
        if tag is None:
            continue
        cursor += geo.DETAILS_ROW_GAP_MM
        if cursor + row_h > build.height:
            break
        label = settings["printFieldLabels"].get(key)
        if label is None:
            label = (labels or {}).get(key) or default_label(key)
        label = _braceless(label)
        x, width = at["details"]["xMm"], size["details"]
        value_x, value_w, align = x, width, "left"
        if label:
            natural = len(label) * 0.54 * pt["details"] * geo.PT_TO_MM
            label_w = min(natural, width * 0.5)
            build.text(f"field-{index}-label", f"Answer {index + 1} label", x, cursor, label_w + 0.01, row_h,
                       pt=pt["details"], colour=palette["text"], text=label, bold=bold["details"])
            value_x, value_w, align = x + label_w + geo.DETAILS_COLUMN_GAP_MM, width - label_w - geo.DETAILS_COLUMN_GAP_MM, "right"
        build.text(f"field-{index}-value", f"Answer {index + 1}", value_x, cursor, value_w, row_h,
                   pt=pt["details"], colour=palette["text"], field=tag, bold=bold["details"], align=align)
        cursor += row_h


def _graphics(build, settings, palette, at, size, stock_key):
    width, height = build.width, build.height
    pad = geo.TILE_PADDING_MM
    if settings["showLogo"]:
        build.add("logo", "logo", "Organisation logo", at["logo"]["xMm"], at["logo"]["yMm"], size["logo"], size["logo"],
                  source="organisation", tile=True)
    if settings["showEventLogo"]:
        build.add("logo", "event-logo", "Event logo", at["eventLogo"]["xMm"], at["eventLogo"]["yMm"],
                  size["eventLogo"], size["eventLogo"], source="event", tile=True)
    if settings["showSponsors"]:
        strip_h = geo.sponsor_strip_height(width, height)
        sx, sy, sw = at["sponsors"]["xMm"], at["sponsors"]["yMm"], size["sponsors"]
        build.add("shape", "sponsor-strip", "Sponsor strip", sx, sy, sw, strip_h, shape="rect", fill=palette["tile"],
                  stroke=None, stroke_mm=0.3, radius_mm=min(2.0, strip_h / 4))
        count = settings["sponsorLimit"]
        slot = (sw - 2 * pad - SPONSOR_GAP_MM * (count - 1)) / count
        for index in range(count):
            build.add("logo", f"sponsor-{index + 1}", f"Sponsor {index + 1}", sx + pad + index * (slot + SPONSOR_GAP_MM),
                      sy + pad, slot, strip_h - 2 * pad, source=f"sponsor_{index + 1}", tile=False)
    if settings["showPhoto"]:
        build.add("photo", "photo", "Photo", at["photo"]["xMm"], at["photo"]["yMm"], size["photo"], size["photo"],
                  shape=settings["photoShape"], filter="none", duotone_dark="#142C2A", duotone_light="#DFFF8F")
    if settings["showSymbol"]:
        side = size["symbol"]
        symbol_h = side / PHOTO_SYMBOL_ASPECT
        build.add("logo", "symbol", "Space Works symbol", at["symbol"]["xMm"], at["symbol"]["yMm"] + (side - symbol_h) / 2,
                  side, symbol_h, source="symbol", tile=False)
    if settings["showQr"]:
        side = min(max(size["qr"] + 2 * pad, stocks.qr_minimum_mm(stock_key)), width, height)
        build.add("checkin_qr", "checkin-qr", "Check-in QR", at["qr"]["xMm"], at["qr"]["yMm"], side, side)


def _watermark(settings, palette, width, height):
    mark = settings["watermark"]
    colour = palette["text"] if mark["colour"] == "text" or palette["accent"] == palette["background"] else palette["accent"]
    text = _braceless(mark["text"]).strip().upper()
    kind = "text" if mark["kind"] == "text" and text else "none"
    return {"kind": kind, "text": text if kind == "text" else "", "asset_id": None,
            "opacity_pct": mark["opacityPct"], "angle_deg": geo.clamp(mark["angleDeg"], -60, 60), "colour": colour}


def compile_front(settings, *, event_accent=None, field_labels=None):
    """-> {stock, page_width_mm, page_height_mm, mono, watermark, background (hex), layers}."""
    stock_key, width, height = stock_for(settings["widthMm"], settings["heightMm"])
    palette = badge_palette.resolve(settings, event_accent)
    decor = geo.template_decor(settings["template"], width, height)
    at, size, pt, bold = (settings["elementPositions"], settings["elementSizes"], settings["elementTextSizes"],
                          settings["elementBold"])
    build = _Builder(width, height)
    if decor["frame"]:
        frame = decor["frame"]
        build.add("shape", "frame", "Frame", frame["inset"], frame["inset"], width - 2 * frame["inset"],
                  height - 2 * frame["inset"], shape="rect", fill=None, stroke=palette["rule"],
                  stroke_mm=frame["rule"], radius_mm=min(20.0, frame["radius"]))
    _header(build, settings, palette, at, size, pt, bold, decor)
    if settings["showName"]:
        name_pt = pt["name"]
        build.text("name", "Name", at["name"]["xMm"], at["name"]["yMm"], size["name"], geo.name_block_height(name_pt),
                   pt=name_pt, colour=palette["text"], field="name", bold=bold["name"] or decor["nameUppercase"],
                   tracking_em=decor["nameTrackingEm"], upper=decor["nameUppercase"], shrink=settings["nameAutoFit"])
    for flag, element, tag, label_key in (("showIdNumber", "idNumber", "number", "idNumberLabel"),
                                          ("showValidUntil", "validUntil", "valid_until", "validUntilLabel")):
        if settings[flag]:
            label = _braceless(settings[label_key]).strip()
            build.text(element, element, at[element]["xMm"], at[element]["yMm"], size[element], _line(pt[element]),
                       pt=pt[element], colour=palette["text"], text=f"{label} {{{{{tag}}}}}".strip(),
                       bold=bold[element], tracking_em=0.02 if element == "idNumber" else 0.0)
    if settings["showEmail"]:
        build.text("email", "Email", at["email"]["xMm"], at["email"]["yMm"], size["email"], _line(pt["email"]),
                   pt=pt["email"], colour=palette["text"], field="email", bold=bold["email"])
    _details(build, settings, palette, at, size, pt, bold, field_labels)
    if settings["showFooter"] and settings["footerText"].strip():
        build.text("footer", "Footer", at["footer"]["xMm"], at["footer"]["yMm"], size["footer"], _line(pt["footer"]),
                   pt=pt["footer"], colour=palette["text"], text=settings["footerText"],
                   bold=bold["footer"] or settings["template"] == "bold")
    _graphics(build, settings, palette, at, size, stock_key)
    return {"stock": stock_key, "page_width_mm": width, "page_height_mm": height,
            "mono": settings["colorMode"] == "mono", "watermark": _watermark(settings, palette, width, height),
            "background": palette["background"], "layers": build.layers}
