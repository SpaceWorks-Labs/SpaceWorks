"""A paired space display screen (decision 307c): a TV or kiosk browser that shows the public view.

The screen registers itself and shows a short pairing code; staff claim the code in the console, which
binds the row to one makerspace and sets its panels. The screen's bearer secret is stored only as a
SHA-256 digest, so a database read cannot replay it. The row carries NO accounts.User foreign key on
purpose: who claimed, changed or unpaired it is recorded in the append-only audit log.
"""
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_noop

from apps.makerspaces.models import Makerspace

PANEL_HERE_NOW = "here_now"
PANEL_CALENDAR = "calendar"
PANEL_MACHINES = "machines"
PANEL_ANNOUNCEMENT = "announcement"
PANEL_PUBLIC_STATS = "public_stats"
PANEL_OPENING_HOURS = "opening_hours"
PANEL_INVENTORY = "inventory_highlights"
PANEL_SPONSORS = "sponsors"
PANELS = (PANEL_HERE_NOW, PANEL_CALENDAR, PANEL_MACHINES, PANEL_ANNOUNCEMENT, PANEL_PUBLIC_STATS, PANEL_OPENING_HOURS,
          PANEL_INVENTORY, PANEL_SPONSORS)
PANEL_LABELS = {
    PANEL_HERE_NOW: gettext_noop("Here now"),
    PANEL_CALENDAR: gettext_noop("Events calendar"),
    PANEL_MACHINES: gettext_noop("Machines now"),
    PANEL_ANNOUNCEMENT: gettext_noop("Announcement"),
    PANEL_PUBLIC_STATS: gettext_noop("Public stats"),
    PANEL_OPENING_HOURS: gettext_noop("Opening hours"),
    PANEL_INVENTORY: gettext_noop("Inventory highlights"),
    PANEL_SPONSORS: gettext_noop("Sponsors"),
}
LAYOUTS = ("single", "grid", "playlist")
THEMES = ("dark", "light", "black", "brand", "space")  # "space" follows the space's own default look
# Never less private than the screen was before settings existed: `profiles` IS that behaviour.
PRIVACY_LEVELS = ("profiles", "first_names", "counts")
MIN_REFRESH, MAX_REFRESH, DEFAULT_REFRESH = 10, 600, 30
MIN_ROTATION, MAX_ROTATION, DEFAULT_ROTATION = 5, 120, 15


class DisplayScreen(models.Model):
    makerspace = models.ForeignKey(Makerspace, on_delete=models.CASCADE, null=True, blank=True,
                                   related_name="display_screens")
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    pairing_code = models.CharField(max_length=8, blank=True, default="")
    code_expires_at = models.DateTimeField()
    name = models.CharField(max_length=80, blank=True, default="")
    panels = models.JSONField(default=list, blank=True)
    rotation_seconds = models.PositiveSmallIntegerField(default=DEFAULT_ROTATION)
    announcement = models.CharField(max_length=280, blank=True, default="")
    config_version = models.PositiveIntegerField(default=1)
    layout = models.CharField(max_length=12, default="playlist")
    theme = models.CharField(max_length=8, default="dark")
    privacy = models.CharField(max_length=12, default="profiles")
    refresh_seconds = models.PositiveSmallIntegerField(default=DEFAULT_REFRESH)
    link_secret_enc = models.TextField(blank=True, default="")  # Fernet; only for staff-provisioned (URL) screens
    slide_seconds = models.JSONField(default=dict, blank=True)  # panel -> seconds, playlist layout only
    players = models.ManyToManyField("presence.AnthiasPlayer", blank=True, related_name="screens")
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["pairing_code"], condition=~Q(pairing_code=""),
                                    name="display_screen_live_code_unique"),
            models.CheckConstraint(
                condition=Q(rotation_seconds__gte=MIN_ROTATION) & Q(rotation_seconds__lte=MAX_ROTATION),
                name="display_screen_rotation_range"),
        ]
        indexes = [models.Index(fields=["makerspace", "revoked_at"], name="display_space_revoked_idx")]
