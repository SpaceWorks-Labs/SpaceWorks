"""Account-wide mail allowances survive tenant and delivery-log deletion."""
from django.db import models


class CloudEmailBudgetAccount(models.Model):
    key = models.CharField(max_length=80, unique=True)
    provider = models.CharField(max_length=16)
    reset_timezone = models.CharField(max_length=64)


class CloudEmailReservation(models.Model):
    account = models.ForeignKey(CloudEmailBudgetAccount, on_delete=models.PROTECT)
    log = models.ForeignKey("integrations.EmailLog", null=True, on_delete=models.SET_NULL)
    attempt_key = models.CharField(max_length=200, unique=True)
    provider = models.CharField(max_length=16)
    day = models.DateField()
    month = models.DateField()
    accepted_day = models.DateField(null=True)
    accepted_month = models.DateField(null=True)
    recipients = models.PositiveIntegerField()
    state = models.CharField(max_length=12, choices=[(v, v) for v in (
        "reserved", "accepted", "uncertain", "released",
    )])
    provider_message_id = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(recipients__gte=1), name="cloud_email_recipients_positive"),
            models.CheckConstraint(condition=models.Q(state__in=["reserved", "accepted", "uncertain", "released"]),
                                   name="cloud_email_state_valid"),
        ]
        indexes = [
            models.Index(fields=["account", "state", "day"], name="cloud_email_account_day"),
            models.Index(fields=["account", "state", "month"], name="cloud_email_account_month"),
        ]
