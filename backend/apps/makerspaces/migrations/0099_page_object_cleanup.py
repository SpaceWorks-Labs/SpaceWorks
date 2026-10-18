"""Persist cleanup intent before image I/O, independently of later rollback."""

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0098_public_pages")]
    operations = [migrations.CreateModel(name="PublicPageObjectCleanup", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("owner_kind", models.CharField(max_length=16, choices=[("makerspace", "Makerspace"), ("organization", "Organization")])),
        ("owner_id", models.PositiveBigIntegerField()), ("page_id", models.PositiveBigIntegerField()),
        ("object_key", models.CharField(max_length=300, unique=True)), ("size_bytes", models.PositiveIntegerField()),
        ("due_at", models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
        ("attempts", models.PositiveIntegerField(default=0)), ("completed_at", models.DateTimeField(null=True)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
    ])]
