"""Disclosure-aware organizer answers with typed source-owned age projections."""
from apps.accounts import rbac
from apps.events import event_authority
from apps.events.contracts.subjects import SubjectKind
from apps.events.answer_derivations.subjects import binding_for
from apps.events.answer_derivations.serialization import project_organizer
from apps.forms_schema.validation import validate_form_schema


def organizer_answers(*, event, actor, subject, schema, snapshot):
    event_authority.require(actor, event, "manage_registrations")
    if not rbac.can(actor, rbac.Action.VIEW_AUDIT, event.makerspace_id):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied()
    schema = validate_form_schema(schema)
    questions = {q["id"]: q for q in schema.get("questions", [])} if isinstance(schema, dict) else {}
    answers = []
    for row in snapshot.get("answers", []):
        question = questions.get(row["id"])
        if question is None or question.get("disclosure", {}).get("organizer") is not True:
            continue
        if row.get("type") == "age_at_event":
            answers.append(project_organizer(actor_id=actor.pk, subject=subject,
                question_id=row["id"], disclosure_policy=lambda **kwargs: True))
        else:
            answers.append(row)
    return {**snapshot, "answers": answers}


def registration_answers(*, event, actor, registration, snapshot):
    from apps.events.hackathons.admission_models import HackathonApplication
    app = HackathonApplication.objects.filter(registration=registration).first()
    subject = binding_for(app, SubjectKind.APPLICATION) if app else binding_for(registration, SubjectKind.REGISTRATION)
    schema = app.event.hackathon_config.application_form if app else event.custom_form
    return organizer_answers(event=event, actor=actor, subject=subject, schema=schema, snapshot=snapshot)
