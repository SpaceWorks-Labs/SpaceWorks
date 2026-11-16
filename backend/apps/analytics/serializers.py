"""Analytics API shapes. Secrets are write-only and never read back; the login password
appears in exactly one response shape (``MetabaseCredentialsSerializer``), returned once."""

from rest_framework import serializers

from .grafana_validation import PROVIDERS


class MetabaseDashboardSerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1, max_value=2**31 - 1)
    title = serializers.CharField(max_length=120, trim_whitespace=True)


class MetabaseSummarySerializer(serializers.Serializer):
    available = serializers.BooleanField(help_text="Logins can be made on this hosting.")
    reason = serializers.CharField(allow_blank=True)
    views_version = serializers.IntegerField()
    provider = serializers.ChoiceField(choices=PROVIDERS, help_text="metabase, grafana or both (decision 263).")
    configured = serializers.BooleanField(help_text="Metabase is on and its URL and embedding secret are set.")
    dashboards = MetabaseDashboardSerializer(many=True)
    can_manage = serializers.BooleanField()


class MetabaseLoginStateSerializer(serializers.Serializer):
    role = serializers.CharField(allow_blank=True)
    exists = serializers.BooleanField(help_text="The role exists in the database right now.")
    created_at = serializers.DateTimeField(allow_null=True)
    rotated_at = serializers.DateTimeField(allow_null=True)


class MetabaseDatabaseSerializer(serializers.Serializer):
    host = serializers.CharField()
    port = serializers.IntegerField()
    database = serializers.CharField()
    schema = serializers.CharField()


class MetabaseConnectionSerializer(serializers.Serializer):
    available = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)
    views_version = serializers.IntegerField()
    provider = serializers.ChoiceField(choices=PROVIDERS)
    configured = serializers.BooleanField()
    dashboards = MetabaseDashboardSerializer(many=True)
    metabase_url = serializers.CharField(allow_blank=True)
    embed_secret_set = serializers.BooleanField()
    show_member_details = serializers.BooleanField(allow_null=True, help_text="Per space only; null on the platform.")
    login = MetabaseLoginStateSerializer()
    database = MetabaseDatabaseSerializer()


class MetabaseConnectionUpdateSerializer(serializers.Serializer):
    metabase_url = serializers.CharField(required=False, allow_blank=True, max_length=300)
    embed_secret = serializers.CharField(required=False, allow_blank=True, max_length=512, write_only=True,
                                         trim_whitespace=True, help_text="Write-only; blank clears it.")
    dashboards = MetabaseDashboardSerializer(many=True, required=False)
    show_member_details = serializers.BooleanField(required=False, help_text="Ignored on the platform.")
    provider = serializers.ChoiceField(choices=PROVIDERS, required=False)


class MetabaseCredentialsSerializer(serializers.Serializer):
    role = serializers.CharField()
    password = serializers.CharField(help_text="Shown once; it is never returned again.")
    host = serializers.CharField()
    port = serializers.IntegerField()
    database = serializers.CharField()
    schema = serializers.CharField()


class MetabaseEmbedSerializer(serializers.Serializer):
    url = serializers.CharField(help_text="Signed Metabase embed URL.")
    expires_at = serializers.DateTimeField()


class MetabaseErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
