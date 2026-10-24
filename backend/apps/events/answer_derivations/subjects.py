"""The same owner resolution for registrations, applications and role-only people."""

from django.apps import apps
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.events.contracts.subjects import AnswerSubject, SubjectKind
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable

SUBJECT_MODELS = {
    SubjectKind.REGISTRATION: "EventRegistration",
    SubjectKind.APPLICATION: "HackathonApplication",
    SubjectKind.ROLE_ASSIGNMENT: "EventRoleAssignment",
}


def require_member(actor_id):
    actor = User.objects.filter(
        pk=actor_id, account_kind="member", is_active=True, access_status="active",
        is_tenant_dump_stub=False, retired_at__isnull=True,
    ).first()
    if actor is None:
        raise NotFound()
    return actor


def require_event(event):
    if not is_servable(event.makerspace) or not module_enabled(event.makerspace, "events"):
        raise NotFound()
    return event


def subject_model(kind):
    if not isinstance(kind, SubjectKind):
        raise NotFound()
    return apps.get_model("events", SUBJECT_MODELS[kind])


def resolve_subject(subject, *, lock=False):
    """No attendee lookup for a role; FK event/member are its identity."""
    if not isinstance(subject, AnswerSubject) or subject.subject_id is None:
        raise NotFound()
    rows = subject_model(subject.kind).objects
    if lock:
        rows = rows.select_for_update()
    row = rows.filter(
        pk=subject.subject_id, event_id=subject.event_id,
        member_id=subject.owner_member_id,
    ).first()
    if row is None:
        raise NotFound()
    event = row.event
    require_event(event)
    return row


def require_owner(actor_id, subject):
    require_member(actor_id)
    if actor_id != subject.owner_member_id:
        raise NotFound()
    resolve_subject(subject)
    return subject


def binding_for(row, kind):
    return AnswerSubject(
        event_id=row.event_id, owner_member_id=row.member_id,
        kind=kind, subject_id=row.pk,
    )


def subject_filter(subject):
    return {"event_id": subject.event_id, f"{subject.kind.value}_id": subject.subject_id}


def subject_for_derivation(row):
    for kind in SubjectKind:
        pk = getattr(row, f"{kind.value}_id")
        if pk is not None:
            source = subject_model(kind).objects.filter(pk=pk, event_id=row.event_id).first()
            if source is None or source.member_id is None:
                raise NotFound()
            return binding_for(source, kind)
    raise NotFound()
