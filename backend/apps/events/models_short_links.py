"""Event short links (`/e/<7-char base62>`) and their PII-free daily visit counter.

A code points at the event row, never at a URL, so it follows slug and host changes.
One live code per event; regenerating retires the current row and inserts a new one.
Retired rows are kept forever so a printed code can never be issued again. The only
update ever allowed is retiring a live row once (model guard + Postgres trigger in the
migration); deletes happen only inside an authorized purge.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

CODE_PATTERN = r"^[0-9A-Za-z]{7}$"


class EventShortLink(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="short_links")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    code = models.CharField(max_length=7, unique=True, db_collation="C")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    retired_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="+")

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(fields=("event",), condition=Q(retired_at__isnull=True),
                                    name="ev_short_link_one_live"),
            models.CheckConstraint(condition=Q(code__regex=CODE_PATTERN), name="ev_short_link_code_shape"),
            models.CheckConstraint(condition=Q(retired_by__isnull=True) | Q(retired_at__isnull=False),
                                   name="ev_short_link_retired_by_needs_at"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get("force_insert"):
            original = type(self).objects.only("code", "event_id", "makerspace_id", "retired_at").get(pk=self.pk)
            if (original.code, original.event_id, original.makerspace_id) != (
                    self.code, self.event_id, self.makerspace_id) or original.retired_at is not None:
                raise ValueError("A short link can only be retired once; its code never changes.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Short links are retired, never deleted.")


class EventShortLinkVisitDay(models.Model):
    """One integer per event per makerspace-local day. No IP, agent, referrer or person."""

    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="short_link_visit_days")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    day = models.DateField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("day", "id")
        constraints = [models.UniqueConstraint(fields=("event", "day"), name="ev_short_link_visit_day_once")]
