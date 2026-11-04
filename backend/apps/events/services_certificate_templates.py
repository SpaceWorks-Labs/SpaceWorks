"""Short, audited design transactions. Storage I/O happens between transactions."""

from uuid import uuid4

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit import services as audit
from apps.events import event_authority
from apps.events.event_permissions import EDIT_DETAILS
from apps.events.feature_gates import require_feature
from apps.events.exceptions import EventInvalidTransition
from apps.events.models import Event, EventCertificateArtwork, EventCertificateTemplateRevision
from apps.events.certificate_templates import normalize_certificate_template
from apps.events import certificate_artwork_storage as storage
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces import limits
from apps.tenant_migration.gate_runtime import assert_write_allowed

FEATURE = "events.certificate_designer"


def require_design(event, actor):
    event_authority.require(actor, event, EDIT_DETAILS)
    require_feature(event, FEATURE)


def _locked(event, actor):
    assert_write_allowed(event.makerspace_id)
    row = Event.objects.select_for_update().get(pk=event.pk)
    row.makerspace = require_module_locked(row.makerspace_id, "events")
    from apps.events.staff_grant_locks import lock_authority
    require_design(row, lock_authority(actor, row))
    if row.status == Event.Status.CANCELLED:
        raise EventInvalidTransition("Cancelled events cannot change certificate designs.")
    return row


def _artwork(event, artwork_id):
    if artwork_id is None:
        return None
    try:
        return EventCertificateArtwork.objects.get(event=event, pk=artwork_id, promoted_at__isnull=False)
    except EventCertificateArtwork.DoesNotExist as exc:
        raise NotFound("Artwork was not found for this event.") from exc


@transaction.atomic
def save_template(event, *, actor, parameters, artwork_id=None):
    event = _locked(event, actor)
    parameters = normalize_certificate_template(parameters)
    artwork = _artwork(event, artwork_id)
    if parameters.get("version") == 2:
        from types import SimpleNamespace
        from .certificate_templates import issuance_layout
        issuance_layout(SimpleNamespace(parameters=parameters, artwork=artwork, event_id=event.pk))
    revision = EventCertificateTemplateRevision.objects.create(
        event=event, artwork=artwork, parameters=parameters,
    )
    audit.record(actor, "event.certificate_template_saved", makerspace=event.makerspace,
                 target=revision, meta={"artwork_id": artwork_id})
    return revision


@transaction.atomic
def reserve_artwork(event, *, actor, content_type, content_length):
    event = _locked(event, actor)
    limits.add_storage(event.makerspace, storage.MAX_BYTES)
    row = EventCertificateArtwork.objects.create(
        event=event, size_bytes=storage.MAX_BYTES, object_key=f"events/certificate-artwork/{event.makerspace_id}/{uuid4()}.png",
    )
    audit.record(actor, "event.certificate_artwork_presigned", makerspace=event.makerspace,
                 target=row, meta={})
    # Signing is local: failure rolls back the row, audit and quota reservation.
    return row, storage.upload_url(row, content_type=content_type, content_length=content_length)


def finalize_artwork(event, artwork_id, *, actor):
    require_design(event, actor)
    try:
        row = EventCertificateArtwork.objects.get(event=event, pk=artwork_id)
    except EventCertificateArtwork.DoesNotExist as exc:
        raise NotFound() from exc
    if row.promoted_at:
        return row
    # Decode/promote without database row locks. S3's conditional PUT elects one
    # immutable final object; only its bytes can be attached by the transaction.
    metadata = storage.promote_bytes(row)
    row = _attach_artwork(event, row.pk, metadata, actor)
    storage.cleanup_staging(row)
    return row


@transaction.atomic
def _attach_artwork(event, artwork_id, metadata, actor):
    event = _locked(event, actor)
    row = EventCertificateArtwork.objects.select_for_update().get(event=event, pk=artwork_id)
    if row.promoted_at:
        return row
    size, digest, version = metadata
    limits.free_storage(event.makerspace, max(0, row.size_bytes - size))
    row.size_bytes, row.sha256, row.version_id = size, digest, version
    row.promoted_at = timezone.now()
    row.save(update_fields=("size_bytes", "sha256", "version_id", "promoted_at"))
    audit.record(actor, "event.certificate_artwork_promoted", makerspace=event.makerspace,
                 target=row, meta={"size_bytes": size})
    return row


def preview_context(event, *, actor, parameters, artwork_id=None):
    from types import SimpleNamespace
    from apps.events.certificate_templates import issuance_layout
    require_design(event, actor)
    artwork = _artwork(event, artwork_id)
    snapshot = issuance_layout(SimpleNamespace(
        parameters=normalize_certificate_template(parameters), artwork=artwork, event_id=event.pk,
    ))
    audit.record(actor, "event.certificate_template_previewed", makerspace=event.makerspace,
                 target=event, meta={"revision_id": None})
    return SimpleNamespace(layout_snapshot=snapshot, recipient_name="Sample attendee",
                           event_title=event.title, issuer_name=event.makerspace.name,
                           event_starts_at=event.starts_at, event_ends_at=event.ends_at,
                           issued_at=timezone.now(), serial="PREVIEW", revision=0)
