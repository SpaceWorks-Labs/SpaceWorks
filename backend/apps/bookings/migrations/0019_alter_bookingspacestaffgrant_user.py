# State-only: 0012 stored the expanded related_name; the abstract grant model declares the
# '%(app_label)s' template. Same name either way, so no SQL is emitted.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0018_website_integrity'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='bookingspacestaffgrant',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_staff_grants', to=settings.AUTH_USER_MODEL),
        ),
    ]
