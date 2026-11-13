"""Decision 361: a restricted or suspended person may hold a MEMBER device grant.

The device-context trigger refused every non-active principal on INSERT and UPDATE, so a
restricted person could neither sign in on a phone nor even heartbeat an existing grant
(its ``last_used_at`` UPDATE fires the trigger). Staff and event grants still need ACTIVE.
"""

from django.db import migrations

from ._0063_restricted_member_device_guard import AFTER, BEFORE


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0062_device_grant_passkey_login"),
    ]

    operations = [migrations.RunSQL(AFTER, BEFORE)]
