"""Drop the account-less borrow-request opt-in (owner decision #75f).

Every borrow request now needs a signed-in account, so the per-makerspace switch has no
reader. Only the switch goes: `Makerspace.anonymous_requester` and every request filed
through it stay, with their contact snapshot and unverified flag, so the history remains
readable and the inert principal stays identifiable.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0104_email_providers")]

    operations = [
        migrations.RemoveField(model_name="makerspace", name="anonymous_requests_enabled"),
    ]
