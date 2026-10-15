"""Complete curated speaker, sponsor, venue and page layout content."""

from django.db import migrations, models
import apps.events.website_content


class Migration(migrations.Migration):
    dependencies = [("events", "0032_website_owner_windows")]
    operations = [
        migrations.AddField("eventpage", "tagline", models.CharField(blank=True, max_length=300)),
        migrations.AddField("eventpage", "accent_color", models.CharField(blank=True, max_length=7)),
        migrations.AddField("eventpage", "section_order", models.JSONField(default=apps.events.website_content.default_section_order)),
        migrations.AddField("eventpage", "section_enabled", models.JSONField(default=apps.events.website_content.default_section_enabled)),
        migrations.AddField("eventpage", "venue", models.JSONField(blank=True, null=True)),
        migrations.AddField("eventpagesection", "headline", models.CharField(blank=True, max_length=200)),
        migrations.AddField("eventpagesection", "organization", models.CharField(blank=True, max_length=200)),
        migrations.AddField("eventpagesection", "website_url", models.URLField(blank=True, max_length=500)),
        migrations.AddField("eventpagesection", "linkedin_url", models.URLField(blank=True, max_length=500)),
        migrations.AddField("eventpagesection", "x_url", models.URLField(blank=True, max_length=500)),
        migrations.AddField("eventpagesection", "sponsor_tier", models.CharField(
            choices=[("platinum", "platinum"), ("gold", "gold"), ("silver", "silver"),
                     ("partner", "partner"), ("community_partner", "community_partner")],
            default="community_partner", max_length=24)),
        migrations.AddField("eventpagesection", "icon", models.CharField(blank=True, max_length=40)),
        migrations.AlterField("eventpagesection", "kind", models.CharField(max_length=16, choices=[
            ("intro", "Introduction"), ("logo", "Page logo"), ("speaker", "Speaker"),
            ("track", "Track"), ("room", "Room"), ("sponsor", "Sponsor"), ("faq", "FAQ"),
            ("resource", "Resource"), ("highlight", "Highlight")])),
    ]
