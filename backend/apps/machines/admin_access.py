"""/control/ "Machines": machine access grants and the retired certification history, all read-only.

Grants are written only through `access_grants_services` (authority, validation, audit, notice).
Certification, guest-certification and induction records are kept as history (decision 319): visible
here, never editable.
"""
from django.contrib import admin

from apps.machines.models import (
    CertificationGrant, CertificationType, EventInductionLink, GuestCertificationGrant, MachineAccessGrant,
)
from config.admin_records import ControlRecordAdmin


@admin.register(MachineAccessGrant)
class MachineAccessGrantAdmin(ControlRecordAdmin):
    makerspace_lookup = "makerspace_id"
    ordering = ("-granted_at",)


class _HistoryAdmin(ControlRecordAdmin):
    makerspace_lookup = "makerspace_id"
    ordering = ("-id",)


@admin.register(CertificationType)
class CertificationTypeAdmin(_HistoryAdmin):
    """Read-only history."""


@admin.register(CertificationGrant)
class CertificationGrantAdmin(_HistoryAdmin):
    makerspace_lookup = "certification_type__makerspace_id"


@admin.register(GuestCertificationGrant)
class GuestCertificationGrantAdmin(_HistoryAdmin):
    """Read-only history."""


@admin.register(EventInductionLink)
class EventInductionLinkAdmin(_HistoryAdmin):
    """Read-only history."""
