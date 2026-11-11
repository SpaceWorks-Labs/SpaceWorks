"""O-B4: the frozen printed card number, and the space-level public-check name default.

Existing spaces keep today's behaviour (name hidden until the holder opts in), mirroring the
`auto_issue` precedent in card_designs 0003; only spaces created after this migration default to True.
"""
from django.db import migrations, models


def keep_existing_spaces_unchanged(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    Settings = apps.get_model("makerspaces", "MemberCardSettings")
    Settings.objects.update(verify_show_name=False)
    for space in Makerspace.objects.exclude(member_card_settings__isnull=False).iterator():
        Settings.objects.create(makerspace=space, auto_issue=False, verify_show_name=False)


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0144_guest_pass_waiver_gate_without_passes")]

    operations = [
        migrations.AddField(model_name="membercard", name="number_text",
                            field=models.CharField(blank=True, default="", max_length=32)),
        migrations.AddConstraint(model_name="membercard", constraint=models.UniqueConstraint(
            condition=models.Q(("number_text", ""), _negated=True), fields=("makerspace", "number_text"),
            name="uniq_member_card_number_text")),
        migrations.AddField(model_name="membercardsettings", name="verify_show_name",
                            field=models.BooleanField(default=True)),
        migrations.RunPython(keep_existing_spaces_unchanged, migrations.RunPython.noop),
    ]
