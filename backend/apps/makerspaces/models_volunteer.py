"""Decision 223 (k), lane L3b: volunteer hours and the membership credit they earn.

An entry is hours a member gave (logged by themselves, by staff, or imported from a verified event
shift); staff approve it. Approved minutes convert into `VolunteerCredit` rows under the space's
`CommunityPolicy`. A credit is applied through the membership charge path (`volunteer_credit.py`) as a
recorded, audited reduction of one charge: money owed stays tracked independently of the payments rail.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_noop
from apps.payments.money_model import MoneyDecimalField


class VolunteerHourEntry(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", gettext_noop("Waiting for approval")
        APPROVED = "approved", gettext_noop("Approved")
        REJECTED = "rejected", gettext_noop("Rejected")

    class Source(models.TextChoices):
        MANUAL = "manual", gettext_noop("Logged by hand")
        EVENT_SHIFT = "event_shift", gettext_noop("Verified event shift")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="volunteer_entries")
    minutes = models.PositiveIntegerField()
    worked_on = models.DateField()
    description = models.CharField(max_length=200, blank=True, default="")
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL)
    #: The event-contribution hours row an imported entry came from (no foreign key: core never imports events).
    source_ref = models.PositiveBigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-worked_on", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(minutes__gt=0, minutes__lte=1440), name="volunteer_entry_minutes_range"),
            models.UniqueConstraint(fields=["makerspace", "source", "source_ref"],
                                    condition=Q(source_ref__isnull=False), name="volunteer_entry_source_unique"),
        ]
        indexes = [models.Index(fields=["makerspace", "member", "status"], name="volunteer_entry_member_idx")]


class VolunteerCredit(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", gettext_noop("Available")
        USED = "used", gettext_noop("Applied to a charge")
        VOID = "void", gettext_noop("Voided")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="volunteer_credits")
    #: Approved minutes this credit consumed (0 on the remainder row a partial application leaves).
    minutes_converted = models.PositiveIntegerField(default=0)
    kind = models.CharField(max_length=12, choices=[("discount", "discount"), ("free_days", "free_days")])
    amount = MoneyDecimalField(max_digits=11, decimal_places=3, default=0)
    days = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=3, blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AVAILABLE)
    applied_payment = models.ForeignKey("payments.Payment", null=True, blank=True, on_delete=models.SET_NULL,
                                        related_name="+")
    applied_amount = MoneyDecimalField(max_digits=11, decimal_places=3, null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    split_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    void_reason = models.CharField(max_length=200, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="volunteer_credit_amount_nonneg"),
            models.CheckConstraint(
                condition=~Q(status="used") | Q(applied_at__isnull=False, applied_amount__isnull=False),
                name="volunteer_credit_used_has_application"),
        ]
        indexes = [models.Index(fields=["makerspace", "member", "status"], name="volunteer_credit_member_idx")]
