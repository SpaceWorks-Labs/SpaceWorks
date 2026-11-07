"""Explicit domain seams. G installs providers; R owns stage transactions."""

from django.utils.translation import gettext
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class ReadinessProvider:
    key: str
    permission: str | None
    label: str
    tab: str
    feature: str
    summarize: Callable


@dataclass(frozen=True)
class Respondent:
    # Member identity where available; registration ID otherwise. No contact matching.
    key: tuple[str, int]
    submitted_at: datetime


_readiness = {}
_respondents = None
_forms = {}
_answers = None


def register_readiness(provider):
    if provider.key in _readiness:
        raise ImproperlyConfigured(f"Duplicate readiness provider: {provider.key}")
    _readiness[provider.key] = provider


def readiness_providers():
    return tuple(_readiness.values())


def register_respondents(provider):
    global _respondents
    if _respondents is not None:
        raise ImproperlyConfigured("Application funnel provider already registered.")
    _respondents = provider


def application_respondents(*, event, actor, since, until):
    """A supplies (is_hackathon, Respondent iterable), omitting virtual/practice rows."""
    if _respondents is None:
        return None
    return _respondents(event=event, actor=actor, since=since, until=until)


@dataclass(frozen=True)
class FormProvider:
    key: str
    resolve: Callable
    read: Callable
    save_locked: Callable


def register_form(provider):
    if provider.key not in {"application", "volunteer", "mentor", "round", "track", "stage"} or provider.key in _forms:
        raise ImproperlyConfigured(f"Duplicate event form provider: {provider.key}")
    _forms[provider.key] = provider


def form_provider(key):
    return _forms.get(key)


def append_stage_revision_locked(*, event, actor, target, schema):
    """R calls inside its event/definition-locked transaction after version CAS.

    Returns the new immutable revision. R sets current_revision and increments
    definition/event versions in that same transaction; failures roll back this
    append and audit together. No old schema or response is ever updated here.
    """
    from copy import deepcopy
    from django.core.exceptions import ValidationError as SchemaError
    from django.db import connections, router
    from rest_framework.exceptions import NotFound, ValidationError
    from apps.audit.services import record
    from apps.events import event_authority
    from apps.forms_schema.schema_v2 import validate_schema
    from apps.forms_schema.submission import FormContextConflict
    from .form_models import EventFormRevision

    database = router.db_for_write(EventFormRevision, instance=event)
    if not connections[database].in_atomic_block:
        raise RuntimeError("Stage revisions require the locked domain transaction.")
    if (getattr(target, "event_id", None) != event.pk or type(getattr(target, "pk", None)) is not int
            or target.pk < 1):
        raise NotFound(gettext("Unknown event form."))
    event_authority.require(actor, event, "edit_details")
    if isinstance(schema, dict) and "event_context" in schema:
        raise ValidationError({"code": "invalid_form_schema", "detail": gettext("Event context is read-only.")})
    try:
        canonical = validate_schema(schema, context="stage")
    except SchemaError as exc:
        raise ValidationError({"code": getattr(exc, "code", None) or "invalid_form_schema",
                               "detail": " ".join(exc.messages)}) from exc
    if canonical["form_id"] != target.form_id:
        raise ValidationError({"code": "invalid_form_context", "detail": gettext("Use the stage's stable form ID.")})
    scope = {"event_id": event.pk, "form_key": "stage", "selector_kind": "stage", "selector_id": target.pk}
    history = EventFormRevision.objects.using(database)
    last = history.filter(**scope).order_by("-revision").first()
    if (getattr(target, "current_revision_id", None) != (last.pk if last else None)
            or canonical["revision"] != (last.revision if last else 1)):
        raise FormContextConflict("form_revision_changed", "Reload the current stage form revision.")
    canonical = deepcopy(canonical)
    canonical["revision"] = last.revision + 1 if last else 1
    revision = history.create(**scope, revision=canonical["revision"], schema=canonical, created_by=actor)
    record(actor, "event.form_revised", makerspace=event.makerspace, target=event,
           meta={"form_key": "stage", "stage_form_id": target.pk,
                 "revision_id": revision.pk, "revision": revision.revision})
    return revision


def register_answer_projector(provider):
    """G installs the authorized live disclosure/age projection, never a raw snapshot passthrough."""
    global _answers
    if _answers is not None:
        raise ImproperlyConfigured("Programme answer projector already registered.")
    _answers = provider


def answer_projector():
    return _answers
