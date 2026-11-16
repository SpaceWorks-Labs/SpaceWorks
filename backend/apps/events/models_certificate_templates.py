"""Private artwork and immutable, event-owned certificate design revisions."""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.db import models
from uuid import uuid4


class EventCertificateArtwork(models.Model):
    resource_id = models.UUIDField(default=uuid4, unique=True, editable=False)
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
                raise ValidationError(gettext("Certificate artwork is immutable after promotion."))
        return super().save(*args, **kwargs)


class EventCertificateTemplateRevision(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE,
                              related_name="certificate_template_revisions")
    artwork = models.ForeignKey(EventCertificateArtwork, on_delete=models.PROTECT,
                                null=True, blank=True, related_name="template_revisions")
    parameters = models.JSONField(default=dict)
    # "" is the event's default design; a certificate kind (winner, mentor_thanks, …) is that
    # kind's own design. Issuance uses the kind's latest design, else the latest default.
    certificate_kind = models.CharField(max_length=24, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-id",)

    def clean(self):
        from .models_certificates import EventAttendanceCertificate
        if self.certificate_kind and self.certificate_kind not in EventAttendanceCertificate.Kind.values:
            raise ValidationError({"certificate_kind": gettext("Choose a certificate kind or the default design.")})
        if self.artwork_id and (self.artwork.event_id != self.event_id
                                or self.artwork.promoted_at is None):
            raise ValidationError(gettext("Use promoted artwork belonging to this event."))

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(gettext("Certificate template revisions are immutable."))
        self.full_clean()
        return super().save(*args, **kwargs)
