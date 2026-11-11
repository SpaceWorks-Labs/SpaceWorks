"""Staff-role invitation contracts. No response ever carries the accept link (U-B)."""

from rest_framework import serializers

from apps.accounts.models_staff_invitations import StaffInvitation
from apps.accounts.pii_presentation import PiiMaskingSerializerMixin


class StaffInvitationSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    """The invitee address is masked for a superadmin without a PII window (#114.1)."""

    pii_account_fields = ("email",)
    email = serializers.CharField(read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)
    roles = serializers.ListField(source="role_snapshot", child=serializers.CharField(), read_only=True)
    machine_type_ids = serializers.ListField(source="machine_scope_snapshot", child=serializers.IntegerField(),
                                             read_only=True)
    machine_ids = serializers.ListField(source="machine_ids_snapshot", child=serializers.IntegerField(),
                                        read_only=True)
    machine_types = serializers.SerializerMethodField()
    machines = serializers.SerializerMethodField()
    pii_masked = serializers.BooleanField(read_only=True, required=False)

    def get_machine_types(self, obj) -> list[dict]:
        from apps.machines.member_scope_names import named_machine_types
        return named_machine_types(obj.machine_scope_snapshot)

    def get_machines(self, obj) -> list[dict]:
        from apps.machines.member_scope_names import named_machines
        return named_machines(obj.machine_ids_snapshot)

    class Meta:
        model = StaffInvitation
        fields = ["id", "email", "makerspace", "role", "role_name", "roles", "machine_type_ids", "machine_ids", "machine_types", "machines", "expires_at",
                  "accepted_at", "revoked_at", "created_at", "pii_masked"]


class StaffInvitationDeliverySerializer(StaffInvitationSerializer):
    delivery_status = serializers.CharField(help_text="Whether the invitation email was sent; never the link.")

    class Meta(StaffInvitationSerializer.Meta):
        fields = [*StaffInvitationSerializer.Meta.fields, "delivery_status"]


class StaffInvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=20, max_length=200, write_only=True)
    makerspace_slug = serializers.SlugField()
    code = serializers.CharField(max_length=16, required=False, default="", allow_blank=True, write_only=True,
                                 help_text="Omit on the first call; then send the 6-digit code emailed to the "
                                           "invitation address.")


class AcceptedMakerspaceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    name = serializers.CharField()


class StaffInvitationAcceptedSerializer(serializers.Serializer):
    detail = serializers.CharField()
    challenge_required = serializers.BooleanField(
        help_text="True after the first call: a code was emailed; call again with `code`.")
    makerspace = AcceptedMakerspaceSerializer(required=False, help_text="The space where the role was granted.")
