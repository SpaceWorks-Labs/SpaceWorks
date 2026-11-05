from rest_framework import serializers

from apps.apiclients.models import ApiClient, ApiKeyRequest
from apps.apiclients.origin_validation import validate_exact_origins
from apps.apiclients.scope_grants import (
    CLIENT_TYPE_SCOPES,
    PEER_SCOPE_ERROR,
    actor_may_grant_privileged_scopes,
    validate_grantable_scopes,
)
from apps.apiclients.scope_registry import BROWSER_SCOPES

TENANT_CLIENT_TYPES = frozenset({"server", "peer"})


class ApiClientSerializer(serializers.ModelSerializer):
    scopes = serializers.ListField(
        child=serializers.CharField(), required=True, allow_empty=False
    )
    allowed_origins = serializers.ListField(
        child=serializers.CharField(), allow_empty=False
    )
    backend_base_url = serializers.SerializerMethodField()
    public_api_base_url = serializers.SerializerMethodField()
    public_makerspace_code = serializers.CharField(
        source="makerspace.public_code",
        read_only=True,
    )

    class Meta:
        model = ApiClient
        fields = [
            "id", "label", "client_id", "client_type", "scopes",
            "rate_limit_tier", "makerspace", "public_makerspace_code",
            "allowed_origins", "backend_base_url", "public_api_base_url",
            "is_active", "last_seen_at", "last_seen_ip", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "client_id", "makerspace", "public_makerspace_code",
            "backend_base_url", "public_api_base_url", "created_at", "updated_at",
            "last_seen_at", "last_seen_ip",
        ]

    def validate_allowed_origins(self, value):
        try:
            return validate_exact_origins(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_scopes(self, value):
        try:
            return validate_grantable_scopes(
                value,
                privileged=self._actor_may_set_privileged_fields(),
            )
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def _actor_may_set_privileged_fields(self):
        """Whether this actor may set globally privileged client fields/scopes.

        Shared by field-level and object-level validation so the two layers cannot
        disagree about who is privileged.
        """
        request = self.context.get("request")
        return actor_may_grant_privileged_scopes(getattr(request, "user", None))

    def validate_client_type_scope_ceiling(self, attrs):
        """Validate the requested state against this serializer's current instance."""
        client_type = attrs.get("client_type") or getattr(
            self.instance, "client_type", "server"
        )
        scopes = attrs.get("scopes", getattr(self.instance, "scopes", []))
        if client_type == "browser" and not set(scopes or []).issubset(BROWSER_SCOPES):
            raise serializers.ValidationError(
                {"scopes": "Browser clients may only use public/read scopes."}
            )
        if client_type == "peer" and not set(scopes or []).issubset(CLIENT_TYPE_SCOPES["peer"]):
            raise serializers.ValidationError({"scopes": PEER_SCOPE_ERROR})
        return attrs

    def validate(self, attrs):
        # Trust knobs remain global-only. Scope validation instead applies the tenant
        # grant ceiling, so tenant input is explicit and never silently discarded.
        if not self._actor_may_set_privileged_fields():
            attrs.pop("rate_limit_tier", None)
            # A Space Manager may choose a server or a peer (read-only) client: both
            # only narrow what the scopes already allow. Browser clients stay global-only.
            if attrs.get("client_type") not in TENANT_CLIENT_TYPES:
                attrs.pop("client_type", None)
        return self.validate_client_type_scope_ceiling(attrs)

    def get_backend_base_url(self, _obj) -> str:
        request = self.context.get("request")
        return request.build_absolute_uri("/").rstrip("/") if request else ""

    def get_public_api_base_url(self, obj) -> str:
        request = self.context.get("request")
        if not request:
            return ""
        code = obj.makerspace.public_code if obj.makerspace_id else ""
        return request.build_absolute_uri(f"/api/v1/public/{code}/").rstrip("/")


class ApiClientScopeOptionSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()
    group = serializers.CharField()
    grantable = serializers.BooleanField()
    lock_reason = serializers.CharField(allow_null=True)
    client_types = serializers.ListField(
        child=serializers.ChoiceField(choices=["server", "browser", "peer"]),
        help_text="Client types this scope may be granted to.",
    )


class ApiClientScopeCatalogResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True, required=False)
    previous = serializers.CharField(allow_null=True, required=False)
    results = ApiClientScopeOptionSerializer(many=True)


class ApiClientCreateResponseSerializer(ApiClientSerializer):
    client_secret = serializers.CharField(read_only=True)

    class Meta(ApiClientSerializer.Meta):
        fields = [
            "id", "label", "client_id", "client_secret", "client_type", "scopes",
            "rate_limit_tier", "makerspace", "public_makerspace_code",
            "allowed_origins", "backend_base_url", "public_api_base_url",
            "is_active", "last_seen_at", "last_seen_ip", "created_at", "updated_at",
        ]
        read_only_fields = [
            *ApiClientSerializer.Meta.read_only_fields,
            "client_secret",
        ]


class ApiKeyRequestSerializer(serializers.ModelSerializer):
    # Required explicitly so the model's blank/default=list cannot bypass validation.
    allowed_origins = serializers.ListField(
        child=serializers.CharField(), allow_empty=False
    )

    class Meta:
        model = ApiKeyRequest
        fields = [
            "id", "makerspace", "label", "reason", "allowed_origins", "status",
            "resolution_note", "created_at", "resolved_at",
        ]
        read_only_fields = [
            "id", "status", "resolution_note", "created_at", "resolved_at",
        ]

    def validate_allowed_origins(self, value):
        try:
            return validate_exact_origins(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
