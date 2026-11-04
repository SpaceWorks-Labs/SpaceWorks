"""Host consent shared by public, collaborative and staff registration transactions."""

from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.audit import services as audit
from apps.makerspaces.models import MakerspaceMembership, MakerspaceWaiver
from apps.makerspaces.waiver_state import current_acceptance


class HostWaiverRequired(APIException):
    status_code = 400
    default_code = "host_waiver_required"

    def __init__(self):
        super().__init__({"code": self.default_code, "detail": "The participant must accept the current host waiver by self-registering.",
                          "host_waiver": "The current host waiver must be accepted."})


def has_current_host_consent(waiver, membership, registration):
    """Shared evidence predicate for transactional checks and batched advisories."""
    return bool(waiver is None or (membership and current_acceptance(membership, active_waiver=waiver))
                or (registration and registration.host_waiver_id == waiver.pk
                    and registration.host_waiver_version_accepted == waiver.version))


def require_host_waiver(event, member, *, actor=None, registration=None,
                        host_waiver_id=None, host_waiver_version=None, host_waiver_accepted=False, allow_consent=True):
    # Caller holds the host root, which serializes waiver publication.
    waiver = MakerspaceWaiver.objects.filter(makerspace_id=event.makerspace_id, is_active=True).first()
    if waiver is None:
        return None
    membership = MakerspaceMembership.objects.filter(
        makerspace_id=event.makerspace_id, user=member, status="active",
    ).first()
    if has_current_host_consent(waiver, membership, registration):
        return None
    if not (allow_consent and member and actor and actor.pk == member.pk and host_waiver_accepted is True
            and host_waiver_id == waiver.pk and host_waiver_version == waiver.version):
        raise HostWaiverRequired()
    return waiver


def stamp_host_waiver(registration, waiver, *, actor, via, event):
    if waiver is None or (registration.host_waiver_id == waiver.pk
                         and registration.host_waiver_version_accepted == waiver.version):
        return
    registration.host_waiver = waiver
    registration.host_waiver_accepted_at = timezone.now()
    registration.host_waiver_version_accepted = waiver.version
    registration.save(update_fields=["host_waiver", "host_waiver_accepted_at", "host_waiver_version_accepted"])
    audit.record(actor, "event.host_waiver_accepted", makerspace=event.makerspace, target=registration,
                 meta={"registration_id": registration.pk, "host_waiver_id": waiver.pk,
                       "host_waiver_version": waiver.version, "via_makerspace_id": via.pk})
