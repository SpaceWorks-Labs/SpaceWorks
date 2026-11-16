"""Certificate signatories (up to three per event), their append-only design approvals and the
per-event "signatories must approve" switch (default off)."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0082_certificate_kind_designs'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='eventcertificatepublicationpolicy',
            name='signatory_approval_required',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='EventCertificateSignatory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slot', models.PositiveSmallIntegerField()),
                ('name', models.CharField(max_length=120)),
                ('title', models.CharField(blank=True, max_length=120)),
                ('version', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='certificate_signatories', to='events.event')),
                ('member', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='certificate_signatory_roles', to=settings.AUTH_USER_MODEL)),
                ('signature', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='signatories', to='events.eventcertificateartwork')),
            ],
            options={
                'ordering': ('event_id', 'slot'),
                'constraints': [
                    models.UniqueConstraint(fields=('event', 'slot'), name='event_cert_signatory_slot'),
                    models.CheckConstraint(condition=models.Q(('slot__gte', 1), ('slot__lte', 3)), name='event_cert_signatory_slot_range'),
                ],
            },
        ),
        migrations.CreateModel(
            name='EventCertificateSignatoryApproval',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('signatory_version', models.PositiveIntegerField()),
                ('approved_at', models.DateTimeField(auto_now_add=True)),
                ('approved_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('signatory', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='approvals', to='events.eventcertificatesignatory')),
                ('template_revision', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='signatory_approvals', to='events.eventcertificatetemplaterevision')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('signatory', 'template_revision', 'signatory_version'), name='event_cert_signatory_approval')],
            },
        ),
    ]
