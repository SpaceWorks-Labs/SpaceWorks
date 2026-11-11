"""Badge geometry (E-B1): how a badge's items are sized and placed for a stock.

A native port of the SpaceWorks-Events badge maths (`lib/idCardPrint/geometry.ts` and
`defaults.ts`), kept numerically identical so an Events design file lands where it was
drawn. Everything is millimetres unless a name says `_pt`. The TypeScript twin
(`frontend/src/features/staff/eventBadges/badgeGeometry.ts`) is checked against
`fixtures/badge_compile_cases.json`, so a change here must regenerate that file.
"""
import math

ELEMENTS = ("header", "name", "email", "details", "qr", "footer", "logo", "eventLogo", "symbol", "photo",
            "sponsors", "idNumber", "validUntil")
SQUARE = frozenset({"qr", "logo", "eventLogo", "symbol", "photo"})
GRAPHIC = SQUARE | {"sponsors"}
PT_TO_MM = 0.3528
LINE_HEIGHT = {"label": 1.2, "heading": 1.1, "name": 1.1, "body": 1.25}
TILE_PADDING_MM = 1.0
DETAILS_ROW_GAP_MM = 1.5
DETAILS_COLUMN_GAP_MM = 4.0
TEMPLATES = ("classic", "bold", "minimal")
FLAG_ELEMENT = (("showEventLogo", "eventLogo"), ("showSymbol", "symbol"), ("showPhoto", "photo"),
                ("showSponsors", "sponsors"), ("showIdNumber", "idNumber"), ("showValidUntil", "validUntil"))
DEFAULT_FLAGS = {"showLogo": True, "showEventLogo": False, "showSymbol": True, "showPhoto": False,
                 "showSponsors": False}


def half_up(value):
    """JavaScript's Math.round (halves go up), so the two languages agree on every cell."""
    return math.floor(value + 0.5)


def r1(value):
    return half_up(value * 10) / 10


def clamp(value, low, high):
    return min(high, max(low, value))


def is_text(element):
    return element not in GRAPHIC


def minimum_element_size(element):
    if element == "symbol":
        return 7.0
    if element == "photo":
        return 8.0
    return 10.0 if element in SQUARE else 20.0


def badge_label_pt(header_pt):
    return min(9.0, max(5.5, half_up(header_pt * 0.5 * 2) / 2))


def paper_scale(width, height):
    """Layout scale relative to A6 (1 on A6), so small stock gets proportionally smaller type and margins."""
    return min(1.6, max(0.45, min(width, height) / 105))


def margin_mm(k):
    return max(3.0, r1(10 * k))


def band_inset_mm(k):
    return max(4.0, r1(5 * k))


def fit_text_size_pt(text, width, size_pt, bold, min_ratio=0.6):
    chars = max(1, len(text.strip()))
    fitting = width / (chars * (0.6 if bold else 0.54) * 0.3528)
    return r1(max(size_pt * min_ratio, min(size_pt, fitting)))


def template_decor(template, width, height):
    k = paper_scale(width, height)
    label_gap = max(1.0, r1(2 * k))
    if template == "bold":
        return {"frame": None, "headerRule": None, "labelGap": label_gap, "nameTrackingEm": 0.0, "nameUppercase": True,
                "band": {"padX": max(2.0, r1(margin_mm(k) - band_inset_mm(k))), "padY": max(2.0, r1(4.5 * k)),
                         "radius": max(1.0, r1(2 * k))}}
    if template == "minimal":
        return {"frame": None, "headerRule": None, "band": None, "labelGap": label_gap, "nameTrackingEm": -0.02,
                "nameUppercase": False}
    return {"frame": {"inset": max(2.5, r1(5 * k)), "rule": 0.3, "radius": max(1.0, r1(2.5 * k))},
            "headerRule": {"gap": max(1.5, r1(3 * k)), "rule": 0.25}, "band": None, "labelGap": label_gap,
            "nameTrackingEm": -0.02, "nameUppercase": False}


def estimate_header_height(template, header_pt, width, height, label=True):
    decor = template_decor(template, width, height)
    total = (badge_label_pt(header_pt) * PT_TO_MM * LINE_HEIGHT["label"] + decor["labelGap"]) if label else 0.0
    total += header_pt * PT_TO_MM * LINE_HEIGHT["heading"]
    if decor["headerRule"]:
        total += decor["headerRule"]["gap"] + decor["headerRule"]["rule"]
    if decor["band"]:
        total += decor["band"]["padY"] * 2
    return r1(total)


def name_block_height(name_pt):
    return r1(name_pt * PT_TO_MM * LINE_HEIGHT["name"] * 1.2)


def sponsor_strip_height(width, height):
    return clamp(r1(10 * paper_scale(width, height)), 6.0, 14.0)


