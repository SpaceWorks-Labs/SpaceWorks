"""Reserve â†’ prepare outside locks â†’ bind â†’ render â†’ reauthorize publication."""

from datetime import timedelta
import hashlib
import json
import logging
from uuid import uuid4

from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit.services import record
from apps.events import event_authority
from apps.events.credentials.boundary import event_command, require_version
from apps.events.credentials.crypto import unwrap
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.credentials.workflow import issue_locked, require_eligible, prepare_issue
from apps.events.event_permissions import CHECK_IN
from apps.events.models_registration import EventRegistration
from apps.events.profile_photos.models import EventMemberPresentation
from apps.events.profile_photos.policy import print_profile
from apps.events.profile_photos.snapshot import prepare_photo
from apps.makerspaces import limits

from .layer_rendering import ImageResource, QrResource
from .print_models import BadgePrintJob, BadgePrintResource, EventBadgeTemplateRevision
from .print_policy import require_job, fields_digest
from .print_snapshot import BadgeSnapshot
from .print_boundary import prepare_scope, print_command
from . import print_storage as storage

logger = logging.getLogger(__name__)


def create(event_id, *, actor, operation_id, expected_version, registration_ids,
           template_revision, stock, include_photo=False):
    event_authority.get_event(actor, event_id, CHECK_IN)
    if (not isinstance(registration_ids, list) or not 1 <= len(registration_ids) <= 200
            or any(type(pk) is not int or pk <= 0 for pk in registration_ids)
            or len(set(registration_ids)) != len(registration_ids)):
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"registration_ids": "Choose 1–200 unique registrations."})
    digest = hashlib.sha256(json.dumps([sorted(registration_ids), expected_version, template_revision,
                                       stock, include_photo]).encode()).hexdigest()
    scope = prepare_scope(event_id, registration_ids)
    credentials = {pk: prepare_issue(event_id, pk) for pk in registration_ids}
    with event_command(event_id, actor=actor, permission=CHECK_IN, account_ids=scope.account_ids,
            tenant_ids=scope.tenant_ids, revalidate=scope.revalidate) as (event, actor):
        previous = BadgePrintJob.objects.filter(event=event, operation_id=operation_id).first()
        if previous:
            if previous.request_sha256 != digest or previous.actor_id != actor.pk:
                raise ProgrammeConflict("Operation ID was already used.", code="operation_conflict")
            return previous
        require_version(event, expected_version)
        revision = EventBadgeTemplateRevision.objects.filter(pk=template_revision, event=event, stock=stock).first()
        if not revision:
            raise NotFound()
        rows = list(EventRegistration.objects.select_for_update().filter(event=event, pk__in=registration_ids).order_by("pk"))
        if len(rows) != len(registration_ids):
            raise NotFound()
        eligible, failures = [], []
        manager = event_authority.can_manage_grants(actor, event)
        for row in rows:
            scope.registrations.bind(row)
            try:
                require_eligible(event, row)
                if not manager and row.status != "attended":
                    raise NotFound()
                eligible.append(row)
            except NotFound:
                failures.append({"registration_id": row.pk, "error_code": "registration_ineligible"})
        if not eligible:
            raise ProgrammeConflict("No selected registrations are eligible for printing.", code="print_ineligible")
        job = BadgePrintJob.objects.create(event=event, actor=actor, operation_id=operation_id,
                request_sha256=digest, template=revision.document, template_revision=revision,
                event_version=event.version, fields_sha256=fields_digest(event, eligible), row_failures=failures,
                stock=stock, include_photo=include_photo, registration_ids=[row.pk for row in eligible],
                object_key=f"events/badge-print/{event.makerspace_id}/{uuid4()}.pdf",
                expires_at=timezone.now()+timedelta(hours=24))
        for row in eligible:
            row.event = event
            credential = issue_locked(event, row, actor=actor, prepared=credentials[row.pk])
            BadgePrintResource.objects.create(job=job, registration=row, kind="qr", credential=credential,
                                              credential_generation=credential.generation, expires_at=job.expires_at,
                                              bound_at=timezone.now())
        record(actor, "event.badge_print_requested", makerspace=event.makerspace, target=job,
               meta={"count": len(eligible), "failed_count": len(failures), "stock": stock, "include_photo": include_photo})
        return job


