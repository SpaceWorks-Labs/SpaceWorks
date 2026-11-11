from copy import deepcopy

import pytest

from apps.tenant_migration.semantic_events_programme import remap_programme


def mapped(label, value):
    return value + 100


def test_frozen_snapshot_remaps_only_declared_ids_and_keeps_hash_provenance():
    source = {"project": {"asset_ids": [1], "assets": [{"id": 1}], "links": [{"id": 2}],
        "track_ids": [3], "prize_ids": [4], "description": "Member 1 uses asset 2",
        "form_answers": {"free_text": "1", "arbitrary_id": 5}},
        "sealed_member_ids": [7, 6], "content_sha256": "a" * 64, "source_content_sha256": ""}
    row = deepcopy(source)
    remap_programme("events.SubmissionSnapshot", source, row, mapped)
    assert row["project"]["asset_ids"] == [101]
    assert row["sealed_member_ids"] == [106, 107]
    assert row["project"]["form_answers"] == source["project"]["form_answers"]
    assert row["project"]["description"] == source["project"]["description"]
    assert row["source_content_sha256"] == "a" * 64
    assert row["content_sha256"] != source["content_sha256"]
    assert source["project"]["asset_ids"] == [1]


def test_result_remaps_round_project_and_award_without_touching_ranks_or_scores():
    source = {"aggregates": {"rounds": [{"round_id": 1, "rows": [{"snapshot_id": 2, "rank": 1, "score": "4.2"}]}],
        "awards": [{"prize_id": 3, "snapshot_id": 2, "rank": 1}]}, "content_sha256": "b" * 64}
    row = deepcopy(source)
    remap_programme("events.EventResultRevision", source, row, mapped)
    assert row["aggregates"]["rounds"][0]["rows"][0] == {"snapshot_id": 102, "rank": 1, "score": "4.2"}
    assert row["aggregates"]["awards"][0] == {"prize_id": 103, "snapshot_id": 102, "rank": 1}


@pytest.mark.parametrize("value", [True, "1", -1, 0])
def test_malformed_typed_references_refuse_instead_of_guessing(value):
    with pytest.raises(ValueError):
        remap_programme("events.HackathonSubmission", {}, {"asset_ids": [value]}, mapped)