def symbol_clear_space(size):
    return math.ceil(size * 2.5) / 10


def element_box_height(element, sizes, width, height):
    if element in SQUARE:
        return sizes[element]
    return sponsor_strip_height(width, height) if element == "sponsors" else 0.0


def default_text_sizes(template="classic", width=105.0, height=148.0):
    """The name is always the largest thing on the card; the heading stays small."""
    base = {"bold": (14, 28, 10, 8.5, 7.5, 11, 8.5), "minimal": (10, 30, 9.5, 8.5, 7.5, 10, 8.5)}.get(
        template, (13, 30, 10, 8.5, 7.5, 11, 8.5))
    k = paper_scale(width, height)

    def scaled(pt, low):
        return max(float(low), half_up(pt * k * 2) / 2)

    sizes = dict.fromkeys(ELEMENTS, 0.0)
    for key, (pt, low) in zip(("header", "name", "email", "details", "footer", "idNumber", "validUntil"),
                              zip(base, (6, 9, 6, 6, 6, 6, 6))):
        sizes[key] = scaled(pt, low)
    return sizes


def default_bold():
    return {**dict.fromkeys(ELEMENTS, False), "header": True, "name": True, "idNumber": True}


def name_size_pt(settings, name):
    """The name's point size after auto-fit (a long name shrinks, never below 30 % of its size)."""
    size = settings["elementTextSizes"]["name"]
    if not settings["nameAutoFit"]:
        return size
    upper = template_decor(settings["template"], settings["widthMm"], settings["heightMm"])["nameUppercase"]
    width = settings["elementSizes"]["name"] / (1.15 if upper else 1)
    bold = settings["elementBold"]["name"] or upper
    fitted = fit_text_size_pt(name, width, size, bold)
    em_mm = (0.6 if bold else 0.54) * PT_TO_MM
    chars = max(1, len(name.strip()))
    area = 0.85 * math.sqrt((1.2 * size * width) / (chars * em_mm))
    return r1(min(fitted, max(size * 0.3, area)))


