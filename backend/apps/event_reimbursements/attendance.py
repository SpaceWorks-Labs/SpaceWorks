"""Canonical venue evidence after the latest correction watermark."""
from apps.events.models import EventCheckInEvent, EventAttendanceCorrection
from apps.payments.event_payouts.errors import require


def evidence(*, claim, programme):
    registration = claim.award.request.registration
    require(registration is not None and registration.event_id == claim.event_id
            and registration.member_id == claim.member_id, "attendance_required")
    marker = EventAttendanceCorrection.objects.filter(registration=registration).order_by("-attendance_revision").first()
    watermark = marker.invalidated_through_checkin_id if marker else 0
    scans = list(EventCheckInEvent.objects.filter(registration=registration, event=claim.event,
        makerspace_id=claim.event.makerspace_id, id__gt=watermark,
        source__in=("qr", "venue_station", "offline_sync"), attended_at__gte=claim.event.starts_at,
        attended_at__lte=claim.event.ends_at).order_by("pk"))
    scans = [scan for scan in scans if (scan.source == "venue_station" and scan.station_version is not None
        or scan.source in ("qr", "offline_sync") and scan.actor_id is not None)]
    attestation = claim.attestations.filter(registration=registration,
        attendance_revision=registration.attendance_revision).order_by("-pk").first()
    eligible = registration.status == "attended" and bool(scans or attestation)
    if programme.attendance_required:
        require(eligible, "attendance_required")
    return {"eligible": eligible or not programme.attendance_required,
        "registration_id": registration.pk, "attendance_revision": registration.attendance_revision,
        "invalidated_through_checkin_id": watermark, "checkin_ids": [scan.pk for scan in scans],
        "attestation_uuid": str(attestation.uuid) if attestation else None,
        "attendance_required": programme.attendance_required}
