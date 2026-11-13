"""Revoke station credentials when data comes back from a backup (#77 C#6; release 2 L11).

A restored ``StationCredential`` would bring back a station URL and PIN digest that may
have been rotated, disabled or leaked since the restore point. So a deployment restore
(entering quarantine) revokes EVERY station credential, and a per-space restore revokes
that space's: each is disabled, gets a new public token (the old station URL stops
resolving) and loses its operator leases. Staff re-issue the station URL and PIN
afterwards (rotate in the kiosk settings). The station rows themselves are kept.
"""
import uuid

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit


@transaction.atomic
def revoke_station_credentials(*, makerspace=None, actor=None, now=None):
    from apps.makerspaces.models_station_leases import StationOperatorLease
    from apps.makerspaces.models_stations import StationCredential

    now = now or timezone.now()
    credentials = StationCredential.objects.select_for_update()
    if makerspace is not None:
        credentials = credentials.filter(station__makerspace=makerspace)
    revoked = 0
    for credential in credentials.order_by("pk"):
        StationCredential.objects.filter(pk=credential.pk).update(
            is_enabled=False, disabled_at=now, public_token=uuid.uuid4(), updated_at=now)
        revoked += 1
    leases = StationOperatorLease.objects.filter(revoked_at__isnull=True)
    if makerspace is not None:
        leases = leases.filter(station__makerspace=makerspace)
    leases.update(revoked_at=now)
    audit.record(actor, "station_credentials.revoked_on_restore", makerspace=makerspace,
                 meta={"scope": "makerspace" if makerspace is not None else "deployment", "revoked": revoked})
    return revoked
