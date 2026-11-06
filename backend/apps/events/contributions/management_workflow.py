"""Posting/shift configuration belongs to the same locked contributor boundary."""
from django.utils.translation import gettext
from django.core.exceptions import ValidationError as ModelValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.accounts.staff_identity import person_q
from apps.events import event_authority
from . import commands
from .allocation import require_capacity_edit
from .authority import HELPER_PERMISSIONS
from .errors import ProgrammeError, check_version
from .models_roles import EventRoleAssignment, EventRolePosting, EventSponsor
from .models_shifts import EventShift
from .ports import ports
from .serializers_management import requirements
from .subjects import subject_for


def _valid(row):
    try:
        row.full_clean(validate_unique=False)
    except ModelValidationError as exc:
        raise ValidationError(getattr(exc, "message_dict", exc.messages)) from exc


def save_posting(*, actor, event_id, payload, posting_id=None):
    if posting_id is None:
        missing = {key: "This field is required." for key in ("role", "title", "opens_at", "closes_at") if key not in payload}
        if missing:
            raise ValidationError(missing)
    schema = ports().forms.validate_schema(schema=payload["form_schema"]) if "form_schema" in payload else None

    def mutate(event, locks):
        row = get_object_or_404(EventRolePosting.objects.select_for_update(), pk=posting_id, event=event) if posting_id else (
            EventRolePosting(event=event, makerspace_id=event.makerspace_id))
        check_version(row, payload["expected_version"]) if posting_id else _zero(payload)
        original_role = row.role
        for key, value in payload.items():
            if key not in ("operation_id", "expected_version", "form_schema"):
                setattr(row, key, value)
        if posting_id and original_role != row.role:
            raise ValidationError({"role": gettext("A posting's role cannot change.")})
        if schema is not None:
            row.form_schema = schema
        if not posting_id or "permission_preset" in payload:
            row.permission_issuer = actor
        row.requirements = requirements(row.requirements)
        if not set(row.permission_preset) <= HELPER_PERMISSIONS.get(row.role, set()) or not all(
                event_authority.can(actor, event, p) for p in row.permission_preset):
            raise ProgrammeError("permission_subset", "The posting exceeds your helper permissions.", status=403)
        if row.closes_at and row.closes_at > event.ends_at:
            raise ValidationError({"closes_at": gettext("The posting must close before the event ends.")})
        if posting_id:
            row.version += 1
        _valid(row)
        row.save()
        # P freezes the current date sources, rather than persisting computed ages.
        if row.state == "closed":
            owners = set(EventRoleAssignment.objects.filter(posting=row).values_list("member_id", flat=True))
            if not owners <= set(locks.account_ids):
                raise ProgrammeError("scope_changed", "Applications changed; retry closing the posting.")
            for assignment in EventRoleAssignment.objects.select_for_update().filter(posting=row,
                    answer_locked_at__isnull=True).order_by("pk"):
                ports().forms.lock_locked(subject=subject_for(assignment), locks=locks)
                commands.changed(assignment, answer_locked_at=timezone.now())
        return row

    # G's combined fence adapter discovers the affected assignment accounts before
    # calling this command for posting closure; declare the complete set up front.
    account_ids = tuple(EventRoleAssignment.objects.filter(posting_id=posting_id,
        event_id=event_id).values_list("member_id", flat=True)) if posting_id else ()
    role = payload.get("role") or get_object_or_404(EventRolePosting, pk=posting_id, event_id=event_id).role
    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="posting.save", feature="events.mentoring" if role == "mentor" else "events.volunteering",
        permission="manage_volunteers" if role == "volunteer" else "manage_team", mutate=mutate,
        account_ids=account_ids, status=200 if posting_id else 201)


def _zero(payload):
    if payload["expected_version"] != 0:
        raise ProgrammeError("stale_version", "Use version zero for a new item.")


