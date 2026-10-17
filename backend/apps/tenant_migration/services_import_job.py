from collections import Counter

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.tenant_migration.models import ImportIdentityDecision, TenantImportJob
from apps.audit import services as audit

from .services_import_run import run_import_job

from .import_job_cleanup import (
    CLEANUP_LEASE_NAME,
    CLEANUP_OBJECTS_LEASE_NAME,
    FINALIZATION_SWEEP_LEASE_NAME,
    cleanup_abandoned_import_objects,
    cleanup_expired_import_jobs,
    resume_expired_finalizing_import_jobs,
)


def submit_identity_decisions(*, actor, job, decisions):
    _require_superadmin(actor)
    from .archive_stream import PortableArchive
    from .import_staging import decrypted_archive
    from .services_import_staging import rows_archive_path

    rows_path = rows_archive_path(job)
    with decrypted_archive(
        rows_path, require_carried_keys=(str(rows_path) == job.archive_path),
    ) as (root, _carried):
        portable = PortableArchive(root)
        source_rows = {
            str(row["id"]): row
            for row in portable.rows("accounts.User")
        }
        if {str(item["source_user_id"]) for item in decisions} != set(source_rows):
            raise ValidationError({"detail": "A decision is required for every archived identity."})
        from .identity_decision_validation import validate_membership_dispositions

        validate_membership_dispositions(portable, decisions)
    with transaction.atomic():
        locked = TenantImportJob.objects.select_for_update().get(pk=job.pk)
        if locked.status not in {
            TenantImportJob.Status.AWAITING_IDENTITY,
            TenantImportJob.Status.READY,
        }:
            raise ValidationError({"detail": "This import no longer accepts identity decisions."})
        locked.identity_decisions.all().delete()
        rows = []
        for item in decisions:
            source_id = str(item["source_user_id"])
            rows.append(
                ImportIdentityDecision(
                    job=locked,
                    source_user_id=source_id,
                    source_email=source_rows[source_id].get("email") or None,
                    identity_resolution=item["identity_resolution"],
                    membership_disposition=item["membership_disposition"],
                    target_user_id=item.get("target_user_id"),
                )
            )
        ImportIdentityDecision.objects.bulk_create(rows)
        locked.status = TenantImportJob.Status.READY
        locked.save(update_fields=("status", "updated_at"))
        audit.record(
            actor,
            "tenant_migration.identity_decisions_submitted",
            target=locked,
            meta={
                "import_id": str(locked.pk),
                "identity_count": len(rows),
                "format_version": 1,
            },
        )
    return locked


@transaction.atomic
def claim_import_job(*, actor, job, target_identity=None):
    """Move a ready import to its single runnable state under a row lock."""
    _require_superadmin(actor)
    locked = TenantImportJob.objects.select_for_update().get(pk=job.pk)
    if locked.status != TenantImportJob.Status.READY:
        from .protocol_errors import ImportStateError

        raise ImportStateError("The import is not ready to run.")
    locked.status = TenantImportJob.Status.MATERIALIZING
    locked.run_request = {"actor_id": actor.pk, "target_identity": target_identity or {}}
    locked.save(update_fields=("status", "run_request", "updated_at"))
    audit.record(
        actor, "tenant_migration.import_run_requested", target=locked,
        meta={"import_id": str(locked.pk), "format_version": 1},
    )
    return locked


def _require_superadmin(actor):
    from apps.accounts.models import User

    # Workers reload the requester before this check: retained platform flags
    # must not authorize archive I/O after deactivation or loss of standing.
    if not (
        getattr(actor, "is_authenticated", False)
        and getattr(actor, "is_active", False)
        and getattr(actor, "account_kind", None) == User.AccountKind.PLATFORM
        and getattr(actor, "is_superuser", False)
        and getattr(actor, "role", None) == User.Role.SUPERADMIN
        and getattr(actor, "access_status", None) == User.AccessStatus.ACTIVE
        and not getattr(actor, "is_tenant_dump_stub", False)
        and getattr(actor, "retired_at", None) is None
    ):
        raise ValidationError({"detail": "Superadmin access is required."})


@transaction.atomic
def scrub_terminal_job(job):
    """Discard per-person provenance while preserving a PII-free aggregate result."""
    locked = TenantImportJob.objects.select_for_update().get(pk=job.pk)
    if locked.status not in TenantImportJob.TERMINAL_STATUSES:
        raise ValidationError("Only a terminal tenant import job can be scrubbed.")
    if locked.scrubbed_at is not None:
        return locked

    decisions = locked.identity_decisions.all()
    resolution_counts = Counter(decisions.values_list("identity_resolution", flat=True))
    membership_counts = Counter(
        decisions.values_list("membership_disposition", flat=True)
    )
    locked.aggregate_outcome = {
        "decision_count": decisions.count(),
        "identity_resolution": {
            value: resolution_counts[value]
            for value, _label in ImportIdentityDecision.IdentityResolution.choices
        },
        "membership_disposition": {
            value: membership_counts[value]
            for value, _label in ImportIdentityDecision.MembershipDisposition.choices
        },
    }
    decisions.delete()
    locked.source_makerspace_id = ""
    locked.source_makerspace_slug = ""
    locked.source_makerspace_name = ""
    locked.source_deployment_id = ""
    locked.source_deployment_identity = {}
    locked.storage_mode = ""
    locked.run_request = {}
    locked.run_attempt = None
    locked.scrubbed_at = timezone.now()
    locked.save(
        update_fields=(
            "aggregate_outcome",
            "source_makerspace_id",
            "source_makerspace_slug",
            "source_makerspace_name",
            "source_deployment_id",
            "source_deployment_identity",
            "storage_mode",
            "run_request",
            "run_attempt",
            "scrubbed_at",
            "updated_at",
        )
    )
    return locked
