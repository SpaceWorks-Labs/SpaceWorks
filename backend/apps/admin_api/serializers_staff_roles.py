"""The staff-roles HTTP contract: one row per person's staff-track membership (U-B).

Capability flags (``can``) are viewer-relative. Names and emails are masked for a
superadmin without a PII window on the space (#114.1).
"""

from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import APIException

from apps.accounts.pii_presentation import PiiMaskingSerializerMixin
from apps.makerspaces.models import MakerspaceMembership


class StaffRoleCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1, required=False,
                                       help_text="Grant to this community member of the space.")
    email = serializers.EmailField(max_length=254, required=False,
                                   help_text="Send an invitation to this address instead.")
    roles = serializers.ListField(child=serializers.CharField(), allow_empty=False, max_length=8)
    machine_type_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), default=list)
    machine_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), default=list,
                                        help_text="Individual machines of this space, unioned with the types.")
    expires_in_days = serializers.IntegerField(min_value=1, max_value=30, default=7,
                                               help_text="Invitation lifetime (email invitations only).")

    def validate(self, attrs):
        if bool(attrs.get("user_id")) == bool(attrs.get("email")):
            raise serializers.ValidationError(gettext("Provide exactly one of user_id or email."))
        return attrs


class StaffRoleChangeSerializer(serializers.Serializer):
    roles = serializers.ListField(child=serializers.CharField(), allow_empty=False, max_length=8, required=False)
    machine_type_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False)
    machine_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False,
                                        help_text="Replaces the individual machines; omit to keep them.")

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(gettext("Provide roles, machine_type_ids or machine_ids."))
        return attrs


class StaffRoleRevokeSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class StaffRoleCapabilitiesSerializer(serializers.Serializer):
    change_roles = serializers.BooleanField()
    revoke = serializers.BooleanField()
    restore = serializers.BooleanField()
    reset_mfa = serializers.BooleanField(help_text="S-A's MFA-reset rule allows this viewer to reset the person.")


class StaffRoleSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    pii_account_fields = ("display_name", "email")
    pii_masked = serializers.BooleanField(read_only=True, required=False)
    user_id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    display_name = serializers.CharField(source="user.display_name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    roles = serializers.SerializerMethodField()
    machine_type_ids = serializers.SerializerMethodField()
    machine_ids = serializers.SerializerMethodField()
    machine_types = serializers.SerializerMethodField()
    machines = serializers.SerializerMethodField()
    mfa_enabled = serializers.SerializerMethodField()
    granted_at = serializers.DateTimeField(source="created_at", read_only=True)
    can = serializers.SerializerMethodField()

    class Meta:
        model = MakerspaceMembership
        fields = ["id", "user_id", "username", "display_name", "email", "roles", "machine_type_ids", "machine_ids", "machine_types", "machines", "status",
                  "mfa_enabled", "granted_at", "revoked_at", "revocation_reason", "can", "pii_masked"]

    def get_pii_makerspace_id(self, instance):
        return instance.makerspace_id

    def get_pii_subject(self, instance):
        return instance.user

    def get_roles(self, obj) -> list[str]:
        from apps.accounts.staff_account_policy import role_keys
        return role_keys(obj)

    def get_machine_type_ids(self, obj) -> list[int]:
        from apps.machines.member_scope_services import current_scope
        return current_scope(obj)

    def get_machine_ids(self, obj) -> list[int]:
        from apps.machines.member_scope_services import current_machine_scope
        return current_machine_scope(obj)

    def get_machine_types(self, obj) -> list[dict]:
        from apps.machines.member_scope_names import named_machine_types
        from apps.machines.member_scope_services import current_scope
        return named_machine_types(current_scope(obj))

    def get_machines(self, obj) -> list[dict]:
        from apps.machines.member_scope_names import named_machines
        from apps.machines.member_scope_services import current_machine_scope
        return named_machines(current_machine_scope(obj))

    def get_mfa_enabled(self, obj) -> bool:
        from apps.accounts import mfa_policy
        return mfa_policy.is_enrolled(obj.user)

    @extend_schema_field(StaffRoleCapabilitiesSerializer)
    def get_can(self, obj):
        from apps.accounts import mfa_reset
        from apps.accounts.staff_account_policy import require_authority

        actor, space = self.context["actor"], self.context["space"]
        try:
            require_authority(actor, space, target=obj.user)
            allowed = True
        except APIException:
            allowed = False
        active = obj.status == "active"
        last = active and "space_manager" in self.get_roles(obj) and not MakerspaceMembership.staff_tracks.filter(
            makerspace=space, status="active", assigned_role__slug="space_manager", user__is_active=True,
            user__access_status="active").exclude(pk=obj.pk).exists()
        return {"change_roles": allowed and active and not last, "revoke": allowed and active and not last,
                "restore": allowed and not active,
                "reset_mfa": active and mfa_reset.rule_for(actor, obj.user, space) is not None}


class StaffRoleChoiceSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()
    combinable = serializers.BooleanField(help_text="False for the Space Manager role, which is held alone.")


class StaffMachineTypeChoiceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class StaffMachineChoiceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    machine_type_id = serializers.IntegerField()


class StaffRolePolicySerializer(serializers.Serializer):
    grantable_roles = StaffRoleChoiceSerializer(many=True)
    can_manage_space_managers = serializers.BooleanField()
    email_invites_available = serializers.BooleanField()
    machine_types = StaffMachineTypeChoiceSerializer(many=True)
    machines = StaffMachineChoiceSerializer(many=True)
    scoped_role_slugs = serializers.ListField(
        child=serializers.CharField(),
        help_text="Roles whose reach is narrowed by machine_type_ids / machine_ids (nothing listed = nothing).")


class StaffRoleListSerializer(serializers.Serializer):
    """DRF page of staff rows, plus the viewer's policy for this space."""
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = StaffRoleSerializer(many=True)
    policy = StaffRolePolicySerializer()


class StaffRoleCreatedSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=("granted", "invited"))
    staff_role = StaffRoleSerializer(allow_null=True)
    invitation_id = serializers.IntegerField(allow_null=True)
    delivery_status = serializers.CharField(allow_null=True, help_text="Invitations only; never the link.")
