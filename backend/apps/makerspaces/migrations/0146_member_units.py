"""Parity O-B1: member units (districts, chapters, branches) inside one makerspace, unit-scoped staff,
plan-to-unit limits, the unit an applicant or imported row chose, and an invite link's preselected unit."""
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def _fk(to, related, *, on_delete=django.db.models.deletion.CASCADE, null=False):
    return models.ForeignKey(to=to, on_delete=on_delete, related_name=related, null=null, blank=null)


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0145_member_card_number_text_verify_name")]

    operations = [
        migrations.CreateModel(
            name="MemberUnitSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("level_names", models.JSONField(blank=True, default=list)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE, related_name="member_unit_settings",
                    to="makerspaces.makerspace")),
            ],
        ),
        migrations.CreateModel(
            name="MemberUnit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("slug", models.SlugField(max_length=80)),
                ("code", models.CharField(max_length=6, validators=[django.core.validators.RegexValidator(
                    "^[A-Z0-9]{1,6}$", "Use 1 to 6 capital letters or digits.")])),
                ("level", models.PositiveSmallIntegerField(default=0)),
                ("path", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("payment_instructions", models.TextField(blank=True, default="")),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", _fk("makerspaces.makerspace", "member_units")),
                ("parent", _fk("makerspaces.memberunit", "children",
                               on_delete=django.db.models.deletion.PROTECT, null=True)),
            ],
            options={"ordering": ["level", "sort_order", "name", "pk"]},
        ),
        migrations.AddConstraint(model_name="memberunit", constraint=models.UniqueConstraint(
            fields=("makerspace", "code"), name="uniq_member_unit_code")),
        migrations.AddConstraint(model_name="memberunit", constraint=models.UniqueConstraint(
            fields=("makerspace", "slug"), name="uniq_member_unit_slug")),
        migrations.AddConstraint(model_name="memberunit", constraint=models.CheckConstraint(
            condition=models.Q(("level__lte", 3)), name="member_unit_level_range")),
        migrations.CreateModel(
            name="MembershipUnit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("assigned_at", models.DateTimeField(auto_now=True)),
                ("makerspace", _fk("makerspaces.makerspace", "membership_unit_rows")),
                ("membership", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE, related_name="unit_assignment",
                    to="makerspaces.makerspacemembership")),
                ("unit", _fk("makerspaces.memberunit", "member_rows", on_delete=django.db.models.deletion.PROTECT)),
            ],
        ),
        migrations.CreateModel(
            name="StaffUnitScope",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", _fk("makerspaces.makerspace", "staff_unit_scope_rows")),
                ("membership", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE, related_name="unit_scope",
                    to="makerspaces.makerspacemembership")),
                ("unit", _fk("makerspaces.memberunit", "staff_scopes", on_delete=django.db.models.deletion.PROTECT)),
            ],
        ),
        migrations.CreateModel(
            name="PlanUnit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("makerspace", _fk("makerspaces.makerspace", "plan_unit_rows")),
                ("plan", _fk("makerspaces.membershipplan", "unit_links")),
                ("unit", _fk("makerspaces.memberunit", "plan_links", on_delete=django.db.models.deletion.PROTECT)),
            ],
        ),
        migrations.AddConstraint(model_name="planunit", constraint=models.UniqueConstraint(
            fields=("plan", "unit"), name="uniq_plan_unit")),
        migrations.CreateModel(
            name="MembershipRequestUnit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("makerspace", _fk("makerspaces.makerspace", "request_unit_rows")),
                ("request", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE, related_name="unit_choice",
                    to="makerspaces.membershiprequest")),
                ("unit", _fk("makerspaces.memberunit", "request_rows", on_delete=django.db.models.deletion.PROTECT)),
            ],
        ),
        migrations.CreateModel(
            name="ImportedMemberUnit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("review_status", models.CharField(
                    choices=[("not_required", "Not required"), ("pending", "Waiting for the unit lead"),
                             ("approved", "Approved"), ("rejected", "Rejected")],
                    default="not_required", max_length=16)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("imported", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE, related_name="unit_row",
                    to="makerspaces.importedmember")),
                ("makerspace", _fk("makerspaces.makerspace", "imported_unit_rows")),
                ("unit", _fk("makerspaces.memberunit", "imported_rows", on_delete=django.db.models.deletion.PROTECT)),
            ],
        ),
        migrations.AddField(
            model_name="membershipinvitelink",
            name="unit",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="invite_links", to="makerspaces.memberunit"),
        ),
    ]
