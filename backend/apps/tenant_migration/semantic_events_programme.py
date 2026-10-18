"""Frozen typed ID slots; free text, URLs and arbitrary answer values stay untouched."""
from copy import deepcopy
import hashlib
import json

SLOTS = {
    "events.HackathonSubmission": {
        "asset_ids.*": "SubmissionAsset", "public_asset_ids.*": "SubmissionAsset",
        "track_ids.*": "HackathonTrack", "prize_ids.*": "HackathonPrize",
    },
    "events.SubmissionSnapshot": {
        "sealed_member_ids.*": "accounts.User",
        "project.asset_ids.*": "SubmissionAsset", "project.public_asset_ids.*": "SubmissionAsset",
        "project.track_ids.*": "HackathonTrack", "project.prize_ids.*": "HackathonPrize",
        "project.assets.*.id": "SubmissionAsset", "project.links.*.id": "SubmissionLink",
    },
    "events.EventResultRevision": {
        "aggregates.rounds.*.round_id": "JudgingRound",
        "aggregates.rounds.*.rows.*.snapshot_id": "SubmissionSnapshot",
        "aggregates.awards.*.prize_id": "HackathonPrize",
        "aggregates.awards.*.snapshot_id": "SubmissionSnapshot",
    },
    "events.EventResultRound": {"calculation.rows.*.snapshot_id": "SubmissionSnapshot"},
    "events.GalleryConsentRevision": {
        "selection.asset_ids.*": "SubmissionAsset", "selection.link_ids.*": "SubmissionLink",
    },
    "events.MentorAssignmentRun": {
        "decisions.*.id": "MentorTeamAssignment",
        "decisions.*.mentor_assignment_id": "EventRoleAssignment",
        "decisions.*.team_id": "HackathonTeam", "unsatisfied_team_ids.*": "HackathonTeam",
    },
    "events.CertificateIssueBatchItem": {
        "award_id": "HackathonPrize", "result_revision_id": "EventResultRevision",
    },
}


def _walk(value, path, label, map_id):
    if not path:
        if value is None:
            return None
        if type(value) is not int or value <= 0:
            raise ValueError("Invalid typed programme reference.")
        return map_id(label if "." in label else "events." + label, value)
    key, *rest = path
    if key == "*":
        if not isinstance(value, list):
            raise ValueError("Expected a typed programme reference vector.")
        return [_walk(item, rest, label, map_id) for item in value]
    if not isinstance(value, dict):
        raise ValueError("Expected a typed programme reference object.")
    if key in value:
        value[key] = _walk(value[key], rest, label, map_id)
    return value


def _hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def remap_programme(label, source, row, map_id):
    if label == "events.EventRegistration" and isinstance(row.get("custom_answers"), dict):
        from apps.events.answer_derivations.portability import remap_canonical_answers
        row["custom_answers"] = remap_canonical_answers(row["custom_answers"], map_id)
    if label == "events.EventFormRevision" and row["selector_id"] is not None:
        target = {"posting": "EventRolePosting", "round": "MentorRound", "track": "HackathonTrack"}.get(row["selector_kind"])
        if target is None:
            raise ValueError("Invalid typed event form selector.")
        row["selector_id"] = map_id("events." + target, row["selector_id"])
    for path, target in SLOTS.get(label, {}).items():
        root = path.split(".", 1)[0]
        if root == "project" and not isinstance(row.get(root), dict):
            # The private document is remapped after authenticated decryption.
            continue
        if root in row:
            row[root] = deepcopy(row[root])
        _walk(row, path.split("."), target, map_id)
    if label == "events.CertificateIssueBatchItem":
        target = {"registration": "events.EventRegistration", "role_assignment": "events.EventRoleAssignment"}.get(row["subject_kind"])
        if target is None:
            raise ValueError("Invalid certificate batch subject.")
        row["subject_id"] = map_id(target, row["subject_id"])
    if label == "events.SubmissionSnapshot" and not isinstance(row.get("project"), dict):
        return
    if label in {"events.SubmissionSnapshot", "events.EventResultRevision"}:
        row["source_content_sha256"] = source.get("source_content_sha256") or source["content_sha256"]
        if label == "events.SubmissionSnapshot":
            row["sealed_member_ids"] = sorted(row["sealed_member_ids"])
            content = {"project": row["project"], "members": row["sealed_member_ids"]}
        else:
            content = row["aggregates"]
        row["content_sha256"] = _hash(content)
