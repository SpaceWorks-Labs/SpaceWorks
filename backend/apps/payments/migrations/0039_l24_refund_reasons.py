# Lane L24 (#163A, #171): three refund-case reasons. Choices only; no data changes.
# Renumbered from 0036 after L6, L18 and L21b; the choices list every reason before it.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0038_l21b_programme_subjects'),
    ]

    operations = [
        migrations.AlterField(
            model_name='refundcase',
            name='reason_code',
            field=models.CharField(choices=[('event_cancelled', 'Event cancelled by the space'), ('registration_cancelled', 'Registration cancelled'), ('booking_cancelled', 'Booking cancelled'), ('staff_cancelled', 'Cancelled by staff'), ('membership_cancelled', 'Membership term cancelled'), ('member_request', 'Member request'), ('capture_flagged', 'Unexpected online capture'), ('fee_waived', 'Loan fee waived by staff'), ('order_unfulfilled', 'Order could not be seated'), ('ticket_type_changed', 'Changed to a cheaper ticket'), ('pass_occurrence_cancelled', 'Pass occurrence cancelled'), ('donation_returned', 'Gift returned to the giver'), ('submission_disqualified', 'Project disqualified'), ('team_rejected', 'Team rejected'), ('price_drop', 'Price lowered after payment'), ('job_cancelled', 'Prepaid job cancelled before it started'), ('quote_difference', 'Actual cost below the prepaid quote')], max_length=32),
        ),
    ]
