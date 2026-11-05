"""Rules for an organiser's stage plan (#177, #178, #180). Each refusal is a typed ``invalid_stage``."""
from .errors import SubmissionError
from .links import KINDS
from .models_stages import MAX_STAGES
from .quota import GROUP_CAPS, MIB

FAMILIES = tuple(sorted(key for key in GROUP_CAPS if key != "resume"))
VIDEO_HOSTS = ("google", "loom", "vimeo", "youtube")
FIELD_TYPES = ("short_text", "long_text", "choice", "url")
FIELD_VISIBILITY = ("staff_and_judges", "staff_only", "public")
ANSWER_LIMITS = {"short_text": 200, "long_text": 5000, "url": 2048, "choice": 80}


def _refuse(index, reason):
    raise SubmissionError("invalid_stage", 400, stage=str(index + 1), reason=reason)


def check_plan(event, stages):
    """Validate the ordered stage list as a whole. ``stages`` are serializer-validated dicts."""
    if not 1 <= len(stages) <= MAX_STAGES:
        raise SubmissionError("invalid_stage_count", 400, limit=str(MAX_STAGES))
    previous_deadline = None
    for index, stage in enumerate(stages):
        last = index == len(stages) - 1
        _check_content(index, stage)
        if stage.get("opens_at") and stage.get("deadline") and stage["deadline"] <= stage["opens_at"]:
            _refuse(index, "deadline_before_opening")
        if stage.get("deadline") and stage["deadline"] > event.ends_at:
            _refuse(index, "deadline_after_event")
        if not last and not stage.get("deadline"):
            _refuse(index, "deadline_required")
        if previous_deadline and stage.get("deadline") and stage["deadline"] <= previous_deadline:
            _refuse(index, "deadlines_out_of_order")
        previous_deadline = stage.get("deadline") or previous_deadline
        if index == 0 and stage.get("requires_previous"):
            _refuse(index, "first_stage_has_no_previous")
        if last and stage.get("shortlist_after"):
            _refuse(index, "last_stage_has_no_shortlist")
        keys = [field["key"] for field in stage.get("custom_fields", [])]
        if len(set(keys)) != len(keys):
            _refuse(index, "duplicate_field_key")
    return stages


def _check_content(index, stage):
    mode = stage.get("content_mode", "files_and_links")
    kinds, families = stage.get("required_link_kinds", []), stage.get("accepted_families", [])
    if not set(kinds) <= KINDS or not set(families) <= set(FAMILIES) or not set(stage.get("video_hosts", [])) <= set(VIDEO_HOSTS):
        _refuse(index, "unknown_choice")
    min_files, max_files = stage.get("min_files", 0), stage.get("max_files")
    if max_files is not None and max_files < min_files:
        _refuse(index, "max_files_below_min")
    if mode == "files_only" and (kinds or stage.get("max_links") is not None or stage.get("video_hosts")):
        _refuse(index, "links_rule_in_files_only")
    if mode == "links_only" and (min_files or max_files is not None or families or stage.get("max_bytes_per_file")):
        _refuse(index, "files_rule_in_links_only")
    if mode == "presentation" and (kinds or min_files):
        _refuse(index, "requirement_in_presentation")
    cap = max(GROUP_CAPS[key] for key in (families or FAMILIES)) * MIB
    if stage.get("max_bytes_per_file") and stage["max_bytes_per_file"] > cap:
        _refuse(index, "file_cap_above_hard_cap")


def field_answer(field, value):
    """Normalise one custom-field answer; ``None`` means empty. Raises on a malformed answer."""
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > ANSWER_LIMITS[field["type"]]:
        raise SubmissionError("submission_field_invalid", 400, fields=[field["key"]])
    if field["type"] == "choice" and value not in field.get("choices", []):
        raise SubmissionError("submission_field_invalid", 400, fields=[field["key"]])
    if field["type"] == "url":
        from .links import normalize_link
        try:
            value, _ = normalize_link(value, "other")
        except SubmissionError as exc:
            raise SubmissionError("submission_field_invalid", 400, fields=[field["key"]]) from exc
    return value.strip() if field["type"] != "url" else value
