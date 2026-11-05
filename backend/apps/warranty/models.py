from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Warranty(models.Model):
    makerspace = models.ForeignKey(
        "makerspaces.Makerspace",
        on_delete=models.CASCADE,
        related_name="warranties",
    )
    asset = models.OneToOneField(
        "inventory.InventoryAsset",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="warranty",
    )

    machine = models.OneToOneField(
        "machines.Machine",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="warranty",
    )
    purchased_on = models.DateField(null=True, blank=True)
    warranty_expires_on = models.DateField(null=True, blank=True)
    vendor_name = models.CharField(max_length=200, blank=True)
    vendor_contact = models.CharField(max_length=200, blank=True)
    # The saved supplier (L12 vendor records); the two text fields stay as typed.
    vendor = models.ForeignKey("procurement.Vendor", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="warranties")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # #188: plain-language admin name (the default plural was broken English).
        verbose_name = "warranty"
        verbose_name_plural = "warranties"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(asset__isnull=False, machine__isnull=True)
                    | models.Q(asset__isnull=True, machine__isnull=False)
                ),
                name="warranty_exactly_one_host",
            ),
        ]

    def clean(self):
        errors = {}
        if self.asset_id and self.asset.makerspace_id != self.makerspace_id:
            errors["asset"] = "Asset must belong to the same makerspace."

        if self.machine_id and self.machine.makerspace_id != self.makerspace_id:
            errors["machine"] = "Machine must belong to the same makerspace."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        if self.machine_id:
            return f"Warranty for machine {self.machine}"
        if self.asset_id:
            return f"Warranty for asset {self.asset}"

        return f"Warranty {self.pk}"


class WarrantyDocument(models.Model):
    warranty = models.ForeignKey(
        Warranty,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    object_key = models.CharField(max_length=300, unique=True)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_filename
