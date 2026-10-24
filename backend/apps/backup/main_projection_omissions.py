"""Deployment-local operational rows never become restored source authority."""
OMITTED_OPERATIONAL_MODELS = frozenset({
    "backup.DeploymentDatabaseIdentity", "sessions.Session",
    "integrations.NotificationMediaGrant",
    "events.EventProgrammeSweepCursor",
    'backup.ManagedDeploymentState', 'backup.ManagedCaptureState', 'backup.ManagedWriterBoundary',
    'backup.ManagedStagedObject',
    'backup.ManagedPresignLease',
    'operations.CloudObjectAccount',
    'operations.CloudObjectReservation',

    'operations.CloudTaskState', 'operations.CloudTickRun', 'operations.CloudTickRateWindow',
    'operations.CloudUsageSample', 'operations.CloudObjectUsageReceipt',
    'integrations.EmailProviderWebhookReceipt',
})

