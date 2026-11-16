import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("makerspaces", "0098_enabled_modules_choices"),
        ("organizations", "0004_organization_is_discoverable"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HostingRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("invited", "Invited"), ("pending_verification", "Awaiting email confirmation"), ("submitted", "Submitted"), ("accepted", "Accepted"), ("rejected", "Rejected"), ("withdrawn", "Withdrawn")], db_index=True, max_length=24)),
                ("source", models.CharField(choices=[("public", "Public form"), ("invited", "Invitation")], max_length=16)),
                ("inviter_kind", models.CharField(blank=True, choices=[("makerspace", "Makerspace"), ("organization", "Organization")], max_length=16)),
                ("applicant_name", models.CharField(blank=True, max_length=200)),
                ("applicant_email", models.EmailField(blank=True, db_index=True, max_length=254)),
                ("applicant_phone", models.CharField(blank=True, max_length=32)),
                ("space_name", models.CharField(max_length=200)),
                ("proposed_slug", models.SlugField(blank=True)),
                ("location", models.CharField(blank=True, max_length=200)),
                ("space_website_url", models.URLField(blank=True)),
                ("description", models.TextField(blank=True, max_length=2000)),
                ("organization_choice", models.CharField(choices=[("own", "Create my own organization"), ("join", "Join the inviting organization")], default="own", max_length=8)),
                ("new_organization_name", models.CharField(blank=True, max_length=200)),
                ("invite_note", models.CharField(blank=True, max_length=500)),
                ("invite_token_digest", models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ("invite_expires_at", models.DateTimeField(blank=True, null=True)),
                ("access_token_digest", models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ("verification_expires_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("withdrawn_at", models.DateTimeField(blank=True, null=True)),
                ("redacted_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.TextField(blank=True, max_length=2000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_makerspace", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="makerspaces.makerspace")),
                ("decided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("invited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("inviter_makerspace", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="makerspaces.makerspace")),
                ("inviter_organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="organizations.organization")),
            ],
            options={
                "ordering": ("-created_at", "-id"),
                "indexes": [
                    models.Index(fields=["status", "created_at"], name="hostreq_status_created"),
                    models.Index(fields=["source", "status", "verification_expires_at"], name="hostreq_verify_sweep"),
                ],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("status", "rejected"), _negated=True) | models.Q(("rejection_reason", ""), _negated=True), name="hostreq_rejected_has_reason"),
                    models.CheckConstraint(condition=models.Q(("status__in", ("accepted", "rejected")), _negated=True) | models.Q(("decided_at__isnull", False)), name="hostreq_decided_has_time"),
                    models.CheckConstraint(condition=models.Q(("status", "withdrawn"), _negated=True) | models.Q(("withdrawn_at__isnull", False)), name="hostreq_withdrawn_has_time"),
                    models.CheckConstraint(condition=models.Q(("source", "public"), _negated=True) | models.Q(("invite_token_digest__isnull", True), ("inviter_kind", "")), name="hostreq_public_has_no_inviter"),
                    models.CheckConstraint(condition=models.Q(("source", "invited"), _negated=True) | models.Q(("inviter_kind", ""), _negated=True), name="hostreq_invited_has_inviter"),
                ],
            },
        ),
    ]
