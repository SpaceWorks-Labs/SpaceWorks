"""Space-level card and certificate templates (decision 314/315): a saved design a space can start new designs from.

Built-in templates live in code (`default_templates/`); this table holds only the ones a space saved or imported.
No user FK and no design FK: the author is in the audit row, and `source_design_id` is a plain reference so a
deleted design never breaks the template. The document is a validated v3 CardDesignDocument (it may reference the
space's own uploaded design assets).
"""
from django.db import models
from django.db.models.functions import Lower


class CardTemplate(models.Model):
    class Kind(models.TextChoices):
        CARD = "card", "Card"
        CERTIFICATE = "certificate", "Certificate"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="card_templates")
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=200, blank=True, default="")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.CARD)
    # "" = any design; otherwise the CardDesign.Domain it was made for (a hint for the gallery, never a restriction).
    domain_hint = models.CharField(max_length=16, blank=True, default="")
    stock = models.CharField(max_length=24)
    theme = models.CharField(max_length=5, default="light")
    document = models.JSONField()
    source_design_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["makerspace_id", "name", "pk"]
        constraints = [models.UniqueConstraint(Lower("name"), "makerspace", name="uniq_card_template_name")]
