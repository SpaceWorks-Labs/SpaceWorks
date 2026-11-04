"""Append-only records of an issue: its history, photos, dispatches and parts.

None of these rows is ever edited or deleted outside a superadmin capability purge or a
tenant purge (the instance `save`/`delete` refuse it), so the issue page is the durable
accountability trail: who reported, who triaged, every send to a technician (#98), every
visit and remark, parts used and needed, the quote, its approval and the payout.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q


class AppendOnlyError(RuntimeError):
    pass


class AppendOnly(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AppendOnlyError(f"{type(self).__name__} rows are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyError(f"{type(self).__name__} rows are append-only.")


class IssueEvent(AppendOnly):
    class Kind(models.TextChoices):
        REPORTED = "reported", "Reported"
        TRIAGED = "triaged", "Triaged"
        REJECTED = "rejected", "Rejected"
        ASSIGNED = "assigned", "Assigned"
        UNASSIGNED = "unassigned", "Unassigned"
        DISPATCHED = "dispatched", "Sent to technicians"
        VISIT = "visit", "Visit"
        STARTED = "started", "Work started"
        REMARK = "remark", "Remark"
        PARTS_USED = "parts_used", "Parts used"
        PARTS_NEEDED = "parts_needed", "Parts needed"
        QUOTE = "quote", "Quote"
        QUOTE_APPROVED = "quote_approved", "Quote approved"
        QUOTE_DECLINED = "quote_declined", "Quote declined"
        PAYOUT = "payout", "Payout recorded"
        FIXED = "fixed", "Fixed"
        CLOSED = "closed", "Closed"
        SERVICE_STATE = "service_state", "Service state"

    issue = models.ForeignKey("maintenance.IssueReport", on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+")
    contact = models.ForeignKey("maintenance.TechnicianContact", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="+")
    note = models.TextField(blank=True)
    occurred_on = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["issue", "created_at"], name="issue_event_timeline_idx")]


class IssuePhoto(AppendOnly):
    """A private photo uploaded to the staging key and promoted exactly once (Hard Rule)."""

    class Stage(models.TextChoices):
        REPORTED = "reported", "With the report"
        WORK = "work", "During the work"
        FIXED = "fixed", "With the fix"

    issue = models.ForeignKey("maintenance.IssueReport", on_delete=models.CASCADE, related_name="photos")
    stage = models.CharField(max_length=10, choices=Stage.choices)
    object_key = models.CharField(max_length=500, unique=True)
    content_type = models.CharField(max_length=64)
    size_bytes = models.PositiveBigIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class TechnicianDispatch(AppendOnly):
    """One send of an issue to one technician over one channel (#98, C-4). Outbound only."""

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        TELEGRAM = "telegram", "Telegram"
        WHATSAPP = "whatsapp", "WhatsApp"
        SMS = "sms", "SMS"

    class Status(models.TextChoices):
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"

    issue = models.ForeignKey("maintenance.IssueReport", on_delete=models.CASCADE, related_name="dispatches")
    # Contacts are archived, never deleted; only a purge removes one, with its history.
    contact = models.ForeignKey("maintenance.TechnicianContact", on_delete=models.CASCADE,
                                related_name="dispatches")
    channel = models.CharField(max_length=10, choices=Channel.choices)
    status = models.CharField(max_length=10, choices=Status.choices)
    failure_code = models.CharField(max_length=64, blank=True, default="")
    provider_message_id = models.CharField(max_length=255, blank=True, default="")
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="+")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at", "-id"]


class RepairPart(AppendOnly):
    """A part used (stock went down through `availability.py`) or needed (a To-Buy row)."""

    class Kind(models.TextChoices):
        USED = "used", "Used"
        NEEDED = "needed", "Needed"

    issue = models.ForeignKey("maintenance.IssueReport", on_delete=models.CASCADE, related_name="parts")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    product = models.ForeignKey("inventory.InventoryProduct", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="+")
    name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    to_buy_item = models.ForeignKey("procurement.ToBuyItem", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(name="repair_part_quantity_positive", condition=Q(quantity__gt=0)),
        ]
