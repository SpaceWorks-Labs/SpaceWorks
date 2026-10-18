"""Explicit read-only domain seams. G installs C/D/A providers at startup."""

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
    if provider.key not in {"application", "volunteer", "mentor", "round", "track"} or provider.key in _forms:
        raise ImproperlyConfigured(f"Duplicate event form provider: {provider.key}")
    _forms[provider.key] = provider


def form_provider(key):
    return _forms.get(key)


def register_answer_projector(provider):
    """G installs the authorized live disclosure/age projection, never a raw snapshot passthrough."""
    global _answers
    if _answers is not None:
        raise ImproperlyConfigured("Programme answer projector already registered.")
    _answers = provider


def answer_projector():
    return _answers
