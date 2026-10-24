"""Refund cases record staff-cancelled bookings, owed in full (owner decision 72)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0024_refund_policy_memberships'),
    ]

    operations = [
        migrations.AlterField(
            model_name='refundcase',
            name='reason_code',
            field=models.CharField(choices=[('event_cancelled', 'Event cancelled by the space'), ('registration_cancelled', 'Registration cancelled'), ('booking_cancelled', 'Booking cancelled'), ('staff_cancelled', 'Cancelled by staff'), ('membership_cancelled', 'Membership term cancelled'), ('member_request', 'Member request')], max_length=32),
        ),
    ]
