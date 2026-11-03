"""Heavy card work as durable Celery jobs (#133): chunked, retried, idempotent, cancellable.

A job's result is a temporary PRIVATE object readable only by its requester (and the
superadmin through the PII-window surface), deleted 7 days after it finishes (Q-I1).
"""
from django.conf import settings
from django.db import models
from django.db.models import Q

BULK_KINDS = ("bulk_sheet", "bulk_per_person", "zip")


class CardJob(models.Model):
    class Kind(models.TextChoices):
        BULK_SHEET = "bulk_sheet", "Print sheets (PDF)"
        BULK_PER_PERSON = "bulk_per_person", "One PDF per person"
        ZIP = "zip", "ZIP of card PDFs"
        EMAIL = "email", "Email cards"
        WALLET_ISSUE = "wallet_issue", "Issue wallet pass"
        WALLET_UPDATE = "wallet_update", "Update wallet passes"
        PHOTO_CLEANUP = "photo_cleanup", "Photo background clean-up"

    class State(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Finished"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="card_jobs")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    # The domain and target the job reads from: a space's member cards, one programme or one event.
    scope = models.CharField(max_length=20, default="member_cards")
    scope_id = models.PositiveBigIntegerField(null=True, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    params = models.JSONField(default=dict, blank=True)
    # Card ids frozen at enqueue, so a job is reproducible and its progress is countable.
    targets = models.JSONField(default=list, blank=True)
    idempotency_key = models.CharField(max_length=64)
    total = models.PositiveIntegerField(default=0)
    done = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    attempts = models.PositiveSmallIntegerField(default=0)
    state = models.CharField(max_length=12, choices=State.choices, default=State.QUEUED)
    error_code = models.CharField(max_length=48, blank=True, default="")
    # Work in progress: per-chunk object keys before the final assembly.
    parts = models.JSONField(default=list, blank=True)
    result_key = models.CharField(max_length=300, blank=True, default="")
    result_size = models.PositiveBigIntegerField(default=0)
    result_content_type = models.CharField(max_length=64, blank=True, default="")
    result_expires_at = models.DateTimeField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["state", "lease_until"], name="cardjob_state_lease_idx"),
                   models.Index(fields=["result_expires_at"], name="cardjob_result_expiry_idx")]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "kind", "idempotency_key"], name="uniq_card_job_idempotency"),
            models.UniqueConstraint(fields=["makerspace"], name="uniq_card_job_running_bulk",
                                    condition=Q(kind__in=BULK_KINDS, state__in=["queued", "running"])),
        ]

    @property
    def finished(self):
        return self.state in (self.State.SUCCEEDED, self.State.FAILED, self.State.CANCELLED)
