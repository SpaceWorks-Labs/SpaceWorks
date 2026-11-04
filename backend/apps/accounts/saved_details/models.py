"""Global owner records: deliberately no Events imports, tenant FK or login updates."""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.encryption.account_mappers import AccountPiiModelMixin


class MemberSavedDetail(AccountPiiModelMixin):
    account_identity_fields = ("user_id", "field_key")
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    field_key = models.CharField(max_length=40)
    value_envelope = models.TextField(blank=True)
    value_type = models.CharField(max_length=20)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
    save_consent_version = models.PositiveIntegerField(default=1)
    consented_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True)

    class Meta:
        app_label = "accounts"
        constraints = [models.UniqueConstraint(fields=["user", "field_key"], name="saved_detail_owner_key")]


class MemberSavedAsset(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    object_key = models.CharField(max_length=300, unique=True)
    staging_key = models.CharField(max_length=300, unique=True)
    verification_key = models.CharField(max_length=300, unique=True)
    cleanup_keys = models.JSONField(default=list)
    sha256 = models.CharField(max_length=64, blank=True)
    size_bytes = models.PositiveBigIntegerField()
    canonical_mime = models.CharField(max_length=100, default="application/pdf")
    state = models.CharField(max_length=20, default="uploading", choices=[(s, s) for s in (
        "uploading", "validating", "ready", "failed", "deleting", "deleted",
    )])
    scan_status = models.CharField(max_length=30, default="pending")
    version = models.PositiveIntegerField(default=1)
    generation = models.PositiveIntegerField(default=1)
    claim_uuid = models.UUIDField(null=True)
    source_version_id = models.CharField(max_length=300, blank=True)
    final_version_id = models.CharField(max_length=300, blank=True)
    failure_code = models.CharField(max_length=50, blank=True)
    last_selected_at = models.DateTimeField(null=True)
    next_cleanup_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "accounts"
        constraints = [models.CheckConstraint(condition=models.Q(size_bytes__lte=10 * 1024**2), name="saved_resume_file_cap")]


class SavedDetailUpdateIntent(AccountPiiModelMixin):
    account_identity_fields = ("user_id", "operation_uuid", "event_id", "subject_kind", "subject_id", "base_versions", "chosen_fields", "key_version", "key_epoch")
    id = models.UUIDField(primary_key=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    operation_uuid = models.UUIDField()
    event_id = models.PositiveBigIntegerField()
    subject_kind = models.CharField(max_length=20)
    subject_id = models.PositiveBigIntegerField()
    base_versions = models.JSONField(default=dict)
    chosen_fields = models.JSONField(default=list)
    encrypted_payload = models.TextField(blank=True)
    key_version = models.PositiveIntegerField()
    key_epoch = models.PositiveBigIntegerField()
    state = models.CharField(max_length=10, default="pending", choices=[(s, s) for s in ("pending", "applied", "conflict", "failed")])
    field_status = models.JSONField(default=dict)
    failure_code = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)
    expires_at = models.DateTimeField()

    class Meta:
        app_label = "accounts"
        constraints = [
            models.UniqueConstraint(fields=["user", "operation_uuid"], name="saved_intent_owner_operation"),
            models.CheckConstraint(condition=models.Q(subject_kind__in=["registration", "application", "role_assignment", "stage_response"]), name="saved_intent_subject_kind"),
        ]


class SavedDetailCommandReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    operation_uuid = models.UUIDField()
    request_sha256 = models.CharField(max_length=64)
    response_metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "accounts"
        constraints = [models.UniqueConstraint(fields=["user", "operation_uuid"], name="saved_receipt_owner_operation")]


class AccountSavedDetailsExportJob(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    job_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    state = models.CharField(max_length=10, default="queued", choices=[(s, s) for s in ("queued", "building", "ready", "failed", "expired")])
    object_key = models.CharField(max_length=300, unique=True)
    cleanup_keys = models.JSONField(default=list)
    sha256 = models.CharField(max_length=64, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    claim_uuid = models.UUIDField(null=True)
    started_at = models.DateTimeField(null=True)
    failure_code = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        app_label = "accounts"


class SavedDetailsObjectCleanup(models.Model):
    """FK-free retry locator survives account erasure; keys contain random UUIDs."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    object_keys = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    next_attempt_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True)

    class Meta:
        app_label = "accounts"
