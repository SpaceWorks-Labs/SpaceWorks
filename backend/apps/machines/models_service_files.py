"""Staged and attached files of machine-service requests (split from models_service_requests)."""

from django.db import models

from .models_service_requests import MachineServiceRequest, ServiceQueue


class ServiceRequestFile(models.Model):
    class Kind(models.TextChoices):
        ATTACHMENT = "attachment", "Attachment"
        MODEL = "model", "Model"
        ESTIMATE = "estimate", "Estimate"
        PREVIEW = "preview", "Preview"
        SCREENSHOT = "screenshot", "Screenshot"

    service_request = models.ForeignKey(
        MachineServiceRequest, null=True, blank=True, on_delete=models.CASCADE, related_name="files"
    )
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT, related_name="service_request_files")
    machine = models.ForeignKey("machines.Machine", null=True, blank=True, on_delete=models.SET_NULL, related_name="service_request_files")
    queue = models.ForeignKey(ServiceQueue, null=True, blank=True, on_delete=models.PROTECT, related_name="staged_files")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    object_key = models.CharField(max_length=255, unique=True)
    content_type = models.CharField(max_length=128, blank=True)
    original_filename = models.CharField(max_length=255, blank=True, default="")
    size_bytes = models.PositiveBigIntegerField(default=0)
    owner_user_id = models.BigIntegerField()
    file_policy_name = models.CharField(max_length=64, default="documents")
    file_policy_version = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    attached_at = models.DateTimeField(null=True, blank=True)
    legacy_print_request_file_id = models.PositiveIntegerField(null=True, blank=True, unique=True, editable=False)

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        if self._state.adding and self.makerspace_id is None and self.machine_id:
            self.makerspace_id = self.machine.makerspace_id
        if self.pk:
            original = type(self).objects.only(
                "attached_at", "owner_user_id", "object_key", "size_bytes", "content_type", "original_filename",
                "file_policy_name", "file_policy_version",
            ).get(pk=self.pk)
            if original.attached_at and any(
                getattr(self, field) != getattr(original, field)
                for field in (
                    "owner_user_id", "object_key", "size_bytes", "content_type", "original_filename",
                    "file_policy_name", "file_policy_version",
                )
            ):
                raise RuntimeError("Attached ServiceRequestFile metadata is immutable.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.kind}:{self.object_key}"

