"""Independent checks of D11 account/credential separation on import targets."""

from django.apps import apps

from .tenant_dump_errors import TenantDumpVerificationError


def verify_staff_transport(using, makerspace_id, *, exclusive=False):
    User = apps.get_model("accounts.User")
    Membership = apps.get_model("makerspaces.MakerspaceMembership")
    staff = User._base_manager.using(using).filter(account_kind="staff")
    if not exclusive:
        staff = staff.filter(staff_makerspace_id=makerspace_id)
    for user in staff:
        if (user.staff_makerspace_id != makerspace_id or user.retired_at is not None
                or user.has_usable_password() or not user.must_change_password
                or user.is_superuser or user.is_staff or user.credential_generation != 0):
            raise TenantDumpVerificationError("Imported staff retained source identity authority.")
        memberships = Membership._base_manager.using(using).filter(user=user)
        if memberships.count() != 1 or not memberships.filter(
            makerspace_id=makerspace_id, assigned_role__is_protected=True,
            assigned_role__is_default=True,
            assigned_role__slug__in=("space_manager", "inventory_manager", "machine_manager",
                                    "event_manager", "booking_manager", "handover"),
        ).exists():
            raise TenantDumpVerificationError("Imported staff lost their tenant role binding.")
        for label, field in (
            ("accounts.UserMFA", "user"), ("accounts.DeviceGrant", "user"),
            ("accounts.StaffInvitation", "account"), ("integrations.NotificationEndpoint", "user"),
        ):
            if apps.get_model(label)._base_manager.using(using).filter(**{field: user}).exists():
                raise TenantDumpVerificationError("A source staff credential survived tenant import.")
