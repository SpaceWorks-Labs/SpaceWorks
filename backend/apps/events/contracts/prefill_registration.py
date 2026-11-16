"""Server-selected A/C/ordinary form context for account-only Saved details."""

from zoneinfo import ZoneInfo

from django.http import Http404

from apps.accounts.saved_details.prefill import PrefillContext, install_context_provider
from apps.events.answer_derivations.subjects import require_member, require_event
from apps.events.models_event import Event
from apps.events.models_registration import EventRegistration
from apps.events.hackathons.admission_models import HackathonApplication, HackathonConfig
from apps.events.registration_access import require_registration_access
from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.contributions.audience_adapter import require_role_audience


class EventPrefillContexts:
    def resolve(self, *, actor_id, selector):
        if selector.get("subject_kind") == "stage_response":
            from apps.events.staged_forms.prefill_provider import resolve_context
            return resolve_context(actor_id=actor_id, selector=selector)
        actor = require_member(actor_id)
        event = Event.objects.select_related("makerspace").filter(pk=selector["event_id"],
            makerspace_id=selector["makerspace_id"]).first()
        if event is None:
            raise Http404
        require_event(event)
        kind, source = selector["subject_kind"], None
        if kind == "role_assignment":
            posting = require_role_audience(actor_id=actor_id, event_id=event.pk, posting_id=selector.get("posting_id"))
            schema = posting.form_schema
            source = EventRoleAssignment.objects.filter(event=event, member=actor, posting=posting,
                state__in=("draft", "proposed", "applied", "approved")).first()
        elif kind in ("registration", "application"):
            if "posting_id" in selector:
                raise Http404
            require_registration_access(event, actor)
            if kind == "application":
                from apps.events.hackathons.admission_transactions import require_programme
                config = require_programme(event)
                source = HackathonApplication.objects.filter(event=event, member=actor).first()
                schema = config.application_form
            else:
                if HackathonConfig.objects.filter(event=event, enabled=True).exists():
                    raise Http404
                source = EventRegistration.objects.filter(event=event, member=actor,
                    status__in=("registered", "attended", "pending_approval", "waitlisted")).first()
                schema = event.custom_form
            # A first-use context must not turn a private/draft/ended event into a
            # vault-reading oracle. Existing owner histories keep their own reads.
            if source is None:
                from apps.events.website_visibility import public_events
                if not public_events(event.makerspace).filter(pk=event.pk).exists():
                    raise Http404
        else:
            raise Http404
        if not isinstance(schema, dict) or schema.get("schema_version") != 2:
            raise Http404
        from apps.forms_schema import validate_form_schema
        from apps.forms_schema.conditions import visible
        schema = validate_form_schema(schema)
        # Prefill has no client answers. Conditional questions are omitted until
        # their controller is explicitly answered by the member's form journey.
        questions = tuple(q for q in schema["questions"] if visible(q.get("show_if"), {}))
        as_of = event.starts_at.astimezone(ZoneInfo(event.timezone_name)).date()
        revision, locked = event.event_date_revision, bool(source and source.answer_locked_at)
        if locked:
            from apps.events.answer_derivations.dates import review_target
            from apps.events.answer_derivations.models import EventAnswerDerivation
            from apps.events.contracts.subjects import AnswerSubject, SubjectKind
            from apps.events.answer_derivations.subjects import subject_filter
            subject = AnswerSubject(event_id=event.pk, owner_member_id=actor_id,
                kind=SubjectKind(kind), subject_id=source.pk)
            revision, as_of = review_target(event, list(EventAnswerDerivation.objects.filter(**subject_filter(subject))))
        return PrefillContext(owner_id=actor_id, event_id=event.pk, subject_kind=kind,
            form_id=schema["form_id"], form_revision=schema["revision"], event_date_revision=revision,
            as_of_date=as_of, questions=questions, locked=locked)


def install():
    install_context_provider(EventPrefillContexts())
