"""Append-only review history for organization applications (O-B5).

`Organization.review_status` is the current standing; this table is the history behind
it. Existing organizations are `approved` and have no rows. Global platform data: it is
never part of a tenant dump.
"""
from django.utils.translation import gettext_noop
from django.conf import settings
from django.db import models


class OrganizationReview(models.Model):
    class Action(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        CHANGES_REQUESTED = "changes_requested", gettext_noop("Changes requested")
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"
        SUSPENDED = "suspended", "Suspended"
        REACTIVATED = "reactivated", "Reactivated"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="reviews",
    )
    action = models.CharField(max_length=24, choices=Action.choices)
    reason = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("organization", "action", "created_at"), name="org_review_history_idx")]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("Organization review history is append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Organization review history is append-only.")
