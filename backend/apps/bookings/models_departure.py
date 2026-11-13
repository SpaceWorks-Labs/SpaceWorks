"""Typed leave remarks: an append-only departure history plus a mutable issue triage row.

`BookingDepartureEvent` is the evidence (who said what, when, from which surface) and is
protected by a Postgres trigger exactly like `BookingCheckInEvent`; its free-text remark is
scoped PII. Anything other than "all good" opens one `BookingIssue`, whose only mutation is
the staff resolution -- the event it points at never changes.
"""

from django.utils.translation import gettext_noop
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin


class DepartureOutcome(models.TextChoices):
    ALL_GOOD = "all_good", gettext_noop("All good")
    ISSUE = "issue", gettext_noop("Something was wrong")
    DAMAGED = "damaged", gettext_noop("Something was damaged")
    LEFT_EARLY = "left_early", gettext_noop("Left early")


class DepartureSource(models.TextChoices):
    STAFF = "staff", "Staff"
    MEMBER = "member", "Member"


class BookingDepartureFields(models.Model):
    departed_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_reason = models.TextField(blank=True, default="")

    class Meta:
        abstract = True


class BookingDepartureEvent(ScopedPiiModelMixin, models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT, related_name="+")
    booking = models.ForeignKey("bookings.Booking", on_delete=models.PROTECT,
                                related_name="departure_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    outcome = models.CharField(max_length=16, choices=DepartureOutcome.choices)
    remark = models.TextField(blank=True, default="")
    source = models.CharField(max_length=8, choices=DepartureSource.choices)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["recorded_at", "pk"]
        constraints = [
            models.CheckConstraint(condition=Q(outcome__in=DepartureOutcome.values),
                                   name="booking_departure_outcome"),
            models.CheckConstraint(condition=Q(source__in=DepartureSource.values),
                                   name="booking_departure_source"),
            models.CheckConstraint(condition=Q(outcome="all_good") | ~Q(remark=""),
                                   name="booking_departure_remark_required"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("BookingDepartureEvent rows are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("BookingDepartureEvent rows are append-only.")


class BookingIssue(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT,
                                   related_name="booking_issues")
    booking = models.ForeignKey("bookings.Booking", on_delete=models.PROTECT, related_name="issues")
    departure = models.OneToOneField(BookingDepartureEvent, on_delete=models.PROTECT, related_name="issue")
    outcome = models.CharField(max_length=16, choices=DepartureOutcome.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="+")
    resolution_note = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["makerspace", "resolved_at"], name="booking_issue_open_idx")]
        constraints = [models.CheckConstraint(condition=~Q(outcome="all_good"),
                                              name="booking_issue_not_all_good")]
