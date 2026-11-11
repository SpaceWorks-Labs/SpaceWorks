"""Role-aware event card design resolution (E-B1; `resolution.py` is O-B4's and stays untouched).

`resolve_event_card` tries the person's ROLE variant at each step of the usual chain (ticket type, event,
each organising organisation's library default, the space default) and then falls back to the ordinary
`resolution.resolve`, so a role with no design of its own prints the attendee design. A role variant only
exists, and is only read, while `events.role_badges` is on.
"""
from django.db import IntegrityError, transaction

from .models import CardDesign
from .resolution import resolve
from .switches import role_badges_on

DOMAIN = "event_card"
ROLES = tuple(value for value, _label in CardDesign.Role.choices)


def _chain(rows, event_id, ticket_type_id, organization_ids):
    if ticket_type_id:
        yield rows.filter(ticket_type_id=ticket_type_id)
    if event_id:
        yield rows.filter(event_id=event_id, ticket_type__isnull=True)
    for organization_id in organization_ids:
        yield rows.filter(organization_id=organization_id, event__isnull=True)
    yield rows.filter(plan__isnull=True, title__isnull=True, programme__isnull=True, organization__isnull=True,
                      event__isnull=True, ticket_type__isnull=True)


def resolve_event_card(makerspace_id, event_id, ticket_type_id, org_ids, role):
    """-> (document, design or None). Never None: ends at the shipped Event pass template."""
    if role in ROLES:
        from apps.makerspaces.models import Makerspace
        space = Makerspace.objects.filter(pk=makerspace_id).first()
        if space is not None and role_badges_on(space):
            rows = CardDesign.objects.filter(makerspace_id=makerspace_id, domain=DOMAIN, card_role=role,
                                             archived_at__isnull=True, published_document__isnull=False)
            for queryset in _chain(rows, event_id, ticket_type_id, org_ids):
                design = queryset.first()
                if design is not None:
                    return design.published_document, design
    return resolve(makerspace_id, DOMAIN, event_id=event_id, ticket_type_id=ticket_type_id, organization_ids=org_ids)


def variant(event, role):
    """This event's own variant row for `role`, or None."""
    return CardDesign.objects.filter(event=event, domain=DOMAIN, card_role=role, ticket_type__isnull=True,
                                     archived_at__isnull=True).first()


def get_or_create_variant(event, role, *, document, actor):
    """-> (design, created). The new row starts as a copy of `document` (the attendee design's draft)."""
    existing = CardDesign.objects.filter(event=event, domain=DOMAIN, card_role=role, ticket_type__isnull=True).first()
    if existing is not None:
        if existing.archived_at is not None:
            from .archive import unarchive
            existing = unarchive(actor, existing)
        return existing, False
    try:
        with transaction.atomic():
            row = CardDesign.objects.create(makerspace=event.makerspace, domain=DOMAIN, event=event, card_role=role,
                                            document=document, updated_by=actor)
    except IntegrityError:
        return CardDesign.objects.get(event=event, domain=DOMAIN, card_role=role, ticket_type__isnull=True), False
    from .models import CardDesignRevision
    CardDesignRevision.objects.create(design=row, revision=row.revision, document=document, created_by=actor)
    from apps.audit import services as audit
    audit.record(actor, "card_design.role_variant_created", makerspace=event.makerspace, target=row,
                 meta={"design_id": row.pk, "domain": DOMAIN, "role": role})
    return row, True
