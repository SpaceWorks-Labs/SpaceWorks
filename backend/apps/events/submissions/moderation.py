from apps.audit.services import record
from .errors import SubmissionError
from .models_projects import HackathonSubmission
from .ports import boundary
from .workflow import canonical_digest
from .pii import prepare_documents


def triage(*, actor, event_id, submission_id, operation_id, expected_version, triage, reason):
    if triage not in {"pending", "eligible", "ineligible", "hidden"} or not isinstance(reason, str) or not 1 <= len(reason) <= 1000:
        raise SubmissionError("triage_reason_required")
    port = boundary()
    with prepare_documents(event_id), port.locked(actor=actor, event_id=event_id, team_id=None, action="triage") as ctx:
        digest = canonical_digest({"submission": submission_id, "version": expected_version, "triage": triage, "reason": reason})
        replay = port.receipt(event_id=event_id, actor_id=actor.pk, operation_id=operation_id, digest=digest)
        if replay is not None:
            return replay
        project = HackathonSubmission.objects.select_for_update().filter(pk=submission_id, event_id=event_id).first()
        if project is None:
            raise SubmissionError("not_found", 404)
        if project.version != expected_version:
            raise SubmissionError("stale_version", 409)
        if not project.current_snapshot_id or project.state == "withdrawn":
            raise SubmissionError("invalid_transition", 409)
        if triage in {"ineligible", "hidden"}:
            port.invalidate_snapshot(context=ctx, snapshot_id=project.current_snapshot_id)
        if triage == "ineligible" and project.triage != "ineligible":  # L21b: staff disqualification.
            from .entry_fees import on_disqualified
            on_disqualified(event=ctx.event, project=project, actor=actor)
        project.triage, project.triage_reason = triage, reason
        project.version += 1
        project.save(update_fields=["triage", "triage_reason", "version"])
        record(actor, "event.submission_triaged", makerspace=ctx.event.makerspace, target=project,
               meta={"triage": triage, "version": project.version})
        result = {"id": project.pk, "event_id": event_id, "version": project.version, "triage": triage,
                  "state": project.state, "snapshot_id": project.current_snapshot_id, "allowed_actions": []}
        port.store_receipt(event_id=event_id, actor_id=actor.pk, operation_id=operation_id, digest=digest, result=result)
        return result
