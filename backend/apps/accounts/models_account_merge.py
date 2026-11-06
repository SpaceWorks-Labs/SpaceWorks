"""Durable account-unification decisions and interactive merge proof state.

``AccountMergeRecord`` is append-only and becomes immutable once ``completed`` (DB
trigger ``accounts_guard_merge_record``): one ``converted`` record per former staff
account (written by the unification migration) and one ``merged`` record per completed
merge (written by the merge engine). Its PII snapshot is ciphertext only; the single
permitted post-completion write is the purge scrub of that snapshot.
``AccountMergeIntent`` is the transient two-sided proof a merge needs (#65).
"""

from django.utils.translation import gettext_lazy
import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class AccountMergeRecord(models.Model):
    class Decision(models.TextChoices):
        CONVERTED = "converted", "Converted"
        MERGED = "merged", "Merged"

    class ProofMethod(models.TextChoices):
        MIGRATION = "migration", gettext_lazy("Unification migration")
        CREDENTIALS = "credentials", gettext_lazy("Password and second factor")
        EMAIL_CODES = "email_codes", gettext_lazy("Two emailed codes")

    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"

    class SnapshotScheme(models.TextChoices):
        DEPLOYMENT = "deployment", gettext_lazy("Deployment field key")
        ACCOUNT = "account", gettext_lazy("Per-account key")
        SCRUBBED = "scrubbed", "Scrubbed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    decision = models.CharField(max_length=16, choices=Decision.choices)
    source = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                               related_name="merge_records_as_source")
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                               null=True, blank=True, related_name="merge_records_as_target")
    proof_method = models.CharField(max_length=16, choices=ProofMethod.choices)
    run_id = models.UUIDField()
    plan_sha256 = models.CharField(max_length=64, blank=True)
    snapshot_scheme = models.CharField(max_length=16, choices=SnapshotScheme.choices)
    snapshot_key_version = models.PositiveIntegerField(null=True, blank=True)
    # Original email/name/phone/Telegram as encrypted JSON; held values live here too.
    snapshot_ciphertext = models.TextField(blank=True)
    held_fields = models.JSONField(default=list, blank=True)
    roles_kept = models.JSONField(default=list, blank=True)
    counts = models.JSONField(default=dict, blank=True)
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(
                Q(decision="converted", target__isnull=True, proof_method="migration")
                | (Q(decision="merged", target__isnull=False,
                     proof_method__in=["credentials", "email_codes"]) & ~Q(target=F("source")))
            ), name="merge_record_decision_shape"),
            models.CheckConstraint(condition=(
                Q(state="pending", completed_at__isnull=True)
                | Q(state="completed", completed_at__isnull=False)
            ), name="merge_record_completion"),
            models.CheckConstraint(condition=(
                Q(snapshot_scheme="scrubbed", snapshot_ciphertext="")
                | (~Q(snapshot_scheme="scrubbed") & ~Q(snapshot_ciphertext=""))
            ), name="merge_record_snapshot_present"),
            models.UniqueConstraint(fields=["source"], condition=Q(decision="converted"),
                                    name="uniq_merge_record_conversion"),
            models.UniqueConstraint(fields=["source"], condition=Q(decision="merged", state="completed"),
                                    name="uniq_merge_record_completed_merge"),
        ]


class AccountMergeIntent(models.Model):
    class Method(models.TextChoices):
        CREDENTIALS = "credentials", gettext_lazy("Password and second factor")
        EMAIL_CODES = "email_codes", gettext_lazy("Two emailed codes")

    class State(models.TextChoices):
        STARTED = "started", "Started"
        PROVED = "proved", "Proved"
        CONSUMED = "consumed", "Consumed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survivor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name="account_merge_intents")
    # Null when the identifier matched nothing, so the start answer never enumerates.
    source = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True,
                               blank=True, related_name="account_merge_intents_as_source")
    method = models.CharField(max_length=16, choices=Method.choices)
    identifier_digest = models.CharField(max_length=64)
    survivor_code_digest = models.CharField(max_length=64, blank=True)
    source_code_digest = models.CharField(max_length=64, blank=True)
    survivor_code_verified_at = models.DateTimeField(null=True, blank=True)
    source_code_verified_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    resends = models.PositiveSmallIntegerField(default=0)
    proved_at = models.DateTimeField(null=True, blank=True)
    preview_sha256 = models.CharField(max_length=64, blank=True)
    state = models.CharField(max_length=16, choices=State.choices, default=State.STARTED)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(source=F("survivor")),
                                   name="merge_intent_distinct_accounts"),
        ]
        indexes = [models.Index(fields=["survivor", "state"], name="merge_intent_survivor_idx")]
