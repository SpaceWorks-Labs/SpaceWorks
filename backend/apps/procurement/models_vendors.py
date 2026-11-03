"""Saved suppliers (machines D12 = inventory D12, PC1).

A vendor is the space's own business record: a company name and how to reach its sales
desk. Contact fields are business data, kept exactly like `Warranty.vendor_contact` and
`LedgerEntry.counterparty` already are (staff-only, exported with the space). To-Buy
purchases and warranties point at a vendor; archiving one keeps every link.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class Vendor(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="vendors")
    name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(max_length=254, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    website = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(Lower("name"), "makerspace", condition=Q(is_archived=False),
                                    name="procurement_vendor_live_name_unique"),
        ]

    def __str__(self):
        return self.name
