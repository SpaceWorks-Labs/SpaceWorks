from uuid import uuid4
import hashlib
from django.utils import timezone

from apps.audit.services import record
from apps.events.credentials.boundary import event_command
from apps.events.event_permissions import CHECK_IN
from apps.events.profile_photos.snapshot import read_public_png
from apps.makerspaces import limits
from .print_models import BadgePrintResource
from .print_policy import require_job, source_tenants
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
        with event_command(job.event_id, actor=actor, permission=CHECK_IN, tenant_ids=source_tenants(job)) as (event, actor):
            require_job(job, actor)
            resource, created = BadgePrintResource.objects.get_or_create(job=job, registration_id=qr.registration_id,
                kind="logo", defaults={"object_key": f"events/badge-print/{event.makerspace_id}/{uuid4()}.png",
                    "source_key_sha256": key_digest, "sha256": digest,
                    "size_bytes": len(content), "expires_at": job.expires_at})
            if created:
                limits.add_storage(event.makerspace, len(content))
            record(actor, "event.badge_logo_reserved", makerspace=event.makerspace, target=resource)
        if resource.bound_at:
            continue
        print_storage.put(resource.object_key, content, "image/png")
        with event_command(job.event_id, actor=actor, permission=CHECK_IN, tenant_ids=source_tenants(job)) as (event, actor):
            require_job(job, actor)
            resource.bound_at = timezone.now()
            resource.save(update_fields=("bound_at",))
            record(actor, "event.badge_resource_bound", makerspace=event.makerspace, target=resource,
                   meta={"job_id": job.pk, "kind": "logo"})
