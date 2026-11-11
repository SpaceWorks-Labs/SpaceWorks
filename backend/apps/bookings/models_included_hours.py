"""Decision 221(d): the per-term ledger of a membership plan's included booking hours.

Usage is never a mutable counter: it is the sum of these rows. A `consume` row holds
the included minutes one booking took from one term; a `reverse` row (pointing at the
consume row it undoes) gives them back when the booking is rejected or cancelled
within the refund policy. Rows are insert-only; a restored booking takes a NEW consume
row with the next `generation`, so one booking holds at most one live consumption.
"""

from django.db import models
from django.db.models import Q


class IncludedHoursUsage(models.Model):
    class Kind(models.TextChoices):
        BOOKING = "booking", "Room booking hours"
        MACHINE = "machine", "Machine time hours"

    class Entry(models.TextChoices):
        CONSUME = "consume", "Consumed"
        REVERSE = "reverse", "Reversed"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    term = models.ForeignKey("makerspaces.MembershipTerm", on_delete=models.CASCADE, related_name="+")
    booking = models.ForeignKey("bookings.Booking", on_delete=models.CASCADE, related_name="included_hours")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    entry = models.CharField(max_length=8, choices=Entry.choices)
    minutes = models.PositiveIntegerField()
    generation = models.PositiveIntegerField(default=1)
    reverses = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [
            models.CheckConstraint(condition=Q(minutes__gt=0), name="incl_hours_minutes_positive"),
            models.CheckConstraint(
                condition=Q(entry="consume", reverses__isnull=True) | Q(entry="reverse", reverses__isnull=False),
                name="incl_hours_reverse_points_back",
            ),
            models.UniqueConstraint(fields=["makerspace", "booking", "generation"], condition=Q(entry="consume"),
                                    name="incl_hours_one_consume_per_generation"),
            models.UniqueConstraint(fields=["makerspace", "reverses"], condition=Q(entry="reverse"),
                                    name="incl_hours_one_reversal"),
        ]
        indexes = [models.Index(fields=["term", "kind"], name="incl_hours_term_kind_idx")]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("IncludedHoursUsage rows are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("IncludedHoursUsage rows are append-only.")
