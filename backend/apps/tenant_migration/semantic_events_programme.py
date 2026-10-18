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
    if label == "events.EventPageSection":
        # Only the declared selector vector is an identity slot. The imported
        # page remains unreleased; person/history selections require new consent.
        options = deepcopy(row.get("options", {}))
        if not isinstance(options, dict) or set(options) - {"ids", "layout", "limit"}:
            raise ValueError("Invalid page section options.")
        target = {"prizes": "HackathonPrize", "project_gallery": "GalleryEntry"}.get(row["kind"])
        ids = options.get("ids", [])
        if (not isinstance(ids, list) or len(ids) > 100
                or any(type(pk) is not int or pk <= 0 for pk in ids) or len(ids) != len(set(ids))):
            raise ValueError("Invalid typed page section selectors.")
        limit = options.get("limit", 12)
        if options.get("layout", "grid") not in {"grid", "list"} or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid page section presentation options.")
        if ids:
            options["ids"] = _walk(ids, ["*"], target, map_id) if target else []
        row["options"] = options
    if label == "events.EventAttendanceCertificate":
        from .semantic_certificate_proof import remap_contribution_proof
        row["layout_snapshot"] = remap_contribution_proof(row["layout_snapshot"], map_id)
    if label in {"events.EventRolePosting", "events.EventShift"}:
        # Evidence references belong to the source programme; target staff must
        # author and attest its own training/briefing IDs. Keep waiver policy.
        row["requirements"] = {**row.get("requirements", {}), "training_ids": [], "briefing_ids": []}
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
