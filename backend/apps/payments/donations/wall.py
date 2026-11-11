"""The public sponsor wall: an opt-in Pages section and an event-page strip.

Public fields only -- name, tier name, logo, website and blurb -- of sponsors that are shown
on the wall, not archived and inside their active window. Never a contact, amount, perk or
charge. Off (`finance.sponsors`) means the section renders nothing and the routes 404.
"""

from django.db.models import Q
from django.utils import timezone

from apps.makerspaces.platform import feature_enabled

from .models import Sponsor, SponsorEventLink

LIMIT = 60


def live_sponsors(space):
    today = timezone.localdate()
    return Sponsor.objects.filter(
        Q(starts_on__isnull=True) | Q(starts_on__lte=today), Q(ends_on__isnull=True) | Q(ends_on__gte=today),
        makerspace=space, show_on_wall=True, archived_at__isnull=True,
    ).select_related("tier").order_by("tier__rank", "name", "pk")


def card(sponsor):
    from apps.inventory.public_image_storage import public_url

    return {"id": sponsor.pk, "name": sponsor.name, "tier": sponsor.tier.name if sponsor.tier_id else "",
            "logo_url": public_url(sponsor.logo_key) if sponsor.logo_key else "",
            "website_url": sponsor.website_url, "blurb": sponsor.blurb}


def wall(space):
    """Public cards for the space's sponsor wall, or None when the switch is off."""
    if not feature_enabled(space, "finance.sponsors"):
        return None
    return [card(row) for row in live_sponsors(space)[:LIMIT]]


def event_wall(event):
    """Space sponsors linked to this event's own `EventSponsor` rows (live and on the wall)."""
    if not feature_enabled(event.makerspace, "finance.sponsors"):
        return None
    ids = SponsorEventLink.objects.filter(event_sponsor__event=event, event_sponsor__active=True).values("sponsor_id")
    return [card(row) for row in live_sponsors(event.makerspace).filter(pk__in=ids)[:LIMIT]]


SUPPORTER_LIMIT = 30


def supporters(campaign):
    """Decision 242(m): who gave to a campaign, for its public page.

    Every received gift counts toward `supporter_count`; a name appears only when its giver chose to
    be named (`recognize_publicly`, off by default), newest first. Never an amount, email or note.
    """
    from .models import Donation

    paid = Donation.objects.filter(campaign=campaign, status=Donation.Status.PAID)
    accounts = paid.filter(donor__isnull=False).values("donor_id").distinct().count()
    guests = paid.filter(donor__isnull=True).count()
    names = []
    for name in paid.filter(recognize_publicly=True).order_by("-paid_at", "-pk").values_list("donor_name", flat=True):
        name = (name or "").strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= SUPPORTER_LIMIT:
            break
    return {"supporter_count": accounts + guests, "supporters": names}
