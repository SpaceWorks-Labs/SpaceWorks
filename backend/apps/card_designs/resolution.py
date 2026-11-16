"""Which design a holder's card renders with (SPEC §4.1 resolution order).

Member cards: the member's primary title override, then their live plan, then the
owner organisation's default (O-B4), then the space default. Event cards and tickets: ticket type, then event, then the organising
organisation's library default, then the space default. ID programmes: the
programme's own design. Only PUBLISHED documents reach holders; with nothing
published yet the domain's shipped template is used.
"""
from django.db import IntegrityError, transaction

from .default_templates import default_document
from .models import CardDesign

TARGETS = ("plan", "title", "programme", "organization", "event", "ticket_type")


def _published(queryset):
    row = queryset.exclude(published_document__isnull=True).first()
    return row


def resolve(makerspace_id, domain, *, plan_id=None, title_id=None, programme_id=None, event_id=None,
            ticket_type_id=None, organization_ids=()):
    """-> (document, design or None). Never None: falls back to the shipped template."""
    # An archived override (decision 219(h)) no longer reaches holders: they fall through.
    # E-B1: role variants are reached only through resolution_roles.resolve_event_card.
    rows = CardDesign.objects.filter(makerspace_id=makerspace_id, domain=domain, archived_at__isnull=True,
                                     card_role__isnull=True)
    chain = []
    if domain == CardDesign.Domain.MEMBER_CARDS:
        if title_id:
            chain.append(rows.filter(title_id=title_id))
        if plan_id:
            chain.append(rows.filter(plan_id=plan_id))
        # O-B4: the space's owner organisation's default, ahead of the space default. One member card serves
        # both the space and the organisation, so this is the same card with the organisation's design.
        from .org_default import owner_organization_id
        organization_id = owner_organization_id(makerspace_id)
        if organization_id:
            chain.append(CardDesign.objects.filter(organization_id=organization_id, domain=domain,
                                                   event__isnull=True, archived_at__isnull=True))
    elif domain == CardDesign.Domain.ID_PROGRAMME:
        chain.append(rows.filter(programme_id=programme_id))
    elif domain != CardDesign.Domain.STAFF_CARDS:  # staff cards: the space default only (appended below)
        if ticket_type_id:
            chain.append(rows.filter(ticket_type_id=ticket_type_id))
        if event_id:
            chain.append(rows.filter(event_id=event_id, ticket_type__isnull=True))
        for organization_id in organization_ids:
            chain.append(rows.filter(organization_id=organization_id, event__isnull=True))
    if domain != CardDesign.Domain.ID_PROGRAMME:
        chain.append(rows.filter(plan__isnull=True, title__isnull=True, programme__isnull=True,
                                 organization__isnull=True, event__isnull=True, ticket_type__isnull=True))
    for queryset in chain:
        design = _published(queryset)
        if design is not None:
            return design.published_document, design
    return default_document(domain), None


def get_or_create(makerspace, domain, *, actor=None, template=None, theme="light", **target):
    """The design row for exactly this target, seeded from a template on first use."""
    if set(target) - set(TARGETS):
        raise ValueError("Unknown design target")
    filters = {f"{key}__isnull": True for key in TARGETS} | {"card_role__isnull": True}
    for key, value in target.items():
        if value is not None:
            filters.pop(f"{key}__isnull")
            filters[key] = value
    existing = CardDesign.objects.filter(makerspace=makerspace, domain=domain, **filters).first()
    if existing is not None and existing.archived_at is not None:
        # Asking for this target's design again brings its archived override back.
        from .archive import unarchive
        existing = unarchive(actor, existing)
    if existing is not None:
        return existing, False
    from .default_templates import build
    document = build(template, domain, theme) if template else default_document(domain)
    try:
        with transaction.atomic():
            row = CardDesign.objects.create(makerspace=makerspace, domain=domain, document=document,
                                            updated_by=actor, **{k: v for k, v in target.items() if v is not None})
    except IntegrityError:
        return CardDesign.objects.get(makerspace=makerspace, domain=domain, **filters), False
    from .models import CardDesignRevision
    CardDesignRevision.objects.create(design=row, revision=row.revision, document=document, created_by=actor)
    from apps.audit import services as audit
    audit.record(actor, "card_design.created", makerspace=makerspace, target=row,
                 meta={"design_id": row.pk, "domain": domain})
    return row, True
