import hashlib
import json

from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit.services import record
from apps.events.credentials.boundary import advance, event_command, require_version
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.models_certificates import EventAttendanceCertificate
from .issuance import create_for_subject_locked
from .models import CertificateIssueBatch, CertificateIssueBatchItem, EventCertificatePublicationPolicy
from .subjects import require_subject

MAX_BATCH = 10_000
CHUNK_SIZE = 100


def preview(event, *, actor, subjects):
    from apps.events import event_authority
    event_authority.require(actor, event, None)
    eligible = []
    with event_command(event.pk, actor=actor) as (event, _actor):
        for item in subjects:
            require_subject(event, **item)
            eligible.append(item)
    return {"eligible_count": len(eligible), "event_version": event.version,
            "public_verification_disclosure": "Verification publishes the event title, date and valid or revoked status only."}


def enqueue(event_id, *, actor, operation_id, expected_version, subjects, publish_event_details,
            all_attended=False, confirmed_count=None):
    if (not isinstance(subjects, list) or not (0 if all_attended else 1) <= len(subjects) <= MAX_BATCH
            or type(publish_event_details) is not bool):
        raise ValidationError({"subjects": "Choose 1–10000 certificate subjects."})
    encoded = json.dumps(subjects, sort_keys=True, separators=(",", ":"))
    if len({json.dumps(row, sort_keys=True) for row in subjects}) != len(subjects):
        raise ValidationError({"subjects": "Subjects must be unique."})
    digest = hashlib.sha256(json.dumps([encoded, expected_version, publish_event_details, all_attended, confirmed_count]).encode()).hexdigest()
    with event_command(event_id, actor=actor) as (event, actor):
        previous = CertificateIssueBatch.objects.filter(event=event, operation_id=operation_id).first()
        if previous:
            if previous.request_sha256 != digest or previous.actor_id != actor.pk:
                raise ProgrammeConflict("Operation ID was already used.", code="operation_conflict")
            return previous
        require_version(event, expected_version)
        if all_attended:
            from apps.events.models_registration import EventRegistration
            subjects = [{"subject_kind": "registration", "subject_id": pk, "kind": "attendance"}
                        for pk in EventRegistration.objects.filter(event=event, status="attended", member__isnull=False)
                        .order_by("pk").values_list("pk", flat=True)[:MAX_BATCH+1]]
            if not 1 <= len(subjects) <= MAX_BATCH or confirmed_count != len(subjects):
                raise ProgrammeConflict("Attendance count changed. Preview again.", code="eligibility_changed")
        for item in subjects:
            require_subject(event, **item)
        if publish_event_details:
            policy, _ = EventCertificatePublicationPolicy.objects.get_or_create(event=event)
            policy.enabled, policy.version = True, policy.version + 1
            policy.save(update_fields=("enabled", "version", "changed_at"))
            record(actor, "event.certificate_publication_enabled", makerspace=event.makerspace,
                   target=policy, meta={"version": policy.version})
        batch = CertificateIssueBatch.objects.create(event=event, actor=actor,
                operation_id=operation_id, request_sha256=digest, version=advance(event),
                public_verification_enabled=publish_event_details)
        for item in subjects:
            CertificateIssueBatchItem.objects.create(batch=batch, **item)
        record(actor, "event.certificate_batch_created", makerspace=event.makerspace,
               target=batch, meta={"count": len(subjects), "publish_event_details": publish_event_details})
        from .tasks import dispatch_batch
        transaction.on_commit(lambda: dispatch_batch(batch.pk), robust=True)
        return batch


def run_chunk(batch_id):
    identity = CertificateIssueBatch.objects.select_related("actor").get(pk=batch_id)
    # Live full-manager authority is required again after queue delay or revocation.
    if identity.actor is None:
        raise NotFound()
    with event_command(identity.event_id, actor=identity.actor) as (event, actor):
        batch = CertificateIssueBatch.objects.select_for_update().get(pk=batch_id)
        if batch.state == "completed":
            return batch
        items = batch.items.select_for_update().filter(state="queued").order_by("pk")[:CHUNK_SIZE]
        batch.state = "running"
        batch.save(update_fields=("state",))
        record(actor, "event.certificate_batch_started", makerspace=event.makerspace, target=batch)
        for item in items:
            try:
                item.certificate = create_for_subject_locked(event,
                    subject_kind=item.subject_kind, subject_id=item.subject_id, kind=item.kind,
                    award_id=item.award_id, result_revision_id=item.result_revision_id, actor=actor,
                    public_verification_enabled=batch.public_verification_enabled)
                item.state = "completed"
            except (ProgrammeConflict, NotFound):
                item.state, item.error_code = "failed", "certificate_ineligible"
            item.save(update_fields=("certificate", "state", "error_code"))
            record(actor, "event.certificate_batch_item_processed", makerspace=event.makerspace,
                   target=item, meta={"state": item.state, "error_code": item.error_code})
        if not batch.items.filter(state="queued").exists():
            batch.state, batch.completed_at = "completed", timezone.now()
            batch.save(update_fields=("state", "completed_at"))
            record(actor, "event.certificate_batch_completed", makerspace=event.makerspace, target=batch)
        return batch


def project(batch):
    return {"id": batch.pk, "event_id": batch.event_id, "version": batch.version,
            "state": batch.state, "allowed_actions": [],
            "total": batch.items.count(), "completed": batch.items.filter(state="completed").count(),
            "failures": [{"id": row.pk, "error_code": row.error_code} for row in batch.items.filter(state="failed")[:100]]}
