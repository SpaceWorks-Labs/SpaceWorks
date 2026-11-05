# #192: a Space Manager may hide a space from the platform directory without a custom
# domain, so the hidden-requires-domain constraint goes.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("makerspaces", "0128_member_card_email_format"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="makerspace",
            name="ck_makerspace_hidden_requires_domain",
        ),
    ]
