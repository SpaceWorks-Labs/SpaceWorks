"""Decision 223: guest passes, day-pass products and the per-space guest policy."""
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("makerspaces", "0136_loan_policy_account_self_renewal"),
    ]

    operations = [
        migrations.CreateModel(
            name="GuestPassPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("guest_borrowing_mode", models.CharField(
                    choices=[("none", "No borrowing"), ("on_site", "On site only, due by the end of the pass"),
                             ("full_with_deposit", "Full borrowing with a mandatory deposit")],
                    default="on_site", max_length=24)),
                ("guest_machine_mode", models.CharField(
                    choices=[("none", "No machine use"), ("supervised", "Supervised use in an instructor's session"),
                             ("after_induction_cert", "After a certification from an induction event")],
                    default="none", max_length=24)),
                ("sponsored_liability", models.CharField(
                    choices=[("guest", "The guest is the accountable borrower"), ("sponsor", "The sponsor pays")],
                    default="guest", max_length=16)),
                ("walk_in_registration_creates", models.CharField(
                    choices=[("guest_pass", "A guest pass"), ("membership", "A full membership")],
                    default="guest_pass", max_length=16)),
                ("waiver_required_on_site", models.BooleanField(default=True)),
                ("sponsor_min_tenure_days", models.PositiveIntegerField(
                    default=30, validators=[django.core.validators.MaxValueValidator(3650)])),
                ("max_concurrent_guests_per_sponsor", models.PositiveIntegerField(
                    default=2, validators=[django.core.validators.MinValueValidator(1),
                                           django.core.validators.MaxValueValidator(50)])),
                ("sponsor_must_be_present", models.BooleanField(default=True)),
                ("visits_before_join_prompt", models.PositiveIntegerField(
                    default=4, validators=[django.core.validators.MinValueValidator(1)])),
                ("hard_visit_cap", models.PositiveIntegerField(
                    blank=True, null=True, validators=[django.core.validators.MinValueValidator(1)])),
                ("day_pass_daily_cap", models.PositiveIntegerField(
                    blank=True, null=True, validators=[django.core.validators.MinValueValidator(1)])),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE, related_name="guest_pass_policy",
                    to="makerspaces.makerspace")),
                ("updated_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="DayPassProduct",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("amount", models.DecimalField(
                    decimal_places=2, default=0, max_digits=10,
                    validators=[django.core.validators.MinValueValidator(0)])),
                ("currency", models.CharField(blank=True, default="", max_length=3)),
                ("entitlements", models.JSONField(blank=True, default=dict)),
                ("daily_cap", models.PositiveIntegerField(
                    blank=True, null=True, validators=[django.core.validators.MinValueValidator(1)])),
                ("is_public", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="day_pass_products",
                    to="makerspaces.makerspace")),
            ],
            options={"ordering": ["name", "pk"]},
        ),
        migrations.AddIndex(
            model_name="daypassproduct",
            index=models.Index(fields=["makerspace", "is_active"], name="daypass_space_active_idx"),
        ),
        migrations.CreateModel(
            name="GuestPass",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(
                    choices=[("event", "Event guest"), ("sponsored", "Sponsored guest"), ("day", "Day pass")],
                    max_length=12)),
                ("status", models.CharField(
                    choices=[("issued", "Issued"), ("active", "Active"), ("expired", "Expired"),
                             ("revoked", "Revoked"), ("converted", "Converted to membership")],
                    default="issued", max_length=12)),
                ("valid_from", models.DateTimeField()),
                ("valid_until", models.DateTimeField()),
                ("pass_date", models.DateField()),
                ("entitlements", models.JSONField(default=dict)),
                ("waiver_version", models.CharField(blank=True, max_length=64, null=True)),
                ("waiver_accepted_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_reason", models.CharField(blank=True, default="", max_length=255)),
                ("operation_id", models.CharField(blank=True, max_length=64, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accepted_waiver", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+",
                    to="makerspaces.makerspacewaiver")),
                ("converted_membership", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to="makerspaces.makerspacemembership")),
                ("holder", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="guest_passes",
                    to=settings.AUTH_USER_MODEL)),
                ("issued_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to=settings.AUTH_USER_MODEL)),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="guest_passes",
                    to="makerspaces.makerspace")),
                ("product", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="passes",
                    to="makerspaces.daypassproduct")),
                ("revoked_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to=settings.AUTH_USER_MODEL)),
                ("sponsor", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="sponsored_guest_passes", to=settings.AUTH_USER_MODEL)),
                ("sponsor_membership", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to="makerspaces.makerspacemembership")),
            ],
            options={"ordering": ["-valid_from", "-pk"]},
        ),
        migrations.AddConstraint(
            model_name="guestpass",
            constraint=models.CheckConstraint(
                condition=Q(("valid_until__gt", F("valid_from"))), name="guest_pass_window_ordered"),
        ),
        migrations.AddConstraint(
            model_name="guestpass",
            constraint=models.CheckConstraint(
                condition=(Q(accepted_waiver__isnull=True, waiver_version__isnull=True, waiver_accepted_at__isnull=True)
                           | Q(accepted_waiver__isnull=False, waiver_version__isnull=False,
                               waiver_accepted_at__isnull=False)),
                name="guest_pass_waiver_all_or_none"),
        ),
        migrations.AddConstraint(
            model_name="guestpass",
            constraint=models.UniqueConstraint(
                condition=Q(status__in=["issued", "active"]), fields=("makerspace", "holder", "pass_date"),
                name="guest_pass_one_live_per_holder_day"),
        ),
        migrations.AddConstraint(
            model_name="guestpass",
            constraint=models.UniqueConstraint(
                condition=Q(operation_id__isnull=False), fields=("makerspace", "operation_id"),
                name="guest_pass_operation_unique"),
        ),
        migrations.AddIndex(
            model_name="guestpass",
            index=models.Index(fields=["makerspace", "holder", "valid_until"], name="guest_pass_holder_idx"),
        ),
        migrations.AddIndex(
            model_name="guestpass",
            index=models.Index(fields=["makerspace", "sponsor", "status"], name="guest_pass_sponsor_idx"),
        ),
    ]
