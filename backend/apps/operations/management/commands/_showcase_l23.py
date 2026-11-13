"""Tinkerspace: metered machine sessions (lane L23) -- history to show on every new screen.

Switches `machines.sessions` on and writes laser-cutter sessions through the session
workflow's own stop step: three finished member sessions over the past week (each writes
its usage entry and, while machine charges are on, its PENDING charge at the rate frozen
at start) and one session that ran past the type's maximum length, auto-stopped and
flagged for staff to check. Sessions are opened directly at past times because the start
step checks live presence; nothing here moves money.
"""

from datetime import timedelta

from django.utils import timezone

from apps.machines import sessions_billing as billing
from apps.machines.models import Machine, MachineSession
from apps.machines.sessions_service import stop

FEATURE = "machines.sessions"
HISTORY = ((6, 45, "member"), (4, 90, "member"), (2, 30, "staff"))


def seed_l23(space, manager, members):
    space.enabled_features = sorted(set(space.enabled_features or []) | {FEATURE})
    space.save(update_fields=["enabled_features"])
    laser = Machine.objects.filter(makerspace=space, machine_type__slug="laser_cutter", is_active=True).first()
    people = list(members.values())
    if laser is None or not people:
        return
    now = timezone.now()
    for index, (days_ago, minutes, reason) in enumerate(HISTORY):
        member = people[index % len(people)]
        started = (now - timedelta(days=days_ago)).replace(hour=15, minute=0, second=0, microsecond=0)
        session = _open(space, laser, member, started, manager if reason == "staff" else member)
        stop(session, actor=manager if reason == "staff" else member, reason=reason,
             at=started + timedelta(minutes=minutes))
    member = people[-1]
    started = now - timedelta(days=1, hours=6)
    session = _open(space, laser, member, started, member)
    stop(session, actor=None, reason=MachineSession.StopReason.MAX_LENGTH, at=started + timedelta(minutes=240))


def _open(space, machine, member, started, actor):
    rate = billing.start_quote(machine, member) if billing.billing_active(space) else None
    return MachineSession.objects.create(
        makerspace=space, machine=machine, machine_type=machine.machine_type, member=member,
        source=MachineSession.Source.STAFF if actor is not member else MachineSession.Source.MEMBER_QR,
        started_at=started, started_by=actor, billable=bool(rate is not None and rate.total > 0),
        quote_snapshot=rate.to_snapshot() if rate is not None else {}, quote_digest=rate.digest if rate else "")
