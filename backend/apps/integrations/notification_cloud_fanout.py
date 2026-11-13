"""Small, explicit legacy fanout envelope; full notifications remain unchanged."""
from django.conf import settings

from apps.operations.cloud_jobs import bounded
from apps.operations.cloud_jobs.contracts import JobsUnavailable


class UnsupportedFanout(JobsUnavailable):
    pass


def free():
    return getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free"


def check():
    if free():
        bounded.check()
        from apps.operations.cloud_runtime import check as admitted
        admitted()


def preflight(makerspace, payload):
    if not free():
        return
    check()
    if len(payload.emails) > 2 or len(payload.inbox) > 2:
        raise UnsupportedFanout("Legacy notification fanout exceeds the free two-recipient limit.")
    for email in payload.emails:
        if (len(email.subject.encode()) > 512 or len(email.text_body.encode()) > 65536
                or len(email.html_body.encode()) > 65536):
            raise UnsupportedFanout("Legacy email content exceeds the free profile limit.")
    # Reject the whole fanout before creating any transport rows. Never silently
    # truncate recipients or repeatedly create the earlier recipients' logs.
    from .models_destinations import NotificationDestination
    rows = NotificationDestination.objects.filter(makerspace=makerspace)
    if rows.count() > 12:
        raise UnsupportedFanout("Legacy notification destinations exceed the free profile limit.")
    counts = {}
    for row in rows:
        counts[row.channel] = counts.get(row.channel, 0) + 1
        if counts[row.channel] > 2 or any(getattr(row, name).count() > 25 for name in (
            "machine_scopes", "machine_type_scopes", "category_scopes")):
            raise UnsupportedFanout("Legacy notification room scope exceeds the free profile limit.")
    from apps.makerspaces.models import MakerspaceMembership
    if MakerspaceMembership.staff_tracks.filter(makerspace=makerspace, status="active").count() > 25:
        raise UnsupportedFanout("Legacy staff resolution exceeds the free profile limit.")
    if len(payload.text.encode()) > 65536:
        raise UnsupportedFanout("Legacy notification content exceeds the free profile limit.")

