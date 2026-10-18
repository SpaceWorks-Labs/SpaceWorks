import hashlib
import json

from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.events import event_authority
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.credentials.workflow import current, require_eligible
from apps.events.event_permissions import CHECK_IN
from apps.events.models_registration import EventRegistration
from apps.events.profile_photos.models import EventMemberPresentation
from apps.events.profile_photos.policy import print_profile
from apps.events.profile_photos.selection_workflow import source_revision


def source_tenants(job):
    from apps.makerspaces.models_profiles import MemberProfile
    return tuple(MemberProfile.objects.filter(pk__in=job.resources.filter(kind="photo").values("source_profile_id"))
                 .order_by("membership__makerspace_id").values_list("membership__makerspace_id", flat=True).distinct())


def fields_digest(event, rows):
    return hashlib.sha256(json.dumps([event.title, event.starts_at.isoformat(), event.makerspace.name,
                                     [[row.pk, row.name, row.member_id] for row in rows]],
                                    sort_keys=True).encode()).hexdigest()


def require_job(job, actor, *, prepared_scope=None):
    from apps.events.models_event import Event
    job.event = Event.objects.select_related("makerspace").get(pk=job.event_id)
    event_authority.require(actor, job.event, CHECK_IN)
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(job.event.makerspace_id)
    from .print_models import BadgePrintJob
    current_job = BadgePrintJob.objects.only("state", "expires_at").get(pk=job.pk)
    if min(job.expires_at, current_job.expires_at) <= timezone.now() or "cancelled" in (job.state, current_job.state):
        raise NotFound()
    if job.event.status not in ("published", "completed"):
        raise NotFound()
    rows = list(EventRegistration.objects.filter(event=job.event, pk__in=job.registration_ids).order_by("pk"))
    if prepared_scope is not None:
        for row in rows:
            prepared_scope.bind(row)
    if job.fields_sha256 != fields_digest(job.event, rows):
        raise ProgrammeConflict("Badge text changed. Prepare a new print job.", code="print_snapshot_changed")
    manager = event_authority.can_manage_grants(actor, job.event)
    for resource in job.resources.select_related("registration"):
        registration = resource.registration
        if prepared_scope is not None:
            prepared_scope.bind(registration)
        registration.event = job.event
        require_eligible(job.event, registration)
        if not manager and registration.status != "attended":
            raise NotFound()
        if resource.kind == "qr":
            credential = current(registration)
            if not credential or credential.pk != resource.credential_id:
                raise ProgrammeConflict("This badge was replaced.", code="credential_changed")
        elif resource.kind == "photo":
            presentation = EventMemberPresentation.objects.filter(pk=resource.presentation_id).first()
            profile = print_profile(presentation)
            if (not presentation or not profile or presentation.version != resource.presentation_version
                    or profile.pk != resource.source_profile_id
                    or source_revision(profile) != resource.source_avatar_revision
                    or hashlib.sha256(profile.avatar_key.encode()).hexdigest() != resource.source_key_sha256):
                raise ProgrammeConflict("The photo choice or consent changed.", code="photo_consent_changed")
        elif resource.kind == "logo":
            if hashlib.sha256(job.event.makerspace.logo_key.encode()).hexdigest() != resource.source_key_sha256:
                raise ProgrammeConflict("The event logo changed. Prepare a new print job.", code="print_snapshot_changed")


def invalidate_profile(profile_id):
    """G may call after avatar/visibility/removal writes. Live checks also deny immediately."""
    from .print_models import BadgePrintJob
    return BadgePrintJob.objects.filter(resources__source_profile_id=profile_id).exclude(
        state="cancelled").values_list("pk", flat=True).distinct()
