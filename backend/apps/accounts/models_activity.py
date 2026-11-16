"""Deployment-local session activity; no token or attestation identity is retained."""

from django.db import models


class DeviceActivityDay(models.Model):
    grant = models.ForeignKey("accounts.DeviceGrant", on_delete=models.CASCADE)
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, blank=True, on_delete=models.CASCADE)
    platform = models.CharField(max_length=16)
    # The app build the person ran that day, from the optional X-SpaceWorks-App-Version header.
    app_version = models.CharField(max_length=32, blank=True, default="")
    local_day = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["grant", "makerspace", "local_day"], nulls_distinct=False,
            name="unique_grant_space_activity_day",
        )]


class WebSessionActivityDay(models.Model):
    """One browser session active on one local day. ``session_hash`` is a keyed digest of the
    session marker, never the marker, a token, an address or a user agent."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    session_hash = models.CharField(max_length=32)
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, blank=True, on_delete=models.CASCADE)
    local_day = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["user", "session_hash", "makerspace", "local_day"], nulls_distinct=False,
            name="unique_web_session_space_activity_day",
        )]


class ChannelUsageDay(models.Model):
    """Authenticated API calls per channel (web, ios, android, api_client) and area per UTC day.

    Counts only: no person, session, address or path is stored. ``area`` is the app that serves
    the route. Deployment-local telemetry, flushed from a cache by a beat task."""

    channel = models.CharField(max_length=16)
    area = models.CharField(max_length=48)
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, blank=True, on_delete=models.CASCADE)
    day = models.DateField()
    count = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["channel", "area", "makerspace", "day"], nulls_distinct=False,
            name="unique_channel_area_space_day",
        )]


class AttestationVerificationLog(models.Model):
    platform = models.CharField(max_length=16)
    mode = models.CharField(max_length=32)
    outcome = models.CharField(max_length=16, choices=[
        ("sent", "Verified"), ("failed", "Rejected"), ("skipped", "Unavailable"),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
