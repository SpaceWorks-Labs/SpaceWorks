"""Core financial byte metadata survives domain purge and tracks all locators."""

from django.conf import settings
from django.db import models
from apps.encryption.mappers import ScopedPiiModelMixin


class FinanceAttachment(ScopedPiiModelMixin, models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT, related_name="finance_attachments")
    event = models.ForeignKey("events.Event", on_delete=models.SET_NULL, null=True, related_name="finance_attachments")
    event_id_snapshot = models.PositiveBigIntegerField()
    event_title_snapshot = models.CharField(max_length=200)
    owner_member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="finance_attachments")
    purpose = models.CharField(max_length=32, choices=[(v, v) for v in (
        "reimbursement_receipt", "reimbursement_payee_document")])
    binding_kind = models.CharField(max_length=8, choices=[("claim", "claim"), ("payee", "payee")])
    binding_uuid = models.UUIDField()
    question_id = models.CharField(max_length=64)
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
    scan_status = models.CharField(max_length=8, default="pending", choices=[(v, v) for v in (
        "pending", "clean", "infected", "skipped", "failed")])
    scanner_policy = models.CharField(max_length=64)
    scanner_version = models.CharField(max_length=64, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    attached_at = models.DateTimeField(null=True)
    retention_policy_revision = models.PositiveBigIntegerField()
    retention_days_snapshot = models.PositiveIntegerField()
    obligation = models.ForeignKey("payments.EventPayoutObligation", on_delete=models.CASCADE,
                                   null=True, related_name="attachments")
    terminal_financial_at = models.DateTimeField(null=True)
    closure_reason_code = models.CharField(max_length=64, blank=True)
    closure_operation_id = models.UUIDField(null=True)
    expires_at = models.DateTimeField(null=True)
    legal_hold_until = models.DateTimeField(null=True)
    legal_hold_reason_code = models.CharField(max_length=64, blank=True)
    expired_at = models.DateTimeField(null=True)
    deletion_receipt = models.JSONField(default=dict)
    lease_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "payments"
        indexes = [models.Index(fields=("state", "expires_at"), name="finance_attachment_expiry")]
        constraints = [
            models.CheckConstraint(condition=(models.Q(purpose="reimbursement_receipt", binding_kind="claim")
                | models.Q(purpose="reimbursement_payee_document", binding_kind="payee")), name="finance_attachment_purpose"),
            models.CheckConstraint(condition=models.Q(expected_bytes__gt=0, expected_bytes__lte=10485760), name="finance_attachment_size"),
        ]
