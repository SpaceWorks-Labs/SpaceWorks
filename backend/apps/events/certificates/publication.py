import hashlib
import json

from apps.audit.services import record
from apps.events.credentials.boundary import event_command, advance, require_version
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.credentials.models import EventCredentialCommand
from .models import EventCertificatePublicationPolicy
from apps.events.models_certificates import EventAttendanceCertificate
from rest_framework.exceptions import NotFound, ValidationError


def set_policy(event_id, *, actor, operation_id, expected_version, enabled, certificate_ids=()):
    if type(enabled) is not bool or len(certificate_ids) > 200 or len(set(certificate_ids)) != len(certificate_ids):
        raise ValidationError("Choose at most 200 unique certificate IDs.")
    digest = hashlib.sha256(json.dumps(["verification_policy", expected_version, enabled, sorted(certificate_ids)]).encode()).hexdigest()
    def identities():
        return tuple(EventAttendanceCertificate.objects.filter(event_id=event_id, pk__in=certificate_ids)
                     .order_by("pk").values_list("pk", "recipient_member_id"))
    subjects = identities()

    def revalidate(event):
        if identities() != subjects:
            raise ProgrammeConflict("Certificate ownership changed.", code="subject_changed")

    with event_command(event_id, actor=actor, account_ids=[pk for _, pk in subjects if pk],
                       revalidate=revalidate) as (event, actor):
        receipt = EventCredentialCommand.objects.filter(event=event, operation_id=operation_id).first()
        if receipt:
            if receipt.actor_id != actor.pk or receipt.request_sha256 != digest:
                raise ProgrammeConflict("Operation ID was already used.", code="operation_conflict")
            return receipt.result
        require_version(event, expected_version)
        certificates = list(EventAttendanceCertificate.objects.select_for_update().filter(
            event=event, pk__in=certificate_ids, status__in=("active", "revoked")).order_by("pk"))
        if len(certificates) != len(certificate_ids):
            raise NotFound()
        for certificate in certificates:
            certificate.public_verification_enabled = enabled
            # This policy flag is separate from the immutable issuance snapshot.
            EventAttendanceCertificate.objects.filter(pk=certificate.pk).update(public_verification_enabled=enabled)
            record(actor, "event.certificate_verification_changed", makerspace=event.makerspace,
                   target=certificate, meta={"enabled": enabled})
        policy, _ = EventCertificatePublicationPolicy.objects.get_or_create(event=event)
        policy.enabled, policy.version = enabled, policy.version+1
        policy.save(update_fields=("enabled", "version", "changed_at"))
        record(actor, "event.certificate_verification_policy_changed", makerspace=event.makerspace, target=policy,
               meta={"enabled": enabled, "version": policy.version})
        result = {"id": policy.pk, "event_id": event.pk, "version": advance(event), "event_version": event.version,
                  "enabled": enabled, "state": "applied", "allowed_actions": [], "certificate_count": len(certificates)}
        EventCredentialCommand.objects.create(event=event, actor=actor, operation_id=operation_id,
                                             request_sha256=digest, result=result)
        return result
