"""Pure stage rules (#177, #178, #180): content enforcement, plan validation, presets. No database."""
from datetime import datetime, timedelta, timezone as tz
from types import SimpleNamespace

import pytest

from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.models_stages import MAX_STAGES, SubmissionStage
from apps.events.submissions.stage_presets import PRESETS, PRESET_KEYS, default_stage
from apps.events.submissions.stage_rules import check_plan, field_answer
from apps.events.submissions.stage_submit import check_content, frozen_stage

NOW = datetime(2026, 11, 5, 9, 30, tzinfo=tz.utc)
EVENT = SimpleNamespace(ends_at=NOW + timedelta(days=10), timezone_name="Asia/Kolkata")


def stage(**values):
    row = SubmissionStage(pk=7, position=1, name="Build", **values)
    row.id = 7
    return row


def asset(kind="images", size=1000):
    return SimpleNamespace(kind=kind, actual_bytes=size)


def link(kind="repo", provider="github"):
    return SimpleNamespace(kind=kind, provider=provider)


def project(answers=None):
    return SimpleNamespace(form_answers={"stage:7": answers} if answers is not None else {})


def code(call):
    with pytest.raises(SubmissionError) as caught:
        call()
    return caught.value.detail["code"], caught.value.detail


def test_default_files_and_links_accepts_either_and_refuses_nothing():
    assert check_content(stage(), project(), [asset()], []) == {}
    assert check_content(stage(), project(), [], [link()]) == {}
    assert code(lambda: check_content(stage(), project(), [], []))[0] == "submission_content_required"


def test_files_only_refuses_links_and_links_only_refuses_files():
    assert code(lambda: check_content(stage(content_mode="files_only"), project(), [asset()], [link()]))[0] \
        == "submission_links_disabled"
    assert code(lambda: check_content(stage(content_mode="links_only"), project(), [asset()], [link()]))[0] \
        == "submission_files_disabled"


def test_presentation_needs_nothing_but_takes_an_optional_deck():
    assert check_content(stage(content_mode="presentation"), project(), [], []) == {}
    assert check_content(stage(content_mode="presentation"), project(), [asset("deck")], []) == {}


def test_required_link_kinds_name_what_is_missing():
    name, body = code(lambda: check_content(stage(required_link_kinds=["repo", "video"]), project(), [], [link("repo")]))
    assert name == "submission_link_required" and list(body["kinds"]) == ["video"]
    assert check_content(stage(required_link_kinds=["repo"]), project(), [], [link("repo")]) == {}


def test_min_and_max_files_and_max_links():
    name, body = code(lambda: check_content(stage(min_files=2), project(), [asset()], [link()]))
    assert name == "submission_files_required" and body["limit"] == "2"
    assert code(lambda: check_content(stage(max_files=1), project(), [asset(), asset()], []))[0] == "submission_too_many_files"
    assert code(lambda: check_content(stage(max_links=1), project(), [], [link(), link("demo")]))[0] \
        == "submission_too_many_links"
    assert check_content(stage(min_files=1, max_files=2, max_links=2), project(), [asset()], [link()]) == {}


def test_accepted_families_size_cap_and_video_hosts():
    assert code(lambda: check_content(stage(accepted_families=["deck"]), project(), [asset("video")], []))[0] \
        == "submission_file_type_not_accepted"
    assert code(lambda: check_content(stage(max_bytes_per_file=10), project(), [asset(size=11)], []))[0] \
        == "submission_file_too_large"
    assert code(lambda: check_content(stage(video_hosts=["youtube"]), project(), [], [link("video", "vimeo")]))[0] \
        == "submission_video_host_not_allowed"
    assert check_content(stage(video_hosts=["youtube"]), project(), [], [link("video", "youtube")]) == {}


def test_custom_fields_required_choice_and_url():
    fields = [{"key": "problem", "label": "Problem", "type": "long_text", "required": True},
              {"key": "track", "label": "Track", "type": "choice", "required": False, "choices": ["a", "b"]},
              {"key": "site", "label": "Site", "type": "url", "required": False}]
    name, body = code(lambda: check_content(stage(custom_fields=fields), project({}), [asset()], []))
    assert name == "submission_field_required" and list(body["fields"]) == ["problem"]
    assert code(lambda: check_content(stage(custom_fields=fields), project({"problem": "x", "track": "c"}), [asset()], []))[0] \
        == "submission_field_invalid"
    assert code(lambda: field_answer(fields[2], "http://plain.example"))[0] == "submission_field_invalid"
    answers = check_content(stage(custom_fields=fields), project({"problem": " Heat ", "site": "https://a.example/x"}),
                            [asset()], [])
    assert answers == {"problem": "Heat", "site": "https://a.example/x"}


def test_frozen_stage_copies_rules_fields_and_answers():
    row = stage(required_link_kinds=["repo"], custom_fields=[{"key": "k", "label": "K", "type": "short_text"}])
    frozen = frozen_stage(row, {"k": "v"})
    assert frozen["rules"]["required_link_kinds"] == ["repo"] and frozen["answers"] == {"k": "v"}
    row.required_link_kinds = []  # A later edit cannot reach the frozen copy.
    assert frozen["rules"]["required_link_kinds"] == ["repo"]


