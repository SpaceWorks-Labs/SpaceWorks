"""Canonical venue evidence after the latest correction watermark."""
from apps.events.models import EventCheckInEvent, EventAttendanceCorrection
from apps.payments.event_payouts.errors import require


def canonical_scans(scans, *, registration, makerspace_id):
    """Keep recorded ingestion provenance without depending on today's staff role.

    Later grant revocation must not erase a real historical venue scan. Matching
    append-only ingestion audit proves the actor/station/session which produced it.
    """
    from apps.audit.models import AuditLog
    records = AuditLog.objects.filter(makerspace_id=makerspace_id, action="event.registration_attended",
        target_id=str(registration.pk), meta__check_in_event_id__in=[scan.pk for scan in scans])
    audits = {row.meta["check_in_event_id"]: row for row in records}
    return [scan for scan in scans if scan.pk in audits and audits[scan.pk].actor_id == scan.actor_id
        and audits[scan.pk].meta.get("source") == scan.source
        and audits[scan.pk].meta.get("operation_id") == str(scan.operation_id)
        and audits[scan.pk].meta.get("station_version") == scan.station_version
        and audits[scan.pk].meta.get("session_id") == (str(scan.session_id) if scan.session_id else None)]


def current_registration(grant):
    return grant.registration or (grant.application.registration if grant.application_id else None)


def participating(grant):
    registration = current_registration(grant)
    return bool(registration is not None and registration.status in ("registered", "attended") and
        (grant.application_id is None or grant.application.state == "confirmed"))


def evidence(*, claim, programme, enforce=True):
    from .accepted_policy import attendance_required
    required = attendance_required(claim.award, programme)
    registration = current_registration(claim.award.request)
    require(registration is not None and registration.event_id == claim.event_id
            and registration.member_id == claim.member_id, "attendance_required")
    marker = EventAttendanceCorrection.objects.filter(registration=registration).order_by("-attendance_revision").first()
    watermark = marker.invalidated_through_checkin_id if marker else 0
    sources = claim.award.calculation_snapshot.get("permitted_venue_sources", programme.permitted_venue_sources) or (
        "qr", "venue_station", "offline_sync")
    scans = list(EventCheckInEvent.objects.filter(registration=registration, event=claim.event,
        makerspace_id=claim.event.makerspace_id, id__gt=watermark,
        source__in=sources, attended_at__gte=claim.event.starts_at,
        attended_at__lte=claim.event.ends_at).order_by("pk"))
    scans = [scan for scan in scans if (scan.source == "venue_station" and scan.station_version is not None
        or scan.source in ("qr", "offline_sync") and scan.actor_id is not None)]
    scans = canonical_scans(scans, registration=registration, makerspace_id=claim.event.makerspace_id)
    # Canonical ingestion authenticated actor/station at recording time; a remote
    # or unconfigured location alone does not become physical venue evidence.
    if claim.event.location_kind not in ("indoor", "outdoor"):
        scans = []
    attestation = claim.attestations.filter(registration=registration, event_id=claim.event_id,
        owner_member_id=claim.member_id, attended_at__gte=claim.event.starts_at, attended_at__lte=claim.event.ends_at,
        attendance_revision=registration.attendance_revision).order_by("-pk").first()
    eligible = registration.status == "attended" and bool(scans or attestation)
    if required and enforce:
        require(eligible, "attendance_required")
    return {"eligible": eligible or not required,
        "registration_id": registration.pk, "attendance_revision": registration.attendance_revision,
        "invalidated_through_checkin_id": watermark, "checkin_ids": [scan.pk for scan in scans],
        "attestation_uuid": str(attestation.uuid) if attestation else None,
        "attendance_required": required}
