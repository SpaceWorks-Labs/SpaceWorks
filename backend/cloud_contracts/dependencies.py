"""Names frozen at integration step 1, implemented exclusively by their owners.

    A name here is a handoff requirement, not evidence that it is implemented.
    No dynamic import, discovery, or runtime plugin registration occurs here.
"""

DEPENDENCIES = {
    "M.database": "config.cloud_database.configure_database",
    "M.admission": "apps.backup.managed.admission.assert_managed_admission",
    "M.roles": "scripts.run_cloud_role",
    "S.capabilities": "apps.storage_capabilities.descriptors.StorageCapabilities",
    "S.usage": "apps.storage_capabilities.accounting.sample_usage",
    "E.settings": "apps.integrations.mail_providers.settings.email_settings",
    "E.budget": "apps.integrations.mail_providers.budget.reserve",
    "E.drain": "apps.integrations.mail_providers.outbox.drain_chunk",
    "J.catalog": "apps.operations.cloud_jobs.catalog.periodic_jobs",
    "J.discovery": "apps.operations.cloud_jobs.discovery.task_modules",
    "J.tick_urls": "apps.operations.cloud_jobs.tick_urls",
    "J.tick": "apps.operations.cloud_jobs.tick_service.run_tick",
    "I.quota": "apps.operations.cloud_quotas.services.snapshot",
    "R.answers": "scripts/cloud_setup/ (answers version 1)",
    "F.worker": "deploy/static/cloudflare/free/ (scheduled handler)",
    "Q.free": "scripts/verify-deployment.sh free --source <tree> --postgres-major 17",
}
