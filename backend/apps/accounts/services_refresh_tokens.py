"""Serialized rotation for persisted SimpleJWT refresh tokens."""

from django.db import transaction
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.accounts.models import User


def rotate_refresh_token(raw_refresh, *, token_class, validate, mint):
    """Consume one refresh JTI and mint its sole replacement under one row lock."""
    token = token_class(raw_refresh)
    jti = token.get(api_settings.JTI_CLAIM)
    if not jti:
        raise TokenError("Token has no id")

    # Departure owns User before revoking its tokens. Resolve the candidate
    # owner without locking, then take that same order and revalidate the JTI.
    owner_id = OutstandingToken.objects.filter(jti=jti).values_list("user_id", flat=True).first()
    if owner_id is None:
        raise TokenError("Token is invalid")
    with transaction.atomic():
        try:
            owner = User.objects.select_for_update(no_key=True).get(pk=owner_id)
        except User.DoesNotExist as exc:
            raise TokenError("Token is invalid") from exc
        if (not owner.is_active or owner.is_tenant_dump_stub or owner.deletion_requested_at
                or owner.access_status != User.AccessStatus.ACTIVE):
            raise TokenError("Account is not available")
        try:
            outstanding = OutstandingToken.objects.select_for_update().get(jti=jti)
        except OutstandingToken.DoesNotExist as exc:
            raise TokenError("Token is invalid") from exc
        if (outstanding.user_id != owner.pk
                or str(token.get(api_settings.USER_ID_CLAIM)) != str(getattr(owner, api_settings.USER_ID_FIELD))):
            raise TokenError("Token is invalid")
        if BlacklistedToken.objects.filter(token=outstanding).exists():
            raise TokenError("Token is blacklisted")

        context = validate(token)
        _blacklisted, created = BlacklistedToken.objects.get_or_create(
            token=outstanding
        )
        if not created:
            raise TokenError("Token is blacklisted")
        return mint(token, context)
