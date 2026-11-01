"""Boundary validation and schema shapes for password credential endpoints."""

from rest_framework import serializers


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)


class RecoveryContextSerializer(serializers.Serializer):
    """Recovery is for a person or the platform superadmin only (one account per person).

    ``person`` is the default; ``member`` is its release-1 name, accepted for one release.
    The release-1 ``staff`` context and its ``makerspace`` slug are gone.
    """

    context = serializers.ChoiceField(choices=["person", "member", "platform"], default="person")
    email = serializers.CharField(max_length=254)

    def validate(self, attrs):
        # The stored envelope context keeps the account kind's name: member | platform.
        attrs["context"] = "platform" if attrs["context"] == "platform" else "member"
        if attrs["context"] == "member" and "email" in attrs:
            attrs["email"] = serializers.EmailField().run_validation(attrs["email"])
        return attrs


class ForgotPasswordRequestSerializer(RecoveryContextSerializer):
    pass


class OtpResetPasswordConfirmSerializer(RecoveryContextSerializer):
    code = serializers.RegexField(r"^\d{6}$", write_only=True)
    new_password = serializers.CharField(
        write_only=True, allow_blank=True, trim_whitespace=False
    )


class LegacyResetPasswordConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True, allow_blank=True, trim_whitespace=False
    )


class ResetPasswordConfirmSerializer(RecoveryContextSerializer):
    """Accept exactly one coexistence payload and annotate the selected method."""

    email = serializers.CharField(required=False, max_length=254)
    code = serializers.RegexField(r"^\d{6}$", required=False, write_only=True)
    uid = serializers.CharField(required=False)
    token = serializers.CharField(required=False, write_only=True)
    new_password = serializers.CharField(
        write_only=True, allow_blank=True, trim_whitespace=False
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        otp_complete = "email" in attrs and "code" in attrs
        link_complete = "uid" in attrs and "token" in attrs
        otp_present = "email" in attrs or "code" in attrs
        link_present = "uid" in attrs or "token" in attrs
        if otp_complete and not link_present:
            attrs["method"] = "otp"
            return attrs
        if link_complete and not otp_present and attrs["context"] == "member":
            attrs["method"] = "link"
            return attrs
        raise serializers.ValidationError(
            {"detail": "Submit either email and code, or uid and token."}
        )


class PasswordUpdatedSerializer(serializers.Serializer):
    detail = serializers.CharField()


class ChangePasswordResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class PasswordResetAcknowledgementSerializer(serializers.Serializer):
    detail = serializers.CharField()


class PasswordResetFailureSerializer(serializers.Serializer):
    detail = serializers.CharField()


class PasswordValidationFailureSerializer(serializers.Serializer):
    new_password = serializers.ListField(child=serializers.CharField())


class RecoveryUnavailableSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField()
