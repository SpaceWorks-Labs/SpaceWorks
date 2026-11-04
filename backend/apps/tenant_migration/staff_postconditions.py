"""Independent checks of carried staff roles on import targets (one account per person).

Staff roles are staff-track memberships on people. After an import every live staff-track
row of the target space must belong to a live person and hold one of the target's own
built-in staff roles, and nothing that is a session, a device or an invitation -- device
grants, staff invitations, chat endpoints -- may have travelled with the space.
"""

from django.apps import apps
from django.db.models import Q

from apps.accounts.staff_identity import person_q

from .tenant_dump_errors import TenantDumpVerificationError


def verify_staff_transport(using, makerspace_id, *, exclusive=False):
    Membership = apps.get_model("makerspaces.MakerspaceMembership")
    rows = Membership.all_tracks.using(using).filter(track="staff")
    if not exclusive:
        rows = rows.filter(makerspace_id=makerspace_id)
    live_person = person_q("user__") & Q(user__merged_into__isnull=True, user__retired_at__isnull=True)
    if rows.exclude(status="revoked").exclude(live_person & Q(makerspace_id=makerspace_id)).exists():
        raise TenantDumpVerificationError("An imported staff role belongs to something other than a live person.")
    if rows.exclude(assigned_role__makerspace_id=makerspace_id, assigned_role__is_protected=True,
                    assigned_role__is_default=True).exists() or rows.filter(assigned_role__slug="member").exists():
        raise TenantDumpVerificationError("Imported staff lost their tenant role binding.")
    for label, scope in (
        ("accounts.DeviceGrant", "staff_makerspace_id"),
        ("accounts.StaffInvitation", "makerspace_id"),
        ("integrations.NotificationEndpoint", "makerspace_id"),
    ):
        if apps.get_model(label)._base_manager.using(using).filter(**{scope: makerspace_id}).exists():
            raise TenantDumpVerificationError("A source session, device or invitation survived tenant import.")
