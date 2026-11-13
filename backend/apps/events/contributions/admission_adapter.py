"""Approved contributors use real registration admission; C owns no attendee writer."""
from django.utils.translation import gettext
from dataclasses import dataclass
from typing import Literal, Protocol
from django.shortcuts import get_object_or_404
from apps.events.contracts.providers import LockedContext
from . import commands
from .errors import ProgrammeError, check_version
from .models_roles import EventRoleAssignment
from .ports import ports, required_hook
from .role_policy import require_requirements


@dataclass(frozen=True, kw_only=True)
class ContributorAdmission:
    event_id: int
    member_id: int
    assignment_id: int
    ticket_type_id: int
    capacity_policy: Literal["event_capacity", "reserved_contributor_capacity"]


class ContributorAdmissions(Protocol):
    def admit_locked(self, *, request: ContributorAdmission, actor_id: int,
                     operation_id: str, locks: LockedContext) -> int:
        """A/G verifies distinct contributor ticket, configured capacity policy,
        audience/waiver/CoC, money and admission locks using existing registration
        services. Return a real EventRegistration ID; never skip capacity checks.
        """
        ...


class CanonicalContributorAdmissions:
    def admit_locked(self, **kwargs):
        from apps.events.services_registration_admission import admit_contributor_locked
        return admit_contributor_locked(**kwargs)


def close_event_locked(*, event, actor, locks):
    """Freeze submitted role/ordinary sources, preserving pending owner review."""
    from apps.events.programme_locks import assert_lock_context
    from apps.events.answer_derivations.models import EventAnswerDerivation
    from apps.events.answer_derivations.subjects import binding_for, subject_model
    from apps.events.answer_derivations.lifecycle import lock_subject_locked
    from apps.events.contracts.subjects import SubjectKind
    assert_lock_context(locks)
    for kind in (SubjectKind.ROLE_ASSIGNMENT, SubjectKind.REGISTRATION):
        ids = EventAnswerDerivation.objects.filter(event=event, locked_at__isnull=True).values_list(
            f"{kind.value}_id", flat=True)
        rows = subject_model(kind).objects.select_for_update().filter(event=event, pk__in=ids, member_id__isnull=False)
        if kind == SubjectKind.ROLE_ASSIGNMENT:
            rows = rows.exclude(state="draft")
        for row in rows.order_by("pk"):
            lock_subject_locked(actor_id=getattr(actor, "pk", None), subject=binding_for(row, kind), locks=locks, closing=True)


def cancel_event_locked(*, event, actor, locks):
    """C's lifecycle remains the only writer of roles, duties and entitlements."""
    from apps.events.programme_locks import assert_lock_context
    from .models_roles import EventRolePosting
    from . import role_workflow
    assert_lock_context(locks)
    close_event_locked(event=event, actor=actor, locks=locks)
    if (EventRoleAssignment.objects.filter(event=event).exists()
            or EventRolePosting.objects.filter(event=event).exists()):
        required_hook(role_workflow, "cancel_event_locked")(event_id=event.pk,
            actor_id=getattr(actor, "pk", None), locks=locks)


def admit(*, actor, event_id, assignment_id, payload):
    initial = get_object_or_404(EventRoleAssignment, event_id=event_id, pk=assignment_id)

    def mutate(event, locks):
        from .models_admission import EventContributorAdmission
        from apps.events.models import EventRegistration, EventTicketType
        row = get_object_or_404(EventRoleAssignment.objects.select_for_update(), event=event, pk=assignment_id,
            state="approved", imported_inert=False)
        check_version(row, payload["expected_version"])
        if payload["capacity_policy"] not in ("event_capacity", "reserved_contributor_capacity"):
            raise ProgrammeError("invalid_capacity_policy", gettext("Choose an explicit contributor capacity policy."), status=400)
        require_requirements(actor_id=row.member_id, assignment_id=row.pk, shift_id=None)
        get_object_or_404(EventTicketType, pk=payload["ticket_type_id"], event=event,
                          makerspace_id=event.makerspace_id, is_active=True)
        request = ContributorAdmission(event_id=event.pk, member_id=row.member_id,
            assignment_id=row.pk, ticket_type_id=payload["ticket_type_id"], capacity_policy=payload["capacity_policy"])
        adapter = getattr(ports(), "admissions", None)
        registration_id = required_hook(adapter, "admit_locked")(request=request, actor_id=actor.pk,
            operation_id=str(payload["operation_id"]), locks=locks)
        registration = get_object_or_404(EventRegistration, pk=registration_id, event=event,
            member_id=row.member_id, ticket_type_id=request.ticket_type_id,
            status__in=["registered", "attended"])
        previous = EventContributorAdmission.objects.filter(assignment=row).first()
        if previous:
            if previous.registration_id != registration.pk:
                raise ProgrammeError("contributor_admitted", gettext("Use the existing contributor registration."))
            return previous
        return commands.new_row(EventContributorAdmission, event, assignment=row, registration=registration,
            capacity_policy=request.capacity_policy, actor=actor)

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="contributor.admit", feature=None, permission=None, account_ids=(initial.member_id,), mutate=mutate, status=201)
