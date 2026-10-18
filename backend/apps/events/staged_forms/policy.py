"""Stage-specific restrictions layered on F's canonical forms validator.

This module deliberately does not implement a second schema/answer validator.
F validates the complete schema first; these checks also run before publication,
prefill and submit so a hidden/optional field cannot bypass context restrictions.
"""

from dataclasses import dataclass
import re


class StagePolicyError(ValueError):
    def __init__(self, code, *, question_ids=()):
        self.code = code
        self.question_ids = tuple(question_ids)
        super().__init__(code)


STAGES = frozenset({"application", "shortlisted", "accepted_rsvp", "pre_event", "post_event"})
BLOCKED_ACTIONS = frozenset({"rsvp", "check_in", "claim_submit"})
AGE_KEYS = frozenset({"date_of_birth", "age_at_event"})


def require_stage_schema(schema, *, derivations=None):
    if derivations is not None and (not isinstance(derivations, dict) or derivations):
        raise StagePolicyError("stage_age_question_unsupported")
    if not isinstance(schema, dict) or not isinstance(schema.get("questions"), list):
        raise StagePolicyError("invalid_form_schema")
    questions = schema["questions"]
    if any(not isinstance(question, dict) or not isinstance(question.get("type"), str)
           or (question.get("profile_field_key") is not None
               and not isinstance(question["profile_field_key"], str)) for question in questions):
        raise StagePolicyError("invalid_form_schema")
    age = tuple(question.get("id") for question in questions if (
        question.get("type") in AGE_KEYS or question.get("profile_field_key") in AGE_KEYS
        or question.get("derivation") or question.get("derivations")))
    if age:
        raise StagePolicyError("stage_age_question_unsupported", question_ids=age)
    files = tuple(question.get("id") for question in questions if question.get("type") == "file"
                  and (not isinstance(question.get("file"), dict)
                       or question["file"].get("purpose") != "stage_form_file"))
    if files:
        raise StagePolicyError("stage_file_purpose_unsupported", question_ids=files)
    return schema


def validate_audience(value):
    if not isinstance(value, dict) or set(value) != {"roles", "track_ids", "travel_requested"}:
        raise StagePolicyError("invalid_stage_audience")
    roles, tracks, travel = value["roles"], value["track_ids"], value["travel_requested"]
    if (not isinstance(roles, list) or len(roles) > 20
            or any(not isinstance(role, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", role) is None for role in roles)
            or len(set(roles)) != len(roles)):
        raise StagePolicyError("invalid_stage_audience")
    if (not isinstance(tracks, list) or len(tracks) > 100
            or any(type(track) is not int or track < 1 for track in tracks)
            or len(set(tracks)) != len(tracks) or (travel is not None and type(travel) is not bool)):
        raise StagePolicyError("invalid_stage_audience")
    # Resolve each role/track against live authoritative providers before publishing
    # or evaluating an audience. A syntactically valid ID is not membership proof.
    return value


def validate_blocking(*, stage, activation_point, required, missed_action, blocked_actions, hackathon):
    if (not isinstance(stage, str) or not isinstance(missed_action, str) or stage not in STAGES
            or missed_action not in {"none", "warn", "block"} or type(required) is not bool or type(hackathon) is not bool):
        raise StagePolicyError("invalid_stage_policy")
    if not isinstance(activation_point, (str, type(None))):
        raise StagePolicyError("invalid_stage_activation")
    if ((stage == "accepted_rsvp" and activation_point not in {"accepted", "rsvp"})
            or (stage != "accepted_rsvp" and activation_point not in {None, ""})):
        raise StagePolicyError("invalid_stage_activation")
    if (not isinstance(blocked_actions, list) or any(not isinstance(action, str) or action not in BLOCKED_ACTIONS for action in blocked_actions)
            or len(set(blocked_actions)) != len(blocked_actions)):
        raise StagePolicyError("invalid_blocked_actions")
    if blocked_actions and (not required or missed_action != "block"):
        raise StagePolicyError("invalid_blocked_actions")
    if not hackathon and "rsvp" in blocked_actions:
        raise StagePolicyError("stage_rsvp_unsupported")
    # These dependencies can never be fulfilled before the action they block.
    if "rsvp" in blocked_actions and (stage in {"pre_event", "post_event"}
                                      or (stage == "accepted_rsvp" and activation_point == "rsvp")):
        raise StagePolicyError("stage_dependency_cycle")
    if "check_in" in blocked_actions and stage == "post_event":
        raise StagePolicyError("stage_dependency_cycle")


@dataclass(frozen=True, kw_only=True)
class Completion:
    state: str
    pinned_form_revision_id: int
    submitted_form_revision_id: int | None
    submitted_response_id: int | None
    completed_response_id: int | None

    def satisfies(self):
        if self.state == "cancelled":
            return True
        return bool(self.state == "completed" and self.submitted_response_id is not None
                    and self.completed_response_id == self.submitted_response_id
                    and self.submitted_form_revision_id == self.pinned_form_revision_id)


def missing_requirements(applicable_definition_ids, assignments):
    """Missing assignment is incomplete; this read-only calculation never writes."""
    return tuple(sorted(key for key in applicable_definition_ids
                        if key not in assignments or not assignments[key].satisfies()))
