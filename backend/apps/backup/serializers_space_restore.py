from rest_framework import serializers

from apps.backup.models import BackupArchive, MakerspaceRestoreOperation


class SpaceRestoreSerializer(serializers.ModelSerializer):
    makerspace_slug = serializers.SlugField(source="makerspace.slug", read_only=True)
    makerspace_name = serializers.CharField(source="makerspace.name", read_only=True)
    blocked = serializers.SerializerMethodField(help_text="Rows outside the space would dangle (#113).")

    class Meta:
        model = MakerspaceRestoreOperation
        fields = (
            "id", "makerspace", "makerspace_slug", "makerspace_name", "archive", "source", "safety_archive",
            "stage", "snapshot_at", "preview", "progress", "report", "error_code", "error_detail",
            "blocked", "created_at", "preview_ready_at", "applied_at", "finished_at",
        )
        read_only_fields = fields

    def get_blocked(self, instance) -> bool:
        return bool(instance.preview.get("blocked"))


class SpaceRestoreCreateSerializer(serializers.Serializer):
    archive = serializers.PrimaryKeyRelatedField(
        queryset=BackupArchive.objects.filter(scope=BackupArchive.Scope.MAKERSPACE),
        help_text="The one-space restore point to roll the makerspace back to.",
    )


class SpaceRestoreConfirmSerializer(serializers.Serializer):
    confirm_slug = serializers.CharField(max_length=100, help_text="The makerspace's slug, typed exactly.")


class BackupScheduleSpaceSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField()
    slug = serializers.SlugField()
    name = serializers.CharField()
    last_nightly_at = serializers.DateTimeField(allow_null=True)
    last_backup_at = serializers.DateTimeField(allow_null=True)


class BackupScheduleSerializer(serializers.Serializer):
    automatic_backups_enabled = serializers.BooleanField()
    platform_nightly = serializers.CharField(help_text="When the whole-platform nightly backup runs (UTC).")
    spaces_nightly = serializers.CharField(help_text="When the nightly one-space backups run (UTC).")
    spaces_per_tick = serializers.IntegerField()
    daily_keep_days = serializers.IntegerField()
    weekly_keep_weeks = serializers.IntegerField()
    on_demand_keep_days = serializers.IntegerField()
    server_restore_key_configured = serializers.BooleanField()
    last_platform_success_at = serializers.DateTimeField(allow_null=True)
    spaces = BackupScheduleSpaceSerializer(many=True)
