"""The sole role lifecycle and role-source synchronization entry point."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.events import event_authority
from apps.events.contracts.subjects import AnswerSubject, SubjectKind
from . import commands
from .errors import ProgrammeError, check_version, require_state
from .models_roles import ACTIVE, EventRoleAssignment, EventRolePosting
from .ports import ports
from .subjects import subject_for
from .form_storage import canonical_answers


def _open(posting):
    now = timezone.now()
    if posting.state != "open" or not posting.opens_at <= now < posting.closes_at:
        raise ProgrammeError("posting_closed", "This posting is closed.")


def _feature(role):
    return {"mentor": "events.mentoring", "volunteer": "events.volunteering"}.get(role)


def apply(*, actor, event_id, posting_id, payload):
    commands.active_member(actor)
    posting = get_object_or_404(EventRolePosting, pk=posting_id, event_id=event_id)
    subject = AnswerSubject(event_id=event_id, owner_member_id=actor.pk,
        kind=SubjectKind.ROLE_ASSIGNMENT, creation_operation_id=payload["operation_id"])
    prepared = ports().forms.prepare(actor_id=actor.pk, subject=subject,
        schema=posting.form_schema, payload=payload, submit=False, previous_answers="{}")

    def authorize(event):
        ports().require_role_audience(actor_id=actor.pk, event_id=event.pk, posting_id=posting_id)

    def mutate(event, locks):
        locked = EventRolePosting.objects.select_for_update().get(pk=posting_id, event=event)
        _open(locked)
        if payload["expected_version"] != 0:
            raise ProgrammeError("stale_version", "Start a new application with version zero.")
        existing = EventRoleAssignment.objects.filter(event=event, member=actor,
            role=locked.role, sponsor__isnull=True, state__in=ACTIVE).first()
        if existing:
            raise ProgrammeError("application_exists", "You already have an application.", application_id=existing.pk)
        row = commands.new_row(EventRoleAssignment, event, member=actor, posting=locked,
            role=locked.role, skills=payload.get("skills", []), availability=payload.get("availability", []))
        result = ports().forms.apply_locked(prepared=prepared, subject=subject_for(row), locks=locks)
        row.answers = canonical_answers(result["answers_json"])
        row.form_schema_version = result["schema_version"]
        row.save(update_fields=["answers", "form_schema_version"])
        return row

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"],
        payload=payload, action="role.apply", feature=_feature(posting.role), permission=False,
        authorize=authorize, account_ids=(actor.pk,), mutate=mutate, status=201)


def edit(*, actor, event_id, assignment_id, payload, submit=False):
    row = commands.owned(EventRoleAssignment, event_id=event_id, pk=assignment_id, actor=actor)
    prepared = ports().forms.prepare(actor_id=actor.pk, subject=subject_for(row),
        schema=row.posting.form_schema if row.posting_id else {}, payload=payload, submit=submit or row.state == "applied",
        previous_answers=row.answers)

    def authorize(event):
        commands.owned(EventRoleAssignment, event_id=event.pk, pk=assignment_id, actor=actor)
        ports().require_role_audience(actor_id=actor.pk, event_id=event.pk, posting_id=row.posting_id)

    def mutate(event, locks):
        posting = EventRolePosting.objects.select_for_update().get(pk=row.posting_id, event=event) if row.posting_id else None
        locked = EventRoleAssignment.objects.select_for_update().get(pk=assignment_id, event=event)
        check_version(locked, payload["expected_version"])
        require_state(locked, "draft", "proposed", "applied")
        if locked.answer_locked_at:
            raise ProgrammeError("answers_locked", "The application answers are locked.")
        if posting:
            _open(posting)
        result = ports().forms.apply_locked(prepared=prepared, subject=subject_for(locked), locks=locks)
        fields = {"answers": canonical_answers(result["answers_json"]), "form_schema_version": result["schema_version"],
                  "consent_revision": result.get("consent_revision")}
        fields.update({key: payload[key] for key in ("skills", "availability") if key in payload})
        if submit:
            fields.update(state="applied", submitted_at=timezone.now())
        return commands.changed(locked, **fields)

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"],
        payload=payload, action="role.submit" if submit else "role.edit", feature=_feature(row.role),
        permission=False, authorize=authorize, account_ids=(actor.pk,), mutate=mutate)


def transition(*, actor, event_id, assignment_id, payload, action):
    row = get_object_or_404(EventRoleAssignment, pk=assignment_id, event_id=event_id)
    own = action in ("withdraw", "date_review")

    def authorize(event):
        if own:
            commands.owned(EventRoleAssignment, event_id=event.pk, pk=assignment_id, actor=actor)

    def mutate(event, locks):
        if row.posting_id:
            EventRolePosting.objects.select_for_update().get(pk=row.posting_id, event=event)
        locked = EventRoleAssignment.objects.select_for_update().get(pk=assignment_id, event=event)
        check_version(locked, payload["expected_version"])
        if action == "date_review":
            ports().forms.review_date_locked(subject=subject_for(locked),
                revision=payload["event_date_revision"], as_of_date=str(payload["reviewed_as_of_date"]), locks=locks)
            return commands.changed(locked, date_review_required=False)
        if action == "approve":
            require_state(locked, "applied", "proposed")
            if locked.role == "co_organizer":
                event_authority.require(actor, event, None)
            if locked.imported_inert:
                raise ProgrammeError("imported_inert", "Reconfirm this imported role before granting authority.")
            ports().forms.require_approval_locked(subject=subject_for(locked), locks=locks)
            ports().require_requirements(actor_id=locked.member_id, assignment_id=locked.pk, shift_id=None)
            commands.changed(locked, state="approved", approved_by=actor, approved_at=timezone.now(),
                             answer_locked_at=timezone.now())
            if locked.role == "mentor":
                from apps.events.mentoring.models_queue import MentorProfile
                if not MentorProfile.objects.filter(assignment=locked).exists():
                    commands.new_row(MentorProfile, event, assignment=locked,
                        skills=locked.skills, availability=locked.availability)
        else:
            require_state(locked, "draft", "proposed", "applied", "approved")
            if action not in ("withdraw", "revoke"):
                raise ProgrammeError("invalid_transition", "Unknown role command.", status=400)
            # Attendance already started is a work lock. Do not discard its evidence.
            from .models_shifts import EventShiftAttendance
            if own and EventShiftAttendance.objects.filter(signup__assignment=locked,
                    state__in=["checked_in", "checked_out"]).exists():
                raise ProgrammeError("work_locked", "Work has started; ask an organizer to close this role.")
            from .shift_workflow import withdraw_assignment_locked
            withdraw_assignment_locked(assignment=locked, actor=actor, event=event, locks=locks, allow_active=not own)
            commands.changed(locked, state="withdrawn" if own else "revoked")
        sync_entitlement_locked(assignment_id=locked.pk, actor_id=actor.pk, locks=locks)
        return locked

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"],
        payload=payload, action=f"role.{action}", feature=_feature(row.role),
        permission=False if own else "manage_team", authorize=authorize,
        account_ids=(row.member_id,), mutate=mutate)


def sync_entitlement_locked(*, assignment_id, locks, actor_id=None):
    from django.db import connection
    if not connection.in_atomic_block:
        raise RuntimeError("Role source synchronization requires workflow locks.")
    row = get_object_or_404(EventRoleAssignment, pk=assignment_id, event_id=locks.event_id)
    if row.makerspace_id not in locks.tenant_ids:
        raise RuntimeError("Missing host fence.")
    from .sources import sync_role_locked
    sync_role_locked(assignment_id=assignment_id, actor_id=actor_id, locks=locks)
