"""Lane L21b: two payment subjects (entry fee, team registration) and two refund-case reasons.

Renumbered after L18's 0037; the choices list every subject and reason before it.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0037_l18_donations_sponsors'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='subject_type',
            field=models.CharField(choices=[('machine_service_request', 'Machine service request'), ('booking', 'Booking'), ('event_registration', 'Event registration'), ('makerspace_membership', 'Makerspace membership'), ('membership_term', 'Membership renewal'), ('membership_request', 'Membership admission'), ('loan_deposit', 'Loan deposit'), ('loan_late_fee', 'Loan late fee'), ('loan_rental', 'Loan rental'), ('loan_damage', 'Loan damage charge'), ('loan_lost', 'Lost item charge'), ('machine_session', 'Machine session'), ('event_order', 'Event ticket order'), ('event_venue_fee', 'Event venue fee'), ('donation', 'Donation'), ('sponsorship', 'Sponsorship'), ('submission_fee', 'Project entry fee'), ('team_registration', 'Team registration')], max_length=48),
        ),
        migrations.AlterField(
            model_name='refundcase',
            name='reason_code',
            field=models.CharField(choices=[('event_cancelled', 'Event cancelled by the space'), ('registration_cancelled', 'Registration cancelled'), ('booking_cancelled', 'Booking cancelled'), ('staff_cancelled', 'Cancelled by staff'), ('membership_cancelled', 'Membership term cancelled'), ('member_request', 'Member request'), ('capture_flagged', 'Unexpected online capture'), ('fee_waived', 'Loan fee waived by staff'), ('order_unfulfilled', 'Order could not be seated'), ('ticket_type_changed', 'Changed to a cheaper ticket'), ('pass_occurrence_cancelled', 'Pass occurrence cancelled'), ('donation_returned', 'Gift returned to the giver'), ('submission_disqualified', 'Project disqualified'), ('team_rejected', 'Team rejected')], max_length=32),
        ),
    ]
