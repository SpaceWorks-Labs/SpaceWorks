"""Locked policy shared by manual approval and posting auto-approval."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.accounts.models import User
from apps.events import event_authority
from . import commands
from .errors import ProgrammeError
from .ports import ports, required_hook
from .subjects import subject_for


def require_requirements(*, actor_id, assignment_id, shift_id):
    from .models_policy import EventRequirementOverride
    from django.db.models import Q
    ids = tuple(EventRequirementOverride.objects.filter(assignment_id=assignment_id).filter(
        Q(shift_id=shift_id) | Q(shift__isnull=True)).values_list("pk", flat=True))
    ports().require_requirements(actor_id=actor_id, assignment_id=assignment_id,
                                 shift_id=shift_id, override_ids=ids)


def approve_locked(*, row, issuer, event, locks):
    if row.imported_inert:
        raise ProgrammeError("imported_inert", "Reconfirm this imported role before granting authority.")
    if row.member_id not in locks.account_ids or issuer.pk not in locks.account_ids:
        raise ProgrammeError("scope_changed", "Approval authority changed; retry.")
    if not event_authority._active(issuer):
        raise ProgrammeError("issuer_inactive", "A current organizer must approve this role.", status=403)
    event_authority.require(issuer, event, None if row.role == "co_organizer" else
                            "manage_volunteers" if row.role == "volunteer" else "manage_team")
    ports().forms.require_approval_locked(subject=subject_for(row), locks=locks)
    require_requirements(actor_id=row.member_id, assignment_id=row.pk, shift_id=None)
    ports().forms.lock_locked(subject=subject_for(row), locks=locks)
    commands.changed(row, state="approved", approved_by=issuer, approved_at=timezone.now(),
                     answer_locked_at=timezone.now())
    if row.role == "mentor":
        from apps.events.mentoring.models_queue import MentorProfile
        MentorProfile.objects.get_or_create(assignment=row, defaults={"event": event,
            "makerspace_id": event.makerspace_id, "skills": row.skills, "availability": row.availability})
    from .role_workflow import sync_entitlement_locked
    sync_entitlement_locked(assignment_id=row.pk, actor_id=issuer.pk, locks=locks)
    from .role_notices import emit_role_locked
    emit_role_locked(row=row, action="role.approve")


def auto_approve_locked(*, row, posting, event, locks):
    if posting.permission_issuer_id is None or posting.permission_issuer_id not in locks.account_ids:
        raise ProgrammeError("issuer_changed", "A current organizer must review this posting.")
    issuer = get_object_or_404(User, pk=posting.permission_issuer_id)
    if not event_authority._active(issuer):
        raise ProgrammeError("issuer_inactive", "A current organizer must approve this role.", status=403)
    event_authority.require(issuer, event, "manage_volunteers" if row.role == "volunteer" else "manage_team")
    if not all(event_authority.can(issuer, event, p) for p in posting.permission_preset):
        raise ProgrammeError("permission_subset", "The posting issuer no longer holds these permissions.", status=403)
    row.delegated_permissions = list(posting.permission_preset)
    row.save(update_fields=["delegated_permissions"])
    approve_locked(row=row, issuer=issuer, event=event, locks=locks)


def reopen_locked(*, row, actor, event, locks, reason):
    from .models_policy import EventRoleAnswerRevision
    from .models_roles import ACTIVE, EventRoleAssignment
    from .form_storage import canonical_answers
    if not reason.strip():
        raise ProgrammeError("reason_required", "Explain why the answers need a new revision.", status=400)
    if EventRoleAssignment.objects.filter(event=event, member_id=row.member_id,
            role=row.role, sponsor_id=row.sponsor_id, state__in=ACTIVE).exclude(pk=row.pk).exists():
        raise ProgrammeError("application_exists", "This member already has an active application.")
    commands.new_row(EventRoleAnswerRevision, event, assignment=row, actor=actor,
        answers=canonical_answers(row.answers if row.answers != "{}" else '{"version":2,"answers":[]}'),
        reason=reason, schema_version=row.form_schema_version,
        locked_at=row.answer_locked_at)
    required_hook(ports().forms, "reopen_locked")(subject=subject_for(row),
        previous_version=row.version, locks=locks)
    from .shift_workflow import withdraw_assignment_locked
    withdraw_assignment_locked(assignment=row, actor=actor, event=event, locks=locks, allow_active=True)
    if row.role == "mentor":
        from apps.events.mentoring.assignment_workflow import end_role_locked
        end_role_locked(assignment=row, actor=actor, event=event)
    commands.changed(row, state="draft", answer_locked_at=None, submitted_at=None,
        approved_at=None, approved_by=None, consent_revision=None, date_review_required=True,
        imported_inert=False, display_on_page=False)
    from .role_workflow import sync_entitlement_locked
    sync_entitlement_locked(assignment_id=row.pk, actor_id=actor.pk, locks=locks)
    from apps.events.certificates.contribution_proof import invalidate_role_locked
    invalidate_role_locked(event=event, assignment_id=row.pk, actor=actor)
    return row
