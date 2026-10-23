"""Additive Events programme schema; runtime capabilities remain off by default."""
import uuid
import django.core.validators
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('accounts', '0037_governance_recovery_context'), ('organizations', '0006_page_reference_restore')]
    operations = [
        migrations.CreateModel(
            name='OrganizationLeaveReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation_id', models.UUIDField()),
                ('expected_version', models.PositiveBigIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={},
        ),
        migrations.AddField(model_name='organizationleavereceipt', name='organization', field=models.ForeignKey('organizations.Organization', on_delete=models.CASCADE, related_name='leave_receipts')),
        migrations.AddField(model_name='organizationleavereceipt', name='actor', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')),
        migrations.AddConstraint(model_name='organizationleavereceipt', constraint=models.UniqueConstraint(fields=('organization', 'actor', 'operation_id'), name='uniq_org_leave_operation')),
    ]
