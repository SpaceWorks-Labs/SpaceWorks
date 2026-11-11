"""r2-superadmin-controls (#185, #187A): literal export classification.

Every new model is platform governance or the platform's own billing, so none is part of a
space's own data copy and none travels in a tenant dump:

* `space_controls.SpaceControlState` -- why/since when a space is paused or read-only and its
  scheduled archive/purge; a target deployment's operator decides its own controls.
* `space_controls.PlatformAnnouncement` / `PlatformAnnouncementTarget` -- platform messages.
* `managed_hosting.*` -- the platform operator's plan tiers, a space's plan, and the
  platform's hosting invoices, receipts and provider settings (secrets as ciphertext).

New column on an omitted model: `hosting_requests.HostingRequest.expected_members`.
"""

OMITTED_MODELS = {
    "space_controls.SpaceControlState": "Platform governance of a hosted space (pause, read-only, schedule).",
    "space_controls.PlatformAnnouncement": "A platform operator's announcement; not tenant data.",
    "space_controls.PlatformAnnouncementTarget": "Which spaces a platform announcement targets.",
    "managed_hosting.HostingPlan": "The platform operator's hosting plan tiers.",
    "managed_hosting.SpacePlanAssignment": "The platform's plan for a hosted space; re-chosen on any target.",
    "managed_hosting.HostingInvoice": "The platform's own invoice to a hosted space; platform finance records.",
    "managed_hosting.HostingInvoiceReceipt": "Append-only receipt of a platform hosting invoice.",
    "managed_hosting.PlatformHostingBillingSettings": "Platform billing switches and encrypted provider keys.",
    "managed_hosting.PlatformThrottleRate": "A superadmin override of a deployment-wide request rate; platform level.",
    "managed_hosting.SpaceHostingType": "Decision 236: the platform's own-vs-hosted choice for a space; re-chosen on any target.",
}
RELATIONAL_USER_FIELDS = frozenset({
    ("space_controls.SpaceControlState", "suspended_by"),
    ("space_controls.SpaceControlState", "read_only_by"),
    ("space_controls.SpaceControlState", "scheduled_by"),
    ("space_controls.PlatformAnnouncement", "created_by"),
    ("space_controls.PlatformAnnouncement", "cancelled_by"),
    ("managed_hosting.HostingPlan", "created_by"),
    ("managed_hosting.SpacePlanAssignment", "assigned_by"),
    ("managed_hosting.HostingInvoice", "created_by"),
    ("managed_hosting.HostingInvoiceReceipt", "recorded_by"),
    ("managed_hosting.PlatformHostingBillingSettings", "updated_by"),
    ("managed_hosting.PlatformThrottleRate", "updated_by"),
    ("managed_hosting.SpaceHostingType", "updated_by"),
})
