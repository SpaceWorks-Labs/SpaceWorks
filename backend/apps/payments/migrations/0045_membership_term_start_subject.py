# #184: a staff-opened membership term charges its own price (subject = that term).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0044_plain_admin_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='subject_type',
            field=models.CharField(choices=[('machine_service_request', 'Machine service request'), ('booking', 'Booking'), ('event_registration', 'Event registration'), ('makerspace_membership', 'Makerspace membership'), ('membership_term', 'Membership renewal'), ('membership_request', 'Membership admission'), ('loan_deposit', 'Loan deposit'), ('loan_late_fee', 'Loan late fee'), ('loan_rental', 'Loan rental'), ('loan_damage', 'Loan damage charge'), ('loan_lost', 'Lost item charge'), ('machine_session', 'Machine session'), ('event_order', 'Event ticket order'), ('event_venue_fee', 'Event venue fee'), ('donation', 'Donation'), ('sponsorship', 'Sponsorship'), ('submission_fee', 'Project entry fee'), ('team_registration', 'Team registration'), ('event_deposit', 'Event deposit'), ('shop_order', 'Shop order'), ('membership_term_start', 'Membership term')], max_length=48),
        ),
    ]
