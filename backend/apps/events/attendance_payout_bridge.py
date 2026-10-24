"""Lane G attendance bridge: revision, correction watermark and payout eligibility.

Called by the canonical attended/correction transitions while their event and
registration locks are held. Every attended transition bumps the registration's
attendance_revision; a correction also appends an immutable EventAttendanceCorrection
whose watermark retires every earlier check-in as reimbursement venue evidence. When the
reimbursement add-on is live, each affected claim's core payout eligibility is then
republished synchronously, taking the domain parents (programme, pool, request, award,
claim) before the core obligation, the same order the add-on's own commands use.
"""


def attended_locked(registration):
    registration.attendance_revision += 1
    return ["attendance_revision"]


def corrected_locked(*, event, registration, actor):
    """Run after the registration's corrected status and revision are saved."""
    from .models import EventAttendanceCorrection, EventCheckInEvent
    latest = EventCheckInEvent.objects.filter(registration=registration, event=event).order_by("-pk").first()
    if latest is None:
        return None
    return EventAttendanceCorrection.objects.create(registration=registration, event=event,
        attendance_revision=registration.attendance_revision, invalidated_through_checkin_id=latest.pk, actor=actor)


def publish_payout_eligibility_locked(*, event, registration, actor):
    from apps.separability.registry import runtime_active
    if not runtime_active("event_reimbursements"):
        return
    from apps.makerspaces.platform import module_enabled
    if not module_enabled(event.makerspace, "event_reimbursements"):
        return
    from django.db.models import Q
    from apps.event_reimbursements.models import ReimbursementClaim, ReimbursementProgramme
    if not ReimbursementProgramme.objects.filter(event=event).exists():
        return
    claims = ReimbursementClaim.objects.filter(event=event).filter(
        Q(award__request__registration=registration) | Q(award__request__application__registration=registration)
    ).order_by("pk").values_list("pk", flat=True)
    from apps.event_reimbursements.claim_workflow import lock_claim_parents
    from apps.event_reimbursements.payout_preflight import publish_claim_locked
    for claim_id in list(claims):
        programme, _pool, _award, claim = lock_claim_parents(event, claim_id=claim_id)
        if claim is not None:
            publish_claim_locked(claim=claim, programme=programme, actor=actor)
