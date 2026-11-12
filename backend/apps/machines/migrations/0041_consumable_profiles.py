"""Decisions 341/343: per-machine-type consumable profiles, their job usage, editable type templates."""
import apps.payments.money_model
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

KINDS = [("material", "Material stock"), ("tool_wear", "Tool wear"), ("time", "Time"),
         ("per_job", "Fixed per job"), ("other", "Other")]
UNITS = [("g", "g"), ("kg", "kg"), ("mm", "mm"), ("m", "m"), ("ml", "ml"), ("l", "l"), ("cm2", "cm²"),
         ("m2", "m²"), ("cm3", "cm³"), ("sheet", "sheet"), ("piece", "piece"), ("min", "min"), ("h", "h"),
         ("use", "use"), ("k_stitch", "1,000 stitches")]
ESTIMATE_BY = [("none", "Not estimated"), ("member", "Member at intake"), ("staff", "Staff when quoting"),
               ("file", "From the job file")]
SOURCES = [("member", "Member"), ("staff", "Staff"), ("adapter", "Machine adapter"), ("file", "Job file")]


class Migration(migrations.Migration):
    dependencies = [
        ("machines", "0040_certifications_to_access_grants"),
        ("makerspaces", "0091_fixed_roles_schema"),
    ]

    operations = [
        migrations.CreateModel(
            name="MachineTypeConsumable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=50)),
                ("name", models.CharField(max_length=100)),
                ("kind", models.CharField(choices=KINDS, default="material", max_length=12)),
                ("unit", models.CharField(choices=UNITS, max_length=12)),
                ("attributes", models.JSONField(blank=True, default=dict)),
                ("required", models.BooleanField(default=False)),
                ("estimate_by", models.CharField(choices=ESTIMATE_BY, default="none", max_length=8)),
                ("record_by", models.JSONField(default=list)),
                ("unit_price", apps.payments.money_model.MoneyDecimalField(
                    blank=True, decimal_places=3, max_digits=13, null=True,
                    validators=[django.core.validators.MinValueValidator(0)])),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("template_key", models.CharField(blank=True, max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("consumable_pool", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="profile_links", to="machines.machineconsumablepool")),
                ("machine_type", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="consumable_profile",
                    to="machines.machinetype")),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="machine_type_consumables",
                    to="makerspaces.makerspace")),
                ("product", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="machine_profile_links", to="inventory.inventoryproduct")),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.AddConstraint(
            model_name="machinetypeconsumable",
            constraint=models.UniqueConstraint(fields=("makerspace", "machine_type", "key"),
                                               name="machine_type_consumable_key_unique"),
        ),
        migrations.AddConstraint(
            model_name="machinetypeconsumable",
            constraint=models.CheckConstraint(
                condition=models.Q(("unit_price__isnull", True), ("unit_price__gte", 0), _connector="OR"),
                name="machine_type_consumable_price_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="machinetypeconsumable",
            constraint=models.CheckConstraint(
                condition=models.Q(("consumable_pool__isnull", True), ("product__isnull", True), _connector="OR"),
                name="machine_type_consumable_single_stock"),
        ),
        migrations.CreateModel(
            name="ServiceRequestConsumableUsage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=50)),
                ("name", models.CharField(max_length=100)),
                ("kind", models.CharField(choices=KINDS, max_length=12)),
                ("unit", models.CharField(choices=UNITS, max_length=12)),
                ("phase", models.CharField(choices=[("estimate", "Estimate"), ("actual", "Actual")], max_length=8)),
                ("quantity", models.DecimalField(decimal_places=3, max_digits=16)),
                ("attributes", models.JSONField(blank=True, default=dict)),
                ("source", models.CharField(choices=SOURCES, max_length=8)),
                ("unit_price", apps.payments.money_model.MoneyDecimalField(
                    blank=True, decimal_places=3, max_digits=13, null=True)),
                ("device_ref", models.CharField(blank=True, max_length=36)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("definition", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="usage",
                    to="machines.machinetypeconsumable")),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="+", to="makerspaces.makerspace")),
                ("service_request", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="profile_usage",
                    to="machines.machineservicerequest")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="servicerequestconsumableusage",
            index=models.Index(fields=["makerspace", "phase", "created_at"], name="profile_usage_scope_idx"),
        ),
        migrations.AddConstraint(
            model_name="servicerequestconsumableusage",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)),
                                              name="profile_usage_quantity_positive"),
        ),
        migrations.AddConstraint(
            model_name="servicerequestconsumableusage",
            constraint=models.UniqueConstraint(condition=models.Q(("phase", "actual")),
                                               fields=("service_request", "definition"),
                                               name="profile_usage_one_actual"),
        ),
        migrations.CreateModel(
            name="MachineTypeTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=50)),
                ("name", models.CharField(max_length=100)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("category", models.CharField(blank=True, max_length=50)),
                ("icon", models.CharField(blank=True, max_length=50)),
                ("based_on", models.CharField(blank=True, max_length=50)),
                ("spec", models.JSONField(default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="machine_type_templates",
                    to="makerspaces.makerspace")),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.AddConstraint(
            model_name="machinetypetemplate",
            constraint=models.UniqueConstraint(fields=("makerspace", "key"), name="machine_type_template_key_unique"),
        ),
    ]
