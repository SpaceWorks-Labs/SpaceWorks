"""Anthias players a space has registered and the web assets SpaceWorks made on them (decision 325).

A player's basic-auth password is stored only as Fernet ciphertext (`apps.makerspaces.secrets`), never
returned by any API. Neither model has an accounts.User foreign key: who changed what is in the audit log.
`AnthiasAssetLink` is the mapping that lets an edit update the asset instead of creating a duplicate.
"""
from django.utils.translation import gettext_noop
from django.db import models

from apps.makerspaces.models import Makerspace
from apps.makerspaces.secrets import decrypt_value, encrypt_value


class AnthiasPlayer(models.Model):
    class Status(models.TextChoices):
        NEVER = "never", gettext_noop("Never synced")
        OK = "ok", gettext_noop("In sync")
        ERROR = "error", "Error"

    makerspace = models.ForeignKey(Makerspace, on_delete=models.CASCADE, related_name="anthias_players")
    name = models.CharField(max_length=80)
    host_url = models.CharField(max_length=200)
    username = models.CharField(max_length=80, blank=True, default="")
    password_enc = models.TextField(blank=True, default="")
    api_version = models.CharField(max_length=8, blank=True, default="")  # "v2" or "v1.2", detected
    anthias_version = models.CharField(max_length=40, blank=True, default="")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.NEVER)
    last_error = models.CharField(max_length=200, blank=True, default="")
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["makerspace"], name="anthias_player_space_idx")]

    def set_password(self, raw):
        self.password_enc = encrypt_value(raw)

    def get_password(self):
        return decrypt_value(self.password_enc)


class AnthiasAssetLink(models.Model):
    player = models.ForeignKey(AnthiasPlayer, on_delete=models.CASCADE, related_name="links")
    display = models.ForeignKey("presence.DisplayScreen", on_delete=models.CASCADE, related_name="anthias_links")
    asset_id = models.CharField(max_length=64)
    synced_hash = models.CharField(max_length=64, blank=True, default="")
    uri_hash = models.CharField(max_length=64, blank=True, default="")  # Anthias v1.2 cannot change an asset's uri

    class Meta:
        constraints = [models.UniqueConstraint(fields=["player", "display"], name="anthias_link_player_display")]


class SpaceNowConfig(models.Model):
    """How the space's public "now" page is laid out (decision 325a): sections, order, privacy, refresh."""
    makerspace = models.OneToOneField(Makerspace, on_delete=models.CASCADE, related_name="now_config")
    sections = models.JSONField(default=list, blank=True)  # ordered; empty = the page's built-in default
    privacy = models.CharField(max_length=12, default="profiles")
    refresh_seconds = models.PositiveSmallIntegerField(default=30)
    updated_at = models.DateTimeField(auto_now=True)
