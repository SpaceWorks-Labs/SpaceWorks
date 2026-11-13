"""Real holders a design can be previewed with (the designer's "Preview as" picker).

Only live cards that this very design would print are offered: member cards in the
design's space, approved cards of the design's programme, active cards of the design's
event. Ticket designs have no card holders. The preview never shows the opt-in
sensitive extras, and a superadmin needs an open PII window (it shows a person's data).
"""
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound

from apps.accounts.pii_presentation import require_pii_access

from .holders import spec_for

DOMAIN_KIND = {"member_cards": "member_card", "id_programme": "programme_card", "event_card": "event_card",
               "staff_cards": "staff_card"}
LIMIT = 30


def _queryset(design):
    kind = DOMAIN_KIND.get(design.domain)
    if kind is None:
        return None, None
    try:
        model = spec_for(kind).model()
    except NotFound:
        return None, None
    if kind == "member_card":
        rows = model.objects.filter(makerspace_id=design.makerspace_id, revoked_at__isnull=True,
                                    membership__isnull=False)
    elif kind == "staff_card":
        rows = model.objects.filter(makerspace_id=design.makerspace_id, revoked_at__isnull=True,
                                    membership__isnull=False)
    elif kind == "programme_card":
        rows = model.objects.filter(programme_id=design.programme_id, status="approved")
    else:
        rows = model.objects.filter(event_id=design.event_id, status="active")
    return kind, rows


def holders(design):
    kind, rows = _queryset(design)
    if rows is None:
        return kind, []
    return kind, list(rows.order_by("-pk")[:LIMIT])


def holder(actor, design, holder_id):
    require_pii_access(actor, design.makerspace_id)
    kind, rows = _queryset(design)
    card = rows.filter(pk=holder_id).first() if rows is not None else None
    if card is None:
        raise NotFound(gettext("That person has no live card for this design."))
    return kind, card


def row(kind, card):
    spec = spec_for(kind)
    values = spec.snapshot(card)
    from .cards import cutout_flags
    return {"id": card.pk, "kind": kind, "name": str(values.get("name") or ""), "number": str(values.get("number") or ""),
            "label": spec.label(card) or "", "cutout": cutout_flags(kind, card)}


def preview_context(kind, card, document):
    """The holder's real values, photo and codes, with the sensitive extras withheld."""
    from .cards import context_for
    context = context_for(kind, card, document, preview=True, preview_label="PREVIEW")
    context.allow_sensitive = False
    return context
