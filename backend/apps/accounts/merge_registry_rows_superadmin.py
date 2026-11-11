"""Account-merge dispositions for r2-superadmin-controls (#185, #187A)."""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R

_MOVE = "Mutable ownership or attribution; moves to the survivor."

ROWS = (
    (R, "space_controls.SpaceControlState", "suspended_by read_only_by scheduled_by", _MOVE),
    (R, "space_controls.PlatformAnnouncement", "created_by cancelled_by", _MOVE),
    (R, "managed_hosting.HostingPlan", "created_by", _MOVE),
    (R, "managed_hosting.SpacePlanAssignment", "assigned_by", _MOVE),
    (R, "managed_hosting.HostingInvoice", "created_by", _MOVE),
    (R, "managed_hosting.PlatformHostingBillingSettings", "updated_by", _MOVE),
    (R, "managed_hosting.PlatformThrottleRate", "updated_by", _MOVE),
    (R, "managed_hosting.SpaceHostingType", "updated_by", _MOVE),
    (K, "managed_hosting.HostingInvoiceReceipt", "recorded_by",
     "Append-only payment receipt; actor_ids_for follows the alias."),
)
