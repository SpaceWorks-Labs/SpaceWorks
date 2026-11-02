"""Technician contacts, their coverage and the per-area defaults (#93, #98, #128 C-3/C-4).

A contact is either IN-HOUSE (a person of this space, usually holding the Technician
role) or EXTERNAL (a contractor who never signs in). Phone, email and chat handles are
scoped PII (encrypted). Email always works; Telegram, WhatsApp and SMS only after the
contact completed the one-time opt-in link, recorded here as consent per channel.

An in-house contact's coverage is also the Technician's scope (Q-T1 a): the machine
types, inventory and rooms they may run maintenance on and set service state for.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin

AREA_CHOICES = [("machines", "Machines"), ("inventory", "Inventory"), ("rooms", "Rooms")]
CHANNELS = ("email", "telegram", "whatsapp", "sms")


def default_channels():
    return ["email"]


class TechnicianContact(ScopedPiiModelMixin, models.Model):
    class Kind(models.TextChoices):
        IN_HOUSE = "in_house", "In-house"
        EXTERNAL = "external", "External contractor"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="technician_contacts")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    person = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="+")
    name = models.CharField(max_length=200)
    email = models.TextField(blank=True)
    phone = models.TextField(blank=True)
    telegram_handle = models.TextField(blank=True)
    # Chosen channels (#98); each chat channel still needs its opt-in below.
    channels = models.JSONField(default=default_channels)
    telegram_chat_id = models.TextField(blank=True)
    telegram_opted_in_at = models.DateTimeField(null=True, blank=True)
    whatsapp_opted_in_at = models.DateTimeField(null=True, blank=True)
    sms_opted_in_at = models.DateTimeField(null=True, blank=True)
    # The one-time opt-in link: only a digest of the token is kept.
    opt_in_digest = models.CharField(max_length=64, blank=True, default="")
    opt_in_expires_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(name="technician_external_has_no_person",
                                   condition=Q(kind="in_house") | Q(person__isnull=True)),
            models.UniqueConstraint(fields=["makerspace", "person"], condition=Q(person__isnull=False),
                                    name="technician_one_contact_per_person"),
        ]
        indexes = [models.Index(fields=["opt_in_digest"], name="technician_opt_in_idx")]

    def __str__(self):
        return self.name


class TechnicianCoverage(models.Model):
    """One covered area: a machine type, all inventory, or one room."""

    class Kind(models.TextChoices):
        MACHINE_TYPE = "machine_type", "Machine type"
        INVENTORY = "inventory", "Inventory"
        ROOM = "room", "Room"

    contact = models.ForeignKey(TechnicianContact, on_delete=models.CASCADE, related_name="coverage")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    machine_type = models.ForeignKey("machines.MachineType", null=True, blank=True, on_delete=models.CASCADE,
                                     related_name="+")
    room = models.ForeignKey("bookings.BookableSpace", null=True, blank=True, on_delete=models.CASCADE,
                             related_name="+")

    class Meta:
        constraints = [
            models.CheckConstraint(name="technician_coverage_shape", condition=(
                Q(kind="machine_type", machine_type__isnull=False, room__isnull=True)
                | Q(kind="inventory", machine_type__isnull=True, room__isnull=True)
                | Q(kind="room", machine_type__isnull=True, room__isnull=False))),
            models.UniqueConstraint(fields=["contact", "kind", "machine_type", "room"],
                                    nulls_distinct=False, name="technician_coverage_uniq"),
        ]


class TechnicianDefault(models.Model):
    """Pre-ticked recipients for an area, a machine type or a room (#98)."""

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="technician_defaults")
    area = models.CharField(max_length=10, choices=AREA_CHOICES)
    machine_type = models.ForeignKey("machines.MachineType", null=True, blank=True, on_delete=models.CASCADE,
                                     related_name="+")
    room = models.ForeignKey("bookings.BookableSpace", null=True, blank=True, on_delete=models.CASCADE,
                             related_name="+")
    contact = models.ForeignKey(TechnicianContact, on_delete=models.CASCADE, related_name="defaults")

    class Meta:
        constraints = [
            models.CheckConstraint(name="technician_default_shape", condition=(
                Q(area="machines", room__isnull=True) | Q(area="inventory", machine_type__isnull=True,
                                                          room__isnull=True)
                | Q(area="rooms", machine_type__isnull=True))),
            models.UniqueConstraint(fields=["makerspace", "area", "machine_type", "room", "contact"],
                                    nulls_distinct=False, name="technician_default_uniq"),
        ]
