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
from . import role_policy


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
        commands.changed(locked, **fields)
        if submit and posting and not posting.approval_required:
            role_policy.auto_approve_locked(row=locked, posting=posting, event=event, locks=locks)
        return locked

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"],
        payload=payload, action="role.submit" if submit else "role.edit", feature=_feature(row.role),
        permission=False, authorize=authorize, account_ids=(actor.pk,), mutate=mutate,
        authority_ids=(row.posting.permission_issuer_id,) if submit and row.posting_id
            and row.posting.permission_issuer_id else ())


def transition(*, actor, event_id, assignment_id, payload, action):
    row = get_object_or_404(EventRoleAssignment, pk=assignment_id, event_id=event_id)
    own = action in ("withdraw", "date_review", "decline")
    from .shift_workflow import transition_scope
    from .models_shifts import EventShiftSignup
    shift_ids = EventShiftSignup.objects.filter(assignment=row).values_list("shift_id", flat=True)
    affected_accounts, issuer_ids = transition_scope(event_id=event_id, shift_ids=shift_ids)

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
        if action in ("reopen_answers", "reconfirm"):
            if action == "reconfirm" and not locked.imported_inert:
                raise ProgrammeError("invalid_transition", "Only imported roles need reconfirmation.")
            require_state(locked, "applied", "approved", "proposed", "declined", "completed")
            return role_policy.reopen_locked(row=locked, actor=actor, event=event, locks=locks,
                                             reason=payload.get("reason", ""))
        if action == "approve":
            require_state(locked, "applied", "proposed")
            role_policy.approve_locked(row=locked, issuer=actor, event=event, locks=locks)
        else:
            require_state(locked, "draft", "proposed", "applied", "approved")
            if action not in ("withdraw", "revoke", "decline", "complete", "reject"):
                raise ProgrammeError("invalid_transition", "Unknown role command.", status=400)
            if action == "complete":
                require_state(locked, "approved")
                if not payload.get("reason", "").strip():
                    raise ProgrammeError("reason_required", "Explain the completion.", status=400)
            if action in ("decline", "reject"):
                require_state(locked, "proposed", "applied")
            # Attendance already started is a work lock. Do not discard its evidence.
            from .models_shifts import EventShiftAttendance
            if own and EventShiftAttendance.objects.filter(signup__assignment=locked,
                    state__in=["checked_in", "checked_out"]).exists():
                raise ProgrammeError("work_locked", "Work has started; ask an organizer to close this role.")
            from .shift_workflow import withdraw_assignment_locked
            withdraw_assignment_locked(assignment=locked, actor=actor, event=event, locks=locks, allow_active=not own)
            commands.changed(locked, state={"withdraw": "withdrawn", "revoke": "revoked",
                "complete": "completed", "decline": "declined", "reject": "declined"}[action])
            if payload.get("reason"):
                commands.changed(locked, application_notes=payload["reason"])
            if locked.role == "mentor":
                from apps.events.mentoring.assignment_workflow import end_role_locked
                end_role_locked(assignment=locked, actor=actor, event=event)
        sync_entitlement_locked(assignment_id=locked.pk, actor_id=actor.pk, locks=locks)
        return locked

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"],
        payload=payload, action=f"role.{action}", feature=_feature(row.role),
        permission=False if own else "manage_volunteers" if row.role == "volunteer" else "manage_team", authorize=authorize,
        account_ids=(row.member_id, *affected_accounts), authority_ids=issuer_ids, mutate=mutate)


def sync_entitlement_locked(*, assignment_id, locks, actor_id=None):
    from django.db import connection
    if not connection.in_atomic_block:
        raise RuntimeError("Role source synchronization requires workflow locks.")
    row = get_object_or_404(EventRoleAssignment, pk=assignment_id, event_id=locks.event_id)
    if row.makerspace_id not in locks.tenant_ids:
        raise RuntimeError("Missing host fence.")
    from .sources import sync_role_locked
    sync_role_locked(assignment_id=assignment_id, actor_id=actor_id, locks=locks)
