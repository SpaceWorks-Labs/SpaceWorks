"""Export, backup and source-gate limits."""

from config.settings_runtime import ImproperlyConfigured, env
from config.settings_storage import EVIDENCE_URL_TTL_SECONDS, PUBLIC_IMAGE_URL_TTL_SECONDS

# A bounded repeatable-read snapshot is part of the export's correctness contract.
# Operators may tune the bound, but disabling it would pin PostgreSQL vacuum forever.
DATA_EXPORT_DEADLINE_SECONDS = env.int("DATA_EXPORT_DEADLINE_SECONDS", default=900)
DATA_EXPORT_PAGE_SIZE = env.int("DATA_EXPORT_PAGE_SIZE", default=500)
DATA_EXPORT_RETENTION_SECONDS = env.int(
    "DATA_EXPORT_RETENTION_SECONDS", default=7 * 24 * 60 * 60
)
DATA_EXPORT_DOWNLOAD_TTL_SECONDS = env.int(
    "DATA_EXPORT_DOWNLOAD_TTL_SECONDS", default=5 * 60
)
TENANT_MIGRATION_GATE_LEASE_SECONDS = env.int(
    "TENANT_MIGRATION_GATE_LEASE_SECONDS", default=2 * 60 * 60
)
TENANT_MIGRATION_PRESIGN_DRAIN_SECONDS = env.int(
    "TENANT_MIGRATION_PRESIGN_DRAIN_SECONDS",
    default=max(
        EVIDENCE_URL_TTL_SECONDS,
        PUBLIC_IMAGE_URL_TTL_SECONDS,
    ),
)
BACKUP_AGE_RECIPIENT = env("BACKUP_AGE_RECIPIENT", default="")
BACKUP_ARCHIVE_SIGNING_PRIVATE_KEY = env(
    "BACKUP_ARCHIVE_SIGNING_PRIVATE_KEY", default=""
)
BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY = env(
    "BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY", default=""
)
TENANT_MIGRATION_AGE_RECIPIENT = env(
    "TENANT_MIGRATION_AGE_RECIPIENT", default=""
)
TENANT_MIGRATION_AGE_IDENTITY_FILE = env(
    "TENANT_MIGRATION_AGE_IDENTITY_FILE", default=""
)
BACKUP_DOWNLOAD_TTL_SECONDS = env.int("BACKUP_DOWNLOAD_TTL_SECONDS", default=5 * 60)
BACKUP_LEASE_SECONDS = env.int("BACKUP_LEASE_SECONDS", default=2 * 60 * 60)
BACKUP_DECISION_SECONDS = env.int("BACKUP_DECISION_SECONDS", default=5 * 60)
BACKUP_PRESIGN_DRAIN_SECONDS = env.int(
    "BACKUP_PRESIGN_DRAIN_SECONDS",
    default=max(EVIDENCE_URL_TTL_SECONDS, PUBLIC_IMAGE_URL_TTL_SECONDS),
)
BACKUP_OPS_DIR = env("BACKUP_OPS_DIR", default="/var/lib/spaceworks/ops")
TENANT_DUMP_STAGING_DIR = env("TENANT_DUMP_STAGING_DIR", default="")
TENANT_DUMP_STAGING_MAX_AGE_SECONDS = env.int(
    "TENANT_DUMP_STAGING_MAX_AGE_SECONDS", default=7 * 24 * 60 * 60
)
# Beat runs return reminders hourly; the internal cron endpoint remains a manual/external fallback.
REMINDER_SWEEP_BATCH_SIZE = env.int("REMINDER_SWEEP_BATCH_SIZE", default=200)
if REMINDER_SWEEP_BATCH_SIZE < 1:
    raise ImproperlyConfigured("REMINDER_SWEEP_BATCH_SIZE must be positive.")
