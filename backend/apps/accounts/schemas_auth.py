"""OpenAPI serializers for browser session endpoints."""

from drf_spectacular.utils import inline_serializer
from rest_framework import serializers


AuthMembershipSerializer = inline_serializer(
    name="AuthMembership",
    fields={
        "id": serializers.IntegerField(),
        "slug": serializers.CharField(),
        # An organization-derived entry claims no role: organization grants confer
        # actions, never identity, so role/role_id/role_slug are null there and
        # role_name carries the organization's name.
        "role": serializers.CharField(allow_null=True),
        "role_id": serializers.IntegerField(allow_null=True),
        "role_ids": serializers.ListField(child=serializers.IntegerField()),
        "role_slugs": serializers.ListField(child=serializers.CharField()),
        "role_names": serializers.ListField(child=serializers.CharField()),
        "role_name": serializers.CharField(),
        "role_slug": serializers.CharField(allow_null=True),
        "source": serializers.ChoiceField(choices=["membership", "organization"]),
        "actions": serializers.ListField(child=serializers.CharField()),
        "can_configure_machine_types": serializers.BooleanField(),
        "is_machine_only": serializers.BooleanField(),
        "can_refer": serializers.BooleanField(),
        "can_verify": serializers.BooleanField(),
        "verified_at": serializers.DateTimeField(allow_null=True),
        "referrals_enabled": serializers.BooleanField(),
    },
)
class AuthUserPayload(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    display_name = serializers.CharField()
    phone = serializers.CharField()
    email_verified = serializers.BooleanField()
    role = serializers.CharField()
    is_superuser = serializers.BooleanField()
    must_change_password = serializers.BooleanField()
    account_kind = serializers.ChoiceField(choices=("member", "staff", "platform"))
    staff_makerspace = inline_serializer(name="AuthStaffMakerspace", fields={
        "id": serializers.IntegerField(), "slug": serializers.CharField(), "name": serializers.CharField(),
    }, allow_null=True)
    makerspaces = serializers.ListField(child=AuthMembershipSerializer)

    def get_fields(self):
        from apps.makerspaces.resource_grant_sources import registered_sources

        fields = super().get_fields()
        for source in registered_sources():
            if source.payload_serializer is not None:
                fields[source.key] = source.payload_serializer(many=True, required=False)
        return fields


UserPayloadSerializer = AuthUserPayload()

LoginRequestSerializer = inline_serializer(
    name="LoginRequest",
    fields={
        "username": serializers.CharField(),
        "password": serializers.CharField(write_only=True),
        "context": serializers.ChoiceField(choices=("member", "staff", "platform"), required=False),
        "makerspace": serializers.SlugField(required=False, max_length=150),
        "surface": serializers.ChoiceField(
            choices=("member", "staff", "delegated"), required=False
        ),
    },
)
LoginResponseSerializer = inline_serializer(
    name="LoginResponse",
    fields={
        "access": serializers.CharField(),
        "surface": serializers.ChoiceField(
            choices=("member", "staff", "staff_api", "delegated", "platform", "verification_only")
        ),
        "user": UserPayloadSerializer,
    },
)
RefreshResponseSerializer = inline_serializer(
    name="RefreshResponse", fields={"access": serializers.CharField(), "user": AuthUserPayload()}
)
LogoutResponseSerializer = inline_serializer(
    name="LogoutResponse", fields={"detail": serializers.CharField()}
)
