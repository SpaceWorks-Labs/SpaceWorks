"""Unified accounts A+2: convert every live staff account into a person, in place.

Refuses while live staff exist unless ``ACCOUNT_UNIFICATION_ACK`` equals the reviewed
``plan_sha256`` (Q5). Each staff account keeps its staff-track row and roles, its
password and MFA, and its username; its email is re-stamped unverified (#65); a
colliding email/phone/Telegram id moves to an encrypted hold in its ``converted`` record
(Q14); its credentials are revoked. Then every native device grant and family ends
(members' too, Q18/#66), staff recovery envelopes and open invitations are revoked, the
deployment auth generation advances, and the person-email key replaces the split ones.
There is no automatic community membership for converted staff (Q13/#66).

Irreversible: restore the pre-upgrade backup to roll back.
"""

from django.db import migrations, models
from django.contrib.postgres.operations import ValidateConstraint
from django.db.models.functions import Lower

from ._0050_conversion import convert


def irreversible(apps, schema_editor):
    raise RuntimeError("Account unification is irreversible; restore the pre-upgrade backup.")


class Migration(migrations.Migration):
    atomic = True
    dependencies = [
        ("accounts", "0049_unified_accounts_schema"),
        ("audit", "0009_audit_verification_runs"),
        ("backup", "0037_extracted_restore_points"),
        ("integrations", "0049_organization_email_sender"),
        ("makerspaces", "0114_membership_track"),
        ("sessions", "0001_initial"),
        ("token_blacklist", "0013_alter_blacklistedtoken_options_and_more"),
    ]

    operations = [
        migrations.RunPython(convert, irreversible),
        ValidateConstraint(model_name="user", name="user_account_context"),
        migrations.RemoveConstraint(model_name="user", name="uniq_member_email"),
        migrations.RemoveConstraint(model_name="user", name="uniq_staff_space_email"),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                Lower("email"), condition=models.Q(("account_kind", "member"), models.Q(("email", ""), _negated=True)),
                name="uniq_person_email",
            ),
        ),
    ]
