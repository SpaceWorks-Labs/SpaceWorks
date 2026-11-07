"""Per-space key lifecycle state (lane L8, #120, #128 C-26): jobs, search keys, retired browser keys.

None of these rows holds usable key material. A ``MakerspaceSearchKey`` salt is useless
without the deployment's ``PII_SEARCH_HASH_KEY``; a ``RetiredPublishableKey`` is a public
browser key kept only for its grace window. All are deployment-local and never travel.
"""

from django.utils.translation import gettext_noop
from django.db import models
from django.db.models import Q


class KeyRotationJob(models.Model):
    """One background re-encrypt or re-index of one space, with progress the UI polls."""

    class Kind(models.TextChoices):
        ROTATION = "rotation", gettext_noop("Key rotation")
        EMERGENCY_REKEY = "emergency_rekey", gettext_noop("Emergency re-key")
        SEARCH_REINDEX = "search_reindex", gettext_noop("Search key rotation")

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="key_rotation_jobs")
    kind = models.CharField(max_length=24, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    from_version = models.PositiveIntegerField(null=True, blank=True)
    to_version = models.PositiveIntegerField()
    rows_done = models.PositiveIntegerField(default=0)
    rows_skipped = models.PositiveIntegerField(default=0)
    cursor = models.JSONField(default=dict, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error_code = models.CharField(max_length=64, blank=True, default="")
    retained_versions = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at", "-id")
        constraints = [
            models.UniqueConstraint(fields=["makerspace"], condition=Q(status="running"),
                                    name="uniq_running_key_job_per_makerspace"),
        ]


class MakerspaceSearchKey(models.Model):
    """A per-space blind-index key: HMAC(PII_SEARCH_HASH_KEY, space, version, salt)."""

    class Status(models.TextChoices):
        BUILDING = "building", "Building"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="search_keys")
    version = models.PositiveIntegerField()
    salt = models.BinaryField(max_length=32)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.BUILDING)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "version"], name="uniq_makerspace_search_key_version"),
            models.UniqueConstraint(fields=["makerspace"], condition=Q(status="active"),
                                    name="uniq_makerspace_active_search_key"),
            models.UniqueConstraint(fields=["makerspace"], condition=Q(status="building"),
                                    name="uniq_makerspace_building_search_key"),
            models.CheckConstraint(condition=Q(version__gte=1), name="ck_makerspace_search_key_version"),
        ]


class RetiredPublishableKey(models.Model):
    """A rotated ``public_api_key``, accepted until ``valid_until`` and refused after (#77)."""

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="retired_publishable_keys")
    key = models.CharField(max_length=40, unique=True)
    retired_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["makerspace", "valid_until"], name="enc_retired_pubkey_valid_idx")]
