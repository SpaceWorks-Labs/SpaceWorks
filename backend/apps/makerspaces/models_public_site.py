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
    public_stats_show_holder_names = models.BooleanField(default=False)
    # "Closed for now" banner on the public page (#77). Text only; no lifecycle state.
    public_closed_notice = models.CharField(max_length=280, blank=True, default="")
    public_reopens_on = models.DateField(null=True, blank=True)

    class Meta:
        abstract = True
