"""Global replay coordination; a receipt never grants organization authority."""
from django.conf import settings
from django.db import models


class OrganizationLeaveReceipt(models.Model):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="leave_receipts")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    operation_id = models.UUIDField()
    expected_version = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("organization", "actor", "operation_id"),
                                               name="uniq_org_leave_operation")]
