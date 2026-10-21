"""Refund cases (an entitlement, never money) and per-area refund policies."""

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('makerspaces', '0103_page_reference_restore'),
        ('payments', '0022_bd_r1_bills_branding'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RefundCase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('due', 'Due under policy'), ('request', 'Requested by member')], max_length=16)),
                ('area', models.CharField(choices=[('machines', 'Machines'), ('bookings', 'Bookings'), ('events', 'Events'), ('membership', 'Membership'), ('loans', 'Loans')], max_length=16)),
                ('reason_code', models.CharField(choices=[('event_cancelled', 'Event cancelled by the space'), ('registration_cancelled', 'Registration cancelled'), ('booking_cancelled', 'Booking cancelled'), ('member_request', 'Member request')], max_length=32)),
                ('member_reason', models.CharField(blank=True, default='', max_length=500)),
                ('due_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('policy_snapshot', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('open', 'Open'), ('approved', 'Approved'), ('approval_failed', 'Approval failed'), ('declined', 'Declined'), ('withdrawn', 'Withdrawn'), ('void', 'Void')], default='open', max_length=16)),
                ('approved_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('decision_note', models.CharField(blank=True, default='', max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('decided_at', models.DateTimeField(blank=True, null=True)),
                ('decided_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='decided_refund_cases', to=settings.AUTH_USER_MODEL)),
                ('payment', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='refund_cases', to='payments.payment')),
                ('refund', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='refund_cases', to='payments.refund')),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='requested_refund_cases', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at', '-pk'],
                'indexes': [models.Index(fields=['status', 'area'], name='refund_case_status_area')],
                'constraints': [models.UniqueConstraint(condition=models.Q(('status__in', ['open', 'approval_failed'])), fields=('payment',), name='refund_case_one_active_per_payment'), models.UniqueConstraint(condition=models.Q(('kind', 'due')), fields=('payment',), name='refund_case_one_due_per_payment'), models.CheckConstraint(condition=models.Q(('due_amount__gte', 0)), name='refund_case_due_not_negative'), models.CheckConstraint(condition=models.Q(('approved_amount__isnull', True), ('approved_amount__gt', 0), _connector='OR'), name='refund_case_approved_positive')],
            },
        ),
        migrations.CreateModel(
            name='RefundPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('area', models.CharField(choices=[('events', 'Events'), ('bookings', 'Bookings')], max_length=16)),
                ('full_before_minutes', models.PositiveIntegerField(default=0)),
                ('partial_before_minutes', models.PositiveIntegerField(default=0)),
                ('partial_percent', models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MaxValueValidator(100)])),
                ('cancellation_fee', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('makerspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='refund_policies', to='makerspaces.makerspace')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['makerspace_id', 'area'],
                'constraints': [models.UniqueConstraint(fields=('makerspace', 'area'), name='refund_policy_one_per_area'), models.CheckConstraint(condition=models.Q(('full_before_minutes__gte', models.F('partial_before_minutes'))), name='refund_policy_windows_ordered'), models.CheckConstraint(condition=models.Q(('partial_percent__lte', 100)), name='refund_policy_percent_range'), models.CheckConstraint(condition=models.Q(('cancellation_fee__gte', 0)), name='refund_policy_fee_not_negative')],
            },
        ),
    ]
