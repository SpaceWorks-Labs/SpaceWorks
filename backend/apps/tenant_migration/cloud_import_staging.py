"""Managed staging carries only encrypted, digest-bound locators between jobs."""
from pathlib import Path
import tempfile

from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.backup.digests import sha256_file
from apps.backup.managed import staging
from .archive_stream import PortableArchive
from .import_staging import decrypted_archive, seal_rows_sidecar
from .models_import_job import TenantImportJob
from .services_import_job import _require_superadmin


def stage(job_id, actor_id):
    from .services_import_staging import _claim_staging_lease, _publish_staging, _persist_staging_failure
    from apps.operations.cloud_jobs.admission import admit_import
    if not admit_import(TenantImportJob.objects.filter(pk=job_id).first()):
        return TenantImportJob.objects.get(pk=job_id)
    claim = _claim_staging_lease(job_id)
    if claim is None:
        return TenantImportJob.objects.filter(pk=job_id).first()
    token, job = claim
    actor = User.objects.filter(pk=actor_id).first()
    try:
        _require_superadmin(actor)
        with staging.materialize(job.archive_path) as local:
            if sha256_file(local) != job.source_archive_digest:
                raise ValidationError("The encrypted archive digest does not match.")
            with decrypted_archive(local) as (root, _carried):
                from .archive_envelope import FORMAT, FORMAT_VERSION
                from .pairing import _validated_identity
                portable = PortableArchive(root)
                manifest = portable.json("migration-manifest.json")
                if manifest.get("format") != FORMAT or manifest.get("format_version") != FORMAT_VERSION:
                    raise ValidationError("The tenant migration format is unsupported.")
                source = manifest.get("source", {}).get("makerspace", {})
                identity = _validated_identity(manifest.get("source", {}).get("deployment"), "source")
                users = list(portable.rows("accounts.User"))
                with tempfile.TemporaryDirectory(prefix="spaceworks-rows-") as directory:
                    path = Path(directory, "rows.age")
                    with path.open("xb") as output:
                        seal_rows_sidecar(root, output)
                    locator = staging.store(path, owner=job.pk, label="rows", expires_at=job.expires_at)
        _publish_staging(job_id, token, None, manifest, source, identity, users, actor, locator=locator)
    except Exception as exc:
        _persist_staging_failure(job_id, token, actor, exc, None)
    return TenantImportJob.objects.filter(pk=job_id).first()
