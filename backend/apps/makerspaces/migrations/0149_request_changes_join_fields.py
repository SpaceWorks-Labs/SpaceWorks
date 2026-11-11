"""Parity O-B2: "ask for changes" on a join request, and the per-plan photo / phone / state toggles.

* `MembershipRequest.state` gains `changes_requested` (so the column grows from 16 to 24 characters) and the
  two "one open request" constraints now count it as open.
* The request remembers why changes were asked, when, and that its single round was used.
* A plan chooses whether the join form collects a photo, a phone number and a state (GST place of supply).
"""
from django.db import migrations, models

OPEN = ["requested", "invited", "awaiting_vouches", "awaiting_payment", "changes_requested"]
STATES = [
    ("requested", "Requested"), ("invited", "Invited"), ("awaiting_vouches", "Awaiting vouches"),
    ("awaiting_payment", "Awaiting payment"), ("changes_requested", "Changes requested"),
    ("expired", "Expired"), ("canceled", "Canceled"), ("active", "Active"), ("revoked", "Revoked"),
]
FIELD_MODES = [("off", "Off"), ("optional", "Optional"), ("required", "Required")]


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0148_makerspace_kind")]

    operations = [
        migrations.RemoveConstraint(model_name="membershiprequest", name="uniq_open_membership_request_user"),
        migrations.RemoveConstraint(model_name="membershiprequest", name="uniq_open_membership_request_email"),
        migrations.AlterField(model_name="membershiprequest", name="state",
                              field=models.CharField(choices=STATES, max_length=24)),
        migrations.AddField(model_name="membershiprequest", name="changes_note",
                            field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="membershiprequest", name="changes_requested_at",
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="membershiprequest", name="changes_rounds",
                            field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddConstraint(model_name="membershiprequest", constraint=models.UniqueConstraint(
            condition=models.Q(("state__in", OPEN), ("user__isnull", False)), fields=("makerspace", "user"),
            name="uniq_open_membership_request_user")),
        migrations.AddConstraint(model_name="membershiprequest", constraint=models.UniqueConstraint(
            condition=models.Q(models.Q(("state__in", OPEN)), models.Q(("invite_email", ""), _negated=True)),
            fields=("makerspace", "invite_email"), name="uniq_open_membership_request_email")),
        migrations.AddField(model_name="membershipplan", name="join_photo",
                            field=models.CharField(choices=FIELD_MODES, default="off", max_length=8)),
        migrations.AddField(model_name="membershipplan", name="join_phone",
                            field=models.CharField(choices=[("hidden", "Hidden"), ("optional", "Optional"),
                                                            ("required", "Required")], default="hidden", max_length=8)),
        migrations.AddField(model_name="membershipplan", name="join_state",
                            field=models.CharField(choices=[("hidden", "Hidden"), ("optional", "Optional"),
                                                            ("required", "Required")], default="hidden", max_length=8)),
    ]
