"""FK-free locators survive whole-tenant deletion and source-state changes."""
from uuid import uuid4
from django.db import models
from django.conf import settings
from .model_base import Immutable


class CleanupQuerySet(models.QuerySet):
    def delete(self):
        raise RuntimeError("Finance cleanup locators are permanent.")

    def update(self, **kwargs):
        if set(kwargs) & {"source_makerspace_id", "asset_id", "bucket", "staging_key", "object_key"}:
            raise RuntimeError("Finance cleanup locators are immutable.")
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, **kwargs):
        if set(fields) & {"source_makerspace_id", "asset_id", "bucket", "staging_key", "object_key"}:
            raise RuntimeError("Finance cleanup locators are immutable.")
        return super().bulk_update(objs, fields, **kwargs)


class FinanceObjectCleanup(models.Model):
    objects = models.Manager.from_queryset(CleanupQuerySet)()
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    source_makerspace_id = models.PositiveBigIntegerField()
    asset_id = models.PositiveBigIntegerField(unique=True)
    bucket = models.CharField(max_length=200)
    staging_key = models.CharField(max_length=500, unique=True)
    object_key = models.CharField(max_length=500, unique=True)
    next_attempt_at = models.DateTimeField(null=True, db_index=True)
    lease_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    attempts = models.PositiveBigIntegerField(default=0)
    deleted_at = models.DateTimeField(null=True)
    last_error_code = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payments"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            names = ("source_makerspace_id", "asset_id", "bucket", "staging_key", "object_key")
            old = type(self).objects.filter(pk=self.pk).values(*names).get()
            if any(old[name] != getattr(self, name) for name in names):
                raise RuntimeError("Finance cleanup locators are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Finance cleanup locators are permanent.")


class FinanceRetentionPolicy(models.Model):
    """Audited, prospective receipt policy; existing attachments keep snapshots."""
    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="finance_retention_policy")
    version = models.PositiveBigIntegerField(default=1)
    receipt_days = models.PositiveIntegerField(default=2555)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "payments"
        constraints = [models.CheckConstraint(condition=models.Q(receipt_days__gte=1, receipt_days__lte=36500),
                                              name="finance_receipt_retention_range")]


class FinanceSweepCursor(models.Model):
    """Deployment coordination only; drop on import, no tenant/account authority."""
    key = models.CharField(max_length=32, primary_key=True)
    last_id = models.CharField(max_length=64, blank=True)

    class Meta:
        app_label = "payments"


class FinanceRetentionPolicyRevision(Immutable):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="finance_policy_revisions")
    policy_version = models.PositiveBigIntegerField()
    receipt_days = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    operation_id = models.UUIDField(unique=True)
    command_digest = models.CharField(max_length=64)
    reason_code = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payments"
        constraints = [models.UniqueConstraint(fields=("makerspace", "policy_version"), name="finance_policy_revision_unique")]
