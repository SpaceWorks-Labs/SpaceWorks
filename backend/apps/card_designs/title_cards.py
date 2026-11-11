"""The "title cards" list: which titles have their own card design, its state and its live cards (O-B4, parity C6).

Per title: `status` is `inherits` (no override, or an archived one: holders fall through to the plan, the
organisation default or the space default), `draft` (never published), `published`, or `changes`
(published, with newer unpublished edits). `live_cards` counts live member cards whose PRIMARY title is
this one; `number_pattern` is the live numbering pattern for the title ("" = the space default's).
"""
from django.db.models import Count, Q

from .models import CardDesign
from .models_numbering import CardNumberScheme


def status_of(design):
    if design is None or design.archived_at is not None:
        return "inherits"
    if design.published_document is None:
        return "draft"
    return "changes" if design.published_revision != design.revision else "published"


def title_rows(makerspace):
    from apps.makerspaces.models import MembershipTitle
    titles = list(MembershipTitle.objects.filter(makerspace=makerspace, archived_at__isnull=True)
                  .order_by("sort_order", "name"))
    designs = {row.title_id: row for row in CardDesign.objects.filter(
        makerspace=makerspace, domain="member_cards", title__isnull=False)}
    schemes = {row.title_id: row for row in CardNumberScheme.objects.filter(
        makerspace=makerspace, title__isnull=False)}
    counts = dict(MembershipTitle.objects.filter(makerspace=makerspace).annotate(
        live=Count("assignments", filter=Q(assignments__is_primary=True,
                                           assignments__membership__member_cards__revoked_at__isnull=True,
                                           assignments__membership__status="active"), distinct=True)
    ).values_list("pk", "live"))
    rows = []
    for title in titles:
        design, scheme = designs.get(title.pk), schemes.get(title.pk)
        rows.append({"title_id": title.pk, "title": title.name, "design_id": design.pk if design else None,
                     "status": status_of(design), "number_pattern": scheme.pattern if scheme else "",
                     "live_cards": counts.get(title.pk, 0)})
    return rows
