"""E consumes verified work evidence, independently of attendee registration."""
from django.utils.translation import gettext
from dataclasses import dataclass
from django.db import connection
from django.shortcuts import get_object_or_404
from apps.accounts.models import User
from .commands import active_member
from .errors import ProgrammeError
from .models_roles import EventRoleAssignment
from .models_shifts import EventContributionHours, EventContributionHoursEntry


@dataclass(frozen=True)
class VerifiedContributionSubject:
    event_id: int
    member_id: int
    assignment_id: int
    minutes: int
    evidence: tuple[tuple[int, int], ...]


def resolve(*, event_id, assignment_id, locks):
    """Only call under E/G's event/fence locks during issue or live validation.

    E must revalidate this evidence before issue/download and own revocation on
    changed hours. A role label or imported approval never proves worked hours.
    """
    if not connection.in_atomic_block or locks.event_id != event_id:
        raise RuntimeError("Contribution certificates require the common event lock.")
    role = get_object_or_404(EventRoleAssignment, event_id=event_id, pk=assignment_id,
        state__in=["approved", "completed"], imported_inert=False)
    if role.makerspace_id not in locks.tenant_ids or role.member_id not in locks.account_ids:
        raise RuntimeError("Missing certificate subject fences.")
    active_member(get_object_or_404(User, pk=role.member_id))
    rows = list(EventContributionHours.objects.select_for_update().filter(event_id=event_id,
        signup__assignment=role, signup__member_id=role.member_id, signup__shift__kind="volunteer",
        signup__attendance__state="checked_out", state__in=["verified", "adjusted"]).order_by("pk"))
    evidence = []
    for row in rows:
        entry = EventContributionHoursEntry.objects.filter(hours=row, minutes=row.minutes,
            previous_version=row.version - 1, kind=row.state).exclude(actor_id=role.member_id).first()
        if entry is None or entry.actor_id is None:
            raise ProgrammeError("hours_unverified", gettext("Work needs independent verification."))
        evidence.append((row.pk, row.version))
    minutes = sum(row.minutes for row in rows)
    if minutes <= 0:
        raise ProgrammeError("hours_unverified", gettext("Verified contribution hours are required."))
    return VerifiedContributionSubject(event_id, role.member_id, role.pk, minutes, tuple(evidence))
