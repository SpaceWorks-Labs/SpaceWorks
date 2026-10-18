import hashlib
import json
from django.shortcuts import get_object_or_404

from apps.events.credentials.boundary import advance, event_command, require_version
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.credentials.models import EventCredentialCommand
from apps.events.models_certificates import EventAttendanceCertificate
from .issuance import create_for_subject_locked
from .lifecycle import revoke


def change_certificate(event_id, certificate_id, *, actor, action, operation_id, expected_version, reason):
    digest = hashlib.sha256(json.dumps(["certificate", action, certificate_id, expected_version, reason]).encode()).hexdigest()
    with event_command(event_id, actor=actor) as (event, actor):
        receipt = EventCredentialCommand.objects.filter(event=event, operation_id=operation_id).first()
        if receipt:
            if receipt.actor_id != actor.pk or receipt.request_sha256 != digest:
                raise ProgrammeConflict("Operation ID was already used.", code="operation_conflict")
            return receipt.result
        require_version(event, expected_version)
        row = get_object_or_404(EventAttendanceCertificate, pk=certificate_id, event=event)
        if action == "revoke":
            row = revoke(row, actor=actor, reason=reason)
        elif action == "reissue":
            if row.status != "revoked":
                raise ProgrammeConflict("Revoke the earlier certificate before reissuing.")
            row = create_for_subject_locked(event, subject_kind="registration" if row.registration_id else "role_assignment",
                subject_id=row.registration_id or row.role_assignment_id, kind=row.kind, actor=actor,
                award_id=row.award_id, result_revision_id=row.result_revision_id)
        else:
            raise ValueError("Unknown certificate action.")
        result = {"id": row.pk, "event_id": event.pk, "version": advance(event),
                  "state": "applied", "allowed_actions": []}
        EventCredentialCommand.objects.create(event=event, operation_id=operation_id, actor=actor,
                                             request_sha256=digest, result=result)
        return result
