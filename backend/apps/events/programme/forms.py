"""Form editing adapters; domain writers retain form ownership and their audit trail."""

from copy import deepcopy

from django.core.exceptions import ValidationError as SchemaError
from rest_framework.exceptions import NotFound, ValidationError

from apps.events import event_authority, services
from apps.events.event_permissions import EDIT_DETAILS
from apps.audit.services import record
from apps.forms_schema.profile_fields import PROFILE_FIELDS
from apps.forms_schema.submission import validate_submission
from apps.forms_schema.validation import validate_form_schema

from .commands import ProgrammeConflict, ProgrammeUnavailable, event_version, execute_command
from .providers import form_provider
from .form_models import EventFormRevision


FORM_PERMISSIONS = {"registration": (EDIT_DETAILS,), "application": (EDIT_DETAILS,),
                    "volunteer": ("manage_volunteers",), "mentor": ("manage_team",),
                    "round": ("manage_team", "mentor_queue"), "track": ("manage_hackathon",)}
SELECTORS = {"volunteer": "posting_id", "mentor": "posting_id", "round": "round_id", "track": "track_id"}


def _permission(key):
    if key not in FORM_PERMISSIONS:
        raise NotFound("Unknown event form.")
    return FORM_PERMISSIONS[key][0]


def require_form(actor, event, key):
    _permission(key)
    for permission in FORM_PERMISSIONS[key]:
        event_authority.require(actor, event, permission)


def selector_for(key, data):
    selector = {name: data[name] for name in ("posting_id", "round_id", "track_id") if name in data}
    required = SELECTORS.get(key)
    if set(selector) != ({required} if required else set()):
        raise ValidationError({"selector": f"Use only {required}." if required else "This form has no nested selector."})
    return selector


def resolve_form(event, *, actor, key, selector, locked=False):
    require_form(actor, event, key)
    if key == "registration":
        return None
    provider = form_provider(key)
    if provider is None:
        raise ProgrammeUnavailable("form_provider_unavailable", "This form editor is not available yet.")
    target = provider.resolve(event=event, actor=actor, selector=selector, locked=locked)
    if target is None or getattr(target, "event_id", None) != event.pk:
        raise NotFound("Unknown event form.")
    return target


def project_form(event, *, actor, key, selector=None):
    selector = selector_for(key, selector or {})
    target = resolve_form(event, actor=actor, key=key, selector=selector)
    schema = event.custom_form if key == "registration" else form_provider(key).read(event=event, actor=actor, target=target)
    return {"event_id": event.pk, "version": event_version(event), "form_key": key, "schema": schema}


def _schema(raw):
    try:
        return validate_form_schema(raw)
    except SchemaError as exc:
        raise ValidationError({"code": getattr(exc, "code", None) or "invalid_form_schema",
                               "detail": " ".join(exc.messages)}) from exc


def save_form(event, *, actor, key, data):
    require_form(actor, event, key)
    if isinstance(data["schema"], dict) and "event_context" in data["schema"]:
        raise ValidationError({"code": "invalid_form_schema", "detail": "Event context is read-only.",
                               "fields": {"event_context": ["Remove this read-only field before saving."]}})
    schema = _schema(data["schema"])
    selector = selector_for(key, data)

    def apply(locked, locked_actor):
        target = resolve_form(locked, actor=locked_actor, key=key, selector=selector, locked=True)
        before = event_version(locked)
        selected = next(iter(selector), None)
        scope = {"event": locked, "form_key": key, "selector_kind": selected.removesuffix("_id") if selected else "none",
                 "selector_id": selector[selected] if selected else None}
        last = EventFormRevision.objects.filter(**scope).order_by("-revision").first()
        previous = locked.custom_form if key == "registration" else form_provider(key).read(
            event=locked, actor=locked_actor, target=target)
        check_editor_revision(schema, previous)
        old_number = previous.get("revision", 0) if isinstance(previous, dict) else 0
        revision_number = max(old_number, last.revision if last else 0) + 1
        next_schema = deepcopy(schema)
        if isinstance(next_schema, dict):
            next_schema["revision"] = revision_number
        if key == "registration":
            locked = services.update_event(locked, actor=locked_actor, custom_form=next_schema)
        else:
            form_provider(key).save_locked(event=locked, actor=locked_actor, target=target, schema=next_schema)
            locked.refresh_from_db()
        if event_version(locked) <= before:
            raise ProgrammeUnavailable("event_version_writer_unavailable", "Event version writer integration is required.")
        revision = EventFormRevision.objects.create(**scope, revision=revision_number,
                                                    schema=next_schema, created_by=locked_actor)
        record(locked_actor, "event.form_revised", makerspace=locked.makerspace, target=locked,
               meta={"form_key": key, "revision_id": revision.pk, "revision": revision_number, **selector})
        return {"event_id": locked.pk, "version": event_version(locked), "form_key": key, "revision_id": revision.pk}

    reference = execute_command(event=event, actor=actor, command=f"form:{key}", payload=data,
                           expected_version=data["expected_version"], operation_id=data["operation_id"],
                           execute=apply, permission=_permission(key),
                           authorize=lambda locked, held: resolve_form(locked, actor=held, key=key, selector=selector, locked=True))
    revision = EventFormRevision.objects.get(pk=reference["revision_id"], event=event, form_key=key)
    return {"event_id": event.pk, "version": reference["version"], "form_key": key, "schema": revision.schema}


def check_editor_revision(schema, previous):
    if isinstance(schema, dict):
        expected = previous.get("revision", 1) if isinstance(previous, dict) else 1
        if schema["revision"] != expected:
            raise ProgrammeConflict("form_revision_changed", "The form changed. Reload its current revision.")


def validate_form_preview(event, *, actor, key, schema, sample_answers, **selection):
    selector = selector_for(key, selection)
    resolve_form(event, actor=actor, key=key, selector=selector)
    schema = _schema(schema)
    # Builder previews evaluate supplied values and conditional visibility, without
    # requiring a completed member submission or reading an account's private DOB.
    preview = deepcopy(schema)
    questions = preview.get("questions", []) if isinstance(preview, dict) else (preview or [])
    for question in questions:
        question["required"] = False
    try:
        result = validate_submission(schema=preview, payload={
            "answers": sample_answers,
            "save_choices": {key: False for key, field in PROFILE_FIELDS.items() if field.persistable},
        })
    except ValidationError as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
        return {"valid": False, "visible_question_ids": [], "errors": detail.get("fields", detail)}
    return {"valid": True, "visible_question_ids": list(result.visible_question_ids), "errors": {}}
