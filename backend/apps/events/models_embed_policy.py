"""Per-space allow-list for the framable event card at `/embed/<slug>/<token>/`."""

from django.conf import settings
from django.db import models


class EventEmbedPolicy(models.Model):
    """Off by default. `allowed_origins` are exact lowercase HTTPS origins (frame-ancestors)."""

    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE,
                                      related_name="event_embed_policy")
    enabled = models.BooleanField(default=False)
    allowed_origins = models.JSONField(default=list, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("makerspace_id",)
