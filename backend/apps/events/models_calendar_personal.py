"""Release 2 L18: one person's private calendar links beyond the per-area feeds.

`kind=shifts` is their approved volunteer and mentor shifts (`events.shifts_feed`);
`kind=combined` is their bookings, event registrations and shifts in one feed
(`calendar.combined_feed`, C-14e). Bearer links like `MemberCalendarFeed`: only the SHA-256
digest is stored, the raw 256-bit token is shown once, and rotation or revocation kills the
old link. The rows never travel with a tenant move (the person re-issues their link).
"""

from django.utils.translation import gettext_noop
from django.conf import settings
from django.db import models


class PersonalCalendarFeed(models.Model):
    class Kind(models.TextChoices):
        SHIFTS = "shifts", gettext_noop("My shifts")
        COMBINED = "combined", gettext_noop("Everything of mine")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    token_digest = models.BinaryField(max_length=32, unique=True)
    token_hint = models.CharField(max_length=8)
    created_at = models.DateTimeField(auto_now_add=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["makerspace", "user", "kind"],
                                               name="personal_calendar_feed_one_per_kind")]
