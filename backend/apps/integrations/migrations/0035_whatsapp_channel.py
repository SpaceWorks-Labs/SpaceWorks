from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('integrations', '0034_notification_contract')]
    operations = [
        migrations.AlterField(model_name='notificationpreference', name='channel', field=models.CharField(max_length=16, choices=[('in_app', 'Inbox'), ('email', 'Email'), ('telegram', 'Telegram'), ('slack', 'Slack'), ('mattermost', 'Mattermost'), ('discord', 'Discord'), ('webhook', 'Signed webhook'), ('native_push', 'Native push'), ('whatsapp', 'WhatsApp')])),
        migrations.AlterField(model_name='notificationdeliverylog', name='channel', field=models.CharField(max_length=16, choices=[('whatsapp', 'WhatsApp'), ('telegram', 'Telegram'), ('slack', 'Slack'), ('mattermost', 'Mattermost'), ('discord', 'Discord'), ('webhook', 'Signed webhook'), ('native_push', 'Native push')])),
        migrations.AlterField(model_name='dailynotificationcounter', name='channel', field=models.CharField(max_length=16, choices=[('whatsapp', 'WhatsApp'), ('telegram', 'Telegram'), ('slack', 'Slack'), ('mattermost', 'Mattermost'), ('discord', 'Discord'), ('webhook', 'Signed webhook'), ('native_push', 'Native push')])),
    ]
