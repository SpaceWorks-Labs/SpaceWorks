"""Immutable certificate JSON snapshots are private artwork reference sites."""

from django.apps import apps

from .object_ownership import MAIN_COMPONENT, ObjectReference, slice_component
from .recipient_selection import BackupBuildError


def certificate_snapshot_references(sovereign):
    model = apps.get_model("events.EventAttendanceCertificate")
    rows = model._base_manager.values("pk", "layout_snapshot", "event__makerspace_id")
    for row in rows.iterator(chunk_size=500):
        snapshot = row["layout_snapshot"]
        if not isinstance(snapshot, dict):
            raise BackupBuildError("Certificate layout snapshot must be an object.")
        key = snapshot.get("artwork_object_key")
        if not key:
            continue
        if not isinstance(key, str):
            raise BackupBuildError("Certificate artwork reference must be an object key.")
        owner = row["event__makerspace_id"]
        yield ObjectReference(
            bucket_kind="private", object_key=key,
            site=f"events.EventAttendanceCertificate:{row['pk']}:layout_snapshot.artwork_object_key",
            candidate_owner=slice_component(owner) if owner in sovereign else MAIN_COMPONENT,
            canonical_makerspace_id=owner, module_key="events",
            coordination_policy="", coordination_makerspace_id=None,
        )
