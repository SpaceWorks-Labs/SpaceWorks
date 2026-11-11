from django.utils.translation import gettext
import secrets

"""Event invitations contain digests only; clear codes are returned once."""

from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import F, Q


class EventInvite(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    # Exactly one of event/series: a series allowlist entry (parity E-B5, B12/B14) admits its email to
    # every occurrence and is never consumed; an event invite keeps its one-event, counted-use rules.
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.CASCADE,
                              related_name="invites")
    series = models.ForeignKey("events.EventSeries", null=True, blank=True, on_delete=models.CASCADE,
                               related_name="invites")
    code_digest = models.CharField(max_length=64, editable=False, default=secrets.token_hex)
    email_digest = models.CharField(max_length=64, blank=True, editable=False, default="")
    max_uses = models.PositiveIntegerField(default=1)
    uses = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if self.event_id and self.event.makerspace_id != self.makerspace_id:
            raise ValidationError({"event": gettext("Event must belong to this makerspace.")})
        if self.series_id and self.series.makerspace_id != self.makerspace_id:
            raise ValidationError({"series": gettext("Series must belong to this makerspace.")})

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["event", "code_digest"], name="event_invite_unique_code"),
            models.UniqueConstraint(fields=["series", "code_digest"], name="event_invite_series_unique_code"),
            models.CheckConstraint(
                condition=(Q(event__isnull=False, series__isnull=True)
                           | Q(event__isnull=True, series__isnull=False)),
                name="event_invite_one_target"),
            models.CheckConstraint(condition=Q(max_uses__gte=1), name="event_invite_positive_limit"),
            models.CheckConstraint(condition=Q(uses__lte=F("max_uses")), name="event_invite_usage_limit"),
        ]
