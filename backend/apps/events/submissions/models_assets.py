"""Private asset identity and durable work. G authors migrations/import barrels."""
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone


class AssetFields(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    kind = models.CharField(max_length=32)
    purpose = models.CharField(max_length=32, default="project")
    public_requested = models.BooleanField(default=False)
    original_filename = models.CharField(max_length=240)
    extension = models.CharField(max_length=16)
    subtype = models.CharField(max_length=32)
    policy_name = models.CharField(max_length=64, default="hackathon-maker-v1")
    policy_version = models.PositiveIntegerField(default=1)
    effective_cap = models.PositiveBigIntegerField()
    declared_mime = models.CharField(max_length=160)
    declared_bytes = models.PositiveBigIntegerField()
    canonical_mime = models.CharField(max_length=160, blank=True)
    actual_bytes = models.PositiveBigIntegerField(default=0)
    staging_key = models.CharField(max_length=512, editable=False, unique=True)
    verification_key = models.CharField(max_length=512, editable=False, unique=True)
    object_key = models.CharField(max_length=512, editable=False, unique=True)
    source_version_id = models.CharField(max_length=256, blank=True, editable=False)
    verification_version_id = models.CharField(max_length=256, blank=True, editable=False)
    final_version_id = models.CharField(max_length=256, blank=True, editable=False)
    source_etag = models.CharField(max_length=256, blank=True, editable=False)
    sha256 = models.CharField(max_length=64, blank=True, editable=False)
    original_sha256 = models.CharField(max_length=64, blank=True, editable=False)
    state = models.CharField(max_length=24, default="reserved", db_index=True)
    scan_backend = models.CharField(max_length=16, default="none")
    scan_status = models.CharField(max_length=24, default="pending")
    scan_version = models.CharField(max_length=64, blank=True)
    scanned_at = models.DateTimeField(null=True)
    manifest = models.JSONField(default=list)
    media_metadata = models.JSONField(default=dict)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    multipart_upload_id = models.TextField(blank=True, editable=False)
    part_size = models.PositiveBigIntegerField(default=0)
    generation = models.PositiveIntegerField(default=1)
    claim = models.UUIDField(default=uuid4, editable=False)
    version = models.PositiveIntegerField(default=1)
    last_activity_at = models.DateTimeField(default=timezone.now)
    upload_not_after = models.DateTimeField(null=True)
    reserved_bytes = models.PositiveBigIntegerField()
    charged_bytes = models.PositiveBigIntegerField(default=0)
    failure_code = models.CharField(max_length=64, blank=True)
    ready_at = models.DateTimeField(null=True)
    expires_at = models.DateTimeField(null=True, db_index=True)
    expired_at = models.DateTimeField(null=True)
    deleted_at = models.DateTimeField(null=True)
    expired_size_bytes = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True
        app_label = "events"
        constraints = [
            models.CheckConstraint(condition=Q(declared_bytes__gt=0), name="%(class)s_declared_positive"),
            models.CheckConstraint(condition=Q(declared_bytes__lte=F("effective_cap")), name="%(class)s_cap"),
            models.CheckConstraint(condition=~Q(state="ready") | (
                Q(ready_at__isnull=False, actual_bytes__gt=0, expired_at__isnull=True) & ~Q(sha256="") &
                Q(scan_status__in=["clean", "skipped"])), name="%(class)s_ready_shape"),
            models.CheckConstraint(condition=Q(state__in=["reserved", "uploading", "uploaded", "validating", "promoting",
                "ready", "rejected", "quarantined", "aborted", "expiring", "expired", "deleting", "copying"]),
                name="%(class)s_valid_state"),
        ]


class SubmissionAsset(AssetFields):
    submission = models.ForeignKey("events.HackathonSubmission", on_delete=models.CASCADE, related_name="assets")
    team = models.ForeignKey("events.HackathonTeam", on_delete=models.PROTECT, related_name="+")

    class Meta(AssetFields.Meta):
        abstract = False


class HackathonParticipantAsset(AssetFields):
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    purpose = models.CharField(max_length=32, default="resume", editable=False)

    class Meta(AssetFields.Meta):
        abstract = False
        constraints = AssetFields.Meta.constraints + [
            models.CheckConstraint(condition=Q(purpose="resume", extension="pdf", kind="resume"),
                                   name="participant_asset_resume_only"),
        ]


class EventAssetUsage(models.Model):
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE, related_name="asset_usage")
    budget_bytes = models.PositiveBigIntegerField(null=True)
    reserved_bytes = models.PositiveBigIntegerField(default=0)
    used_bytes = models.PositiveBigIntegerField(default=0)
    failed_cleanup_bytes = models.PositiveBigIntegerField(default=0)
    first_results_published_at = models.DateTimeField(null=True)
    retention_anchor = models.DateTimeField(null=True)
    retention_anchor_kind = models.CharField(max_length=16, blank=True)
    expires_at = models.DateTimeField(null=True)

    class Meta:
        app_label = "events"


class SubmissionAssetWork(models.Model):
    asset = models.OneToOneField(SubmissionAsset, null=True, on_delete=models.CASCADE, related_name="work")
    participant_asset = models.OneToOneField(HackathonParticipantAsset, null=True, on_delete=models.CASCADE, related_name="work")
    state = models.CharField(max_length=24, default="pending", db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    lease_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    last_code = models.CharField(max_length=64, blank=True)
    saved_asset_id = models.PositiveBigIntegerField(null=True)
    saved_detail_version = models.PositiveIntegerField(null=True)

    class Meta:
        app_label = "events"
        constraints = [models.CheckConstraint(condition=(
            Q(asset__isnull=False, participant_asset__isnull=True) |
            Q(asset__isnull=True, participant_asset__isnull=False)), name="asset_work_one_subject")]
