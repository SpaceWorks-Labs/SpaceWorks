from uuid import uuid4
import hashlib
from django.utils import timezone

from apps.audit.services import record
from apps.events.profile_photos.snapshot import read_public_png
from apps.makerspaces import limits
from .print_models import BadgePrintResource
from .print_policy import require_job
from .print_boundary import print_command
from . import print_storage


def prepare_logo(job, actor):
    if not any(layer["type"] == "logo" for layer in job.template["layers"]):
        return
    key = job.event.makerspace.logo_key
    if not key:
        return
    content = read_public_png(key)
    digest = hashlib.sha256(content).hexdigest()
    key_digest = hashlib.sha256(key.encode()).hexdigest()
    for qr in job.resources.filter(kind="qr"):
        with print_command(job, actor=actor) as (event, actor, scope):
            require_job(job, actor, prepared_scope=scope)
            if hashlib.sha256(event.makerspace.logo_key.encode()).hexdigest() != key_digest:
                from apps.events.credentials.errors import ProgrammeConflict
                raise ProgrammeConflict("The event logo changed.", code="print_snapshot_changed")
            resource, created = BadgePrintResource.objects.get_or_create(job=job, registration_id=qr.registration_id,
                kind="logo", defaults={"object_key": f"events/badge-print/{event.makerspace_id}/{uuid4()}.png",
                    "source_key_sha256": key_digest, "sha256": digest,
                    "size_bytes": len(content), "expires_at": job.expires_at})
            if resource.sha256 != digest or resource.source_key_sha256 != key_digest:
                from apps.events.credentials.errors import ProgrammeConflict
                raise ProgrammeConflict("Logo reservation changed.", code="print_snapshot_changed")
            if created:
                limits.add_storage(event.makerspace, len(content))
            record(actor, "event.badge_logo_reserved", makerspace=event.makerspace, target=resource)
        if resource.bound_at:
            continue
        print_storage.put(resource.object_key, content, "image/png")
        with print_command(job, actor=actor) as (event, actor, scope):
            require_job(job, actor, prepared_scope=scope)
            resource = BadgePrintResource.objects.select_for_update().get(pk=resource.pk)
            if resource.bound_at:
                continue
            resource.bound_at = timezone.now()
            resource.save(update_fields=("bound_at",))
            record(actor, "event.badge_resource_bound", makerspace=event.makerspace, target=resource,
                   meta={"job_id": job.pk, "kind": "logo"})
