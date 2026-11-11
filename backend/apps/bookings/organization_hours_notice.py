"""Tell the booking staff once when an organization's hours bank runs low or runs out.

Called by `organization_hours.consume` after a booking takes hours. A staff-only notice (the bookings
family's recipients: Space Managers and Booking Managers, per the space's matrix and each person's own
preferences), never a message to the organization. The remainder of a booking is still charged when the bank
is empty, so this is a heads-up, not a block. One notice per organization, period and level: the revision
carries all three, so a repeat finds its twin and stays silent.
"""
from django.utils.translation import gettext

from apps.integrations.notification_sources import NotificationSource, register_source

SOURCE = "bookings.hours_bank"
EVENT = "hours_bank_low"
LOW_SHARE = 5  # "low" is a fifth of the pool or less


def level_for(pool, used):
    remaining = pool - used
    if pool > 0 and remaining <= 0:
        return "exhausted"
    return "low" if pool > 0 and remaining * LOW_SHARE <= pool else None


def alert_if_needed(makerspace, organization, period_key, pool, used):
    """Never raises: a notice cannot undo the booking that triggered it."""
    level = level_for(pool, used)
    if level is None:
        return None
    from apps.hardware_requests.notifications_p2 import fanout, revision, safe_adapter
    from apps.integrations.notification_links import local_link

    @safe_adapter
    def send():
        values = {"organization": organization.name, "period": period_key,
                  "hours": round(max(0, pool - used) / 60, 1)}
        if level == "exhausted":
            staff = {"subject": gettext("%(organization)s has used all its included hours") % values,
                     "text": gettext("The hours bank of %(organization)s is empty for %(period)s. "
                                     "Further bookings are charged in full.") % values}
        else:
            staff = {"subject": gettext("%(organization)s is running low on included hours") % values,
                     "text": gettext("%(organization)s has %(hours)s hours left in its hours bank for "
                                     "%(period)s.") % values}
        staff["link"] = local_link(makerspace, "admin", "bookings")
        return fanout(space=makerspace, feature="bookings", stream="bookings", event=EVENT, kind=SOURCE,
                      source=organization.pk, version=revision(organization.pk, period_key, level),
                      subject=organization, staff=staff, rooms=False,
                      context={"organization_id": organization.pk, "level": level})
    return send()


def eligible(envelope):
    from apps.makerspaces.platform import module_enabled

    from .organization_hours import applies, bank
    from apps.organizations.models import Organization
    organization = Organization.objects.filter(pk=envelope.context.get("organization_id")).first()
    space = envelope.makerspace
    return bool(organization is not None and envelope.audience == "staff"
                and str(organization.pk) == str(envelope.source_id) and module_enabled(space, "bookings")
                and applies(space) and bank(space, organization) is not None)


def register():
    register_source(SOURCE, NotificationSource(eligible))
