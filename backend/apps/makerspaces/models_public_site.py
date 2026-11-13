"""Public-site settings, independent of the core hardware catalogue."""

from django.db import models


class PublicSiteSettings(models.Model):
    website_embed_origins = models.JSONField(default=list, blank=True)
    event_default_registration_audience = models.CharField(
        max_length=32, default="members",
        choices=[("members", "Members"), ("accounts", "Authenticated accounts"), ("invite", "Invited accounts"), ("participating_organizations", "Participating organizations")],
    )
    public_inventory_enabled = models.BooleanField(default=True)
    public_site_enabled = models.BooleanField(default=True)
    public_landing_page = models.CharField(
        max_length=16, default="auto",
        choices=[(key, key.title()) for key in
                 ("auto", "inventory", "events", "machines", "bookings", "membership")],
    )
    public_stats_enabled = models.BooleanField(default=False)
    public_stats_config = models.JSONField(default=dict, blank=True)
    public_stats_show_holder_names = models.BooleanField(default=False)
    # Settings › Public stats (#170, `public_stats_settings.py`): ordered section keys and
    # headline metric keys as comma-separated lists, the fixed period and the TV mode.
    public_stats_sections = models.CharField(max_length=120, blank=True, default="machines,printing,lending")
    public_stats_period = models.CharField(
        max_length=8, default="month",
        choices=[("month", "This month"), ("year", "This year"), ("all", "All time"), ("fy", "This financial year")],
    )
    public_stats_headline = models.CharField(max_length=200, blank=True, default="")
    public_stats_tv_mode_enabled = models.BooleanField(default=False)
    public_stats_tv_refresh_seconds = models.PositiveSmallIntegerField(default=60)
    # "Closed for now" banner on the public page (#77). Text only; no lifecycle state.
    public_closed_notice = models.CharField(max_length=280, blank=True, default="")
    public_reopens_on = models.DateField(null=True, blank=True)

    class Meta:
        abstract = True
