"""Certification RECORDS only -- decision 319 retired certifications as a gate and as a feature.

Machine use is decided by `apps.machines.access_grants.can_use`; nothing here gates anything any more.
What remains is the read-only history of certification grants (data export, /control/), the conversion
source for migration 0040, and the helpers the retired induction/report code still reads.
"""

from django.db.models import Q
from django.utils import timezone

from apps.machines.models import CertificationGrant, CertificationType

FEATURE_KEY = "machines.certifications"
PURPOSE_SERVICE = "service"
PURPOSE_BOOKING = "booking"
PURPOSES = (PURPOSE_SERVICE, PURPOSE_BOOKING)


def active_grant(membership, certification_type, now=None):
    """The membership's live grant for this type, or None.

    "Live" is unrevoked AND unexpired at ``now``; expiry is read from the grant's stored
    ``expires_at`` rather than recomputed from the type's current ``validity_days``, so
    tightening the policy cannot retroactively invalidate correctly-issued training.
    """
    if membership is None or certification_type is None:
        return None
    moment = now or timezone.now()
    return (
        CertificationGrant.objects.filter(
            membership=membership,
            certification_type=certification_type,
            revoked_at__isnull=True,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=moment))
        .order_by("-granted_at", "-pk")
        .first()
    )


def live_certification_names(membership, now=None):
    """Retired (decision 319 addendum): certifications are no longer shown on profiles or cards.

    The records are kept as history; this returns nothing so no surface advertises a retired feature."""
    return ()


def required_types(makerspace, machine_type, *, for_service=False, for_booking=False):
    """Active certification types for this machine type, narrowed by purpose.

    With neither flag this is the plain listing of active types (what the staff console
    reads); the gate always passes exactly one, so it never over-gates.
    """
    queryset = CertificationType.objects.filter(
        makerspace=makerspace, machine_type=machine_type, is_active=True
    ).order_by("name", "pk")
    if not (for_service or for_booking):
        return queryset
    flags = Q()
    if for_service:
        flags |= Q(is_required_for_service=True)
    if for_booking:
        flags |= Q(is_required_for_booking=True)
    return queryset.filter(flags)
