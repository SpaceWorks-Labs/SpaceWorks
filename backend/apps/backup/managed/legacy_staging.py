"""Read-only refusal of work whose only payload still lives on a prior host."""


def _exists(cursor, table):
    cursor.execute("SELECT to_regclass(%s)", ["public." + table])
    return cursor.fetchone()[0] is not None


def _refuse():
    from .admission import ManagedAdmissionError
    raise ManagedAdmissionError(
        "Legacy local staging must be drained or migrated on its original host before managed admission."
    )


def assert_durable_staging(cursor):
    """No filesystem checks, age-based completion, mutation, or silent adoption.

    New managed import markers already name durable upload/locator ownership.
    Captures have no path column. An append-only request proof binds new work
    to this deployment/database; timestamps never establish managed origin.
    """
    if _exists(cursor, "tenant_migration_tenantimportjob"):
        cursor.execute("""
SELECT EXISTS (
 SELECT 1 FROM public.tenant_migration_tenantimportjob
 WHERE NOT (status IN ('completed','failed','abandoned')
            AND (scrubbed_at IS NOT NULL OR archive_path=''))
   AND archive_path NOT LIKE 'cloud-stage:%%'
   AND archive_path NOT LIKE 'cloud-upload:%%'
)
""")
        if cursor.fetchone()[0]:
            _refuse()
    if not _exists(cursor, "tenant_migration_tenantdumpcapture"):
        return
    binding = None
    if _exists(cursor, "backup_manageddeploymentstate"):
        cursor.execute("SELECT deployment_id::text,database_uuid::text FROM public.backup_manageddeploymentstate WHERE id=1")
        binding = cursor.fetchone()
    origin_clause, parameters = "", []
    if binding is not None and _exists(cursor, "audit_auditlog"):
        origin_clause = """
 AND NOT EXISTS (
  SELECT 1 FROM public.audit_auditlog a
  WHERE a.action='tenant_migration.tenant_dump_requested'
    AND a.target_type='tenant_migration.tenantdumpcapture' AND a.target_id=c.id::text
    AND a.meta->>'staging_backend'='managed-object-v1'
    AND a.meta->>'staging_capture_id'=c.id::text
    AND a.meta->>'staging_deployment_id'=%s
    AND a.meta->>'staging_database_uuid'=%s
 )
"""
        parameters = list(binding)
    durable = _exists(cursor, "backup_managedstagedobject")
    durable_clause = """
 AND NOT EXISTS (
  SELECT 1 FROM public.backup_managedstagedobject s
  WHERE s.owner=c.id AND s.label IN ('source','derived')
    AND s.available AND s.selected AND s.delete_requested_at IS NULL
    AND s.deleted_at IS NULL AND s.expires_at>CURRENT_TIMESTAMP
 )
""" if durable else ""
    cursor.execute("""
SELECT EXISTS (
 SELECT 1 FROM public.tenant_migration_tenantdumpcapture c
 WHERE c.status NOT IN ('published','refused','failed')
""" + origin_clause + durable_clause + ")", parameters)
    if cursor.fetchone()[0]:
        _refuse()


def request_origin(capture):
    """Written with capture creation, through the existing append-only audit API."""
    from .models import ManagedDeploymentState
    binding = ManagedDeploymentState.objects.get(pk=1)
    return {"staging_backend": "managed-object-v1", "staging_capture_id": str(capture.pk),
            "staging_deployment_id": str(binding.deployment_id),
            "staging_database_uuid": str(binding.database_uuid)}
