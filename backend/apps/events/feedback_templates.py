"""Static starter surveys; responses freeze template replacement."""

from copy import deepcopy

from django.db import transaction

from apps.events import event_authority
from apps.events.event_permissions import EDIT_DETAILS
from apps.events.exceptions import EventInvalidTransition
from apps.events.services import _audit
from apps.events.services_feedback import _locked_event, _locked_survey, configure_survey


def _rating(question_id, label):
    return {"id": question_id, "label": label, "type": "single_choice",
            "required": True, "options": ["1", "2", "3", "4", "5"]}


def _text(question_id, label):
    return {"id": question_id, "label": label, "type": "paragraph", "required": False, "options": []}


FEEDBACK_TEMPLATES = {
    "quick_pulse": ("Quick pulse", [_rating("rating", "How was the event?"),
                                    _text("comment", "What could we improve?")]),
    "event_review": ("Event review", [_rating("overall", "Overall experience"),
                                      _rating("organization", "Organization"),
                                      _text("highlight", "What worked best?"),
                                      _text("improve", "What could we improve?")]),
    "session_speaker": ("Session & speaker review", [_rating("session", "Session quality"),
                       _rating("speaker", "Speaker clarity"),
                       _text("takeaway", "Your main takeaway"),
                       _text("comment", "Suggestions for the speaker")]),
}


@transaction.atomic
def apply_feedback_template(event, *, actor, template):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(event.makerspace_id)
    event = _locked_event(event)
    event_authority.require(actor, event, EDIT_DETAILS)
    survey = _locked_survey(event, required=False)
    if survey is not None and survey.responses.exists():
        raise EventInvalidTransition("Templates cannot replace a survey with responses.")
    title, questions = FEEDBACK_TEMPLATES[template]
    survey = configure_survey(event, actor=actor, title=title,
                              questions=deepcopy(questions),
                              certificate_enabled=bool(survey and survey.certificate_enabled))
    _audit(event, actor, "event.feedback_template_applied", survey, {"template": template})
    return survey
