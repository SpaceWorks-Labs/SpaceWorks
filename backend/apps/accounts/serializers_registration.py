from django.utils.translation import gettext
from rest_framework import serializers


class MemberSignUpSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=200, trim_whitespace=True)
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(max_length=32, allow_blank=True, required=False, default="")
    password = serializers.CharField(max_length=128, write_only=True)
    website = serializers.CharField(required=False, allow_blank=True, default="")
    # Decision 308: the username is asked for at sign-up (pre-filled by the client from
    # GET /handles/check). Optional on the wire so older clients keep working: without it the
    # server claims the best suggestion atomically with the account.
    handle = serializers.CharField(required=False, allow_blank=True, max_length=30, default="")

    def validate_handle(self, value):
        if not value:
            return ""
        from apps.makerspaces.public_profile_handles import check_handle

        ok, reason = check_handle(value)
        if not ok:
            raise serializers.ValidationError({
                "invalid": gettext("Use 3-30 letters, numbers, dots, underscores or hyphens; start and end with a letter or number."),
                "reserved": gettext("This name is reserved."),
                "taken": gettext("This name is unavailable."),
            }[reason], code=reason)
        return value.lower()

    def validate_display_name(self, value):
        if not value.strip():
            raise serializers.ValidationError(gettext("This field may not be blank."))
        return value


class EmailVerificationConfirmSerializer(serializers.Serializer):
    # Code-only: the endpoint is authenticated, so the caller's active challenge is
    # resolved from request.user + their current email. No challenge_id is exposed
    # (signup/resend return generic acks and the email carries only the code), and we
    # never touch another user's challenge.
    code = serializers.CharField(max_length=6)
