"""Live certificate scope and operational writes without decrypting frozen PII."""
from django.utils.translation import gettext
from contextlib import contextmanager

from apps.events.credentials.boundary import event_command
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.models_certificates import EventAttendanceCertificate as Certificate
from .preparation import prepare_issuance


def certificate_preparation(certificate, *, for_issue=False):
    return prepare_issuance(certificate.event_id, [{
        "subject_kind": "registration" if certificate.registration_id else "role_assignment",
        "subject_id": certificate.registration_id or certificate.role_assignment_id,
        "kind": certificate.kind,
    }], for_issue=for_issue)


@contextmanager
def certificate_command(certificate_id, *, actor=None):
    identity = Certificate.objects.get(pk=certificate_id)
    if actor is not None:
        from apps.events import event_authority
        event_authority.get_event(actor, identity.event_id, None)
    prepared = certificate_preparation(identity)
    with event_command(identity.event_id, actor=actor, account_ids=prepared.account_ids,
                       revalidate=prepared.revalidate) as (event, actor):
        row = Certificate.objects.select_for_update().get(pk=certificate_id, event=event)
        recipient = prepared.recipient("registration" if row.registration_id else "role_assignment",
                                        row.registration_id or row.role_assignment_id)
        if row.recipient_member_id != recipient.member_id:
            raise ProgrammeConflict(gettext("Certificate subject changed."), code="subject_changed")
        row.event = event
        yield event, actor, row, recipient


def save_operational(row, fields):
    """The lifecycle validates transitions while holding this exact row lock.

    Updating only closed operational columns avoids Model.save comparing/decrypting
    every issuance field (and calling a broker) under an Event lock. No issuance
    snapshot or PII column can pass this boundary; database guards still apply.
    """
    allowed = {"status", "render_token", "render_started_at", "render_attempts", "size_bytes",
               "sha256", "rendered_at", "revoked_at", "revoked_by", "revocation_reason"}
    if not set(fields) <= allowed:
        raise RuntimeError("Only certificate lifecycle columns may change.")
    values = {Certificate._meta.get_field(name).attname:
              getattr(row, Certificate._meta.get_field(name).attname) for name in fields}
    Certificate.objects.filter(pk=row.pk).update(**values)