def plan(*rows):
    return [{"name": f"S{index}", "content_mode": "files_and_links", **row} for index, row in enumerate(rows)]


def test_plan_rules_refuse_meaningless_combinations():
    later = NOW + timedelta(days=2)
    cases = {
        "links_rule_in_files_only": plan({"content_mode": "files_only", "required_link_kinds": ["repo"]}),
        "files_rule_in_links_only": plan({"content_mode": "links_only", "min_files": 1}),
        "requirement_in_presentation": plan({"content_mode": "presentation", "required_link_kinds": ["repo"]}),
        "max_files_below_min": plan({"min_files": 3, "max_files": 2}),
        "deadline_required": plan({}, {"deadline": later}),
        "deadlines_out_of_order": plan({"deadline": later}, {"deadline": later - timedelta(hours=1)}),
        "first_stage_has_no_previous": plan({"requires_previous": True}),
        "last_stage_has_no_shortlist": plan({"shortlist_after": True}),
        "deadline_after_event": plan({"deadline": EVENT.ends_at + timedelta(minutes=1)}),
        "file_cap_above_hard_cap": plan({"accepted_families": ["deck"], "max_bytes_per_file": 51 * 1024 ** 2}),
        "duplicate_field_key": plan({"custom_fields": [{"key": "a"}, {"key": "a"}]}),
    }
    for reason, stages in cases.items():
        name, body = code(lambda: check_plan(EVENT, stages))
        assert (name, body["reason"]) == ("invalid_stage", reason), reason
    assert code(lambda: check_plan(EVENT, []))[0] == "invalid_stage_count"
    assert code(lambda: check_plan(EVENT, plan(*[{"deadline": NOW + timedelta(hours=i)} for i in range(MAX_STAGES + 1)])))[0] \
        == "invalid_stage_count"


def test_presets_cover_the_owner_list_and_are_valid_plans():
    assert {"single", "idea_final", "idea_prototype_final", "hardware_build", "design_sprint", "full_pipeline",
            "ideathon", "case_competition"} == PRESET_KEYS
    for preset in PRESETS:
        stages = [{**row, "deadline": NOW + timedelta(days=index + 1)} for index, row in enumerate(preset["stages"])]
        assert check_plan(EVENT, stages) == stages, preset["key"]
        assert all(row["public_after_publish"] is False for row in stages)
        assert not any(key in preset for key in ("entry_fee", "team_fee"))  # A preset never creates money settings.
    full = next(p for p in PRESETS if p["key"] == "full_pipeline")
    assert full["requires_admission"] and [s["shortlist_after"] for s in full["stages"]] == [True, True, False]


def test_single_submission_default_copies_the_window():
    config = SimpleNamespace(submission_opens_at=NOW, submission_deadline=NOW + timedelta(days=1),
                             submission_grace_minutes=15, late_policy="accept_flagged")
    row = default_stage(config)
    assert (row["content_mode"], row["deadline"], row["grace_minutes"], row["late_policy"]) == (
        "files_and_links", config.submission_deadline, 15, "accept_flagged")


@pytest.mark.parametrize("configured", [False, True])
def test_first_stage_initialization_is_complete_and_private(configured, monkeypatch):
    from apps.events.models import Event
    from apps.events.submissions import stage_runtime

    event = Event(pk=17)
    context = SimpleNamespace(deadline=NOW + timedelta(days=1), grace_seconds=900, late_policy="accept_flagged")
    config = SimpleNamespace(submission_opens_at=NOW, submission_deadline=context.deadline,
                             submission_grace_minutes=15, late_policy=context.late_policy) if configured else None
    monkeypatch.setattr(stage_runtime, "stages_for", lambda event_id: [])
    # Exercise the actual initializer/ORM field constructor without a database.
    monkeypatch.setattr(SubmissionStage.objects, "create", lambda **values: SubmissionStage(**values))
    [created] = stage_runtime.ensure_stages(event, config, context=context)
    assert created.event_id == event.pk and created.position == 1
    assert created.public_after_publish is False
    assert (created.deadline, created.grace_minutes, created.late_policy) == (
        context.deadline, 15, context.late_policy)


def test_initialization_preserves_an_existing_explicit_public_stage(monkeypatch):
    from apps.events.models import Event
    from apps.events.submissions import stage_runtime

    event = Event(pk=17)
    existing = SubmissionStage(event=event, position=1, name="Published stage", public_after_publish=True)
    monkeypatch.setattr(stage_runtime, "stages_for", lambda event_id: [existing])
    monkeypatch.setattr(SubmissionStage.objects, "create", lambda **values: pytest.fail("Existing stage must be retained"))
    assert stage_runtime.ensure_stages(event, None) == [existing]
    assert existing.public_after_publish is True
