"""Additive Events programme schema; runtime capabilities remain off by default."""
import uuid
import django.core.validators
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('accounts', '0037_governance_recovery_context'), ('encryption', '0007_tenant_import_fence_operation')]
    operations = [
        migrations.CreateModel(
            name='AccountPiiKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField()),
                ('wrapped_dek', models.BinaryField()),
                ('broker_backend', models.CharField(max_length=16)),
                ('broker_key_id', models.CharField(max_length=255)),
                ('status', models.CharField(max_length=16, choices=[('active', 'Active'), ('rotated', 'Rotated'), ('disabled', 'Disabled')], default='active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name='PiiAccountWriteFence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.CharField(max_length=8, choices=[('open', 'Open'), ('closed', 'Closed'), ('erased', 'Erased')], default='open')),
                ('epoch', models.PositiveBigIntegerField(default=1)),
                ('claim_id', models.UUIDField(null=True, blank=True)),
                ('claim_expires_at', models.DateTimeField(null=True, blank=True)),
                ('operation_id', models.UUIDField(null=True, blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={},
        ),
        migrations.AddField(model_name='accountpiikey', name='user', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='account_pii_keys')),
        migrations.AddField(model_name='piiaccountwritefence', name='user', field=models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='account_pii_write_fence')),
        migrations.AddConstraint(model_name='accountpiikey', constraint=models.UniqueConstraint(fields=['user', 'version'], name='account_dek_version_unique')),
        migrations.AddConstraint(model_name='accountpiikey', constraint=models.UniqueConstraint(fields=['user'], condition=models.Q(status='active'), name='account_active_dek_unique')),
        migrations.AddConstraint(model_name='accountpiikey', constraint=models.CheckConstraint(condition=models.Q(version__gte=1), name='account_dek_positive')),
        migrations.AddConstraint(model_name='piiaccountwritefence', constraint=models.CheckConstraint(condition=models.Q(epoch__gte=1), name='account_fence_epoch_positive')),
    ]
