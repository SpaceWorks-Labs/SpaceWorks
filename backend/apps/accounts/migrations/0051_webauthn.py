"""Login security A+3: passkeys, the platform passkey switch and the 3-day staff grace.

Schema only (lane S0). Also re-creates 0049's device-context trigger function so a staff
device grant accepts a passkey as its enabled factor (``_0051_passkey_device_guard``).
"""

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

from ._0051_passkey_device_guard import AFTER, BEFORE

CEREMONY_PURPOSES = ("registration", "login", "mfa", "reauth")
GRACE_SOURCES = ("grant", "invite", "merge", "upgrade")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0050_unified_accounts_convert"),
    ]

    operations = [
        migrations.AddField(
            model_name="platformloginmethods",
            name="passkeys_enabled",
            field=models.BooleanField(default=True, help_text="Whether people may add and use passkeys. Offered, never forced: switching it off never removes a passkey, and nobody is ever required to have one."),
        ),
        migrations.CreateModel(
            name="WebAuthnCredential",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("credential_id", models.CharField(max_length=1366, unique=True)),
                ("public_key", models.BinaryField()),
                ("sign_count", models.PositiveBigIntegerField(default=0)),
                ("transports", models.JSONField(blank=True, default=list)),
                ("aaguid", models.CharField(blank=True, default="", max_length=36)),
                ("backed_up", models.BooleanField(default=False)),
                ("rp_id", models.CharField(max_length=253)),
                ("name", models.CharField(blank=True, default="", max_length=64)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="webauthn_credentials", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["user", "rp_id"], name="webauthn_cred_user_rp")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("credential_id", ""), _negated=True), name="webauthn_credential_id_present"),
                    models.CheckConstraint(condition=models.Q(("rp_id", ""), _negated=True), name="webauthn_credential_rp_id_present"),
                ],
            },
        ),
        migrations.CreateModel(
            name="WebAuthnCeremony",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("purpose", models.CharField(choices=[(value, value) for value in CEREMONY_PURPOSES], max_length=16)),
                ("challenge", models.CharField(max_length=128, unique=True)),
                ("rp_id", models.CharField(max_length=253)),
                ("origin", models.CharField(max_length=300)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("mfa_challenge", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="+", to="accounts.mfachallenge")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["expires_at"], name="webauthn_ceremony_expiry")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("purpose__in", CEREMONY_PURPOSES)), name="webauthn_ceremony_purpose_known"),
                    models.CheckConstraint(condition=models.Q(models.Q(("purpose", "registration"), _negated=True), ("user__isnull", False), _connector="OR"), name="webauthn_ceremony_registration_has_user"),
                    models.CheckConstraint(condition=models.Q(models.Q(("purpose", "mfa"), _negated=True), models.Q(("mfa_challenge__isnull", False), ("user__isnull", False)), _connector="OR"), name="webauthn_ceremony_mfa_has_challenge"),
                    models.CheckConstraint(condition=models.Q(("expires_at__gt", models.F("created_at"))), name="webauthn_ceremony_expires_after_creation"),
                ],
            },
        ),
        migrations.CreateModel(
            name="StaffMfaGrace",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("started_at", models.DateTimeField()),
                ("source", models.CharField(choices=[(value, value) for value in GRACE_SOURCES], max_length=8)),
                ("ends_at", models.DateTimeField()),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="staff_mfa_grace", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("source__in", GRACE_SOURCES)), name="staff_mfa_grace_source_known"),
                    models.CheckConstraint(condition=models.Q(("ends_at__gt", models.F("started_at"))), name="staff_mfa_grace_ends_after_start"),
                ],
            },
        ),
        migrations.RunSQL(AFTER, BEFORE),
    ]
