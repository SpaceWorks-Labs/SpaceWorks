"""Creation-only setup uses the same profile validators as later settings edits."""
from rest_framework import serializers
from apps.admin_api.serializers_makerspace_profile import MakerspaceProfileSerializer
from apps.makerspaces.module_aliases import canonical_module_keys
from apps.makerspaces.module_registry import MODULE_KEYS
from apps.makerspaces.role_catalog import ROLE_CATALOG


class FirstStaffInviteSerializer(serializers.Serializer):
    """Invite the first staff member by email; they accept while signed in to their own account."""
    email = serializers.EmailField(max_length=254)
    role_slug = serializers.ChoiceField(choices=[role.slug for role in ROLE_CATALOG if role.granted_actions])


class CreationProfileSerializer(MakerspaceProfileSerializer):
    """Explicit fields override a pack; omitted fields keep its configuration."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not field.read_only:
                field.required = False

    def to_internal_value(self, data):
        # Nested serializers receive data through run_validation, not initial_data.
        if isinstance(data, dict):
            unknown = set(data) - {"timezone", "country", "opening_hours", "default_currency"}
            if unknown:
                raise serializers.ValidationError({name: ["Unknown profile field."] for name in sorted(unknown)})
        return super().to_internal_value(data)

    def validate(self, attrs):
        return attrs


class ModuleKeyListField(serializers.ListField):
    """Live module keys only in the schema; a retired key from an older client (`printing`,
    decision 340b) is read as the key it was folded into before the choices are checked."""

    def to_internal_value(self, data):
        if isinstance(data, list):
            data = canonical_module_keys(data)
        return super().to_internal_value(data)


class MakerspaceCreationSetupSerializer(serializers.Serializer):
    profile = CreationProfileSerializer(required=False)
    modules = ModuleKeyListField(child=serializers.ChoiceField(choices=sorted(MODULE_KEYS)), max_length=60, required=False)
    first_staff_invite = FirstStaffInviteSerializer(
        required=False, help_text="Atomically creates a staff-role invitation for this address (one account per "
        "person). The invitee accepts it while signed in to their own account with this email; nothing is "
        "attached by email alone. Requires email onboarding.",
    )


class CreationInviteDeliverySerializer(serializers.Serializer):
    """Whether the invitation email was sent. The link goes to the invitee only."""
    delivery_status = serializers.CharField()
