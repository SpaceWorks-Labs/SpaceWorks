"""Release-2 lane L2: literal export classification.

New L2 models are coordination, custody or delivery state, so none is part of a space's
own data copy and none travels in a tenant dump:

* `events.SubmissionIntegrityCheck` -- job state of the GitHub check; the informational
  flag itself is already classified with the submission snapshot.
* `events.SubmissionStorageCleanupReceipt` -- permanent, FK-free deployment custody proof.
* `events.MentorAlertRoute` -- which of the space's chat rooms receive mentor alerts;
  rooms are re-chosen on the target, like room destinations' credentials.
* `notifications.BrowserAlertSubscription` -- push-service endpoints and auth secrets
  are capabilities; the person opts in again on the target.
* `notifications.NotificationEscalation` -- delivery telemetry.
* `integrations.OrganizationEmailSender` -- organisation-global (organisations do not travel).
* `hosting_requests.HostingRequestRevision` -- platform coordination, like its request.

New columns on exported models: `EventBroadcast.undo_hold` and
`EventFeedbackSurvey.anonymous` are plain settings and export with their rows.
"""

OMITTED_MODELS = {
    "notifications.BrowserFirebaseInstallation": "Platform installation ownership fence; never portable.",
    "notifications.BrowserFirebaseRegistration": "Firebase registration is a delivery capability; opt in again on target.",
    "events.SubmissionIntegrityCheck": "Job state of the informational GitHub check; the flag row carries the result.",
    "events.SubmissionStorageCleanupReceipt": "Permanent FK-free deployment custody proof; never tenant data.",
    "events.MentorAlertRoute": "Chat-room routing for alerts; target staff choose rooms again.",
    "notifications.BrowserAlertSubscription": "Push endpoints and auth secrets are capabilities; people opt in again.",
    "notifications.NotificationEscalation": "Delivery telemetry; never portable.",
    "integrations.OrganizationEmailSender": "Organisation-global sender settings; organisations do not travel.",
    "hosting_requests.HostingRequestRevision": "Platform coordination history of a hosting request; no tenant.",
}
EXTRA_FIELDS = {
    "events.EventFeedbackSurvey": "anonymous",
    "events.EventBroadcast": "undo_hold",
}
RELATIONAL_USER_FIELDS = frozenset({
    ("notifications.BrowserFirebaseInstallation", "user"),
    ("notifications.BrowserFirebaseRegistration", "user"),
    ("events.MentorAlertRoute", "created_by"),
    ("notifications.BrowserAlertSubscription", "user"),
    ("integrations.OrganizationEmailSender", "updated_by"),
    ("hosting_requests.HostingRequestRevision", "actor"),
})
