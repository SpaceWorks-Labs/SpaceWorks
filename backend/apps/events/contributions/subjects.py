"""Role-only applications use P's third derivation subject, without registration."""
from django.shortcuts import get_object_or_404
from apps.events.contracts.subjects import AnswerSubject, SubjectKind
from .commands import active_member
from .models_roles import EventRoleAssignment


def subject_for(row):
    return AnswerSubject(event_id=row.event_id, owner_member_id=row.member_id,
                         kind=SubjectKind.ROLE_ASSIGNMENT, subject_id=row.pk)


def require_owner(actor_id, subject):
    from apps.accounts.models import User
    from rest_framework.exceptions import NotFound
    actor = get_object_or_404(User, pk=actor_id)
    active_member(actor)
    if subject.kind != SubjectKind.ROLE_ASSIGNMENT or subject.owner_member_id != actor_id:
        raise NotFound()
    if subject.subject_id is not None:
        get_object_or_404(EventRoleAssignment, pk=subject.subject_id,
                          event_id=subject.event_id, member_id=actor_id)
    return subject


def require_resume_eligible(*, actor_id, event_id):
    """Eligibility only. D alone grants/revokes/evaluates sponsor consent."""
    from apps.accounts.models import User
    from rest_framework.exceptions import NotFound
    active_member(get_object_or_404(User, pk=actor_id))
    if not EventRoleAssignment.objects.filter(event_id=event_id, member_id=actor_id,
        role__in=["volunteer", "mentor"],
        state__in=["draft", "proposed", "applied", "approved", "completed"], imported_inert=False).exists():
        raise NotFound()
    return True
