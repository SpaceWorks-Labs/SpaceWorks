from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.pii_presentation import PiiMaskingSerializerMixin, person_pii_visible
from apps.admin_api.serializers_audit import AuditLogSerializer  # noqa: F401 - re-export
from apps.makerspaces.models import MakerspaceMembership


class UserSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    """Account email and name are masked for a superadmin without a window (#114).

    On a makerspace's staff route Lane D's response net (`platform_tenant_pii`) already
    masks by that space's window, so this only decides on platform routes, where no one
    space applies: the person's own reveal, or windows on every space they belong to.
    """

    pii_account_fields = ("email", "first_name", "last_name")
    pii_masked = serializers.BooleanField(read_only=True, required=False)

    def pii_row_visible(self, viewer, instance):
        from apps.accounts.platform_tenant_pii import admitted_spaces
        request = self.context.get("request")
        if request is not None and admitted_spaces(request) is not None:
            return True
        return person_pii_visible(viewer, instance)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "access_status",
            "restriction_reason",
            "telegram_user_id",
            "is_active",
            "pii_masked",
        ]
        read_only_fields = ["id"]


class StaffMembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    makerspace_id = serializers.IntegerField(source="makerspace.id")
    makerspace_slug = serializers.SlugField(source="makerspace.slug")

    class Meta:
        model = MakerspaceMembership
        fields = ["id", "user", "makerspace_id", "makerspace_slug", "role", "created_at"]


class StaffCreateSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    makerspace_id = serializers.IntegerField()
    # Fixed staff roles only; Member uses the community admission surface.
    role = serializers.ChoiceField(
        choices=[
            MakerspaceMembership.Role.SPACE_MANAGER,
            MakerspaceMembership.Role.INVENTORY_MANAGER,
            MakerspaceMembership.Role.MACHINE_MANAGER,
            MakerspaceMembership.Role.EVENT_MANAGER,
            MakerspaceMembership.Role.BOOKING_MANAGER,
            MakerspaceMembership.Role.HANDOVER,
            MakerspaceMembership.Role.TECHNICIAN,
        ]
    )
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate_password(self, value):
        if not value:
            return value
        # Build an unsaved User from the submitted fields so
        # UserAttributeSimilarityValidator (enabled in settings) can reject a
        # password derived from the username/email/name. Without user context that
        # validator is silently skipped.
        candidate_user = User(
            username=self.initial_data.get("username", "") or "",
            email=self.initial_data.get("email", "") or "",
            first_name=self.initial_data.get("first_name", "") or "",
            last_name=self.initial_data.get("last_name", "") or "",
        )
        try:
            validate_password(value, user=candidate_user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value


class RestrictUserSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)
    status = serializers.ChoiceField(
        choices=[User.AccessStatus.RESTRICTED, User.AccessStatus.SUSPENDED],
        default=User.AccessStatus.RESTRICTED,
    )


class ResetPasswordRequestSerializer(serializers.Serializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        min_length=8,
    )


class ResetPasswordResponseSerializer(serializers.Serializer):
    username = serializers.CharField()
    temporary_password = serializers.CharField()
