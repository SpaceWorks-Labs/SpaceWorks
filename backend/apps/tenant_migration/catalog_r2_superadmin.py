"""r2-superadmin-controls (#185, #187A): tenant-dump field snapshot.

Every new model is OMITTED (data_export ``classification_r2_superadmin`` gives each reason);
``HostingRequest.expected_members`` is a new column on a row that is dropped already.
"""

FIELD_NAMES = {
    "space_controls.SpaceControlState": frozenset(
        "id makerspace suspended_at suspension_reason suspended_by read_only_at read_only_reason read_only_source "
        "read_only_by archive_on purge_due_at purge_grace_days schedule_note scheduled_by scheduled_at "
        "reminders_sent updated_at".split()),
    "space_controls.PlatformAnnouncement": frozenset(
        "id title body severity audience starts_at ends_at send_email show_to_members email_sent_at "
        "email_recipient_count cancelled_at cancelled_by created_by created_at".split()),
    "space_controls.PlatformAnnouncementTarget": frozenset("id announcement makerspace".split()),
    "managed_hosting.HostingPlan": frozenset(
        "id key name description is_active trial_days price_minor currency billing_period limits allowed_modules "
        "created_by created_at updated_at".split()),
    "managed_hosting.SpacePlanAssignment": frozenset(
        "id makerspace plan assigned_by assigned_at trial_ends_at trial_expired_at reminders_sent".split()),
    "managed_hosting.HostingInvoice": frozenset(
        "id number makerspace makerspace_id_snapshot makerspace_name plan description amount_minor currency "
        "period_start period_end due_on status paid_at voided_at void_reason provider provider_session_id "
        "created_by created_at".split()),
    "managed_hosting.HostingInvoiceReceipt": frozenset(
        "id invoice method reference received_on amount_minor note recorded_by recorded_at".split()),
    "managed_hosting.PlatformHostingBillingSettings": frozenset(
        "id auto_enforce_enabled grace_days provider stripe_secret_key stripe_webhook_secret razorpay_key_id "
        "razorpay_key_secret razorpay_webhook_secret updated_by updated_at".split()),
}
EXTRA_FIELDS = {
    "hosting_requests.HostingRequest": frozenset({"expected_members"}),
}
