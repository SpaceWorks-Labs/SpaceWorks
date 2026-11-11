# Decision 223(l): per-makerspace and platform wallet-pass signing credentials (encrypted, write-only).
import django.db.models.deletion
from django.db import migrations, models


def _fields():
    return [
        ('apple_pass_type_id', models.CharField(blank=True, default='', max_length=120)),
        ('apple_team_id', models.CharField(blank=True, default='', max_length=20)),
        ('apple_cert_pem', models.TextField(blank=True, default='')),
        ('apple_key_pem', models.TextField(blank=True, default='')),
        ('apple_wwdr_pem', models.TextField(blank=True, default='')),
        ('apple_cert_fingerprint', models.CharField(blank=True, default='', max_length=64)),
        ('apple_cert_expires_at', models.DateTimeField(blank=True, null=True)),
        ('google_issuer_id', models.CharField(blank=True, default='', max_length=32)),
        ('google_class_prefix', models.CharField(blank=True, default='spaceworks_card', max_length=40)),
        ('google_service_account', models.TextField(blank=True, default='')),
        ('google_key_fingerprint', models.CharField(blank=True, default='', max_length=64)),
        ('updated_at', models.DateTimeField(auto_now=True)),
    ]


class Migration(migrations.Migration):

    dependencies = [
        ('card_designs', '0005_outfit_font_family'),
        ('makerspaces', '0123_l3_member_cards'),
    ]

    operations = [
        migrations.CreateModel(
            name='MakerspaceWalletCredentials',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                *_fields(),
                ('makerspace', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                                    related_name='wallet_credentials', to='makerspaces.makerspace')),
            ],
            options={'verbose_name_plural': 'makerspace wallet credentials', 'abstract': False},
        ),
        migrations.CreateModel(
            name='PlatformWalletCredentials',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                *_fields(),
            ],
            options={'verbose_name_plural': 'platform wallet credentials', 'abstract': False},
        ),
    ]
