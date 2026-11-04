"""Render one holder's card: the published design + a frozen snapshot of its values.

Single cards render in the request (one card is not heavy, SPEC §6); every bulk
output is a CardJob. Sensitive extras render only where the design places them and
only for a holder who opted in (Q-I5); nothing else ever reads them.
"""
from rest_framework.exceptions import ValidationError

from .holders import spec_for
from .layout import normalize_document
from .models import CardDesignAsset, CardHolderExtras
from .rendering import RenderContext, render_pdf, render_png
from .storage import read_optional

FORMATS = ("pdf", "png")
SIDES = ("front", "back")


def assets_for(makerspace_id, document):
    from .layout import asset_ids
    ids = asset_ids(document)
    rows = CardDesignAsset.objects.filter(makerspace_id=makerspace_id, asset_id__in=ids, ready=True)
    data, colours = {}, {}
    for row in rows:
        key = str(row.asset_id)
        data[key] = read_optional(row.object_key)
        colours[key] = row.mean_colour or "#808080"
    return data, colours


def extras_values(kind, card):
    row = CardHolderExtras.objects.filter(**{kind: card}, consent_at__isnull=False).first()
    if row is None:
        return {}, False
    contact = " · ".join(part for part in (row.emergency_contact_name, row.emergency_contact_phone) if part)
    return {"blood_group": row.blood_group, "emergency_contact": contact}, True


def context_for(kind, card, document, *, preview=False, preview_label=""):
    spec = spec_for(kind)
    values = dict(spec.snapshot(card))
    extras, opted_in = extras_values(kind, card)
    values.update(extras)
    from . import tokens
    token = tokens.live(kind, card)
    assets, colours = assets_for(card.makerspace_id, document)
    return RenderContext(values=values, allow_sensitive=opted_in, desk_qr=spec.desk_payload(card),
                         verify_qr=tokens.url(token.token) if token else None, photo=spec.photo_bytes(card),
                         logos=spec.logos(card), assets=assets, asset_colours=colours, preview=preview,
                         preview_label=preview_label)


def document_for(kind, card):
    document, _design = spec_for(kind).design(card)
    return normalize_document(document, check_contrast=False)


def render(kind, card, *, fmt="pdf", side="front", preview_label=""):
    """-> (bytes, content type, filename)."""
    if fmt not in FORMATS or side not in SIDES:
        raise ValidationError({"format": "Choose pdf or png, and the front or back."})
    document = document_for(kind, card)
    context = context_for(kind, card, document, preview=bool(preview_label), preview_label=preview_label)
    name = spec_for(kind).filename(card)
    if fmt == "png":
        return render_png(document, context, side=side), "image/png", f"{name}-{side}.png"
    return render_pdf(document, context, title=name), "application/pdf", f"{name}.pdf"


def sample_context(makerspace, document, *, long=False):
    """Designer previews: sample people, placeholder QR codes, the real space branding."""
    from .data_fields import SAMPLE_LONG, SAMPLE_SHORT
    from .images import read_public_image
    assets, colours = assets_for(makerspace.pk, document)
    values = dict(SAMPLE_LONG if long else SAMPLE_SHORT)
    values["space"] = (makerspace.branding_config or {}).get("display_name") or makerspace.name
    return RenderContext(values=values, allow_sensitive=True, preview=True, preview_label="PREVIEW",
                         logos={"space": read_public_image(makerspace.logo_key)}, assets=assets,
                         asset_colours=colours)
