"""Decision 223 (k) / open item B13: an organization hours bank for house and partner-event bookings.

`OrganizationHoursAllowance` is the staff-set base allowance of one organization at one space (minutes, optionally
resetting every month or year). `OrganizationHoursLedger` is the append-only history around it: a booking's
`consume` row (negative), the `release` row that gives it back (positive, pointing at the consume row), and the
staff `grant` / `adjust` rows. The balance is never stored: it is the allowance plus the sum of the ledger rows of
the period being read (see `organization_hours`). Both rows reference a deployment-global organization, so neither
travels in a tenant export (same rule as `BookingOrganizationLink`).
"""
from django.conf import settings
from django.db import models
from django.db.models import Q


class OrganizationHoursAllowance(models.Model):
    class Period(models.TextChoices):
        NONE = "none", "One pool, never resets"
        MONTHLY = "monthly", "Resets every calendar month"
        YEARLY = "yearly", "Resets every calendar year"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="+")
    allowance_minutes = models.PositiveIntegerField(default=0)
    period = models.CharField(max_length=8, choices=Period.choices, default=Period.NONE)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["makerspace", "organization"],
                                               name="org_hours_allowance_one_per_org_space")]


class OrganizationHoursLedger(models.Model):
    class Entry(models.TextChoices):
        GRANT = "grant", "Granted"
        CONSUME = "consume", "Consumed by a booking"
        RELEASE = "release", "Released from a booking"
        ADJUST = "adjust", "Adjusted"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="+")
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="organization_hours")
    entry = models.CharField(max_length=8, choices=Entry.choices)
    #: Signed: consume is negative, release / grant positive, adjust either.
    minutes = models.IntegerField()
    #: "all", "YYYY-MM" or "YYYY": the period whose balance this row belongs to.
    period_key = models.CharField(max_length=8)
    generation = models.PositiveIntegerField(default=1)
    reverses = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    reason = models.CharField(max_length=500, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(condition=~Q(minutes=0), name="org_hours_minutes_nonzero"),
            models.CheckConstraint(
                condition=(Q(entry="consume", minutes__lt=0, booking__isnull=False, reverses__isnull=True)
                           | Q(entry="release", minutes__gt=0, booking__isnull=False, reverses__isnull=False)
                           | Q(entry="grant", minutes__gt=0, booking__isnull=True, reverses__isnull=True)
                           | Q(entry="adjust", booking__isnull=True, reverses__isnull=True)),
                name="org_hours_entry_shape"),
            models.UniqueConstraint(fields=["makerspace", "booking", "generation"], condition=Q(entry="consume"),
                                    name="org_hours_one_consume_per_generation"),
            models.UniqueConstraint(fields=["makerspace", "reverses"], condition=Q(entry="release"),
                                    name="org_hours_one_release"),
        ]
        indexes = [models.Index(fields=["makerspace", "organization", "period_key"], name="org_hours_period_idx")]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("OrganizationHoursLedger rows are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("OrganizationHoursLedger rows are append-only.")
