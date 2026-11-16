"""Phase 1f-1 tracking; no historical rows are backfilled."""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [('machines', '0028_drop_role_machine_scope'), ('makerspaces', '0093_fixed_roles_constraint'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(name='MachineStatusEvent', fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ('makerspace', models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)),
            ('machine', models.ForeignKey("machines.Machine", on_delete=models.CASCADE, related_name="status_events")),
            ('from_status', models.CharField(max_length=20)),
            ('to_status', models.CharField(max_length=20)),
            ('at', models.DateTimeField(auto_now_add=True)),
            ('source', models.CharField(max_length=32)),
        ], options={'indexes': [models.Index(fields=["machine", "at"], name="machine_status_timeline_idx")]}),
        migrations.CreateModel(name='ConsumableCostRecord', fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ('makerspace', models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)),
            ('source_kind', models.CharField(max_length=32, choices=[(s, s) for s in (
        "pooled_service", "manual_adjustment", "non_pool_consumption",
    )])),
            ('source_id', models.PositiveBigIntegerField()),
            ('quantity', models.DecimalField(max_digits=12, decimal_places=2)),
            ('measurement_unit', models.CharField(max_length=16)),
            ('unit_price_minor_per_measurement_unit', models.DecimalField(max_digits=24, decimal_places=10)),
            ('cost_total_minor', models.PositiveBigIntegerField()),
            ('currency', models.CharField(max_length=3)),
            ('recorded_at', models.DateTimeField(auto_now_add=True)),
        ], options={'constraints': [
            models.UniqueConstraint(fields=["makerspace", "source_kind", "source_id"], name="unique_consumable_cost_source"),
            models.CheckConstraint(condition=Q(quantity__gte=0) & Q(unit_price_minor_per_measurement_unit__gte=0), name="consumable_cost_nonnegative"),
        ]}),
        migrations.AddField(model_name='machineusageentry', name='member', field=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="machine_usage_entries")),
        migrations.AddField(model_name='machineusageentry', name='started_at', field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name='machineconsumablepool', name='unit_cost', field=models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True, validators=[MinValueValidator(0)])),
        migrations.AddField(model_name='machineconsumablepool', name='cost_currency', field=models.CharField(max_length=3, blank=True)),
        migrations.AddField(model_name='machineconsumablepool', name='cost_unit', field=models.CharField(max_length=16, blank=True)),
        migrations.RunSQL(sql="CREATE FUNCTION machines_tracking_reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$\nBEGIN\n    IF TG_OP = 'DELETE' AND current_setting('app.allow_immutable_delete', true) = 'on' THEN\n        RETURN OLD;\n    END IF;\n    RAISE EXCEPTION 'tracking facts are append-only';\nEND;\n$$;\nCREATE TRIGGER machinestatusevent_immutable BEFORE UPDATE OR DELETE ON machines_machinestatusevent FOR EACH ROW EXECUTE FUNCTION machines_tracking_reject_mutation();\nCREATE TRIGGER consumablecostrecord_immutable BEFORE UPDATE OR DELETE ON machines_consumablecostrecord FOR EACH ROW EXECUTE FUNCTION machines_tracking_reject_mutation();\n", reverse_sql='DROP TRIGGER IF EXISTS machinestatusevent_immutable ON machines_machinestatusevent;\nDROP TRIGGER IF EXISTS consumablecostrecord_immutable ON machines_consumablecostrecord;\nDROP FUNCTION IF EXISTS machines_tracking_reject_mutation();'),
    ]