def save_shift(*, actor, event_id, payload, shift_id=None):
    if shift_id is None:
        missing = {key: "This field is required." for key in ("posting_id", "starts_at", "ends_at", "signup_deadline", "task") if key not in payload}
        if missing:
            raise ValidationError(missing)
    def mutate(event, locks):
        row = get_object_or_404(EventShift.objects.select_for_update(), pk=shift_id, event=event) if shift_id else (
            EventShift(event=event, makerspace_id=event.makerspace_id))
        check_version(row, payload["expected_version"]) if shift_id else _zero(payload)
        if shift_id and (row.signups.exists() or row.bookings.filter(state="booked").exists()):
            schedule_keys = {"posting_id", "starts_at", "ends_at", "kind", "mentor_assignment_id", "state"}
            if payload.get("cancel_bookings") or any(key in payload and payload[key] != getattr(row, key) for key in schedule_keys):
                if row.kind != "office_hours" or not payload.get("cancel_bookings") or not payload.get("reason", "").strip():
                    raise ProgrammeError("active_bookings", "Explicitly cancel booked teams with a reason before changing this slot.")
                from apps.events.mentoring.models_queue import OfficeHoursChange
                from apps.events.mentoring.office_hours_workflow import cancel_locked
                event_authority.require(actor, event, "manage_team")
                old = {key: str(getattr(row, key)) for key in schedule_keys}
                new = {key: str(payload.get(key, getattr(row, key))) for key in schedule_keys}
                commands.new_row(OfficeHoursChange, event, slot=row, actor=actor,
                    reason=payload["reason"], old_schedule=old, new_schedule=new)
                for booking in row.bookings.select_for_update().filter(state="booked").order_by("pk"):
                    cancel_locked(actor=actor, event=event, booking_id=booking.pk, locks=locks, reason_code="slot_changed")
        if shift_id and "kind" in payload and payload["kind"] != row.kind and (row.signups.exists() or row.bookings.exists()):
            raise ValidationError({"kind": gettext("A slot with participation history cannot change kind.")})
        for key, value in payload.items():
            if key not in ("operation_id", "expected_version", "cancel_bookings", "reason"):
                setattr(row, key, value)
        row.posting = get_object_or_404(EventRolePosting, pk=row.posting_id, event=event)
        row.requirements = requirements(row.requirements)
        if not set(row.permission_preset) <= set(row.posting.permission_preset):
            raise ProgrammeError("permission_subset", "Shift permissions exceed the posting preset.", status=403)
        if row.kind == "office_hours":
            get_object_or_404(EventRoleAssignment, pk=row.mentor_assignment_id, event=event,
                              role="mentor", state="approved", imported_inert=False)
        if row.starts_at is None or row.ends_at is None or not event.starts_at <= row.starts_at < row.ends_at <= event.ends_at:
            raise ValidationError({"starts_at": gettext("Choose an interval inside the event.")})
        booked = (row.bookings.filter(state="booked").count() if row.kind == "office_hours" else
                  row.signups.filter(state="approved").count()) if shift_id else 0
        require_capacity_edit(row, capacity=row.capacity, booked=booked)
        if shift_id:
            row.version += 1
        _valid(row)
        row.save()
        return row

    kind = payload.get("kind") or (get_object_or_404(EventShift, pk=shift_id, event_id=event_id).kind if shift_id else "volunteer")
    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="shift.save", feature="events.mentoring" if kind == "office_hours" else "events.volunteering",
        permission="manage_team" if kind == "office_hours" else "manage_volunteers",
        mutate=mutate, status=200 if shift_id else 201)


def save_role(*, actor, event_id, payload, assignment_id=None):
    if assignment_id is None:
        missing = {key: "This field is required." for key in ("member_id", "role") if key not in payload}
        if missing:
            raise ValidationError(missing)
    def mutate(event, locks):
        if assignment_id:
            row = get_object_or_404(EventRoleAssignment.objects.select_for_update(), pk=assignment_id, event=event)
            check_version(row, payload["expected_version"])
            if set(payload) - {"operation_id", "expected_version", "display_on_page"}:
                raise ValidationError(gettext("Existing role identity and authority use their dedicated workflows."))
            return commands.changed(row, display_on_page=payload.get("display_on_page", row.display_on_page))
        _zero(payload)
        from apps.accounts.models import User
        member = get_object_or_404(User, person_q(), pk=payload.get("member_id"),
                                   is_active=True, access_status="active", is_tenant_dump_stub=False)
        role = payload.get("role")
        if role == "co_organizer":
            event_authority.require(actor, event, None)
        posting = get_object_or_404(EventRolePosting, pk=payload["posting_id"], event=event,
            role=role) if payload.get("posting_id") else None
        sponsor = get_object_or_404(EventSponsor, pk=payload["sponsor_id"], event=event,
            active=True) if payload.get("sponsor_id") else None
        row = EventRoleAssignment(event=event, makerspace_id=event.makerspace_id, member=member,
            role=role, posting=posting, sponsor=sponsor, origin="staff", state="proposed",
            delegated_permissions=payload.get("delegated_permissions", []), track_ids=payload.get("track_ids", []))
        _valid(row)
        row.save()
        return row

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="role.save", feature=None, permission="manage_team", mutate=mutate,
        account_ids=(get_object_or_404(EventRoleAssignment, event_id=event_id, pk=assignment_id).member_id,)
            if assignment_id else (payload["member_id"],), status=200 if assignment_id else 201)
