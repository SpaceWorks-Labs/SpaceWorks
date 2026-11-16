"""Batch print preview: the first sheet of a bulk job, rendered before the job is queued.

Bounded on purpose so it stays a request-sized task (#133): at most one sheet of cards
(10 CR80 cards on A4), front and back, rasterised at 96 dpi. The counts say how many
sheets the real job will print. Real holders appear on it, so it is audited like an
export summary (`card_job.previewed`, counts only) and refuses a superadmin without a
PII window.
"""
import base64
from math import ceil

from apps.accounts.pii_presentation import require_pii_access
from apps.audit import services as audit

from .cards import context_for, document_for
from .holders import spec_for
from .layout import sides
from .raster import pdf_page_to_png
from .sheets import grid, render_sheets

PREVIEW_DPI = 96


def _uri(png):
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def preview(actor, makerspace, kind, card_ids, params, *, scope):
    require_pii_access(actor, makerspace.pk)
    model = spec_for(kind).model()
    ids = list(card_ids)
    paper, order = params.get("paper", "a4"), params.get("order", "duplex")
    result = {"total": len(ids), "per_page": 0, "sheets": 0, "paper": paper, "order": order, "front": None,
              "back": None, "mixed_sizes": False}
    if not ids:
        return result
    first = model.objects.filter(pk__in=ids)
    cards = sorted(first.filter(pk__in=ids[:40]), key=lambda card: ids.index(card.pk))
    rendered = [(document_for(kind, card), card) for card in cards]
    document = rendered[0][0]
    size = (document["front"]["page_width_mm"], document["front"]["page_height_mm"])
    same = [(doc, card) for doc, card in rendered
            if (doc["front"]["page_width_mm"], doc["front"]["page_height_mm"]) == size]
    columns, rows, _left, _top = grid(paper, *size)
    per_page = columns * rows
    page = [(doc, context_for(kind, card, doc)) for doc, card in same[:per_page]]
    pdf = render_sheets(page, paper=paper, order=order, crop_marks=params.get("crop_marks", True),
                        title="Sheet preview")
    result.update(per_page=per_page, sheets=ceil(len(ids) / per_page), mixed_sizes=len(same) != len(rendered),
                  front=_uri(pdf_page_to_png(pdf, 0, dpi=PREVIEW_DPI)))
    if any("back" in sides(doc) for doc, _ctx in page):
        result["back"] = _uri(pdf_page_to_png(pdf, 1, dpi=PREVIEW_DPI))
    audit.record(actor, "card_job.previewed", makerspace=makerspace, target=makerspace,
                 meta={"scope": scope, "count": len(ids), "shown": len(page), "paper": paper})
    return result
