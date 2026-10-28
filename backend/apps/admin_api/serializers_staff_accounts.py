"""The shared staff-account HTTP contract; capability flags are viewer-relative."""

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import APIException

from apps.accounts.models import StaffInvitation, User
from apps.accounts.staff_account_policy import require_authority, role_keys
from apps.accounts.services_staff_invitations import onboarding_available
from apps.makerspaces.models import MakerspaceMembership
from apps.admin_api.serializers_roles import RoleSerializer


class StaffAccountCreateSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=200)
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True, default="")
    username = serializers.CharField(max_length=150, required=False)
    roles = serializers.ListField(child=serializers.CharField(), allow_empty=False, max_length=6)
    machine_type_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), default=list)

    def validate(self, attrs):
        if not attrs.get("email") and not attrs.get("username"):
            raise serializers.ValidationError("Provide an email address or username.")
        return attrs


class StaffAccountChangeSerializer(serializers.Serializer):
    roles = serializers.ListField(child=serializers.CharField(), allow_empty=False, max_length=6, required=False)
    machine_type_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide roles or machine_type_ids.")
        return attrs


class StaffAccountDeactivateSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class StaffAccountPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(max_length=1024, required=False, trim_whitespace=False, write_only=True)
    generate = serializers.BooleanField(required=False, default=False)
    reset_mfa = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if bool(attrs.get("password")) == attrs.get("generate", False):
            raise serializers.ValidationError("Provide a password or generate=true, exclusively.")
        return attrs


class StaffAccountPasswordResultSerializer(serializers.Serializer):
    generated_password = serializers.CharField(allow_null=True)


class StaffAccountCapabilitiesSerializer(serializers.Serializer):
    change_roles = serializers.BooleanField()
    set_password = serializers.BooleanField()
    deactivate = serializers.BooleanField()
    reactivate = serializers.BooleanField()
    resend_invite = serializers.BooleanField()


class StaffAccountSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    machine_type_ids = serializers.SerializerMethodField()
    mfa_enabled = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(source="date_joined")
    invitation_pending = serializers.SerializerMethodField()
    can = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "display_name", "email", "roles", "machine_type_ids", "is_active",
                  "must_change_password", "mfa_enabled", "last_login", "created_at", "invitation_pending", "can"]

    def membership(self, obj):
        cache = self.__dict__.setdefault("_membership_cache", {})
        if obj.pk not in cache:
            cache[obj.pk] = obj.makerspace_memberships.select_related("user", "assigned_role").prefetch_related(
                "additional_roles__role").get(makerspace_id=obj.staff_makerspace_id)
        return cache[obj.pk]

    def get_roles(self, obj) -> list[str]:
        cache = self.__dict__.setdefault("_role_cache", {})
        if obj.pk not in cache:
            cache[obj.pk] = role_keys(self.membership(obj))
        return cache[obj.pk]

    def get_machine_type_ids(self, obj) -> list[int]:
        from apps.machines.member_scope_services import current_scope
        return current_scope(self.membership(obj))

    def get_mfa_enabled(self, obj) -> bool:
        from apps.accounts.models_mfa import UserMFA
        return UserMFA.objects.filter(user=obj, enabled_at__isnull=False).exists()

    def get_invitation_pending(self, obj) -> bool:
        return StaffInvitation.objects.filter(account=obj, accepted_at__isnull=True,
            revoked_at__isnull=True, expires_at__gt=timezone.now(),
            credential_generation=obj.credential_generation).exists()

    @extend_schema_field(StaffAccountCapabilitiesSerializer)
    def get_can(self, obj):
        actor, space = self.context["actor"], self.context["space"]
        allowed = True
        try:
            require_authority(actor, space, target=obj)
        except APIException:
            allowed = False
        last = False
        if "space_manager" in self.get_roles(obj):
            last = not MakerspaceMembership.objects.filter(makerspace=space, status="active",
                assigned_role__slug="space_manager", user__is_active=True,
                user__access_status="active", user__retired_at__isnull=True,
                user__is_tenant_dump_stub=False).exclude(user=obj).exists()
        return {"change_roles": allowed and not last, "set_password": allowed and obj.is_active,
                "deactivate": allowed and obj.is_active and not last,
                "reactivate": allowed and not obj.is_active,
                "resend_invite": allowed and obj.is_active and bool(obj.email)
                    and not obj.has_usable_password() and onboarding_available(space)}


class StaffAccountCreatedSerializer(serializers.Serializer):
    account = StaffAccountSerializer()
    invitation_sent = serializers.BooleanField()


class StaffAccountInvitationResultSerializer(serializers.Serializer):
    invitation_sent = serializers.BooleanField()


class StaffMachineTypeChoiceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class StaffAccountPolicySerializer(serializers.Serializer):
    creatable_roles = serializers.ListField(child=serializers.CharField())
    can_manage_space_managers = serializers.BooleanField()
    email_onboarding_available = serializers.BooleanField()
    machine_types = StaffMachineTypeChoiceSerializer(many=True)
    roles = RoleSerializer(many=True)
