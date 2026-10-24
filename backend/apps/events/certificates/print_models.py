from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class EventBadgeTemplateRevision(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="badge_template_revisions")
    document = models.JSONField()
    stock = models.CharField(max_length=24)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Badge template revisions are immutable.")
        return super().save(*args, **kwargs)


class BadgePrintJob(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    operation_id = models.UUIDField()
    request_sha256 = models.CharField(max_length=64)
    event_version = models.PositiveIntegerField(default=0)
    fields_sha256 = models.CharField(max_length=64)
    template = models.JSONField()
    template_revision = models.ForeignKey(EventBadgeTemplateRevision, on_delete=models.PROTECT)
    stock = models.CharField(max_length=24)
    include_photo = models.BooleanField(default=False)
    registration_ids = models.JSONField(default=list)
    state = models.CharField(max_length=12, default="queued")
    render_token = models.UUIDField(null=True, blank=True)
    render_started_at = models.DateTimeField(null=True, blank=True)
    row_failures = models.JSONField(default=list)
    object_key = models.CharField(max_length=512, unique=True)
    sha256 = models.CharField(max_length=64, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    cleaned_at = models.DateTimeField(null=True, blank=True)
    next_cleanup_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("event", "operation_id"), name="event_badge_print_op")]

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.get(pk=self.pk)
            frozen = ("event_id", "operation_id", "request_sha256", "event_version", "fields_sha256",
                      "template", "template_revision_id", "stock", "include_photo", "registration_ids",
                      "object_key", "created_at", "expires_at")
            if any(getattr(old, key) != getattr(self, key) for key in frozen):
                raise ValidationError("Print-job snapshots are immutable. Prepare a new job.")
        return super().save(*args, **kwargs)


class BadgePrintResource(models.Model):
    job = models.ForeignKey(BadgePrintJob, on_delete=models.CASCADE, related_name="resources")
    registration = models.ForeignKey("events.EventRegistration", on_delete=models.CASCADE)
    kind = models.CharField(max_length=8, choices=((key, key) for key in ("photo", "logo", "qr")))
    credential = models.ForeignKey("events.EventRegistrationCredential", on_delete=models.CASCADE,
                                   null=True, blank=True)
    credential_generation = models.PositiveIntegerField(default=0)
    presentation = models.ForeignKey("events.EventMemberPresentation", on_delete=models.SET_NULL,
                                     null=True, blank=True)
    presentation_version = models.PositiveIntegerField(default=0)
    source_profile_id = models.PositiveBigIntegerField(null=True, blank=True)
    source_avatar_revision = models.CharField(max_length=64, blank=True)
    source_key_sha256 = models.CharField(max_length=64, blank=True)
    object_key = models.CharField(max_length=512, unique=True, null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    bound_at = models.DateTimeField(null=True, blank=True)
    cleaned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("job", "registration", "kind"), name="event_badge_print_resource")]

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.get(pk=self.pk)
            if old.bound_at:
                mutable = {"cleaned_at"}
                fields = [field.attname for field in self._meta.concrete_fields if field.name not in mutable]
                if any(getattr(old, key) != getattr(self, key) for key in fields):
                    raise ValidationError("Bound print resources are immutable.")
        return super().save(*args, **kwargs)


class BadgePrintCleanupReceipt(models.Model):
    """Permanent, FK-free locator custody survives event and tenant deletion."""
    makerspace_id_snapshot = models.PositiveBigIntegerField()
    event_id_snapshot = models.PositiveBigIntegerField()
    object_key = models.CharField(max_length=512, unique=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    released = models.BooleanField(default=False)
    not_before = models.DateTimeField()
    next_attempt_at = models.DateTimeField()
    cleaned_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)

    def delete(self, *args, **kwargs):
        raise ValidationError("Print cleanup custody is permanent.")
