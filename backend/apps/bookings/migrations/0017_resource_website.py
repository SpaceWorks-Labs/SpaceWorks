"""Private editorial pages; existing resources acquire no published website."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bookings", "0016_booking_broadcasts")]
    operations = [
        migrations.CreateModel(name="BookingResourcePage", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("released", models.BooleanField(default=False)),
            ("revision", models.PositiveIntegerField(default=1)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("space", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                related_name="website_page", to="bookings.bookablespace")),
        ]),
        migrations.CreateModel(name="BookingResourcePageAsset", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("object_key", models.CharField(max_length=300, unique=True)),
            ("size_bytes", models.PositiveIntegerField()),
            ("alt_text", models.CharField(max_length=200)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("page", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                related_name="assets", to="bookings.bookingresourcepage")),
        ]),
        migrations.CreateModel(name="BookingResourcePageSection", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("kind", models.CharField(choices=[("rules", "Rules"), ("amenity", "Amenity"),
                ("faq", "FAQ"), ("link", "Link"), ("sponsor", "Sponsor"), ("gallery", "Gallery")], max_length=16)),
            ("slug", models.SlugField(max_length=80)),
            ("title", models.CharField(max_length=200)),
            ("body", models.CharField(blank=True, max_length=10000)),
            ("url", models.URLField(blank=True, max_length=500)),
            ("visibility", models.CharField(choices=[("draft", "Draft"), ("published", "Published")], default="draft", max_length=12)),
            ("position", models.PositiveIntegerField(default=0)),
            ("asset", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                to="bookings.bookingresourcepageasset")),
            ("page", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                related_name="sections", to="bookings.bookingresourcepage")),
        ], options={"ordering": ("position", "id"), "constraints": [
            models.UniqueConstraint(fields=("page", "slug"), name="booking_section_page_slug")]}),
    ]
