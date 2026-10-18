from uuid import uuid4
from django.utils import timezone
from rest_framework.exceptions import NotFound
from apps.audit.services import record
from apps.events import certificate_artwork_storage as storage
from apps.makerspaces import limits
from .library import tenant_command
from .library_models import EventCertificateLibraryTemplate, EventCertificateLibraryArtwork


def reserve(makerspace_id, template_id, *, actor, content_type, content_length):
    with tenant_command(makerspace_id, actor) as space:
        template = EventCertificateLibraryTemplate.objects.filter(pk=template_id, makerspace=space).first()
        if not template:
            raise NotFound()
        limits.add_storage(space, storage.MAX_BYTES)
        row = EventCertificateLibraryArtwork.objects.create(template=template,
            object_key=f"events/certificate-library/{space.pk}/{uuid4()}.png", sha256="", size_bytes=storage.MAX_BYTES)
        url = storage.upload_url(row, content_type=content_type, content_length=content_length)
        record(actor, "event.certificate_library_artwork_reserved", makerspace=space, target=row)
        return row, url


def finalize(makerspace_id, template_id, artwork_id, *, actor):
    with tenant_command(makerspace_id, actor):
        row = EventCertificateLibraryArtwork.objects.filter(pk=artwork_id, template_id=template_id,
                    template__makerspace_id=makerspace_id).first()
        if not row:
            raise NotFound()
        if row.promoted_at:
            return row
    size, digest, version = storage.promote_bytes(row)
    with tenant_command(makerspace_id, actor) as space:
        row = EventCertificateLibraryArtwork.objects.select_for_update().get(pk=row.pk)
        if not row.promoted_at:
            limits.free_storage(space, max(0, row.size_bytes-size))
            row.size_bytes, row.sha256, row.version_id, row.promoted_at = size, digest, version, timezone.now()
            row.save(update_fields=("size_bytes", "sha256", "version_id", "promoted_at"))
            record(actor, "event.certificate_library_artwork_promoted", makerspace=space, target=row,
                   meta={"size_bytes": size})
    storage.cleanup_staging(row)
    return row
