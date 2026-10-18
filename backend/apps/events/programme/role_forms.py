"""Contributor form integration reuses the same F/P prepared workflow as A/G."""
import json
from apps.events.answer_derivations.subjects import resolve_subject
from apps.events.hackathons.admission_models import HackathonConfig
from apps.forms_schema.validation import validate_form_schema
from . import prepared_forms as engine


def project_subject(*, subject, snapshot, audience):
    from apps.events.answer_derivations.serialization import answer_review, project_owner
    result, omitted = [], []
    for row in (snapshot or {}).get("answers", []):
        # Private role answers have no public/reviewer disclosure by default.
        if audience != "owner":
            omitted.append(row["id"])
        elif row.get("type") == "age_at_event":
            result.append(project_owner(actor_id=subject.owner_member_id, subject=subject, question_id=row["id"]))
        else:
            result.append(row)
    return {"answers": result, "omitted_question_ids": omitted,
        "answer_review": answer_review(actor_id=subject.owner_member_id, subject=subject),
        "save_intent": engine.intent_for(subject) if audience == "owner" else None}


class RoleForms:
    def validate_schema(self, *, schema):
        return validate_form_schema(schema)

    def context(self, *, actor_id, event_id, schema):
        from apps.events.models_event import Event
        from apps.events.hackathons.api_context import form_descriptor
        from apps.events.hackathons.admission_models import HackathonCocRevision
        config = HackathonConfig.objects.filter(event_id=event_id).first()
        coc = HackathonCocRevision.objects.filter(event_id=event_id, revision=config.coc_revision).first() if config else None
        return {"form": form_descriptor(Event.objects.get(pk=event_id), schema),
            "coc": {"revision": coc.revision, "body": coc.body} if coc else None}

    def prepare(self, *, actor_id, subject, schema, payload, submit, previous_answers):
        prepared = engine.prepare(actor_id=actor_id, subject=subject, schema=schema,
            payload=payload, submit=submit, previous_answers=previous_answers)
        config = HackathonConfig.objects.filter(event_id=subject.event_id).first()
        if submit and config:
            from apps.events.contributions.errors import ProgrammeError
            if prepared.consent_revision != config.coc_revision:
                raise ProgrammeError("coc_required", "Accept the current code of conduct.", status=400)
        return prepared

    def apply_locked(self, *, prepared, subject, locks):
        row = resolve_subject(subject)
        schema = row.posting.form_schema if row.posting_id else []
        engine.require_current(prepared, row.event, schema)
        snapshot, intent_id = engine.apply_locked(prepared, subject=subject, locks=locks)
        if snapshot.get("version") != 2:
            snapshot = {"version": 2, "answers": snapshot.get("answers", [])}
        return {"answers_json": json.dumps(snapshot), "consent_revision": prepared.consent_revision,
            "schema_version": snapshot.get("version", 2), "save_intent": intent_id}

    def lock_locked(self, *, subject, locks):
        from apps.events.answer_derivations.lifecycle import lock_subject_locked
        return lock_subject_locked(actor_id=subject.owner_member_id, subject=subject, locks=locks)

    def require_approval_locked(self, *, subject, locks):
        from apps.events.contributions.errors import ProgrammeError
        row = resolve_subject(subject)
        if row.date_review_required:
            raise ProgrammeError("date_review_required", "Review the current event date.")
        config = HackathonConfig.objects.filter(event_id=subject.event_id).first()
        if config and row.consent_revision != config.coc_revision:
            raise ProgrammeError("coc_required", "Accept the current code of conduct.", status=400)

    def project(self, *, subject, audience, actor_id=None):
        row = resolve_subject(subject)
        snapshot = json.loads(row.answers)
        result = project_subject(subject=subject, snapshot=snapshot, audience=audience)
        if audience == "organizer" and actor_id is not None:
            from apps.accounts.models import User
            from .answer_projection import organizer_answers
            projected = organizer_answers(event=row.event, actor=User.objects.get(pk=actor_id),
                subject=subject, schema=row.posting.form_schema if row.posting_id else [], snapshot=snapshot)
            result["answers"] = projected["answers"]
            result["omitted_question_ids"] = sorted({a["id"] for a in snapshot.get("answers", [])}
                - {a["id"] for a in projected["answers"]})
        return result

    def review_date_locked(self, *, subject, revision, as_of_date, locks):
        from apps.events.answer_derivations.lifecycle import review_date_locked
        return review_date_locked(actor_id=subject.owner_member_id, subject=subject,
            revision=revision, as_of_date=as_of_date, locks=locks)

    def validate_round(self, *, schema, answers):
        from apps.forms_schema.submission import validate_submission
        return validate_submission(schema=schema or [], payload={"answers": answers}).snapshot

    def reopen_locked(self, *, subject, previous_version, locks):
        from .form_lifecycle import archive_sources_locked
        return archive_sources_locked(subject=subject, locks=locks,
            archive_kind="role_revision", archive_id=previous_version)

    def export_owner(self, *, subject, actor_id):
        from apps.events.answer_derivations.serialization import owner_export
        return {**self.project(subject=subject, audience="owner"), "sources": owner_export(actor_id=actor_id, subject=subject)}
