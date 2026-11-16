from django.utils.translation import gettext
from uuid import uuid4
from django.core.exceptions import ValidationError
from django.db import models


class EventCertificateLibraryTemplate(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    version = models.PositiveIntegerField(default=1)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class EventCertificateLibraryArtwork(models.Model):
    template = models.ForeignKey(EventCertificateLibraryTemplate, on_delete=models.CASCADE, related_name="artworks")
    resource_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    object_key = models.CharField(max_length=512, unique=True)
    sha256 = models.CharField(max_length=64)
    size_bytes = models.PositiveBigIntegerField()
    version_id = models.CharField(max_length=1024, blank=True)
    promoted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.get(pk=self.pk).promoted_at:
            raise ValidationError(gettext("Promoted library artwork is immutable."))
        return super().save(*args, **kwargs)


class EventCertificateLibraryRevision(models.Model):
    template = models.ForeignKey(EventCertificateLibraryTemplate, on_delete=models.CASCADE, related_name="revisions")
    parameters = models.JSONField()
    artwork = models.ForeignKey(EventCertificateLibraryArtwork, on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-id",)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(gettext("Library revisions are immutable."))
        return super().save(*args, **kwargs)


class EventCertificateLibraryCommand(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    template = models.ForeignKey(EventCertificateLibraryTemplate, on_delete=models.CASCADE)
    operation_id = models.UUIDField()
    request_sha256 = models.CharField(max_length=64)
    result = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("makerspace", "operation_id"), name="event_cert_library_op")]
