"""Explicit native capability qualification, separate from core liveness."""
import boto3
from botocore.config import Config
from django.conf import settings


def verify_bindings(*, check=lambda: None, roles=None):
    from apps.storage_capabilities.runtime import configured_contracts
    from apps.storage_capabilities.verification import verify_and_save
    results = {}
    for role, contract in configured_contracts().items():
        if roles is not None and role not in roles:
            continue
        check()
        if role.startswith("offsite_"):
            from apps.backup.models import BackupDestination
            from apps.backup.offsite_client import destination_client
            destination = BackupDestination.objects.get(pk=role.removeprefix("offsite_"))
            client = destination_client(destination)
        else:
            prefix = "AUDIT_ATTESTATION_S3_" if role == "anchor" else "AWS_"
            client = boto3.client("s3", endpoint_url=contract.identity.endpoint,
                region_name=contract.identity.region,
                aws_access_key_id=getattr(settings, prefix + "ACCESS_KEY_ID", settings.AWS_ACCESS_KEY_ID),
                aws_secret_access_key=getattr(settings, prefix + "SECRET_ACCESS_KEY", settings.AWS_SECRET_ACCESS_KEY),
                aws_session_token=getattr(settings, "AWS_SESSION_TOKEN", "") or None,
                config=Config(connect_timeout=3, read_timeout=3, retries={"total_max_attempts": 1},
                              signature_version=settings.AWS_S3_SIGNATURE_VERSION,
                              s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE}))
        try:
            kwargs = {}
            if role == "anchor":
                kwargs = {"object_lock_mode": settings.AUDIT_ATTESTATION_S3_OBJECT_LOCK_MODE or "COMPLIANCE",
                          "object_lock_retention_seconds": settings.AUDIT_ATTESTATION_RETENTION_DAYS * 86400}
            from apps.storage_clients import qualification
            with qualification():
                results[role] = verify_and_save(client, contract, **kwargs)
            check()
        finally:
            client.close()
    return results


def refresh_chunk(context):
    """Refresh one binding per attempt, using the same native qualification probes."""
    from .cloud_jobs.contracts import ChunkResult
    from apps.storage_capabilities.runtime import configured_contracts
    from apps.storage_capabilities.budget import storage_budget
    roles = sorted(configured_contracts())
    position = int(context.checkpoint.get("position", 0))
    if position >= len(roles):
        return ChunkResult(True, {}, 0)
    context.check()
    with storage_budget(deadline=context.deadline, check_active=context.check):
        from .cloud_runtime import writer
        with writer("presign"):
            verify_bindings(check=context.check, roles=[roles[position]])
    return ChunkResult(position + 1 == len(roles),
                       {} if position + 1 == len(roles) else {"position": position + 1}, 1)
