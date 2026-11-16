"""Device Adapter API v1 state (decisions 310-312): hello profile, bindings, status, commands, events.

An adapter is a ``Device`` of kind ``adapter`` (a bridge, vendor service, door controller, shelf pointer
or kiosk) that calls out over the signed device protocol. It is never an ``accounts.User`` and never an
audit actor. Everything here is device-bound operational state: it is OMITTED from exports and tenant
dumps (the adapter re-enrolls and re-binds on the target, see ``data_export/classification_adapter``).
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_noop


class AdapterProfile(models.Model):
    """What the adapter declared in its last hello; one row per adapter device."""

    device = models.OneToOneField("devices.Device", on_delete=models.CASCADE, primary_key=True,
                                  related_name="adapter_profile")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    protocol_version = models.PositiveSmallIntegerField(default=1)
    adapter_kind = models.CharField(max_length=24)
    vendor = models.CharField(max_length=80, blank=True)
    software_version = models.CharField(max_length=40, blank=True)
    firmware = models.CharField(max_length=40, blank=True)
    health = models.CharField(max_length=12, blank=True)
    health_at = models.DateTimeField(null=True, blank=True)
    capabilities = models.JSONField(default=list)  # [{"name": "...", "version": 1}]
    config_version = models.PositiveIntegerField(default=1)
    hello_at = models.DateTimeField(default=timezone.now)


class AdapterBinding(models.Model):
    """One target (machine, door, storage location...) an adapter controls, with the capabilities it serves."""

    class TargetType(models.TextChoices):
        MACHINE = "machine", gettext_noop("Machine")
        MACHINE_TYPE = "machine_type", gettext_noop("Machine type")
        STORAGE_LOCATION = "storage_location", gettext_noop("Storage location")
        ITEM = "item", gettext_noop("Item")
        BOX = "box", gettext_noop("Box")
        DOOR = "door", gettext_noop("Door")
        SPACE = "space", gettext_noop("Space")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="adapter_bindings")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="adapter_bindings")
    target_type = models.CharField(max_length=24, choices=TargetType.choices)
    # A machine target is a real FK (scoping and purge); every other target is an opaque, tenant-checked id.
    machine = models.ForeignKey("machines.Machine", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="adapter_bindings")
    target_id = models.CharField(max_length=64, blank=True)
    external_ref = models.CharField(max_length=120, blank=True)
    capabilities = models.JSONField(default=list)  # names, a subset of the profile's
    # Server-enforced safety config (caps/safety.py CONFIG): auto_off_idle_minutes, require_area_clear, ...
    config = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [models.Index(fields=["device", "enabled"], name="adapter_binding_device_idx")]
        constraints = [
            models.UniqueConstraint(fields=("device", "target_type", "machine"), condition=Q(machine__isnull=False),
                                    name="devices_adapter_binding_machine_once"),
            models.UniqueConstraint(fields=("device", "target_type", "target_id"), condition=~Q(target_id=""),
                                    name="devices_adapter_binding_target_once"),
        ]


class AdapterStatus(models.Model):
    """Latest normalised status of one binding, overwritten in place (advisory; never changes Machine.status)."""

    binding = models.OneToOneField(AdapterBinding, on_delete=models.CASCADE, primary_key=True, related_name="status")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    state = models.CharField(max_length=16)
    payload = models.JSONField(default=dict)
    observed_at = models.DateTimeField()
    received_at = models.DateTimeField()


class AdapterCommand(models.Model):
    """A server-to-adapter command (control, indicate, aim, stream request) delivered by lease and ack."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        LEASED = "leased", "Leased"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="adapter_commands")
    binding = models.ForeignKey(AdapterBinding, on_delete=models.CASCADE, related_name="commands")
    device_key_version = models.PositiveIntegerField()
    capability = models.CharField(max_length=32)
    command = models.CharField(max_length=32)
    params = models.JSONField(default=dict)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    attempts = models.PositiveIntegerField(default=0)
    lease_token_digest = models.CharField(max_length=64, null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    result_code = models.CharField(max_length=48, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [models.Index(fields=["device", "status", "created_at"], name="adapter_command_delivery_idx")]
        constraints = [models.CheckConstraint(
            condition=~Q(status="leased") | (Q(lease_token_digest__isnull=False) & Q(lease_expires_at__isnull=False)),
            name="adapter_command_lease_complete")]


class AdapterEvent(models.Model):
    """Append-only typed event an adapter reported; idempotent by (device, operation_id)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="adapter_events")
    binding = models.ForeignKey(AdapterBinding, null=True, blank=True, on_delete=models.SET_NULL, related_name="events")
    operation_id = models.UUIDField()
    event_type = models.CharField(max_length=48)
    capability = models.CharField(max_length=32)
    data = models.JSONField(default=dict)
    observed_at = models.DateTimeField()
    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-received_at",)
        indexes = [models.Index(fields=["device", "received_at"], name="adapter_event_device_idx")]
        constraints = [models.UniqueConstraint(fields=("device", "operation_id"), name="adapter_event_once")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("AdapterEvent rows are append-only.")
        return super().save(*args, **kwargs)
