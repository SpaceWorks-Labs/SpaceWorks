"""Private artwork and immutable, event-owned certificate design revisions."""

from django.core.exceptions import ValidationError
from django.db import models


class EventCertificateArtwork(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE,
                              related_name="certificate_artworks")
    object_key = models.CharField(max_length=512, unique=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    version_id = models.CharField(max_length=1024, blank=True)
    promoted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            if original.promoted_at or (self.event_id, self.object_key, self.created_at) != (
                    original.event_id, original.object_key, original.created_at):
                raise ValidationError("Certificate artwork is immutable after promotion.")
        return super().save(*args, **kwargs)


class EventCertificateTemplateRevision(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE,
                              related_name="certificate_template_revisions")
    artwork = models.ForeignKey(EventCertificateArtwork, on_delete=models.PROTECT,
                                null=True, blank=True, related_name="template_revisions")
    parameters = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-id",)

    def clean(self):
        if self.artwork_id and (self.artwork.event_id != self.event_id
                                or self.artwork.promoted_at is None):
            raise ValidationError("Use promoted artwork belonging to this event.")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Certificate template revisions are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)
