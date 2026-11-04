"""Machine-session notices (lane L23): an auto-stopped session tells its member and staff.

Same durable fan-out and channel resolver as the other machine notices (the `printing`
category). The member leg goes to the session's member only; the staff leg to people who
manage that machine type, so they can check and correct the time before confirming.
No room broadcast: a session is one person's machine time.
"""

from apps.accounts import rbac
from apps.hardware_requests.notifications_p2 import fanout, revision, safe_adapter
from apps.integrations.destinations import NotificationScope
from apps.integrations.notification_links import local_link
from apps.integrations.notification_sources import NotificationSource, register_source

KIND = "machines.session"
EVENT = "session_auto_stopped"
REASONS = {"max_length": "the maximum length was reached", "check_out": "the member checked out",
           "closing": "the space closed"}


def _version(row):
    return revision(EVENT, row.ended_at, row.stop_reason)


def eligible(envelope):
    from apps.machines.models import MachineSession
    from apps.machines.sessions_state import sessions_on
    row = rbac.scope_notification_policy(MachineSession.objects.all(),
                                         makerspace_id=envelope.makerspace_id).filter(pk=envelope.source_id).first()
    if row is None or row.ended_at is None or _version(row) != envelope.revision:
        return False
    if not sessions_on(envelope.makerspace):
        return False
    if envelope.audience == "requester":
        return envelope.recipient_id == row.member_id
    if envelope.recipient_id:
        from apps.accounts.models import User

        from . import access
        recipient = User.objects.filter(pk=envelope.recipient_id).first()
        return recipient is not None and access.can_create_machine(recipient, row.makerspace_id, row.machine_type)
    return True


@safe_adapter
def notify_auto_stopped(row):
    reason = REASONS.get(row.stop_reason, "it was stopped automatically")
    name, minutes = row.machine.name, row.duration_minutes
    own = {"subject": f"Your session on {name} stopped",
           "text": f"Your session on {name} stopped after {minutes} minutes because {reason}. Staff check the "
                   "time before any charge is final.",
           "link": local_link(row.makerspace, "member")}
    staff = {"subject": f"Machine session #{row.pk} needs a check",
             "text": f"A session on {name} stopped after {minutes} minutes because {reason}. Check the time and "
                     "confirm it in Machines > Sessions."}
    return fanout(space=row.makerspace, feature="printing", stream="printing", event=EVENT, kind=KIND,
                  source=row.pk, version=_version(row), subject=row, owner=row.member, own=own, staff=staff,
                  rooms=False, scope=NotificationScope(machine=row.machine, machine_type=row.machine_type),
                  context={"machine_id": row.machine_id})


def register():
    register_source(KIND, NotificationSource(eligible))
