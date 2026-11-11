"""What each makerspace in the public directory offers, batched across the whole page.

`offers` is a list of stable area keys and nothing else (no counts, no ids). A key is
emitted only when its module/capability is on AND that area has a public surface switched
on for the space, so a hidden area never leaks. Everything is decided from the already
loaded makerspace rows plus ONE set-based query per area, never one per space.
"""

from django.utils import timezone

from apps.makerspaces.editions import public_surface_available
from apps.makerspaces.platform import feature_enabled, module_enabled

OFFER_ORDER = ("inventory", "machines", "events", "bookings", "shop", "memberships", "donations")


def _inventory(space):
    # Same gate as require_public_catalogue: public site + catalogue switch + module + loans.
    return (
        space.public_site_enabled and space.public_inventory_enabled
        and public_surface_available("public_inventory")
        and module_enabled(space, "public_inventory") and feature_enabled(space, "loans.enabled")
    )


def _machines(space):
    # Public machine-job intake (see machines.public_intake_access.require_public_intake_available).
    from apps.machines.job_policy import JOB_REQUESTS

    return (
        space.public_site_enabled and public_surface_available("machines")
        and module_enabled(space, "machines") and module_enabled(space, "machine_service")
        and feature_enabled(space, JOB_REQUESTS)
        and module_enabled(space, "membership") and module_enabled(space, "presence")
    )


def _shop(space):
    return (
        space.public_site_enabled and public_surface_available("shop")
        and module_enabled(space, "shop") and feature_enabled(space, "shop.online")
    )


def _donations(space, nonprofit_ids):
    # Mirrors payments.donations.nonprofit.donate_entry_enabled, with the settings row batched.
    from apps.payments.availability import charge_tracking_enabled

    return (
        space.pk in nonprofit_ids and feature_enabled(space, "finance.donations")
        and charge_tracking_enabled(space, "donations")
    )


def _ids(model_qs, spaces):
    return set(model_qs.filter(makerspace_id__in=[s.pk for s in spaces]).values_list("makerspace_id", flat=True).distinct())


def next_events(spaces):
    """{makerspace_id: {title, starts_at, public_url}} -- one query, earliest listed event each."""
    from apps.events.models import Event
    from apps.events.website_visibility import listed_q
    from apps.makerspaces.module_registry import module_available

    if not public_surface_available("events") or not module_available("events"):
        return {}
    ids = [s.pk for s in spaces if s.public_site_enabled and module_enabled(s, "events")]
    if not ids:
        return {}
    rows = (
        Event.objects.filter(listed_q(), makerspace_id__in=ids, status=Event.Status.PUBLISHED,
                             ends_at__gte=timezone.now())
        .order_by("makerspace_id", "starts_at", "id").distinct("makerspace_id")
        .values("makerspace_id", "title", "starts_at", "public_token")
    )
    slugs = {s.pk: s.slug for s in spaces}
    return {
        row["makerspace_id"]: {
            "title": row["title"], "starts_at": row["starts_at"],
            "public_url": f"/m/{slugs[row['makerspace_id']]}/events/{row['public_token']}",
        }
        for row in rows
    }


def build_public_offers(spaces):
    """Return ({makerspace_id: [keys]}, {makerspace_id: next_event | None}) for `spaces`."""
    from apps.bookings.models import BookableSpace
    from apps.makerspaces.membership_features import membership_feature_on
    from apps.makerspaces.models import MembershipPlan
    from apps.payments.donations.models import DonationSettings

    spaces = list(spaces)
    upcoming = next_events(spaces)

    booking_ids = _ids(BookableSpace.objects.filter(is_public=True, is_active=True), spaces) \
        if public_surface_available("bookings") else set()
    plan_ids = _ids(MembershipPlan.objects.filter(is_public=True, is_active=True, archived_at__isnull=True), spaces)
    nonprofit_ids = _ids(DonationSettings.objects.filter(is_nonprofit=True), spaces)

    offers = {}
    for space in spaces:
        on = {
            "inventory": _inventory(space),
            "machines": _machines(space),
            "events": space.pk in upcoming,
            "bookings": space.pk in booking_ids and space.public_site_enabled and module_enabled(space, "bookings"),
            "shop": _shop(space),
            "memberships": space.pk in plan_ids and space.public_site_enabled
            and membership_feature_on(space, "public_plans"),
            "donations": space.public_site_enabled and _donations(space, nonprofit_ids),
        }
        offers[space.pk] = [key for key in OFFER_ORDER if on[key]]
    return offers, {space.pk: upcoming.get(space.pk) for space in spaces}
