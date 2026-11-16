from .api_runtime import runtime
from .asset_workflow import initialize_asset
from .ports import boundary
from .workflow import canonical_digest


def copy_from_saved(*, actor, event_id, operation_id, saved_asset_id, saved_detail_version):
    digest = canonical_digest({"from_saved": {"saved_asset_id": saved_asset_id, "saved_detail_version": saved_detail_version}})
    port = boundary()
    with port.locked(actor=actor, event_id=event_id, team_id=None, action="upload"):
        replay = port.receipt(event_id=event_id, actor_id=actor.pk, operation_id=operation_id, digest=digest)
        if replay is not None:
            return {"asset_id": replay["asset_id"], "event_id": event_id, "state": replay["state"]}
    # Account preparation/KMS always precedes event transaction/locks.
    prepared = runtime().saved_resume_provider.prepare(actor_id=actor.pk, saved_asset_id=saved_asset_id,
                                                       saved_detail_version=saved_detail_version)
    result = initialize_asset(actor=actor, event_id=event_id, team_id=None, operation_id=operation_id,
        request_digest=digest,
        participant=True, saved_source={"saved_asset_id": saved_asset_id, "saved_detail_version": saved_detail_version},
        data={"filename": prepared.filename, "mime": "application/pdf", "bytes": prepared.size_bytes,
              "group": "resume", "subtype": "pdf"})
    return {"asset_id": result["asset_id"], "event_id": event_id, "state": "copying"}
