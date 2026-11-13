"""Decision 263: Grafana fields on both analytics connections. Existing rows keep Metabase."""

from django.db import migrations, models

import apps.analytics.grafana_validation


def _fields():
    return [
        ("provider", models.CharField(
            choices=[("metabase", "metabase"), ("grafana", "grafana"), ("both", "both")],
            default="metabase", max_length=16)),
        ("grafana_url", models.CharField(blank=True, default="", max_length=300)),
        ("grafana_token", models.TextField(blank=True, default="")),
        ("grafana_token_set_at", models.DateTimeField(blank=True, null=True)),
        ("grafana_org_id", models.PositiveIntegerField(default=1)),
        ("grafana_dashboards", models.JSONField(
            blank=True, default=list,
            validators=[apps.analytics.grafana_validation.validate_grafana_dashboards])),
    ]


class Migration(migrations.Migration):
    dependencies = [("analytics", "0002_telemetry_config")]

    operations = [
        migrations.AddField(model_name=model, name=name, field=field)
        for model in ("analyticsconnection", "platformanalyticsconnection")
        for name, field in _fields()
    ]
