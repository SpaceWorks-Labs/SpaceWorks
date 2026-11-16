"""Refund policies for paid membership terms, optionally per plan (owner decision 68)."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('makerspaces', '0103_page_reference_restore'),
        ('payments', '0023_refund_cases'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='refundpolicy',
            name='refund_policy_one_per_area',
        ),
        migrations.AddField(
            model_name='refundpolicy',
            name='full_within_days',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='refundpolicy',
            name='partial_mode',
            field=models.CharField(choices=[('percent', 'A fixed percentage'), ('pro_rata', 'Pro rata of unused term time')], default='percent', max_length=16),
        ),
        migrations.AddField(
            model_name='refundpolicy',
            name='plan',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='refund_policies', to='makerspaces.membershipplan'),
        ),
        migrations.AlterField(
            model_name='refundcase',
            name='reason_code',
            field=models.CharField(choices=[('event_cancelled', 'Event cancelled by the space'), ('registration_cancelled', 'Registration cancelled'), ('booking_cancelled', 'Booking cancelled'), ('membership_cancelled', 'Membership term cancelled'), ('member_request', 'Member request')], max_length=32),
        ),
        migrations.AlterField(
            model_name='refundpolicy',
            name='area',
            field=models.CharField(choices=[('events', 'Events'), ('bookings', 'Bookings'), ('membership', 'Memberships')], max_length=16),
        ),
        migrations.AddConstraint(
            model_name='refundpolicy',
            constraint=models.UniqueConstraint(condition=models.Q(('plan__isnull', True)), fields=('makerspace', 'area'), name='refund_policy_one_per_area'),
        ),
        migrations.AddConstraint(
            model_name='refundpolicy',
            constraint=models.UniqueConstraint(condition=models.Q(('plan__isnull', False)), fields=('makerspace', 'area', 'plan'), name='refund_policy_one_per_plan'),
        ),
        migrations.AddConstraint(
            model_name='refundpolicy',
            constraint=models.CheckConstraint(condition=models.Q(('plan__isnull', True), ('area', 'membership'), _connector='OR'), name='refund_policy_plan_is_membership'),
        ),
        migrations.AddConstraint(
            model_name='refundpolicy',
            constraint=models.CheckConstraint(condition=models.Q(('partial_mode', 'percent'), ('area', 'membership'), _connector='OR'), name='refund_policy_pro_rata_is_membership'),
        ),
    ]
