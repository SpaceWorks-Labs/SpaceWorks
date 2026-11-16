from django.conf import settings
from django.db import models


class EventCertificatePublicationPolicy(models.Model):
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE)
    enabled = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=0)
    changed_at = models.DateTimeField(auto_now=True)
    # C4: when on, every signatory a design prints approves it before its certificates render.
    signatory_approval_required = models.BooleanField(default=False)


class CertificateIssueBatch(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    operation_id = models.UUIDField()
    request_sha256 = models.CharField(max_length=64)
    public_verification_enabled = models.BooleanField(default=True)
    state = models.CharField(max_length=12, default="queued", choices=((key, key) for key in
                            ("queued", "running", "completed", "failed")))
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("event", "operation_id"), name="event_certificate_batch_op")]


class CertificateIssueBatchItem(models.Model):
    batch = models.ForeignKey(CertificateIssueBatch, on_delete=models.CASCADE, related_name="items")
    subject_kind = models.CharField(max_length=16, choices=((key, key) for key in ("registration", "role_assignment")))
    subject_id = models.PositiveBigIntegerField()
    kind = models.CharField(max_length=24)
    award_id = models.PositiveBigIntegerField(null=True, blank=True)
    result_revision_id = models.PositiveBigIntegerField(null=True, blank=True)
    certificate = models.ForeignKey("events.EventAttendanceCertificate", on_delete=models.SET_NULL, null=True, blank=True)
    state = models.CharField(max_length=12, default="queued")
    error_code = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("batch", "subject_kind", "subject_id", "kind", "award_id"),
                                              nulls_distinct=False, name="event_certificate_batch_subject")]
