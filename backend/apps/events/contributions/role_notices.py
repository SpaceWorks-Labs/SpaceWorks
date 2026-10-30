"""Role decisions are private owner notices backed by the live assignment."""
from apps.accounts.staff_identity import is_person
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource, register_source
from .models_roles import EventRoleAssignment

SOURCE = "events.role_assignment"
MESSAGES = {
    "role.submit": "Your contributor application was submitted.",
    "role.approve": "Your contributor application was approved.",
    "role.reject": "The event team completed its review of your contributor application.",
    "role.decline": "The contributor invitation was declined.",
    "role.withdraw": "Your contributor application was withdrawn.",
    "role.revoke": "Your contributor assignment was revoked.",
    "role.complete": "Your event contribution was marked completed.",
    "role.reopen_answers": "The event team reopened your contributor answers for review.",
    "role.reconfirm": "Review your imported contributor application before it can be approved.",
    "role.event_cancelled": "The event was cancelled and your contributor duties were closed.",
}


def eligible(envelope):
    if envelope.event not in MESSAGES:
        return False
    from apps.makerspaces.platform import feature_enabled, module_enabled
    from apps.makerspaces.servability import is_servable
    row = EventRoleAssignment.objects.select_related("event__makerspace", "member").filter(
        pk=envelope.source_id, member_id=envelope.recipient_id, event_id=envelope.context.get("event_id")).first()
    if row is None or row.makerspace_id != envelope.makerspace_id or str(row.version) != envelope.revision:
        return False
    event = row.event
    feature = "events.volunteering" if row.role == "volunteer" else "events.mentoring" if row.role == "mentor" else "events.hackathons"
    return bool(is_servable(event.makerspace) and module_enabled(event.makerspace, "events")
        and feature_enabled(event.makerspace, feature) and row.member.is_active
        and is_person(row.member) and row.member.access_status == "active"
        and not row.member.is_tenant_dump_stub)


def emit_role_locked(*, row, action):
    if action not in MESSAGES:
        return
    emit(makerspace=row.event.makerspace, recipient=row.member, feature="events", stream="events",
        event=action, audience="member", source_kind=SOURCE, source_id=str(row.pk), revision=str(row.version),
        subject=row, dedup_key=f"event-role:{row.pk}:{row.version}:{action}", context={"event_id": row.event_id},
        rendered={"subject": "Your event contribution", "text": MESSAGES[action]})


def register():
    register_source(SOURCE, NotificationSource(eligible))
