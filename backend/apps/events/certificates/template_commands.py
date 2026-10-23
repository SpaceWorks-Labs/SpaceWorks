import hashlib
import json
from apps.events.credentials.boundary import event_command, require_version, advance
from apps.events.credentials.models import EventCredentialCommand
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.event_permissions import EDIT_DETAILS
from apps.events.services_certificate_templates import save_template


def save_command(event_id, *, actor, operation_id, expected_version, parameters, artwork_id=None):
    digest = hashlib.sha256(json.dumps(["certificate_design", expected_version, parameters, artwork_id], sort_keys=True).encode()).hexdigest()
    with event_command(event_id, actor=actor, permission=EDIT_DETAILS) as (event, actor):
        receipt = EventCredentialCommand.objects.filter(event=event, operation_id=operation_id).first()
        if receipt:
            if receipt.actor_id != actor.pk or receipt.request_sha256 != digest:
                raise ProgrammeConflict("Operation ID was already used.", code="operation_conflict")
            return receipt.result
        require_version(event, expected_version)
        row = save_template(event, actor=actor, parameters=parameters, artwork_id=artwork_id)
        result = {"id": row.pk, "event_id": event.pk, "version": advance(event), "event_version": event.version,
                  "state": "applied", "allowed_actions": [], "parameters": row.parameters,
                  "artwork_id": row.artwork_id, "created_at": row.created_at.isoformat()}
        EventCredentialCommand.objects.create(event=event, actor=actor, operation_id=operation_id,
                                             request_sha256=digest, result=result)
        return result
