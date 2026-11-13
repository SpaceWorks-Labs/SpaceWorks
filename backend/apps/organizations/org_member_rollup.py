"""Read-only member roll-up for organization governors: counts only, never people.

Spaces are the servable makerspaces the organization OWNS (owner link). `people` is the
deduplicated organization membership (explicit plus derived, `derived_membership`); the
per-space figures are community-membership counts by standing. Nothing here returns a
name, id, email or any other per-person field, so a governor learns sizes, not members.
"""
from django.db.models import Count

from apps.makerspaces.models import MakerspaceMembership
from apps.organizations.audience import owned_space_ids, usable_spaces
from apps.organizations.derived_membership import org_member_breakdown


def member_rollup(organization):
    space_ids = owned_space_ids([organization.pk])
    spaces = list(usable_spaces().filter(pk__in=space_ids).order_by("name", "id"))
    standings = {}
    rows = (MakerspaceMembership.objects.filter(makerspace_id__in=[s.pk for s in spaces])
            .values("makerspace_id", "status").annotate(n=Count("pk")))
    for row in rows:
        standings.setdefault(row["makerspace_id"], {})[row["status"]] = row["n"]
    return {
        "people": org_member_breakdown(organization),
        "spaces": [{"name": s.name, "slug": s.slug,
                    "active": standings.get(s.pk, {}).get("active", 0),
                    "revoked": standings.get(s.pk, {}).get("revoked", 0)} for s in spaces],
        "home_space_card_note": "Member cards are issued by the home space.",
    }
