"""Deployment-wide cache of fetched card-font files (Q-I2). Not tenant data.

One row per (family, weight) the server has fetched from the open catalogue; the file
lives in private object storage under `card-fonts/` and is served by this app.
"""
from django.db import models


class CardFont(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Preparing"
        READY = "ready", "Ready"
        FAILED = "failed", "Unavailable"

    family = models.CharField(max_length=80)
    weight = models.PositiveSmallIntegerField()
    state = models.CharField(max_length=8, choices=State.choices, default=State.PENDING)
    font_key = models.CharField(max_length=200, blank=True, default="")
    sha256 = models.CharField(max_length=64, blank=True, default="")
    size_bytes = models.PositiveBigIntegerField(default=0)
    error = models.CharField(max_length=48, blank=True, default="")
    requested_at = models.DateTimeField(auto_now_add=True)
    fetched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["family", "weight"], name="uniq_card_font_face")]
        ordering = ["family", "weight"]
