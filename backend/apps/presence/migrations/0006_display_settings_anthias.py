"""DISPLAY-2 (decision 325): per-screen display settings, Anthias players and links, public page config."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("presence", "0005_session_account_project"),
        ("makerspaces", "0153_account_profile_merge"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnthiasPlayer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("host_url", models.CharField(max_length=200)),
                ("username", models.CharField(blank=True, default="", max_length=80)),
                ("password_enc", models.TextField(blank=True, default="")),
                ("api_version", models.CharField(blank=True, default="", max_length=8)),
                ("anthias_version", models.CharField(blank=True, default="", max_length=40)),
                ("status", models.CharField(choices=[("never", "Never synced"), ("ok", "In sync"), ("error", "Error")],
                                            default="never", max_length=8)),
                ("last_error", models.CharField(blank=True, default="", max_length=200)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                 related_name="anthias_players", to="makerspaces.makerspace")),
            ],
        ),
        migrations.AddIndex(model_name="anthiasplayer",
                            index=models.Index(fields=["makerspace"], name="anthias_player_space_idx")),
        migrations.AddField(model_name="displayscreen", name="layout",
                            field=models.CharField(default="playlist", max_length=12)),
        migrations.AddField(model_name="displayscreen", name="theme",
                            field=models.CharField(default="dark", max_length=8)),
        migrations.AddField(model_name="displayscreen", name="privacy",
                            field=models.CharField(default="profiles", max_length=12)),
        migrations.AddField(model_name="displayscreen", name="refresh_seconds",
                            field=models.PositiveSmallIntegerField(default=30)),
        migrations.AddField(model_name="displayscreen", name="slide_seconds",
                            field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="displayscreen", name="link_secret_enc",
                            field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="displayscreen", name="players",
                            field=models.ManyToManyField(blank=True, related_name="screens", to="presence.anthiasplayer")),
        migrations.CreateModel(
            name="AnthiasAssetLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("asset_id", models.CharField(max_length=64)),
                ("synced_hash", models.CharField(blank=True, default="", max_length=64)),
                ("uri_hash", models.CharField(blank=True, default="", max_length=64)),
                ("display", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="anthias_links", to="presence.displayscreen")),
                ("player", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                             related_name="links", to="presence.anthiasplayer")),
            ],
        ),
        migrations.AddConstraint(model_name="anthiasassetlink",
                                 constraint=models.UniqueConstraint(fields=("player", "display"),
                                                                    name="anthias_link_player_display")),
        migrations.CreateModel(
            name="SpaceNowConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sections", models.JSONField(blank=True, default=list)),
                ("privacy", models.CharField(default="profiles", max_length=12)),
                ("refresh_seconds", models.PositiveSmallIntegerField(default=30)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                                    related_name="now_config", to="makerspaces.makerspace")),
            ],
        ),
    ]
