"""Response shapes of the module install routes (#193 OpenAPI contract): documentation only."""
from rest_framework import serializers


class ModuleRowSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()
    installed = serializers.BooleanField()
    core = serializers.BooleanField()
    available = serializers.BooleanField(help_text="False when this deployment does not ship the owning app.")
    requires = serializers.ListField(child=serializers.CharField())
    pulls_in = serializers.ListField(child=serializers.CharField())
    required_by = serializers.ListField(child=serializers.CharField())
    workflows = serializers.ListField(child=serializers.CharField())
    install_requires_superadmin = serializers.BooleanField()
    limits = serializers.ListField(child=serializers.CharField())


class ModuleGroupSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()
    always_on = serializers.BooleanField()
    installed_count = serializers.IntegerField()
    module_count = serializers.IntegerField()
    modules = ModuleRowSerializer(many=True)


class DeploymentAppSerializer(serializers.Serializer):
    app_label = serializers.CharField()
    label = serializers.CharField(help_text="Translated display name of the app.")
    shipped = serializers.BooleanField()
    note = serializers.CharField(allow_blank=True)


class DeploymentStatusSerializer(serializers.Serializer):
    apps = DeploymentAppSerializer(many=True)
    env_line = serializers.CharField()
    requires_restart = serializers.BooleanField()


class ModuleProfileSerializer(serializers.Serializer):
    key = serializers.CharField()
    description = serializers.CharField()


class ModuleGroupListSerializer(serializers.Serializer):
    groups = ModuleGroupSerializer(many=True)
    deployment = DeploymentStatusSerializer(allow_null=True, help_text="Superadmin only; otherwise null.")
    profiles = ModuleProfileSerializer(many=True)


class ModuleInstallResultSerializer(serializers.Serializer):
    installed = serializers.ListField(child=serializers.CharField())
    groups = ModuleGroupSerializer(many=True)


class ModuleUninstallResultSerializer(serializers.Serializer):
    uninstalled = serializers.ListField(child=serializers.CharField())
    groups = ModuleGroupSerializer(many=True)
