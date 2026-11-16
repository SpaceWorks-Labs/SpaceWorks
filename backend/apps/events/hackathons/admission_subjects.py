"""P's application derivation resolver: ID/value-only, no membership prerequisite."""
from django.utils.translation import gettext
from dataclasses import dataclass
from django.shortcuts import get_object_or_404
from apps.accounts.models import User
from apps.events.contracts.subjects import AnswerSubject, SubjectKind
from .admission_errors import fail
from .admission_models import HackathonApplication
from .admission_transactions import member_event
from .api_context import form_descriptor


@dataclass(frozen=True)
class ApplicationAnswerContext:
    subject: AnswerSubject
    makerspace_id: int
    form: object
    event_date_revision: int
    answer_locked_at: object
    version: int


def require_owner(actor_id, subject):
    if not isinstance(subject, AnswerSubject) or subject.kind != SubjectKind.APPLICATION or subject.owner_member_id != actor_id:
        fail("not_found", gettext("Not found."), status=404)
    actor = get_object_or_404(User, pk=actor_id)
    from apps.events.models import Event
    event = get_object_or_404(Event, pk=subject.event_id)
    event, config = member_event(actor, event.pk, event.makerspace_id)
    if subject.subject_id is not None:
        get_object_or_404(HackathonApplication, event=event, member=actor, pk=subject.subject_id)
    return subject


def resolve_for_prefill(*, actor_id, event_id, makerspace_id):
    actor = get_object_or_404(User, pk=actor_id)
    event, config = member_event(actor, event_id, makerspace_id)
    application = HackathonApplication.objects.filter(event=event, member=actor).first()
    # First-use context intentionally has no manufactured subject PK.
    return {"event_id": event.pk, "owner_member_id": actor.pk, "subject_kind": "application",
            "subject_id": application.pk if application else None, "makerspace_id": makerspace_id,
            "form": form_descriptor(event, config.application_form),
            "event_date_revision": event.event_date_revision,
            "answer_locked_at": application.answer_locked_at if application else None}
