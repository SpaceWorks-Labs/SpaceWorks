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
    lock_reason = serializers.ChoiceField(
        choices=["core", "not_shipped", "limit"], allow_null=True,
        help_text="Why this actor cannot switch it: core (always on), not_shipped (deployment removed "
                  "the app) or limit (managed fair-use limit; only the platform administrator may switch it on).")


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


class FeatureRequirementSerializer(serializers.Serializer):
    modules = serializers.ListField(child=serializers.CharField(), help_text="Parent module plus every required module.")
    features = serializers.ListField(child=serializers.CharField(), help_text="Directly required features (resolve transitively).")


class ModuleGroupListSerializer(serializers.Serializer):
    groups = ModuleGroupSerializer(many=True)
    deployment = DeploymentStatusSerializer(allow_null=True, help_text="Superadmin only; otherwise null.")
    profiles = ModuleProfileSerializer(many=True)
    capability_purge_url = serializers.CharField(allow_null=True, required=False, help_text="Superadmin only: /control/ capability-purge URL for this space; otherwise null.")
    feature_locks = serializers.DictField(
        child=serializers.ChoiceField(choices=["not_shipped"]), required=False,
        help_text="Feature key -> lock reason for feature switches this deployment cannot turn on "
                  "(its own app or a module it needs is not shipped). Absent keys are switchable.")
    feature_requirements = serializers.DictField(
        child=FeatureRequirementSerializer(), required=False,
        help_text="Feature key -> its direct prerequisites from the capability registry, so a client can "
                  "switch prerequisites on first and switch dependents off with it.")


class ModuleInstallResultSerializer(serializers.Serializer):
    installed = serializers.ListField(child=serializers.CharField())
    groups = ModuleGroupSerializer(many=True)


class ModuleUninstallResultSerializer(serializers.Serializer):
    uninstalled = serializers.ListField(child=serializers.CharField())
    groups = ModuleGroupSerializer(many=True)
