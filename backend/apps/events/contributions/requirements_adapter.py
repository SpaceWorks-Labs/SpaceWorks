"""Live typed training/briefing evidence; exceptional overrides never waive consent."""
from django.utils.translation import gettext
from django.db.models import Q
from django.shortcuts import get_object_or_404
from apps.events.hackathons.admission_models import HackathonConfig
from .models_roles import EventRoleAssignment
from .models_shifts import EventShift
from .models_policy import EventContributorRequirementCompletion, EventRequirementOverride
from .errors import ProgrammeError


def require_requirements(*, actor_id, assignment_id, shift_id, override_ids=()):
    row = get_object_or_404(EventRoleAssignment, pk=assignment_id, member_id=actor_id)
    from apps.events.answer_derivations.subjects import require_member
    require_member(actor_id)
    config = HackathonConfig.objects.filter(event_id=row.event_id).first()
    if config and row.consent_revision != config.coc_revision:
        raise ProgrammeError("coc_required", gettext("Accept the current code of conduct."), status=400)
    required = dict(row.posting.requirements) if row.posting_id else {}
    if shift_id:
        shift = get_object_or_404(EventShift, pk=shift_id, event_id=row.event_id, posting_id=row.posting_id)
        for key, values in shift.requirements.items():
            required[key] = sorted(set(required.get(key, [])) | set(values)) if key.endswith("_ids") else (
                bool(required.get(key)) or values)
    overrides = set(EventRequirementOverride.objects.filter(pk__in=override_ids, assignment=row,
        event_id=row.event_id).filter(Q(shift__isnull=True) | Q(shift_id=shift_id)).values_list("kind", "reference_id"))
    from .commands import digest
    completed = set(EventContributorRequirementCompletion.objects.filter(event_id=row.event_id,
        member_id=actor_id, posting_id=row.posting_id,
        requirements_sha256=digest(row.posting.requirements if row.posting_id else {})).values_list("kind", "reference_id"))
    for kind, key in (("training", "training_ids"), ("briefing", "briefing_ids")):
        if any((kind, pk) not in completed | overrides for pk in required.get(key, [])):
            raise ProgrammeError("requirements_unmet", gettext("Complete the required training and briefing."), status=400)
    if required.get("host_waiver_required") or row.event.registration_audience == "participating_organizations":
        from apps.events.host_waivers import require_host_waiver
        require_host_waiver(row.event, row.member, registration=row, allow_consent=False)


def stamp_role_waiver(*, row, payload, actor):
    from django.utils import timezone
    from apps.audit.services import record
    from apps.events.host_waivers import require_host_waiver
    required = (row.posting_id and row.posting.requirements.get("host_waiver_required")) or (
        row.event.registration_audience == "participating_organizations")
    if not required:
        return
    waiver = require_host_waiver(row.event, row.member, actor=actor, registration=row,
        **{key: payload.get(key) for key in ("host_waiver_id", "host_waiver_version", "host_waiver_accepted")})
    if waiver:
        row.host_waiver, row.host_waiver_version_accepted = waiver, waiver.version
        row.host_waiver_accepted_at = timezone.now()
        row.save(update_fields=["host_waiver", "host_waiver_version_accepted", "host_waiver_accepted_at"])
        record(actor, "event.role.host_waiver_accepted", makerspace=row.event.makerspace, target=row,
            meta={"host_waiver_id": waiver.pk, "host_waiver_version": waiver.version})
