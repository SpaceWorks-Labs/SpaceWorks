"""Schema-specific import projection. G materializes new rows under import locks.

Only declared ID slots are remapped; user text/URLs/form values are never scanned
for numbers. Incomplete upload/session/work data is dropped, not resumed abroad.
"""
from copy import deepcopy
import hashlib
import json


def remap_snapshot(*, project, sealed_member_ids, source_hash, map_id):
    document = deepcopy(project)
    if not isinstance(document, dict) or not isinstance(sealed_member_ids, list):
        raise ValueError("Invalid frozen submission document.")
    mapper = map_id
    def map_id(label, value):
        if type(value) is not int or value <= 0:
            raise ValueError("Invalid frozen submission reference.")
        return mapper(label, value)
    mappings = {"asset_ids": "events.SubmissionAsset", "public_asset_ids": "events.SubmissionAsset",
                "track_ids": "events.HackathonTrack", "prize_ids": "events.HackathonPrize"}
    for field, label in mappings.items():
        document[field] = [map_id(label, value) for value in document.get(field, [])]
    for asset in document.get("assets", []):
        asset["id"] = map_id("events.SubmissionAsset", asset["id"])
    for link in document.get("links", []):
        link["id"] = map_id("events.SubmissionLink", link["id"])
    from apps.events.answer_derivations.portability import remap_canonical_answers
    if "form_answers" in document:
        document["form_answers"] = remap_canonical_answers(document["form_answers"], map_id)
    members = sorted(map_id("accounts.User", value) for value in sealed_member_ids)
    encoded = json.dumps({"project": document, "members": members}, sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    return {"project": document, "sealed_member_ids": members, "source_content_sha256": source_hash,
            "content_sha256": hashlib.sha256(encoded).hexdigest()}


def asset_import_values(values):
    result = dict(values)
    for field in ("multipart_upload_id", "source_version_id", "verification_version_id", "final_version_id", "source_etag"):
        result[field] = ""
    result.update(reserved_bytes=0, public_requested=False, upload_not_after=None)
    if result["state"] not in {"ready", "expired"}:
        from django.utils import timezone
        result.update(state="aborted", expired_at=result.get("expired_at") or timezone.now(),
                      failure_code="upload_not_portable", deleted_at=timezone.now())
    result["charged_bytes"] = result["actual_bytes"] if result["state"] == "ready" else 0
    # G's object journal remaps canonical final version/key, retaining the source
    # absolute retention timestamps. No new 365-day window is computed here.
    return result


def finalize_imported_assets(*, event, accepted_objects):
    """Rebuild only from target-verified canonical object journal entries.

    The importer calls this in its target transaction, after object promotion and
    before enabling the target. Its object journal accounts provider bytes; this
    adapter creates event counters and deployment custody without charging twice.
    accepted_objects maps final keys to (size, SHA-256, target VersionId).
    """
    from django.db import connection
    from apps.makerspaces import limits
    from .models_assets import EventAssetUsage, EventAssetObligation, SubmissionAsset, HackathonParticipantAsset
    from .quota import MANAGED_ALLOWANCE
    if not connection.in_atomic_block or event.makerspace.lifecycle_state != "importing":
        raise RuntimeError("Finalize assets only inside target import publication.")
    managed = not limits.is_self_host()
    usage, _ = EventAssetUsage.objects.get_or_create(event=event, defaults={"budget_bytes": 0})
    usage = EventAssetUsage.objects.select_for_update().get(pk=usage.pk)
    total = 0
    for model in (SubmissionAsset, HackathonParticipantAsset):
        for asset in model.objects.filter(event=event).order_by("pk"):
            if asset.state == "ready":
                proof = accepted_objects.get(asset.object_key)
                if proof is None or tuple(proof[:2]) != (asset.actual_bytes, asset.sha256):
                    raise ValueError("Imported canonical asset lacks a target byte proof.")
                # Retained hashes are authoritative where the target has no
                # versioning; never carry a source bucket's version identifier.
                if len(proof) != 3 or not isinstance(proof[2], str):
                    raise ValueError("Target object version proof is malformed.")
                if asset.final_version_id and asset.final_version_id != proof[2]:
                    raise ValueError("Source bucket version identity survived import.")
                if asset.final_version_id != proof[2]:
                    model.objects.filter(pk=asset.pk).update(final_version_id=proof[2])
                    asset.final_version_id = proof[2]
                total += asset.actual_bytes
            elif asset.state != "expired" and asset.state != "aborted":
                raise ValueError("An imported upload cannot retain runnable work.")
            expected = asset.actual_bytes if asset.state == "ready" else 0
            receipt, created = EventAssetObligation.objects.get_or_create(asset_uuid=asset.public_id, defaults={
                "asset_label": model._meta.label, "asset_id_snapshot": asset.pk,
                "event_id_snapshot": event.pk, "makerspace_id_snapshot": event.makerspace_id,
                "object_key": asset.object_key, "staging_key": asset.staging_key,
                "verification_key": asset.verification_key, "initial_bytes": expected,
                "charged_bytes": expected, "managed": managed,
            })
            exact = {"asset_label": model._meta.label, "asset_id_snapshot": asset.pk,
                "event_id_snapshot": event.pk, "makerspace_id_snapshot": event.makerspace_id,
                "object_key": asset.object_key, "staging_key": asset.staging_key,
                "verification_key": asset.verification_key, "initial_bytes": expected,
                "charged_bytes": expected, "reserved_bytes": 0, "managed": managed}
            if not created and (any(getattr(receipt, key) != value for key, value in exact.items())
                    or receipt.fully_released or receipt.canonical_extra_bytes):
                raise ValueError("Target asset accounting conflicts with its durable receipt.")
    budget = MANAGED_ALLOWANCE if managed else None
    configured = getattr(getattr(event, "hackathon_config", None), "storage_budget_bytes", None)
    if configured is not None:
        budget = min(budget, configured) if budget is not None else configured
    if budget is not None and total > budget:
        raise ValueError("Imported canonical bytes exceed the target event allowance.")
    usage.budget_bytes, usage.used_bytes, usage.reserved_bytes, usage.failed_cleanup_bytes = budget, total, 0, 0
    usage.save(update_fields=["budget_bytes", "used_bytes", "reserved_bytes", "failed_cleanup_bytes"])
    return total
