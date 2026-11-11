"""Decision 263: Grafana API shapes. The service-account token is write-only and never read
back; the viewer summary never carries a public dashboard's access token."""

from rest_framework import serializers

from .grafana_validation import MODES, PROVIDERS, PUBLIC_TOKEN, UID
from .serializers import MetabaseDatabaseSerializer


class GrafanaDashboardViewSerializer(serializers.Serializer):
    uid = serializers.RegexField(rf"^{UID.pattern}$", max_length=40)
    title = serializers.CharField(max_length=120)
    mode = serializers.ChoiceField(choices=MODES)


class GrafanaDashboardSerializer(GrafanaDashboardViewSerializer):
    public_token = serializers.RegexField(rf"^{PUBLIC_TOKEN.pattern}$", required=False, allow_blank=True, max_length=32,
                                          help_text="Public (shared) dashboard access token; blank for render.")


class GrafanaSummarySerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=PROVIDERS)
    views_version = serializers.IntegerField()
    configured = serializers.BooleanField(help_text="Grafana is on, has a URL and lists dashboards.")
    dashboards = GrafanaDashboardViewSerializer(many=True)
    can_manage = serializers.BooleanField()


class GrafanaConnectionSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=PROVIDERS)
    grafana_url = serializers.CharField(allow_blank=True)
    org_id = serializers.IntegerField()
    token_set = serializers.BooleanField()
    token_updated_at = serializers.DateTimeField(allow_null=True)
    dashboards = GrafanaDashboardSerializer(many=True)
    login_role = serializers.CharField(allow_blank=True)
    database = MetabaseDatabaseSerializer()
    private_hosts_allowed = serializers.BooleanField(
        help_text="Whether this Grafana may live on a private or local address.")


class GrafanaConnectionUpdateSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=PROVIDERS, required=False)
    grafana_url = serializers.CharField(required=False, allow_blank=True, max_length=300)
    org_id = serializers.IntegerField(required=False, min_value=1, max_value=2**31 - 1)
    dashboards = GrafanaDashboardSerializer(many=True, required=False)


class GrafanaTokenSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True, max_length=512, help_text="Service-account token; write-only.")


class GrafanaCheckSerializer(serializers.Serializer):
    name = serializers.ChoiceField(choices=("health", "search"))
    ok = serializers.BooleanField()
    detail = serializers.CharField()


class GrafanaTestSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    version = serializers.CharField(allow_blank=True)
    dashboards_found = serializers.IntegerField(allow_null=True)
    checks = GrafanaCheckSerializer(many=True)


class GrafanaEmbedSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=("public",))
    url = serializers.CharField(help_text="The public (shared) dashboard URL.")


class GrafanaBundleDashboardSerializer(serializers.Serializer):
    area = serializers.CharField()
    uid = serializers.CharField()
    title = serializers.CharField()
    dashboard = serializers.JSONField(help_text="Grafana dashboard model (schemaVersion 39).")


class GrafanaBundleSerializer(serializers.Serializer):
    format = serializers.CharField()
    version = serializers.IntegerField()
    scope = serializers.ChoiceField(choices=("space", "platform"))
    makerspace_id = serializers.IntegerField(allow_null=True)
    views_version = serializers.IntegerField()
    ready = serializers.BooleanField(help_text="A read-only login exists.")
    areas = serializers.ListField(child=serializers.CharField())
    datasource = serializers.JSONField(help_text="Grafana data source provisioning (password is a placeholder).")
    dashboards = GrafanaBundleDashboardSerializer(many=True)
    instructions = serializers.ListField(child=serializers.CharField())
