"""Public shift command boundary; internal variants require existing event locks."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.audit.services import record
from apps.events import event_authority
from . import commands
from .allocation import remaining_locked
from .errors import ProgrammeError, check_version, require_state
from .models_roles import EventRoleAssignment
from .models_shifts import EventShift, EventShiftSignup, EventShiftAttendance
from .ports import ports
from .sources import sync_shift_locked
from .role_policy import require_requirements


def conflicts(*, member_id, shift, exclude_signup=None):
    rows = EventShiftSignup.objects.filter(member_id=member_id, state="approved",
        event_id=shift.event_id, shift__starts_at__lt=shift.ends_at, shift__ends_at__gt=shift.starts_at)
    if exclude_signup:
        rows = rows.exclude(pk=exclude_signup)
    return rows.exists()


def _requirements(assignment, shift):
    if assignment.member_id is None or assignment.event_id != shift.event_id or assignment.posting_id != shift.posting_id:
        raise ProgrammeError("invalid_assignment", "Choose your application for this posting.", status=404)
    if assignment.imported_inert or assignment.state not in ("applied", "approved"):
        raise ProgrammeError("role_not_eligible", "This application cannot join a shift.", status=403)
    require_requirements(actor_id=assignment.member_id, assignment_id=assignment.pk, shift_id=shift.pk)


def transition_scope(*, event_id, shift_ids):
    accounts = set(EventShiftSignup.objects.filter(event_id=event_id, shift_id__in=shift_ids).values_list("member_id", flat=True))
    issuers = set(EventShift.objects.filter(event_id=event_id, pk__in=shift_ids,
        posting__permission_issuer__isnull=False).values_list("posting__permission_issuer_id", flat=True))
    return tuple(sorted(accounts)), tuple(sorted(issuers))


def _approve_locked(signup, shift, assignment, actor, locks, *, automated=False):
    if signup.member_id not in locks.account_ids:
        raise ProgrammeError("scope_changed", "The waitlist changed; retry this operation.")
    _requirements(assignment, shift)
    require_state(assignment, "approved")
    issuer = actor
    if shift.permission_preset:
        issuer = shift.posting.permission_issuer if automated else actor
        if issuer is None or issuer.pk not in locks.account_ids:
            raise ProgrammeError("issuer_changed", "The posting issuer changed; retry this operation.")
        if not event_authority.can(issuer, shift.event, "manage_volunteers") or not all(
                event_authority.can(issuer, shift.event, p) for p in shift.permission_preset):
            raise ProgrammeError("permission_subset", "A current organizer must approve these duty permissions.", status=403)
    if conflicts(member_id=signup.member_id, shift=shift, exclude_signup=signup.pk):
        raise ProgrammeError("shift_conflict", "You already have an overlapping duty.")
    booked = shift.signups.filter(state="approved").exclude(pk=signup.pk).count()
    if remaining_locked(shift, booked=booked) == 0:
        if not shift.waitlist_enabled:
            raise ProgrammeError("shift_full", "This shift is full.")
        return commands.changed(signup, state="waitlisted")
    commands.changed(signup, state="approved", approved_at=timezone.now(), approved_by=issuer)
    EventShiftAttendance.objects.get_or_create(signup=signup, defaults={
        "event_id": shift.event_id, "makerspace_id": shift.makerspace_id})
    sync_shift_locked(signup_id=signup.pk, actor_id=issuer.pk, locks=locks)
    from .notifications import schedule_signup_locked
    schedule_signup_locked(signup)
    return signup


def apply(*, actor, event_id, shift_id, payload):
    commands.active_member(actor)
    initial = get_object_or_404(EventShift, pk=shift_id, event_id=event_id)
    issuer_id = initial.posting.permission_issuer_id

    def authorize(event):
        assignment = commands.owned(EventRoleAssignment, event_id=event.pk,
            pk=payload["role_assignment_id"], actor=actor)
        ports().require_role_audience(actor_id=actor.pk, event_id=event.pk, posting_id=assignment.posting_id)

    def mutate(event, locks):
        assignment = get_object_or_404(EventRoleAssignment.objects.select_for_update(),
            pk=payload["role_assignment_id"], event=event, member=actor)
        shift = get_object_or_404(EventShift.objects.select_for_update(), pk=shift_id, event=event, kind="volunteer")
        check_version(shift, payload["expected_version"])
        if shift.state != "open" or timezone.now() >= shift.signup_deadline:
            raise ProgrammeError("shift_closed", "This shift is closed.")
        _requirements(assignment, shift)
        if EventShiftSignup.objects.filter(shift=shift, member=actor).exists():
            raise ProgrammeError("signup_exists", "You already have a signup for this shift.")
        signup = commands.new_row(EventShiftSignup, event, shift=shift, assignment=assignment, member=actor)
        if not shift.approval_required and assignment.state == "approved":
            _approve_locked(signup, shift, assignment, actor, locks, automated=True)
        return signup

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="shift.apply", feature="events.volunteering", permission=False, authorize=authorize,
        account_ids=(actor.pk,), authority_ids=(issuer_id,) if issuer_id else (), mutate=mutate, status=201)


def promote_locked(*, shift, actor, event, locks):
    if shift.state != "open" or timezone.now() >= shift.starts_at:
        return
    # FIFO with safe skips for people whose eligibility changed while waiting.
    for signup in shift.signups.select_for_update().filter(state="waitlisted").order_by("queue_at", "pk"):
        if remaining_locked(shift, booked=shift.signups.filter(state="approved").count()) == 0:
            break
        assignment = EventRoleAssignment.objects.get(pk=signup.assignment_id)
        if assignment.state != "approved" or conflicts(member_id=signup.member_id, shift=shift):
            continue
        try:
            _requirements(assignment, shift)
        except Exception as exc:
            from rest_framework.exceptions import APIException
            if isinstance(exc, APIException) and exc.status_code in (400, 403, 404):
                continue
            raise
        _approve_locked(signup, shift, assignment, actor, locks, automated=True)
        record(actor, "event.shift.waitlist_promoted", makerspace=event.makerspace,
               target=signup, meta={"event_id": event.pk})


def transition(*, actor, event_id, signup_id, payload, action, staff=False):
    row = get_object_or_404(EventShiftSignup, pk=signup_id, event_id=event_id)
    account_ids, issuer_ids = transition_scope(event_id=event_id, shift_ids=(row.shift_id,))
    own = action == "withdraw" and not staff

    def authorize(event):
        if own:
            commands.owned(EventShiftSignup, event_id=event.pk, pk=signup_id, actor=actor)

    def mutate(event, locks):
        assignment = EventRoleAssignment.objects.select_for_update().get(pk=row.assignment_id, event=event)
        shift = EventShift.objects.select_for_update().get(pk=row.shift_id, event=event)
        signup = EventShiftSignup.objects.select_for_update().get(pk=signup_id, event=event)
        check_version(signup, payload["expected_version"])
        if action == "approve":
            require_state(signup, "applied", "waitlisted")
            if timezone.now() >= shift.starts_at or shift.state != "open":
                raise ProgrammeError("shift_closed", "This shift is closed.")
            return _approve_locked(signup, shift, assignment, actor, locks)
        if action != "withdraw":
            raise ProgrammeError("invalid_transition", "Unknown shift command.", status=400)
        require_state(signup, "applied", "approved", "waitlisted")
        if EventShiftAttendance.objects.filter(signup=signup, state__in=["checked_in", "checked_out"]).exists():
            raise ProgrammeError("work_locked", "Work has started; ask an organizer to close this shift.")
        commands.changed(signup, state="withdrawn")
        sync_shift_locked(signup_id=signup.pk, actor_id=actor.pk, locks=locks)
        from .notifications import cancelled_signup_locked
        cancelled_signup_locked(signup)
        promote_locked(shift=shift, actor=actor, event=event, locks=locks)
        return signup

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action=f"shift.{action}", feature="events.volunteering", permission=False if own else "manage_volunteers",
        authorize=authorize, account_ids=account_ids, authority_ids=issuer_ids, mutate=mutate)


def withdraw_assignment_locked(*, assignment, actor, event, locks, allow_active=False, reason_code="role_withdrawn"):
    rows = EventShiftSignup.objects.filter(assignment=assignment,
        state__in=["applied", "approved", "waitlisted"]).order_by("shift_id", "pk")
    shift_ids = list(rows.values_list("shift_id", flat=True))
    shifts = {row.pk: row for row in EventShift.objects.select_for_update().filter(pk__in=shift_ids).order_by("pk")}
    for signup in rows.select_for_update():
        if allow_active and EventShiftAttendance.objects.filter(signup=signup,
            state__in=["checked_in", "checked_out"]).exists():
            continue
        shift = shifts[signup.shift_id]
        commands.changed(signup, state="withdrawn")
        sync_shift_locked(signup_id=signup.pk, actor_id=actor.pk, locks=locks)
        from .notifications import cancelled_signup_locked
        cancelled_signup_locked(signup)
        record(actor, "event.shift.withdrawn_with_role", makerspace=event.makerspace,
               target=signup, meta={"event_id": event.pk})
        promote_locked(shift=shift, actor=actor, event=event, locks=locks)
    from apps.events.mentoring.models_queue import OfficeHoursBooking
    bookings = OfficeHoursBooking.objects.filter(mentor_assignment=assignment, state="booked").order_by("slot_id", "pk")
    slot_ids = list(bookings.values_list("slot_id", flat=True))
    slots = {row.pk: row for row in EventShift.objects.select_for_update().filter(pk__in=slot_ids).order_by("pk")}
    from apps.events.mentoring.office_hours_workflow import cancel_locked
    for booking in bookings.select_for_update():
        if slots[booking.slot_id].starts_at <= timezone.now():
            if allow_active:
                continue
            raise ProgrammeError("work_locked", "A booked office-hour session has started.")
        cancel_locked(actor=actor, event=event, booking_id=booking.pk, locks=locks, reason_code=reason_code)
