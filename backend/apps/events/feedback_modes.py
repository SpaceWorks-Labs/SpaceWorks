"""Feedback form modes (G36, #71): certificate, anonymous, or identified.

* **certificate** -- unchanged: a signed-in attendee confirms their email and gets a
  certificate; the response is linked to the registration.
* **anonymous** -- the per-form switch, allowed only while certificates are off and while
  the space has `events.anonymous_feedback` on. The response row has no registration,
  no account, no IP and no timestamp finer than the row's own creation; the audit row has
  no actor and no target id. Public submission is rate-limited; reports aggregate only.
  A form marked anonymous while the switch is off accepts nothing (404) rather than
  quietly collecting identified answers under an anonymous promise.
* **identified** -- certificates and anonymity both off: a signed-in attendee answers
  and the response is linked to their registration, without a certificate.
"""

from django.db import transaction

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled

FEATURE = "events.anonymous_feedback"


def feedback_mode(survey):
    if survey.certificate_enabled:
        return "certificate"
    if survey.anonymous:
        return "anonymous" if feature_enabled(survey.event.makerspace, FEATURE) else "unavailable"
    return "identified"


def resolve_anonymous(event, survey, requested, certificate_enabled):
    """The value `configure_survey` stores; enabling needs the switch and no certificates."""
    from rest_framework.exceptions import ValidationError
    if requested is None:
        if survey is not None and survey.pk:
            return survey.anonymous and not certificate_enabled
        return not certificate_enabled and feature_enabled(event.makerspace, FEATURE)
    if requested and certificate_enabled:
        raise ValidationError({"anonymous": "Anonymous feedback needs certificates turned off."})
    if requested and not feature_enabled(event.makerspace, FEATURE):
        raise ValidationError({"anonymous": "Anonymous feedback is switched off for this makerspace."})
    return requested


def record_anonymous_change(actor, event, survey, was_anonymous):
    if survey.anonymous and not was_anonymous:
        audit.record(actor, "event.feedback_anonymous_enabled", makerspace=event.makerspace, target=survey,
                     meta={})


@transaction.atomic
def submit_member_feedback(event, *, actor, answers, registration=None):
    """Identified feedback without a certificate (both switches off)."""
    from apps.events.exceptions import FeedbackConflict, FeedbackIneligible
    from apps.events.models import EventFeedbackResponse, EventRegistration
    from apps.presence.guard import require_active_member
    from .services_feedback import _locked_event, _locked_survey, _merge_answered_ids, _snapshot, _submission_ready
    locked_event = _locked_event(event)
    survey = _locked_survey(locked_event)
    if survey.certificate_enabled or survey.anonymous or not _submission_ready(locked_event, survey):
        raise FeedbackIneligible()
    # No select_related on the nullable via-space FK under FOR UPDATE (Postgres refuses it).
    rows = EventRegistration.objects.select_for_update().filter(
        event=locked_event, member=actor, status=EventRegistration.Status.ATTENDED)
    if registration is not None:
        rows = rows.filter(pk=registration.pk)
    locked = rows.first()
    if locked is None:
        raise FeedbackIneligible()
    require_active_member(actor, locked.registered_via_makerspace or locked_event.makerspace)
    snapshot, encoded = _snapshot(survey.questions, answers)
    existing = EventFeedbackResponse.objects.select_for_update().filter(survey=survey, registration=locked).first()
    if existing is not None:
        if existing.answers_snapshot != encoded:
            raise FeedbackConflict()
        return existing, None
    response = EventFeedbackResponse.objects.create(survey=survey, registration=locked,
                                                    answers_snapshot=encoded, certificate_requested=False)
    _merge_answered_ids(survey, snapshot)
    audit.record(actor, "event.feedback_submitted", makerspace=locked_event.makerspace, target=response,
                 meta={"mode": "identified"})
    return response, None


def submit(event, survey, *, user, data, registration=None):
    """One dispatcher for the public and member routes."""
    from rest_framework.exceptions import NotAuthenticated, NotFound, ValidationError
    from .services_feedback import submit_anonymous_feedback, submit_identified_feedback
    mode = feedback_mode(survey)
    if mode == "unavailable":
        raise NotFound()
    if mode == "anonymous":
        if "email" in data:
            raise ValidationError({"email": "Email is not accepted for anonymous feedback."})
        return submit_anonymous_feedback(event, data["answers"])
    if not user.is_authenticated:
        raise NotAuthenticated()
    if mode == "identified":
        return submit_member_feedback(event, actor=user, answers=data["answers"], registration=registration)
    if "email" not in data:
        raise ValidationError({"email": "This field is required."})
    return submit_identified_feedback(event, actor=user, email=data["email"], answers=data["answers"],
                                      registration=registration)
