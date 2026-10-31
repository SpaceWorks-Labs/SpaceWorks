"""Live section adapters. Optional domains load behind runtime/module gates."""

from django.utils import timezone
from .platform import module_enabled


def event_cards(kind, owner, *, page=1):
    from apps.separability.registry import runtime_active
    from .editions import public_surface_available
    if not runtime_active("events") or not public_surface_available("events"):
        return [], 0
    if kind == "organization":
        from apps.organizations.public_catalog import public_events_for
        rows = public_events_for(owner)
    else:
        if not module_enabled(owner, "events"):
            return [], 0
        from apps.events.website_visibility import listed_events
        rows = listed_events(owner).select_related("makerspace").order_by("starts_at", "id")
    if rows is None:
        return [], 0
    count = rows.count()
    offset = (page - 1) * 24
    if offset >= count:
        return [], count
    from .public_page_access import canonical_origin
    return [{"title": row.title, "starts_at": row.starts_at, "ends_at": row.ends_at,
             "event_url": f"{canonical_origin(row.makerspace)}/e/{row.public_token}"}
            for row in rows[offset:offset + 24]], count


def public_catalogue_open(owner):
    """The public inventory list's own gate, as a predicate (edition, module, feature)."""
    from django.http import Http404
    from rest_framework.exceptions import ValidationError
    from .public_site import require_public_catalogue
    try:
        require_public_catalogue(owner)
    except (Http404, ValidationError):
        return False
    return True


def derived_payload(kind, owner, key, payload, *, request=None):
    title = payload.get("title", "")
    if key == "functional_content":
        from .public_page_projection import functional_links
        return functional_links(owner)
    if key == "linked_makerspaces":
        from apps.organizations.public_catalog import linked_spaces_for, space_card
        rows = linked_spaces_for(owner)
        return {"title": title, "count": rows.count(), "results": [space_card(row) for row in rows[:24]],
                "collection_url": f"/api/v1/public/organizations/{owner.slug}/makerspaces/"}
    if key == "organization_events":
        from apps.separability.registry import runtime_active
        if not runtime_active("events"):
            return None
        from apps.organizations.public_catalog import public_events_for, archive_card
        now = timezone.now()
        upcoming = public_events_for(owner, now=now)
        past = public_events_for(owner, period="past", now=now)
        from .public_page_access import canonical_origin
        base = f"/api/v1/public/organizations/{owner.slug}/events/"
        return {"title": title, "upcoming": {"count": upcoming.count() if upcoming is not None else 0,
                "results": [{"title": row.title, "starts_at": row.starts_at, "ends_at": row.ends_at,
                             "event_url": f"{canonical_origin(row.makerspace)}/e/{row.public_token}"}
                            for row in (upcoming[:24] if upcoming is not None else [])], "collection_url": base + "?period=upcoming"},
                "past": {"count": past.count() if past is not None else 0,
                         "results": [archive_card(row) for row in (past[:24] if past is not None else [])],
                         "collection_url": base + "?period=past"}}
    if key == "upcoming_events":
        if not module_enabled(owner, "events"):
            return None
        from .public_page_serializers import PageEventQuery
        query = PageEventQuery(data=request.query_params if request else {})
        query.is_valid(raise_exception=True)
        cards, count = event_cards(kind, owner, page=query.validated_data["events_page"])
        return {"title": title, "count": count, "results": cards,
                "collection_url": f"/api/v1/public/{owner.slug}/page/"}
    if key == "stats":
        metrics = {}
        if payload["show_published_event_count"] and module_enabled(owner, "events"):
            _, metrics["published_event_count"] = event_cards(kind, owner)
        if payload["show_public_inventory_units"] and public_catalogue_open(owner):
            from apps.inventory.models import InventoryProduct
            from apps.inventory.public_availability import get_public_availability
            # Exactly the rows the public catalogue lists: archived products are gone.
            projected = (get_public_availability(row) for row in InventoryProduct.objects.filter(
                makerspace=owner, is_public=True, is_archived=False))
            metrics["public_exact_count_subset_units"] = sum(row["count"] for row in projected if row and "count" in row)
        page = getattr(owner, "public_page", None)
        current_consent = bool(page and page.draft_revision_id and any(
            row["type"] == "stats" and row["enabled"] and row["payload"].get("publish_public_member_count")
            for row in page.draft_revision.document["sections"]))
        if payload["publish_public_member_count"] and current_consent and module_enabled(owner, "membership"):
            from .models import MakerspaceMembership
            metrics["public_member_count"] = MakerspaceMembership.objects.filter(
                makerspace=owner, status="active", user__account_kind="member", user__is_active=True,
                user__access_status="active", user__is_tenant_dump_stub=False).count()
        # An empty metrics block would render a bare heading; omit the section instead.
        return {"title": title, "metrics": metrics} if metrics else None
    if key == "membership_plans":
        from .public_page_plans import plan_cards
        return plan_cards(owner, title)
    if key == "location":
        if not payload["enabled_publicly"]:
            return None
        if payload["source"] == "makerspace_public":
            return {"title": title, "enabled_publicly": True,
                    "address": getattr(owner, "location", ""), "map_url": getattr(owner, "map_url", "")}
        return payload
    return payload
