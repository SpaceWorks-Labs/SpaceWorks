"""Staff and signatory commands for certificate signatories (C4). Every change is audited."""
import logging

from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit.services import record
from apps.events.credentials.errors import ProgrammeConflict

from .signatories import approval_required, current_designs, design_status, printed_slots

logger = logging.getLogger(__name__)
FIELDS = ("name", "title", "member_id", "signature_id")


def _locked(event, actor):
    from apps.events.services_certificate_templates import _locked as design_lock
    return design_lock(event, actor)


def _member(event, member_id):
    if member_id is None:
        return None
    from apps.accounts.models import User
    from apps.accounts.staff_identity import person_q
    from apps.makerspaces.models import MakerspaceMembership
    user = User.objects.filter(person_q(), pk=member_id, is_active=True, access_status="active",
                               retired_at__isnull=True).first()
    if user is None or not MakerspaceMembership.objects.filter(
            user=user, makerspace_id=event.makerspace_id, status="active").exists():
        raise ValidationError({"member_id": "Choose an active account of this space."})
    return user


def _signature(event, artwork_id):
    if artwork_id is None:
        return None
    from apps.events.models_certificate_templates import EventCertificateArtwork
    row = EventCertificateArtwork.objects.filter(event=event, pk=artwork_id, promoted_at__isnull=False).first()
    if row is None:
        raise ValidationError({"signature_artwork_id": "Upload and finalise the signature image first."})
    return row


@transaction.atomic
def save_signatory(event, *, actor, slot, name, title="", member_id=None, signature_artwork_id=None):
    from .signatory_models import EventCertificateSignatory
    event = _locked(event, actor)
    member, signature = _member(event, member_id), _signature(event, signature_artwork_id)
    row = EventCertificateSignatory.objects.select_for_update().filter(event=event, slot=slot).first()
    values = {"name": name.strip(), "title": title.strip(), "member_id": member.pk if member else None,
              "signature_id": signature.pk if signature else None}
    if not values["name"]:
        raise ValidationError({"name": "Enter the signatory's name."})
    if approval_required(event) and member is None:
        raise ValidationError({"member_id": "Signatories must approve designs here, so choose their account."})
    if row is None:
        row = EventCertificateSignatory(event=event, slot=slot, **values)
    elif all(getattr(row, key) == value for key, value in values.items()):
        return row
    else:
        for key, value in values.items():
            setattr(row, key, value)
        row.version += 1
    row.full_clean()
    row.save()
    record(actor, "event.certificate_signatory_saved", makerspace=event.makerspace, target=row,
           meta={"slot": slot, "version": row.version, "has_signature": bool(signature),
                 "has_account": bool(member)})
    transaction.on_commit(lambda: request_approvals(event.pk), robust=True)
    return row


@transaction.atomic
def remove_signatory(event, *, actor, slot):
    from .signatory_models import EventCertificateSignatory
    event = _locked(event, actor)
    row = EventCertificateSignatory.objects.select_for_update().filter(event=event, slot=slot).first()
    if row is None:
        raise NotFound()
    if any(slot in printed_slots(design.parameters) for design in current_designs(event)):
        raise ProgrammeConflict("A current certificate design prints this signature. Remove the layer first.",
                                code="signatory_in_use")
    record(actor, "event.certificate_signatory_removed", makerspace=event.makerspace, target=row,
           meta={"slot": slot, "version": row.version})
    row.delete()


@transaction.atomic
def set_approval_required(event, *, actor, required):
    from .models import EventCertificatePublicationPolicy
    from .signatory_models import EventCertificateSignatory
    event = _locked(event, actor)
    if required and EventCertificateSignatory.objects.filter(event=event, member__isnull=True).exists():
        raise ValidationError({"required": "Choose an account for every signatory before requiring approval."})
    policy, _ = EventCertificatePublicationPolicy.objects.select_for_update().get_or_create(event=event)
    if policy.signatory_approval_required != required:
        policy.signatory_approval_required = required
        policy.save(update_fields=("signatory_approval_required", "changed_at"))
        record(actor, "event.certificate_signatory_approval_policy_changed", makerspace=event.makerspace,
               target=policy, meta={"required": required})
        if required:
            transaction.on_commit(lambda: request_approvals(event.pk), robust=True)
    return policy


def approve(event_id, *, actor, signatory_id, template_revision_id):
    """The signatory approves one design revision with their current details."""
    from apps.events.models import Event
    from apps.events.models_certificate_templates import EventCertificateTemplateRevision
    from apps.makerspaces.guards import require_module_locked
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    from .signatory_models import EventCertificateSignatory, EventCertificateSignatoryApproval
    with transaction.atomic():
        event = Event.objects.select_for_update().filter(pk=event_id).first()
        if event is None:
            raise NotFound()
        assert_write_allowed(event.makerspace_id)
        event.makerspace = require_module_locked(event.makerspace_id, "events")
        signatory = EventCertificateSignatory.objects.select_for_update().filter(
            pk=signatory_id, event=event, member=actor).first()
        revision = EventCertificateTemplateRevision.objects.filter(pk=template_revision_id, event=event).first()
        if signatory is None or revision is None:
            raise NotFound()
        if signatory.slot not in printed_slots(revision.parameters):
            raise ValidationError({"template_revision_id": "This design does not print your signature."})
        row, created = EventCertificateSignatoryApproval.objects.get_or_create(
            signatory=signatory, template_revision=revision, signatory_version=signatory.version,
            defaults={"approved_by": actor})
        if created:
            record(actor, "event.certificate_design_approved", makerspace=event.makerspace, target=row,
                   meta={"slot": signatory.slot, "template_revision_id": revision.pk,
                         "signatory_version": signatory.version})
            transaction.on_commit(lambda: _render_released(event.pk, revision.pk), robust=True)
        return row


def _render_released(event_id, revision_id):
    from apps.events.models_certificates import EventAttendanceCertificate
    from .tasks import render_one
    for pk in EventAttendanceCertificate.objects.filter(event_id=event_id, template_revision_id=revision_id,
                                                        status__in=("pending", "failed")).values_list("pk", flat=True)[:500]:
        try:
            render_one.delay(pk)
        except Exception:
            logger.warning("event_certificate_release_dispatch_failed", extra={"certificate_id": pk})


def pending_for(actor, makerspace_id):
    """Designs waiting for this person's approval, across this space's events."""
    from .signatory_models import EventCertificateSignatory
    result = []
    for signatory in EventCertificateSignatory.objects.select_related("event").filter(
            member=actor, event__makerspace_id=makerspace_id).order_by("event_id", "slot"):
        event = signatory.event
        if not approval_required(event):
            continue
        for design in current_designs(event):
            status = {item["slot"]: item for item in design_status(event, design)}.get(signatory.slot)
            if status is not None:
                result.append({"signatory_id": signatory.pk, "slot": signatory.slot, "event_id": event.pk,
                               "event_title": event.title, "template_revision_id": design.pk,
                               "certificate_kind": design.certificate_kind, "approved": status["approved"],
                               "name": signatory.name, "title": signatory.title})
    return result


def request_approvals(event_id):
    """Notify each signatory with a current design still waiting for them. Never blocks a command."""
    from .signatory_notifications import notify
    try:
        notify(event_id)
    except Exception:
        logger.warning("event_certificate_signatory_notice_failed", extra={"event_id": event_id})
