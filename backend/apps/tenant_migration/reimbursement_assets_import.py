"""Stage-form uploads and finance attachments on the target of a portable import.

Accepted bytes (``ready``/``attached``) travel through the object journal and keep
their absolute retention timestamps. Anything still in flight on the source never
resumes abroad: its row stays as inert history under fresh coordination locators.
Every imported row then gets the target deployment's own FK-free cleanup locator, so
retention and late deletion work exactly as for a row created there.
"""
from uuid import uuid4

PORTABLE_STATES = ("ready", "attached")
IN_FLIGHT_STATES = ("initiated", "uploaded", "validating")


def asset_import_row(label, source, row, object_key_map):
    row.update(lease_token=None, lease_until=None, attempts=0, staging_version_id="", final_version_id="")
    opaque = uuid4().hex
    row["staging_key"] = f"import-staging/{opaque}"
    if source["state"] not in PORTABLE_STATES:
        object_key_map = {**object_key_map, str(source["object_key"]): f"import-coordination/{opaque}/final"}
        if source["state"] in IN_FLIGHT_STATES:
            row["state"], row["error_code"] = "failed", "upload_not_portable"
    return row, object_key_map


def register_imported_assets(target):
    """Create target cleanup locators for every imported stage upload and finance attachment."""
    from django.conf import settings
    from apps.events.staged_forms.retention_registration import STAGE_RETENTION_PROVIDER
    from apps.events.staged_forms.upload_models import StageFormAsset
    from apps.payments.event_payouts.attachment_models import FinanceAttachment
    from apps.payments.event_payouts.cleanup_models import FinanceObjectCleanup
    stage = list(StageFormAsset.objects.select_related("event").filter(event__makerspace=target).order_by("pk"))
    STAGE_RETENTION_PROVIDER.after_import_locked(stage)
    finance = list(FinanceAttachment.objects.filter(makerspace=target).exclude(
        pk__in=FinanceObjectCleanup.objects.values("asset_id")).order_by("pk"))
    for row in finance:
        FinanceObjectCleanup.objects.create(source_makerspace_id=target.pk, asset_id=row.pk,
            bucket=settings.AWS_STORAGE_BUCKET_NAME, staging_key=row.staging_key, object_key=row.object_key,
            next_attempt_at=row.expires_at)
    return len(stage), len(finance)
