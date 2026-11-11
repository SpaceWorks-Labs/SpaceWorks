"""The staff notice for a newly reported incident (never blocks the report).

One staff leg through the `maintenance` family (the reach of machine managers and the Space
Manager), scoped to the machine when the incident names one. An incident placed in the lending,
events or bookings area also reaches that area's managers (open item F1), resolved through the
area's own staff-feature action so mutes and `receives_notifications` still apply. Bodies carry the incident id,
its kind, severity and area -- never the description, a name or a contact detail.
"""

from apps.hardware_requests.notifications_p2 import fanout, revision, safe_adapter
from apps.integrations.destinations import NotificationScope
from apps.integrations.notification_sources import NotificationSource, register_source

KIND = "maintenance.incident"
EVENT = "incident_reported"


def _version(incident):
    return revision(incident.pk, EVENT, incident.severity, incident.area)


def eligible(envelope):
    from apps.maintenance.models import Incident

    from .scope import incidents_on
    from apps.accounts import rbac
    row = rbac.scope_notification_policy(Incident.objects.all(), makerspace_id=envelope.makerspace_id).filter(
        pk=envelope.source_id).first()
    return bool(row is not None and envelope.audience == "staff" and envelope.event == EVENT
                and _version(row) == envelope.revision and incidents_on(envelope.makerspace)
                and row.status in row.OPEN_STATUSES)


# The area owner's notification feature (the same action matrix staff alerts already use).
_AREA_FEATURE = {"lending": "hardware_requests", "events": "events", "bookings": "bookings"}


def _area_staff_ids(incident):
    feature = _AREA_FEATURE.get(incident.area)
    if feature is None:
        return []
    from apps.integrations.staff_notifications import staff_user_ids_for_feature
    return staff_user_ids_for_feature(incident.makerspace, feature)


@safe_adapter
def staff_reported(incident):
    kind = incident.get_kind_display().lower()
    text = (f"A {incident.get_severity_display().lower()}-severity {kind} (#{incident.pk}) was reported in "
            f"{incident.get_area_display()}. Review it in the incident register.")
    scope = NotificationScope(machine=incident.machine) if incident.machine_id else None
    return fanout(space=incident.makerspace, feature="maintenance", stream="maintenance", event=EVENT, kind=KIND,
                  source=incident.pk, version=_version(incident), subject=incident, scope=scope,
                  staff={"subject": f"Safety {kind} reported", "text": text},
                  context={"incident_id": incident.pk, "area": incident.area},
                  staff_context={"incident_id": incident.pk}, staff_extra_ids=_area_staff_ids(incident))


def register():
    register_source(KIND, NotificationSource(eligible))
