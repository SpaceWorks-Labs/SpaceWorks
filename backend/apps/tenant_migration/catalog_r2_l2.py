"""Release-2 lane L2: tenant-dump field snapshot, authority and projections.

Every new L2 model is DROPPED (data_export `classification_r2_l2.OMITTED_MODELS` gives
the reason). New columns on travelling rows:

* `EventBroadcast.undo_hold` -- a historical send mode; an in-flight hold never travels
  because the campaign projection already cancels unsent campaigns.
* `EventFeedbackSurvey.anonymous` -- the form's promise to respondents; it travels.
* `NotificationInboxRow.snoozed_until/archived_on` -- the whole row is dropped already.
* `HostingRequest.changes_note/changes_requested_at` -- platform rows, dropped already.
"""

FIELD_NAMES = {
    "events.SubmissionIntegrityCheck": frozenset(
        "id snapshot event makerspace state attempts next_attempt_at checked_at".split()),
    "events.SubmissionStorageCleanupReceipt": frozenset(
        "id makerspace_id_snapshot event_id_snapshot asset_uuid key_sha256 versions_deleted markers_deleted "
        "uploads_aborted verified_absent_at".split()),
    "events.MentorAlertRoute": frozenset("id event makerspace destination created_by created_at".split()),
    "notifications.BrowserAlertSubscription": frozenset(
        "id makerspace user endpoint endpoint_sha256 p256dh auth_secret created_at last_sent_at failures "
        "revoked_at".split()),
    "notifications.NotificationEscalation": frozenset(
        "id makerspace event_key feature event escalated_at rooms_posted".split()),
    "integrations.OrganizationEmailSender": frozenset(
        "id organization sender_name reply_to updated_by updated_at".split()),
    "hosting_requests.HostingRequestRevision": frozenset(
        "id request kind note changed_fields actor created_at".split()),
}
EXTRA_FIELDS = {
    "events.EventBroadcast": frozenset({"undo_hold"}),
    "events.EventFeedbackSurvey": frozenset({"anonymous"}),
    "notifications.NotificationInboxRow": frozenset({"snoozed_until", "archived_on"}),
    "hosting_requests.HostingRequest": frozenset({"changes_note", "changes_requested_at"}),
    "organizations.OrganizationInvitation": frozenset({"invitee_email_digest"}),
}


def authority_entries(authority, disposition):
    def same(label, names, chosen, reason):
        return tuple(((label, name), authority(chosen, reason)) for name in names.split())

    return (
        *same("events.EventBroadcast", "undo_hold", disposition.PRESERVE,
              "Historical send mode; unsent campaigns are cancelled by the broadcast projection."),
        *same("events.EventFeedbackSurvey", "anonymous", disposition.PRESERVE,
              "The form's anonymity promise to respondents travels with the form."),
        *same("notifications.NotificationInboxRow", "snoozed_until archived_on", disposition.DROP,
              "Personal inbox state is omitted from portable artifacts."),
    )
