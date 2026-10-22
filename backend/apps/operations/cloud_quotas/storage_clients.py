"""Explicit per-binding runtime credentials, never borrowed from a different sink."""
from apps.storage_clients import s3_client
from botocore.config import Config
from django.conf import settings


def binding_client(role, contract):
    if role.startswith("offsite_"):
        from apps.backup.models import BackupDestination
        from apps.backup.offsite_client import destination_client
        return destination_client(BackupDestination.objects.get(pk=role.removeprefix("offsite_")))
    prefix = "AUDIT_ATTESTATION_S3_" if role == "anchor" else "AWS_"
    return s3_client("s3", endpoint_url=contract.identity.endpoint, region_name=contract.identity.region,
        aws_access_key_id=getattr(settings, prefix + "ACCESS_KEY_ID", "") or None,
        aws_secret_access_key=getattr(settings, prefix + "SECRET_ACCESS_KEY", "") or None,
        aws_session_token=getattr(settings, prefix + "SESSION_TOKEN", "") or None,
        config=Config(connect_timeout=2, read_timeout=2, retries={"total_max_attempts": 1},
                      signature_version=settings.AWS_S3_SIGNATURE_VERSION,
                      s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE}))
