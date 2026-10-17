"""Explicit browser cookie namespaces; cookies never select their own account context."""

import re

from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed


class SessionContextSerializer(serializers.Serializer):
    context = serializers.RegexField(r"\A(?:member|platform|staff:[-a-zA-Z0-9_]+)\Z",
                                     max_length=156, default="member")


def request_context(request):
    serializer = SessionContextSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data["context"]


def cookie_name(context):
    if context == "member":
        return settings.AUTH_REFRESH_COOKIE
    if context == "platform":
        return "refresh_token_platform"
    if re.fullmatch(r"staff:[-a-zA-Z0-9_]+", context):
        return "refresh_token_staff_" + context.partition(":")[2]
    raise AuthenticationFailed("Invalid account context.")


def token_context(token):
    kind = token.get("kind")
    if kind == "staff":
        from apps.makerspaces.models import Makerspace
        slug = Makerspace.objects.filter(pk=token.get("makerspace")).values_list("slug", flat=True).first()
        if not slug:
            raise AuthenticationFailed("Invalid account context.")
        return "staff:" + slug
    if kind in {"member", "platform"}:
        return kind
    raise AuthenticationFailed("Invalid account context.")


def validate_context(token, context):
    if token_context(token) != context:
        raise AuthenticationFailed("Invalid account context.")


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
