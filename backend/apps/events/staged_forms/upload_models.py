"""Assignment-bound stage files cannot resolve core finance attachments."""

from django.conf import settings
from django.db import models
from apps.encryption.mappers import ScopedPiiModelMixin


class StageFormAsset(ScopedPiiModelMixin, models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="stage_assets")
    assignment = models.ForeignKey("events.StageFormAssignment", on_delete=models.CASCADE, related_name="assets")
    owner_member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stage_assets")
    response = models.ForeignKey("events.StageFormResponse", on_delete=models.SET_NULL, null=True, related_name="assets")
    form_revision = models.ForeignKey("events.EventFormRevision", on_delete=models.PROTECT, related_name="stage_assets")
    question_id = models.CharField(max_length=64)
    purpose = models.CharField(max_length=16, default="stage_form_file", choices=[("stage_form_file", "stage_form_file")])
    state = models.CharField(max_length=12, default="initiated", choices=[(v, v) for v in (
        "initiated", "uploaded", "validating", "ready", "attached", "failed", "expired", "deleting", "deleted")])
    version = models.PositiveBigIntegerField(default=1)
    generation = models.PositiveBigIntegerField(default=1)
    expected_bytes = models.PositiveBigIntegerField()
    actual_bytes = models.PositiveBigIntegerField(null=True)
    declared_mime = models.CharField(max_length=100)
    canonical_mime = models.CharField(max_length=100, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    original_filename = models.TextField()
    staging_key = models.CharField(max_length=500, unique=True)
    staging_version_id = models.CharField(max_length=200, blank=True)
    object_key = models.CharField(max_length=500, unique=True)
    final_version_id = models.CharField(max_length=200, blank=True)
    scan_status = models.CharField(max_length=8, default="pending")
    scanner_policy = models.CharField(max_length=64)
    scanner_version = models.CharField(max_length=64, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    attached_at = models.DateTimeField(null=True)
    retention_days_snapshot = models.PositiveIntegerField(default=365)
    expires_at = models.DateTimeField(null=True)
    expired_at = models.DateTimeField(null=True)
    deletion_receipt = models.JSONField(default=dict)
    lease_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "events"
        constraints = [
            models.CheckConstraint(condition=models.Q(purpose="stage_form_file"), name="stage_asset_purpose"),
            models.CheckConstraint(condition=models.Q(expected_bytes__gt=0, expected_bytes__lte=10485760), name="stage_asset_size"),
            models.CheckConstraint(condition=models.Q(version__gte=1, generation__gte=1), name="stage_asset_versions"),
            models.CheckConstraint(condition=(~models.Q(state__in=("ready", "attached")) | models.Q(
                actual_bytes=models.F("expected_bytes"), scan_status__in=("clean", "skipped"),
                actual_bytes__isnull=False,
                canonical_mime__in=("application/pdf", "image/jpeg", "image/png", "image/heic"),
                sha256__regex=r"^[a-f0-9]{64}$")), name="stage_asset_ready_integrity"),
        ]


class StageFileCleanup(models.Model):
    """FK-free, permanent locators survive event/tenant purge and late workers."""
    source_asset_id = models.PositiveBigIntegerField(unique=True)
    tenant_id = models.PositiveBigIntegerField(db_index=True)
    event_id_snapshot = models.PositiveBigIntegerField()
    bucket = models.CharField(max_length=255)
    staging_key = models.CharField(max_length=500, unique=True)
    object_key = models.CharField(max_length=500, unique=True)
    not_before = models.DateTimeField()
    next_attempt_at = models.DateTimeField(db_index=True)
    lease_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)
    last_deleted_at = models.DateTimeField(null=True)
    last_error_code = models.CharField(max_length=64, blank=True)

    class Meta:
        app_label = "events"

    def delete(self, *args, **kwargs):
        raise RuntimeError("Stage cleanup locators are permanent.")