def _geometry(template, width, height, flags):
    k = paper_scale(width, height)
    m = margin_mm(k)
    decor = template_decor(template, width, height)
    text = default_text_sizes(template, width, height)

    def line(pt):
        return pt * PT_TO_MM * LINE_HEIGHT["body"]

    def wide(mm):
        return max(20.0, r1(mm))

    qr_size = min(40.0, max(16.0, r1((21 if template == "minimal" else 24) * k)))
    logo_size = min(20.0, max(10.0, r1((10 if template == "minimal" else 12) * k)))
    symbol_size = clamp(r1(9 * k), 7.0, 14.0)
    photo_size = clamp(r1(24 * k), 12.0, 34.0)
    qr = (r1(width - m - qr_size - 1), r1(height - m - qr_size - 1))
    qr_left = qr[0] + 1
    inset = band_inset_mm(k)
    header = (inset, inset) if decor["band"] else (m, m)
    text_x = r1(inset + decor["band"]["padX"]) if decor["band"] else m
    left_of_qr = qr_left - text_x - 4 * k
    logo = (r1(width - m - logo_size), m)
    footer_width = sponsors_width = left_of_qr
    if template == "bold":
        beside = qr_left - 4 * k - logo_size
        if beside - text_x - 3 * k >= 30:
            logo = (r1(beside), r1(height - m - logo_size))
            footer_width = beside - text_x - 3 * k
            if flags.get("showLogo"):
                sponsors_width = footer_width
        else:
            logo = (r1(width - m - logo_size), r1(qr[1] + 1 - 3 * k - logo_size))
    logo_on_top = template != "bold" and flags.get("showLogo")
    if template == "bold":
        event_logo = (r1(width - inset - logo_size), inset)
    else:
        event_logo = (r1(logo[0] - 3 * k - logo_size if logo_on_top else width - m - logo_size), m)
    if flags.get("showEventLogo"):
        header_right = event_logo[0] - (2 if template == "bold" else 4) * k
    else:
        header_right = width - inset if template == "bold" else logo[0] - 4 * k
    header_width = wide(header_right - inset) if decor["band"] else wide(header_right - text_x)
    footer_line = line(text["footer"])
    symbol_gap = max(symbol_clear_space(symbol_size), r1(2 * k))
    beside_footer = footer_width - symbol_size - symbol_gap >= 20
    plain_footer = (text_x, r1(height - m - footer_line))
    symbol = (text_x, r1(height - m - symbol_size)) if beside_footer else (
        text_x, r1(plain_footer[1] - symbol_gap - symbol_size))
    if flags.get("showSymbol") and beside_footer:
        footer = (r1(text_x + symbol_size + symbol_gap), r1(height - m - symbol_size / 2 - footer_line / 2))
    else:
        footer = plain_footer
    footer_row_top = symbol[1] if flags.get("showSymbol") else footer[1]
    footer_box = footer_width - symbol_size - symbol_gap if flags.get("showSymbol") and beside_footer else footer_width
    header_bottom = header[1] + estimate_header_height(template, text["header"], width, height)
    name_ratio = {"bold": 0.26, "minimal": 0.36}.get(template, 0.3)
    landscape = width > height * 1.15
    name_y = r1(max(header_bottom + (8 if template == "minimal" else 6) * k, height * name_ratio))
    content_x = text_x
    photo = (text_x, r1(header_bottom + 4 * k))
    if flags.get("showPhoto"):
        if landscape:
            photo = (text_x, name_y)
            content_x = r1(text_x + photo_size + 3 * k)
        else:
            name_y = r1(photo[1] + photo_size + 3 * k)
    elif landscape:
        photo = (text_x, name_y)
    email_y = r1(name_y + name_block_height(text["name"]) + 1.5 * k)
    id_y = r1(email_y + line(text["email"]) + 2 * k)
    valid_y = r1(id_y + (line(text["idNumber"]) + 1 * k if flags.get("showIdNumber") else 0))
    if flags.get("showValidUntil"):
        member_bottom = valid_y + line(text["validUntil"])
    elif flags.get("showIdNumber"):
        member_bottom = id_y + line(text["idNumber"])
    else:
        member_bottom = None
    details_y = r1(email_y + line(text["email"]) + 4 * k if member_bottom is None else member_bottom + 3 * k)
    full = width - content_x - m
    name_width = wide(min(full, left_of_qr - (content_x - text_x)) if landscape else full)
    sponsors_h = sponsor_strip_height(width, height)
    sponsors = (text_x, r1(footer_row_top - max(2 * k, symbol_gap) - sponsors_h))
    positions = {"header": header, "name": (content_x, name_y), "email": (content_x, email_y),
                 "details": (content_x, details_y), "qr": qr, "footer": footer, "logo": logo,
                 "eventLogo": event_logo, "symbol": symbol, "photo": photo, "sponsors": sponsors,
                 "idNumber": (content_x, id_y), "validUntil": (content_x, valid_y)}
    sizes = {"header": header_width, "name": name_width, "email": name_width,
             "details": wide(left_of_qr - (content_x - text_x)), "qr": qr_size, "footer": wide(footer_box),
             "logo": logo_size, "eventLogo": logo_size, "symbol": symbol_size, "photo": photo_size,
             "sponsors": wide(sponsors_width), "idNumber": name_width, "validUntil": name_width}
    return ({key: {"xMm": value[0], "yMm": value[1]} for key, value in positions.items()}, sizes)


def geometry_with_optional_defaults(template, width, height, flags):
    """Where an optional item goes when it is turned on, without reflowing the rest."""
    flags = {**DEFAULT_FLAGS, **{key: bool(value) for key, value in flags.items()}}
    positions, sizes = _geometry(template, width, height, flags)
    for flag, element in FLAG_ELEMENT:
        if flags.get(flag):
            continue
        enabled_positions, enabled_sizes = _geometry(template, width, height, {**flags, flag: True})
        positions[element], sizes[element] = enabled_positions[element], enabled_sizes[element]
    return positions, sizes


def layout_for_paper(template, width, height, flags=None):
    positions, sizes = geometry_with_optional_defaults(template, width, height, flags or DEFAULT_FLAGS)
    return {"elementPositions": positions, "elementSizes": sizes,
            "elementTextSizes": default_text_sizes(template, width, height), "elementBold": default_bold()}


def layout_flags(settings):
    flags = {key: settings[key] for key in ("showLogo", "showEventLogo", "showSymbol", "showPhoto", "showSponsors")}
    flags.update({key: True for key in ("showIdNumber", "showValidUntil") if settings.get(key)})
    return flags


def is_default_layout(settings):
    """True while positions and sizes are untouched, so a stock or toggle change may reflow them."""
    fresh = layout_for_paper(settings["template"], settings["widthMm"], settings["heightMm"], layout_flags(settings))
    return fresh["elementPositions"] == settings["elementPositions"] and fresh["elementSizes"] == settings["elementSizes"]


def watermark_size_pt(text, width, height, angle):
    chars = max(1, len(text.strip()))
    span = width if angle == 0 else math.hypot(width, height) * 0.85
    fitting = (span * 0.75) / (chars * 0.62 * PT_TO_MM)
    tallest = (min(width, height) * 0.4) / PT_TO_MM
    return r1(max(6.0, min(fitting, tallest)))
