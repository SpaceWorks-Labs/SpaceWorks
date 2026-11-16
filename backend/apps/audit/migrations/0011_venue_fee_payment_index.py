"""Bound event venue-payment provenance lookup without rewriting audit history."""
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models
from django.db.models.fields.json import KeyTextTransform


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("audit", "0010_plain_admin_names")]
    operations = [
        AddIndexConcurrently(
            model_name="auditlog",
            index=models.Index(
                models.F("makerspace"), KeyTextTransform("payment_id", "meta"),
                name="audit_venue_fee_payment_idx",
                condition=models.Q(action="event.venue_fee_charged", target_type="events.eventvenuefee"),
            ),
        ),
    ]
