"""Per-space "use the platform's credentials when this space has none" (decisions 240, 281).

The switch is ``ChannelConfiguration.use_platform_sender``. Its model default becomes True for NEW rows.
SMS/WhatsApp rows keep their stored (explicit) value. Email and native-push rows never used the flag
(the writer refused it), so their stored False was only the old default; the platform fallback already
applied to them, so those rows are set to True to keep today's behaviour. A space with no row is ON.
"""
from django.db import migrations, models


def email_and_push_on(apps, schema_editor):
    ChannelConfiguration = apps.get_model("integrations", "ChannelConfiguration")
    ChannelConfiguration.objects.filter(channel__in=("email", "native_push")).update(use_platform_sender=True)


class Migration(migrations.Migration):
    dependencies = [("integrations", "0052_firebase_web_config")]

    operations = [
        migrations.AlterField(model_name="channelconfiguration", name="use_platform_sender",
                              field=models.BooleanField(default=True)),
        migrations.RunPython(email_and_push_on, migrations.RunPython.noop),
    ]
