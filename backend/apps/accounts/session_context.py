"""Explicit browser cookie namespaces; cookies never select their own account context.

Release 2 (one account per person) keeps exactly two refresh cookies: the person's
(``AUTH_REFRESH_COOKIE``, normally ``refresh_token``) and the superadmin's
(``refresh_token_platform``). The release-1 per-makerspace ``refresh_token_staff_<slug>``
cookies are no longer read; logout expires any that a browser still holds (one release).
"""

from django.utils.translation import gettext
from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

PERSON = "person"
PLATFORM = "platform"
LEGACY_STAFF_COOKIE_PREFIX = "refresh_token_staff_"


class SessionContextSerializer(serializers.Serializer):
    context = serializers.RegexField(
        r"\A(?:person|platform)\Z", max_length=16, default=PERSON,
        help_text="Which browser session: person (default) or platform (the superadmin). A staff "
                  "role is a person's, so there is no per-space session (the release-1 `member` "
                  "and `staff:<slug>` names were removed in U-B, #162(4)).",
    )


def request_context(request):
    serializer = SessionContextSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return PLATFORM if serializer.validated_data["context"] == PLATFORM else PERSON


def cookie_name(context):
    if context == PERSON:
        return settings.AUTH_REFRESH_COOKIE
    if context == PLATFORM:
        return "refresh_token_platform"
    raise AuthenticationFailed(gettext("Invalid account context."))


def legacy_staff_cookie_names(request):
    """Release-1 staff cookies a browser still sends; expired at logout, never read."""
    return sorted(name for name in getattr(request, "COOKIES", {}) if name.startswith(LEGACY_STAFF_COOKIE_PREFIX))


def token_context(token):
    kind = token.get("kind")
    if kind in {PERSON, PLATFORM}:
        return kind
    raise AuthenticationFailed(gettext("Invalid account context."))


def validate_context(token, context):
    if token_context(token) != context:
        raise AuthenticationFailed(gettext("Invalid account context."))


def decode_cookie(raw, context):
    from rest_framework_simplejwt.exceptions import TokenError
    from apps.accounts.claim_tokens import ClaimRefreshToken
    from apps.accounts.tokens import SpaceWorksRefreshToken
    try:
        token = ClaimRefreshToken(raw)
    except TokenError:
        token = SpaceWorksRefreshToken(raw)
    validate_context(token, context)
    return token
