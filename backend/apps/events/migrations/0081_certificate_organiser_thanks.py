"""Organiser thank-you certificates: approved co-organisers may receive `organiser_thanks`."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0080_prize_outcome_peoples_choice'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventattendancecertificate',
            name='kind',
            field=models.CharField(choices=[('attendance', 'Attendance'), ('participant', 'Participant'),
                                            ('finalist', 'Finalist'), ('winner', 'Winner'),
                                            ('volunteer_thanks', 'Volunteer thanks'),
                                            ('mentor_thanks', 'Mentor thanks'), ('judge_thanks', 'Judge thanks'),
                                            ('organiser_thanks', 'Organiser thanks')],
                                   default='attendance', max_length=24),
        ),
    ]
