from django.db import migrations, models
from django.db.models import F, Q
from django.db.models.functions import Lower
import django.db.models.deletion
import apps.accounts.managers


def split_existing_accounts(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Membership = apps.get_model("makerspaces", "MakerspaceMembership")
    Additional = apps.get_model("makerspaces", "MembershipAdditionalRole")
    Scope = apps.get_model("machines", "MembershipMachineTypeScope")
    Role = apps.get_model("makerspaces", "MakerspaceRole")
    db = schema_editor.connection.alias
    User.objects.using(db).filter(is_superuser=True).update(account_kind="platform", role="superadmin")
    User.objects.using(db).filter(is_superuser=False).update(account_kind="member", role="requester")
    # D12: dev authority is rebuilt from seeds, never split an existing person's records.
    Additional.objects.using(db).all().delete()
    Scope.objects.using(db).all().delete()
    Membership.objects.using(db).filter(user__account_kind="platform").delete()
    for role in Role.objects.using(db).filter(slug="member"):
        Membership.objects.using(db).filter(makerspace_id=role.makerspace_id).update(
            assigned_role_id=role.pk, role="custom")


CONSTRAINTS = [
        models.CheckConstraint(
            condition=(
                Q(account_kind="staff", staff_makerspace__isnull=False, retired_at__isnull=True)
                | Q(account_kind="staff", staff_makerspace__isnull=True,
                    retired_at__isnull=False, is_active=False)
                | Q(account_kind__in=["member", "platform"],
                    staff_makerspace__isnull=True, retired_at__isnull=True)
            ), name="user_account_context",
        ),
        models.CheckConstraint(
            condition=(Q(account_kind="platform", is_superuser=True, role="superadmin")
                       | (Q(account_kind__in=["member", "staff"], is_superuser=False)
                          & ~Q(role="superadmin"))),
            name="user_platform_flags",
        ),
        models.UniqueConstraint(Lower("email"), condition=Q(account_kind="member") & ~Q(email=""),
                                name="uniq_member_email"),
        models.UniqueConstraint(Lower("email"), F("staff_makerspace"),
                                condition=Q(account_kind="staff") & ~Q(email=""),
                                name="uniq_staff_space_email"),
        models.UniqueConstraint(Lower("email"), condition=Q(account_kind="platform") & ~Q(email=""),
                                name="uniq_platform_email"),
        *[
            models.UniqueConstraint(fields=[field], condition=Q(account_kind="member") & ~Q(**{field: ""}),
                                    name=name)
            for field, name in (
                ("phone_e164", "uniq_member_phone_e164"),
                ("telegram_user_id", "uniq_member_telegram_id"),
                ("external_checkin_user_id", "uniq_member_checkin_id"),
            )
        ],
    ]


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0031_platformloginmethods_provider_switches"),
        ("makerspaces", "0096_enable_existing_presence"),
        ("machines", "0028_drop_role_machine_scope"),
    ]
    operations = [
        migrations.AddField("user", "account_kind", models.CharField(
            choices=[("member", "Member"), ("staff", "Staff"), ("platform", "Platform")],
            default="member", max_length=16)),
        migrations.AddField("user", "staff_makerspace", models.ForeignKey(
            to="makerspaces.makerspace", null=True, blank=True,
            related_name="staff_accounts", on_delete=django.db.models.deletion.PROTECT)),
        migrations.AddField("user", "retired_at", models.DateTimeField(null=True, blank=True)),
        migrations.AddField("user", "credential_generation", models.PositiveIntegerField(default=0)),
        migrations.AlterModelManagers("user", [("objects", apps.accounts.managers.UserManager())]),
        migrations.RunPython(split_existing_accounts, migrations.RunPython.noop),
        *[migrations.RemoveConstraint("user", name) for name in (
            "uniq_external_checkin_user_id", "uniq_telegram_user_id", "uniq_ci_nonempty_email",
            "uniq_nonempty_phone_e164",
        )],
        *[migrations.AddConstraint("user", constraint) for constraint in CONSTRAINTS],
    ]
