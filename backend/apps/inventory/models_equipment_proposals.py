"""Inventory-owned kit snapshots and proposal idempotency records.

These records do not reserve or consume inventory. Optional event and booking
contexts belong to those domains and must not become foreign keys here.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.encryption.mappers import ScopedPiiModelMixin


class EquipmentKitTemplate(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    revision = models.PositiveBigIntegerField(default=1)
    current_version = models.PositiveIntegerField(default=1)
    published_for_contexts = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class EquipmentKitVersion(models.Model):
    template = models.ForeignKey(EquipmentKitTemplate, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    name = models.CharField(max_length=200)
    lines = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["template", "version"], name="uniq_equipment_kit_version"),
        ]


class EquipmentConsumablePlan(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT)
    borrower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    kit_version = models.ForeignKey(EquipmentKitVersion, on_delete=models.PROTECT)
    lines = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class EquipmentKitAllocation(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT)
    request = models.OneToOneField("hardware_requests.HardwareRequest", on_delete=models.PROTECT)
    kit_version = models.ForeignKey(EquipmentKitVersion, on_delete=models.PROTECT)
    lines = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class EquipmentProposalReceipt(ScopedPiiModelMixin, models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT)
    # The original borrower remains on a verified merge shell; replay separately
    # reauthorizes the present actor and uses this identity for the fingerprint.
    borrower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    operation_id = models.UUIDField()
    fingerprint_version = models.PositiveSmallIntegerField(default=2)
    payload_sha256 = models.CharField(max_length=64)
    intent_snapshot = models.TextField()
    intent_version = models.PositiveSmallIntegerField(default=2)
    outcome_kind = models.CharField(max_length=24, choices=[
        ("request", "Request"), ("consumable_plan", "Consumable plan"),
    ])
    imported_nonreplayable = models.BooleanField(default=False)
    request = models.ForeignKey(
        "hardware_requests.HardwareRequest", null=True, blank=True, on_delete=models.PROTECT,
    )
    consumable_plan = models.ForeignKey(
        EquipmentConsumablePlan, null=True, blank=True, on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "operation_id"], name="uniq_equipment_proposal_op"),
            models.CheckConstraint(condition=Q(creator__isnull=False) | Q(imported_nonreplayable=True),
                                   name="equipment_proposal_creator_or_sticky"),
            models.CheckConstraint(
                condition=(
                    Q(request__isnull=False, consumable_plan__isnull=True)
                    | Q(request__isnull=True, consumable_plan__isnull=False)
                ),
                name="equipment_proposal_one_result",
            ),
        ]


class EquipmentConsumableUseReceipt(ScopedPiiModelMixin, models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT)
    operation_id = models.UUIDField()
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    product = models.ForeignKey("inventory.InventoryProduct", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    payload_sha256 = models.CharField(max_length=64)
    intent_snapshot = models.TextField()
    intent_version = models.PositiveSmallIntegerField(default=2)
    imported_nonreplayable = models.BooleanField(default=False)
    allocation = models.ForeignKey(EquipmentKitAllocation, null=True, blank=True, on_delete=models.PROTECT)
    plan = models.ForeignKey(EquipmentConsumablePlan, null=True, blank=True, on_delete=models.PROTECT)
    adjustment = models.OneToOneField("operations.InventoryAdjustment", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "operation_id"], name="uniq_equipment_use_op"),
            models.CheckConstraint(condition=Q(creator__isnull=False) | Q(imported_nonreplayable=True),
                                   name="equipment_use_creator_or_sticky"),
            models.CheckConstraint(
                condition=Q(allocation__isnull=False, plan__isnull=True) | Q(allocation__isnull=True, plan__isnull=False),
                name="equipment_use_one_source",
            ),
        ]
