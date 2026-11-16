"""Bulk cards from a CSV (decision 344(b)): one card per row of merge values, printed from the PUBLISHED design.

For people who hold no card record in SpaceWorks (visitors, one-day volunteers, a printed badge run): the CSV's
header names data tags (`name`, `role`, `number`, `valid_until`, `first_name`, ... and `field:<key>` answers), each row
fills them, and the published design is drawn once per row onto sheets (or one card per page).

What a CSV card can NOT carry, by design: it has no record, so the check QR, the desk QR and the check-in QR print
nothing (never a fake code), photos print the initials placeholder, and the sensitive tags (blood group, emergency
contact) stay empty. Approval is respected: only a published design prints. Every run is audited with the row count.
"""
import csv
import io

from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from .data_fields import SENSITIVE_TAGS, valid_tag
from .layout import normalize_document
from .rendering import RenderContext

MAX_BYTES = 256 * 1024
MAX_ROWS = 200
MAX_COLUMNS = 40
MAX_VALUE = 200
PREVIEW_ROWS = 3


def _clean(value):
    """Printable text only: control characters out, whitespace folded, length capped."""
    text = "".join(ch for ch in str(value) if ch == " " or ch.isprintable())
    return " ".join(text.split())[:MAX_VALUE]


def parse(text):
    """-> (columns, unknown_columns, rows). Refuses oversized or empty input with a typed 400."""
    if not isinstance(text, str) or not text.strip():
        raise ValidationError({"csv": gettext("Paste or upload a CSV file with a header row.")})
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValidationError({"csv": gettext("A CSV merge takes at most 256 KB.")})
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    try:
        header = [_clean(name).lower() for name in next(reader)]
        body = [row for row in reader if any(cell.strip() for cell in row)]
    except (csv.Error, StopIteration):
        raise ValidationError({"csv": gettext("That file isn't a readable CSV.")}) from None
    if not header or len(header) > MAX_COLUMNS or len(set(header)) != len(header):
        raise ValidationError({"csv": gettext("Use one header row with up to 40 distinct column names.")})
    if not 1 <= len(body) <= MAX_ROWS:
        raise ValidationError({"csv": gettext("A CSV merge prints 1 to 200 cards.")})
    known = [name for name in header if valid_tag(name) and name not in SENSITIVE_TAGS]
    unknown = [name for name in header if name not in known]
    rows = [{name: _clean(row[index]) if index < len(row) else "" for index, name in enumerate(header) if name in known}
            for row in body]
    return known, unknown, rows


def _values(row, space_name):
    values = {"space": space_name, **row}
    name = values.get("name", "")
    if name and "first_name" not in row and "last_name" not in row:  # the two-weight name, like the holder adapter
        first, _sep, last = name.partition(" ")
        values["first_name"], values["last_name"] = first, last
    return values


def _published(design):
    from .cards import assets_for
    from .images import read_public_image
    space = design.makerspace
    document = normalize_document(design.published_document, check_contrast=False)
    assets, colours = assets_for(space.pk, document)
    name = (space.branding_config or {}).get("display_name") or space.name
    return document, name, {"logos": {"space": read_public_image(space.logo_key)}, "assets": assets, "asset_colours": colours}


def preview_images(design, rows, *, count=PREVIEW_ROWS, dpi=96):
    """Decision 345(e): the first rows drawn from the PUBLISHED version, exactly as the PDF prints them (PNG data
    URIs of the front, screen resolution); [] while nothing is published."""
    import base64
    from .rendering import render_png
    if design.published_document is None:
        return []
    document, name, shared = _published(design)
    return ["data:image/png;base64," + base64.b64encode(render_png(
        document, RenderContext(values=_values(row, name), **shared), side="front", dpi=dpi)).decode("ascii")
        for row in rows[:count]]


def render(actor, design, text, *, paper="a4", order="duplex", crop_marks=True):
    """-> PDF bytes of every row on the published design. Audited as `card_design.csv_merged`."""
    from .sheets import render_sheets
    if design.published_document is None:
        raise ValidationError({"design": gettext("Publish the design first: a CSV run prints the published version."),
                               "code": "not_published"})
    columns, _unknown, rows = parse(text)
    space = design.makerspace
    document, space_name, shared = _published(design)
    cards = [(document, RenderContext(values=_values(row, space_name), **shared)) for row in rows]
    pdf = render_sheets(cards, paper=paper, order=order, crop_marks=crop_marks, title=design.name or "Cards")
    audit.record(actor, "card_design.csv_merged", makerspace=space, target=design,
                 meta={"design_id": design.pk, "rows": len(rows), "columns": columns, "paper": paper,
                       "revision": design.published_revision})
    return pdf
