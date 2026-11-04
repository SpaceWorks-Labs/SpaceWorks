"""Explicit JSON reference slots and fidelity transforms; never search user text.

G's catalogue invokes these on decrypted values before target envelope sealing.
Object keys/versions are replaced by G's capture journal, never ID-string edits.
"""
from copy import deepcopy

COORDINATION = frozenset({"events.StageActivationJob", "events.StageReconcileCursor", "events.StageFileCleanup"})
REFERENCES = {
    "events.StageFormResponse.answers_snapshot": "answers[type=file].value[].asset_id -> events.StageFormAsset",
    "events.StageFormResponseRevision.answers_snapshot": "answers[type=file].value[].asset_id -> events.StageFormAsset",
    "events.EventStageForm.audience": "track_ids[] -> events.HackathonTrack",
    "events.StageFormAssignment.policy_snapshot": "audience.track_ids[] -> events.HackathonTrack",
}


def remap_json(field, value, *, map_id):
    if field not in REFERENCES:
        raise ValueError("Unregistered stage JSON field.")
    result = deepcopy(value)
    if field.endswith("answers_snapshot"):
        for answer in result.get("answers", []):
            if answer.get("type") == "file":
                for reference in answer.get("value", []):
                    if set(reference) != {"asset_id", "generation", "sha256"}:
                        raise ValueError("Invalid stage file reference.")
                    reference["asset_id"] = map_id("events.StageFormAsset", reference["asset_id"])
    else:
        audience = result["audience"] if field.endswith("policy_snapshot") and "audience" in result else result
        for index, pk in enumerate(audience.get("track_ids", [])):
            audience["track_ids"][index] = map_id("events.HackathonTrack", pk)
    return result


def import_values(label, values, *, fidelity):
    if fidelity not in ("PORTABLE", "REDACTED"):
        raise ValueError("Unknown export fidelity.")
    if label in COORDINATION:
        return None
    result = deepcopy(values)
    if label == "events.StageFormAssignment":
        if result.get("registration_id") is None and result.get("application_id") is None:
            return None
        result["imported_paused"] = True
        result["creation_operation_id"] = None
    elif label == "events.StageFormAsset":
        if result["state"] not in ("attached", "expired", "deleted"):
            # Unattached presigns/work never resume on the target deployment.
            return None
        result.update(staging_version_id="", final_version_id="", lease_token=None, lease_until=None, attempts=0)
        # G supplies remapped final object locator/version after capture. Keep
        # absolute expires_at and duration: importing never restarts retention.
    return result


def generic_export_answers(*, schema, snapshot, current_schema):
    """Generic exports get no sensitive values, file IDs, or private byte URLs."""
    from apps.forms_schema.sensitive_policy import project_answers
    return project_answers(schema, snapshot, viewer="organizer", current_schema=current_schema)
