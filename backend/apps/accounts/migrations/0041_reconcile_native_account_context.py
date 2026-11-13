"""Bind native authority to immutable account contexts after both historical branches."""

from django.db import migrations, models
from django.db.models import F, Q
from django.utils import timezone

from ._0041_account_guards import SQL, REVERSE


def reconcile_existing_authority(apps, schema_editor):
    db = schema_editor.connection.alias
    User = apps.get_model("accounts", "User")
    # Never silently turn an archived staff/platform principal into a member or
    # erase its lifecycle work. Such source data needs an explicit repair first.
    lifecycle = Q(deletion_requested_at__isnull=False) | Q(deletion_purge_after__isnull=False)
    for name in ("purge_started_at", "account_restored_at", "account_purged_at"):
        lifecycle |= Q(**{f"{name}__isnull": False})
    lifecycle |= ~Q(deletion_email_ciphertext="") | ~Q(deletion_username="")
    if User.objects.using(db).exclude(account_kind="member").filter(lifecycle).exists():
        raise RuntimeError("Non-member account lifecycle data requires explicit reconciliation.")
    for model in ("AccountPurgeProgress", "AccountPurgeObject", "AppleRevocation", "AccountRestoreIntent"):
        if apps.get_model("accounts", model).objects.using(db).filter(user__isnull=False).exclude(
                user__account_kind="member").exists():
            raise RuntimeError(f"Non-member {model} data requires explicit reconciliation.")
    if apps.get_model("accounts", "AppleRefreshCredential").objects.using(db).exclude(
            social_identity__user__account_kind="member").exists():
        raise RuntimeError("Non-member Apple credentials require explicit reconciliation.")
    Envelope = apps.get_model("accounts", "PasswordResetEnvelope")
    if Envelope.objects.using(db).exclude(context=F("user__account_kind")).exists() or Envelope.objects.using(db).filter(
        Q(context="staff") & ~Q(makerspace_id=F("user__staff_makerspace_id"))
        | ~Q(context="staff") & Q(makerspace_id__isnull=False),
    ).exists():
        raise RuntimeError("Recovery account namespaces require explicit reconciliation.")
    if Envelope.objects.using(db).filter(purpose="restore").exclude(context="member").exists():
        raise RuntimeError("Non-member restore envelopes require explicit reconciliation.")
    Grant = apps.get_model("accounts", "DeviceGrant")
    Family = apps.get_model("accounts", "DeviceRefreshFamily")
    Token = apps.get_model("accounts", "DeviceRefreshToken")
    Push = apps.get_model("integrations", "PushDevice")
    now = timezone.now()
    for grant in Grant.objects.using(db).select_related("user", "registration").iterator():
        user, app = grant.user, grant.registration
        grant.staff_makerspace_id = user.staff_makerspace_id
        grant.credential_generation = user.credential_generation
        # Old staff grants lack proved password + MFA provenance. Incompatible
        # member/platform authority is also permanently revoked, never relabelled.
        valid = (grant.authority == user.account_kind == "member" and user.is_active
                 and user.retired_at is None and not user.is_tenant_dump_stub
                 and not user.deletion_requested_at and user.access_status == "active"
                 and app.status == "approved" and app.revoked_at is None
                 and (grant.platform, grant.app_id, grant.environment) == (app.platform, app.app_id, app.environment))
        if not valid or grant.status == "revoked" or grant.revoked_at:
            grant.status = "revoked"
            grant.revoked_at = grant.revoked_at or now
            Family.objects.using(db).filter(grant_id=grant.pk, revoked_at__isnull=True).update(revoked_at=now)
            Token.objects.using(db).filter(family__grant_id=grant.pk, blacklisted_at__isnull=True).update(blacklisted_at=now)
            Push.objects.using(db).filter(device_grant_id=grant.pk, active=True).update(active=False, invalidated_at=now)
        grant.save(using=db, update_fields=["staff_makerspace_id", "credential_generation", "status", "revoked_at"])
    # Orphaned/mismatched family ownership must never issue a token for its grant.
    for family in Family.objects.using(db).select_related("grant").iterator():
        if family.user_id != family.grant.user_id:
            Family.objects.using(db).filter(pk=family.pk).update(revoked_at=now)
            Token.objects.using(db).filter(family_id=family.pk, blacklisted_at__isnull=True).update(blacklisted_at=now)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0040_merge_mobile_account_split"),
                    ("integrations", "0040_merge_mobile_notifications")]
    operations = [
        migrations.AddField("devicegrant", "staff_makerspace_id",
            models.PositiveBigIntegerField(null=True, blank=True, editable=False)),
        migrations.AddField("devicegrant", "credential_generation", models.PositiveIntegerField(default=0, editable=False)),
        migrations.AddField("devicegrant", "login_method", models.CharField(max_length=16, blank=True, default="",
            choices=[("password", "Password"), ("phone", "Phone"), ("social", "Social")])),
        migrations.RunPython(reconcile_existing_authority, migrations.RunPython.noop),
        migrations.AddConstraint("user", models.CheckConstraint(condition=(Q(account_kind="member") | Q(
            deletion_requested_at__isnull=True, deletion_purge_after__isnull=True,
            purge_started_at__isnull=True, account_restored_at__isnull=True, account_purged_at__isnull=True,
            deletion_email_ciphertext="", deletion_username="",
        )), name="user_member_lifecycle")),
        migrations.AddConstraint("devicegrant", models.CheckConstraint(condition=(Q(status="revoked") | Q(
            authority="member", staff_makerspace_id__isnull=True,
        ) | Q(authority="staff", staff_makerspace_id__isnull=False, login_method="password")),
            name="device_grant_account_context")),
        migrations.AddConstraint("passwordresetenvelope", models.CheckConstraint(condition=(Q(purpose="reset") | Q(
            purpose="restore", context="member", makerspace__isnull=True,
        )), name="reset_restore_member_context")),
        migrations.RunSQL(SQL, REVERSE),
    ]
