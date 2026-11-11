"""Decision 223 (k), lane L3b: community policy, minors and guardian consent, volunteer hours and credit."""
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import F, Q


def _user(null=True, rel="+"):
    return models.ForeignKey(blank=null, null=null, on_delete=django.db.models.deletion.SET_NULL,
                             related_name=rel, to=settings.AUTH_USER_MODEL)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("payments", "0046_guest_pass_subject"),
        ("makerspaces", "0137_guest_passes"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommunityPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("minors_admitted", models.BooleanField(default=False)),
                ("minors_minimum_age", models.PositiveSmallIntegerField(
                    default=13, validators=[django.core.validators.MaxValueValidator(17)])),
                ("adult_age", models.PositiveSmallIntegerField(
                    default=18, validators=[django.core.validators.MinValueValidator(16),
                                            django.core.validators.MaxValueValidator(21)])),
                ("guardian_must_be_present", models.BooleanField(default=True)),
                ("minors_may_borrow", models.BooleanField(default=False)),
                ("minors_may_use_machines", models.BooleanField(default=False)),
                ("consent_valid_days", models.PositiveIntegerField(
                    default=365, validators=[django.core.validators.MinValueValidator(1),
                                             django.core.validators.MaxValueValidator(1825)])),
                ("volunteer_minutes_per_credit", models.PositiveIntegerField(
                    default=0, validators=[django.core.validators.MaxValueValidator(100000)])),
                ("volunteer_credit_kind", models.CharField(
                    choices=[("discount", "A discount amount"), ("free_days", "Free days on the next term")],
                    default="discount", max_length=12)),
                ("volunteer_credit_amount", models.DecimalField(
                    decimal_places=2, default=0, max_digits=10,
                    validators=[django.core.validators.MinValueValidator(0)])),
                ("volunteer_credit_days", models.PositiveIntegerField(
                    default=0, validators=[django.core.validators.MaxValueValidator(366)])),
                ("join_followup_enabled", models.BooleanField(default=False)),
                ("join_followup_delay_hours", models.PositiveIntegerField(
                    default=24, validators=[django.core.validators.MinValueValidator(1),
                                            django.core.validators.MaxValueValidator(336)])),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE, related_name="community_policy",
                    to="makerspaces.makerspace")),
                ("updated_by", _user()),
            ],
        ),
        migrations.CreateModel(
            name="GuardianConsentTerms",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                ("version", models.CharField(max_length=64)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("superseded_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", _user()),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="guardian_terms",
                    to="makerspaces.makerspace")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="guardianconsentterms",
            constraint=models.UniqueConstraint(fields=("makerspace", "version"), name="guardian_terms_version_unique"),
        ),
        migrations.AddConstraint(
            model_name="guardianconsentterms",
            constraint=models.UniqueConstraint(condition=Q(is_active=True), fields=("makerspace",),
                                               name="guardian_terms_one_active"),
        ),
        migrations.CreateModel(
            name="MinorProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date_of_birth", models.TextField(blank=True, default="")),
                ("declared_under_age", models.BooleanField(default=False)),
                ("guardian_name", models.TextField(blank=True, default="")),
                ("guardian_email", models.TextField(blank=True, default="")),
                ("guardian_phone", models.TextField(blank=True, default="")),
                ("cleared_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("guardian_user", _user()),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="minor_profiles",
                    to="makerspaces.makerspace")),
                ("recorded_by", _user()),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="minor_profiles",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-pk"]},
        ),
        migrations.AddConstraint(
            model_name="minorprofile",
            constraint=models.UniqueConstraint(fields=("makerspace", "user"), name="minor_profile_one_per_space"),
        ),
        migrations.CreateModel(
            name="GuardianConsent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("terms_version", models.CharField(max_length=64)),
                ("method", models.CharField(
                    choices=[("guardian_account", "Signed by the guardian in their own account"),
                             ("staff_recorded", "Signed on paper or at the desk and recorded by staff")],
                    max_length=20)),
                ("signed_name", models.TextField()),
                ("signed_at", models.DateTimeField()),
                ("valid_until", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("operation_id", models.CharField(blank=True, max_length=64, null=True)),
                ("guardian_user", _user()),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="+", to="makerspaces.makerspace")),
                ("profile", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="consents",
                    to="makerspaces.minorprofile")),
                ("recorded_by", _user()),
                ("revoked_by", _user()),
                ("terms", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="consents",
                    to="makerspaces.guardianconsentterms")),
            ],
            options={"ordering": ["-signed_at", "-pk"]},
        ),
        migrations.AddConstraint(
            model_name="guardianconsent",
            constraint=models.CheckConstraint(condition=Q(valid_until__gt=F("signed_at")),
                                              name="guardian_consent_window"),
        ),
        migrations.AddConstraint(
            model_name="guardianconsent",
            constraint=models.UniqueConstraint(condition=Q(operation_id__isnull=False),
                                               fields=("makerspace", "operation_id"),
                                               name="guardian_consent_operation_unique"),
        ),
        migrations.AddIndex(
            model_name="guardianconsent",
            index=models.Index(fields=["profile", "valid_until"], name="guardian_consent_profile_idx"),
        ),
        migrations.CreateModel(
            name="VolunteerHourEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("minutes", models.PositiveIntegerField()),
                ("worked_on", models.DateField()),
                ("description", models.CharField(blank=True, default="", max_length=200)),
                ("source", models.CharField(
                    choices=[("manual", "Logged by hand"), ("event_shift", "Verified event shift")],
                    default="manual", max_length=16)),
                ("source_ref", models.PositiveBigIntegerField(blank=True, null=True)),
                ("status", models.CharField(
                    choices=[("pending", "Waiting for approval"), ("approved", "Approved"),
                             ("rejected", "Rejected")], default="pending", max_length=10)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_note", models.CharField(blank=True, default="", max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="+", to="makerspaces.makerspace")),
                ("member", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="volunteer_entries",
                    to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", _user()),
                ("submitted_by", _user()),
            ],
            options={"ordering": ["-worked_on", "-pk"]},
        ),
        migrations.AddConstraint(
            model_name="volunteerhourentry",
            constraint=models.CheckConstraint(condition=Q(minutes__gt=0, minutes__lte=1440),
                                              name="volunteer_entry_minutes_range"),
        ),
        migrations.AddConstraint(
            model_name="volunteerhourentry",
            constraint=models.UniqueConstraint(condition=Q(source_ref__isnull=False),
                                               fields=("makerspace", "source", "source_ref"),
                                               name="volunteer_entry_source_unique"),
        ),
        migrations.AddIndex(
            model_name="volunteerhourentry",
            index=models.Index(fields=["makerspace", "member", "status"], name="volunteer_entry_member_idx"),
        ),
        migrations.CreateModel(
            name="VolunteerCredit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("minutes_converted", models.PositiveIntegerField(default=0)),
                ("kind", models.CharField(choices=[("discount", "discount"), ("free_days", "free_days")],
                                          max_length=12)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("days", models.PositiveIntegerField(default=0)),
                ("currency", models.CharField(blank=True, default="", max_length=3)),
                ("status", models.CharField(
                    choices=[("available", "Available"), ("used", "Applied to a charge"), ("void", "Voided")],
                    default="available", max_length=10)),
                ("applied_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("void_reason", models.CharField(blank=True, default="", max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("applied_payment", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to="payments.payment")),
                ("created_by", _user()),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="+", to="makerspaces.makerspace")),
                ("member", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="volunteer_credits",
                    to=settings.AUTH_USER_MODEL)),
                ("split_from", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to="makerspaces.volunteercredit")),
            ],
            options={"ordering": ["created_at", "pk"]},
        ),
        migrations.AddConstraint(
            model_name="volunteercredit",
            constraint=models.CheckConstraint(condition=Q(amount__gte=0), name="volunteer_credit_amount_nonneg"),
        ),
        migrations.AddConstraint(
            model_name="volunteercredit",
            constraint=models.CheckConstraint(
                condition=~Q(status="used") | Q(applied_at__isnull=False, applied_amount__isnull=False),
                name="volunteer_credit_used_has_application"),
        ),
        migrations.AddIndex(
            model_name="volunteercredit",
            index=models.Index(fields=["makerspace", "member", "status"], name="volunteer_credit_member_idx"),
        ),
    ]