def prepare_resources(job, *, actor):
    from .print_logo import prepare_logo
    require_job(job, actor)
    prepare_logo(job, actor)
    prepared = []
    if job.include_photo:
        for qr in job.resources.filter(kind="qr").select_related("registration"):
            presentation = EventMemberPresentation.objects.filter(event=job.event, member_id=qr.registration.member_id).first()
            profile = print_profile(presentation)
            if profile:
                # Exact avatar and consent versions are captured before any DB locks.
                prepared.append((qr.registration_id, presentation.pk, presentation.version,
                                 profile.membership.makerspace_id, prepare_photo(profile)))
    for registration_id, presentation_id, version, source_tenant, photo in prepared:
        # Persist ownership BEFORE network I/O so a failed upload remains cleanup-owned.
        with print_command(job, actor=actor) as (event, actor, scope):
            require_job(job, actor, prepared_scope=scope)
            require_prepared_photo(job, registration_id, presentation_id, version, photo)
            resource, created = BadgePrintResource.objects.get_or_create(job=job, registration_id=registration_id,
                kind="photo", defaults=dict(presentation_id=presentation_id, presentation_version=version,
                    source_profile_id=photo.profile_id, source_avatar_revision=photo.source_revision,
                    source_key_sha256=photo.source_key_digest, object_key=f"events/badge-print/{event.makerspace_id}/{uuid4()}.png",
                    sha256=photo.sha256, size_bytes=len(photo.pixels), expires_at=job.expires_at))
            if created:
                limits.add_storage(event.makerspace, len(photo.pixels))
            if resource.sha256 != photo.sha256 or resource.presentation_version != version:
                raise ProgrammeConflict("Prepared photo differs from its reservation.", code="photo_source_changed")
            require_job(job, actor, prepared_scope=scope)
        if resource.bound_at:
            continue
        storage.put(resource.object_key, photo.pixels, "image/png")
        with print_command(job, actor=actor) as (_event, actor, scope):
            require_job(job, actor, prepared_scope=scope)
            require_prepared_photo(job, registration_id, presentation_id, version, photo)
            resource = BadgePrintResource.objects.select_for_update().get(pk=resource.pk)
            if resource.bound_at:
                continue
            resource.bound_at = timezone.now()
            resource.save(update_fields=("bound_at",))
            record(actor, "event.badge_resource_bound", makerspace=job.event.makerspace, target=resource,
                   meta={"job_id": job.pk, "kind": "photo"})


def require_prepared_photo(job, registration_id, presentation_id, version, photo):
    member_id = EventRegistration.objects.values_list("member_id", flat=True).get(pk=registration_id, event_id=job.event_id)
    presentation = EventMemberPresentation.objects.filter(pk=presentation_id, event_id=job.event_id, member_id=member_id).first()
    profile = print_profile(presentation)
    if (not profile or presentation.version != version or profile.pk != photo.profile_id
            or profile.membership_id != photo.membership_id
            or profile.updated_at.isoformat().replace("+00:00", "Z") != photo.source_revision
            or hashlib.sha256(profile.avatar_key.encode()).hexdigest() != photo.source_key_digest):
        raise ProgrammeConflict("Photo source or consent changed.", code="photo_source_changed")


def snapshots(job):
    result = []
    for qr in job.resources.filter(kind="qr").select_related("registration"):
        registration = qr.registration
        photo = job.resources.filter(kind="photo", registration=registration, bound_at__isnull=False).first()
        logo = job.resources.filter(kind="logo", registration=registration, bound_at__isnull=False).first()
        result.append(BadgeSnapshot(registration_id=registration.pk, event_id=job.event_id,
            member_id=registration.member_id, authorized_fields=(("name", registration.name),
                ("event", job.event.title), ("eventDate", job.event.starts_at.strftime("%d %B %Y")),
                ("organisation", job.event.makerspace.name), ("issueDate", job.created_at.strftime("%d %B %Y"))), template_revision=str(job.template_revision_id),
            stock=job.stock, logo_artwork_revision=str(logo.pk) if logo else None, credential_generation=qr.credential_generation,
            credential_render_handle=qr.pk, presentation_id=photo.presentation_id if photo else None,
            presentation_version=photo.presentation_version if photo else None,
            source_profile_id=photo.source_profile_id if photo else None,
            source_avatar_revision=photo.source_avatar_revision if photo else None,
            photo_sha256=photo.sha256 if photo else None, photo_render_handle=photo.pk if photo else None,
            created_at=job.created_at, expires_at=job.expires_at))
    return tuple(result)


def render(job, *, actor):
    from apps.events.badge_rendering import render_credential_badges_pdf
    from .print_claims import claim, finish, fail, reserve_pdf
    job = claim(job, actor)
    if job.state == "ready":
        require_job(job, actor)
        return job
    try:
        prepare_resources(job, actor=actor)
        require_job(job, actor)
        def resolve(handle):
            resource = job.resources.get(pk=handle)
            if resource.kind == "qr":
                return QrResource(unwrap(resource.credential, job.event_id))
            return ImageResource(storage.read(resource.object_key, resource.sha256), resource.sha256)
        payload = render_credential_badges_pdf(job.template, snapshots(job), resolver=resolve)
        reserve_pdf(job, actor, len(payload), hashlib.sha256(payload).hexdigest())
        size, digest = storage.put(job.object_key, payload, "application/pdf")
        return finish(job, actor, size, digest)
    except Exception:
        try:
            fail(job)
        except Exception:
            logger.warning("event_badge_print_failure_deferred", extra={"job_id": job.pk})
        raise


def download(job, *, actor):
    require_job(job, actor)
    if job.state != "ready":
        raise ProgrammeConflict("This print job is not ready.", code="print_not_ready")
    content = storage.read(job.object_key, job.sha256)
    # Recheck after object I/O and immediately before HTTP releases these bounded bytes.
    job.refresh_from_db()
    require_job(job, actor)
    record(actor, "event.badge_print_downloaded", makerspace=job.event.makerspace, target=job)
    return content
