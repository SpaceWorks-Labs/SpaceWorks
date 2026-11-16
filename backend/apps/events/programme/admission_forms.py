"""Application FormPort: canonical F snapshots, P source lifecycle, owner views."""
from dataclasses import replace
import json
from types import SimpleNamespace

from apps.events.contracts.subjects import SubjectKind
from apps.events.answer_derivations.subjects import binding_for
from apps.events.hackathons.admission_ports import PreparedAnswers, OwnerAnswers
from apps.events.registration_form_adapter import validate_registration_form
from apps.forms_schema.validation import validate_form_schema
from . import prepared_forms as engine


class AdmissionForms:
    def validate_schema(self, schema):
        return validate_form_schema(schema)

    def prepare(self, *, event, config, actor, subject, payload, draft):
        from apps.events.hackathons.admission_models import HackathonApplication
        previous = HackathonApplication.objects.filter(pk=subject.subject_id, event=event,
            member=actor).values_list("answers_snapshot", flat=True).first() if subject.subject_id else None
        prepared = engine.prepare(actor_id=actor.pk, subject=subject, schema=config.application_form,
            payload=payload, submit=not draft, previous_answers=previous)
        trusted = validate_registration_form(payload, schema=config.application_form,
            subject=subject, application=True,
            validator=lambda **kwargs: SimpleNamespace(snapshot=prepared.snapshot))
        return PreparedAnswers(snapshot=prepared.snapshot, form_sha256=prepared.form_sha256,
            normalized_input={**payload, "answers": prepared.snapshot}, subject=subject,
            trusted_registration_form=trusted, saved_intent=prepared.saved_intent, derivations=prepared)

    def require_current_locked(self, *, event, config, prepared, locks):
        engine.require_current(prepared.derivations, event, config.application_form)

    def attach_locked(self, *, application, prepared, locks, store_intent):
        subject = binding_for(application, SubjectKind.APPLICATION)
        snapshot, _ = engine.apply_locked(prepared.derivations, subject=subject, locks=locks, store_intent=store_intent)
        return replace(prepared, snapshot=snapshot)

    def project_owner(self, *, application, snapshot):
        subject = binding_for(application, SubjectKind.APPLICATION)
        from .role_forms import project_subject
        projected = project_subject(subject=subject, snapshot=snapshot, audience="owner")
        return OwnerAnswers(projected["answers"], projected["answer_review"], tuple(projected["omitted_question_ids"]))

    def lock_answers_locked(self, *, application, at, locks, closing=False):
        from apps.events.answer_derivations.lifecycle import lock_subject_locked
        lock_subject_locked(actor_id=application.member_id,
            subject=binding_for(application, SubjectKind.APPLICATION), locks=locks, closing=closing)

    def archive_answers_locked(self, *, application, revision_id, locks):
        from .form_lifecycle import archive_sources_locked
        archive_sources_locked(subject=binding_for(application, SubjectKind.APPLICATION), locks=locks,
            archive_kind="application_revision", archive_id=revision_id)

    def project_intent(self, *, application):
        return engine.intent_for(binding_for(application, SubjectKind.APPLICATION))

    def date_review_locked(self, *, application, revision, as_of_date, locks):
        from apps.events.answer_derivations.lifecycle import review_date_locked
        return review_date_locked(actor_id=application.member_id,
            subject=binding_for(application, SubjectKind.APPLICATION), revision=revision,
            as_of_date=as_of_date, locks=locks)
