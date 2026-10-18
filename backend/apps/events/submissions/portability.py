"""Schema-specific import projection. G materializes new rows under import locks.

Only declared ID slots are remapped; user text/URLs/form values are never scanned
for numbers. Incomplete upload/session/work data is dropped, not resumed abroad.
"""
from copy import deepcopy
import hashlib
import json


def remap_snapshot(*, project, sealed_member_ids, source_hash, map_id):
    document = deepcopy(project)
    mappings = {"asset_ids": "events.SubmissionAsset", "public_asset_ids": "events.SubmissionAsset",
                "track_ids": "events.HackathonTrack", "prize_ids": "events.HackathonPrize"}
    for field, label in mappings.items():
        document[field] = [map_id(label, value) for value in document.get(field, [])]
    for asset in document.get("assets", []):
        asset["id"] = map_id("events.SubmissionAsset", asset["id"])
    for link in document.get("links", []):
        link["id"] = map_id("events.SubmissionLink", link["id"])
    members = sorted(map_id("accounts.User", value) for value in sealed_member_ids)
    encoded = json.dumps({"project": document, "members": members}, sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    return {"project": document, "sealed_member_ids": members, "source_content_sha256": source_hash,
            "content_sha256": hashlib.sha256(encoded).hexdigest()}


def asset_import_values(values):
    result = dict(values)
    for field in ("multipart_upload_id", "source_version_id", "verification_version_id", "source_etag"):
        result[field] = ""
    result.update(reserved_bytes=0, public_requested=False, upload_not_after=None)
    # G's object journal remaps canonical final version/key, retaining the source
    # absolute retention timestamps. No new 365-day window is computed here.
    return result
