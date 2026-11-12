"""Revoke only the explicitly selected browser context, under the account lock."""

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.session_context import decode_cookie
from apps.accounts.surface_policy import assert_surface, token_kind, validate_account_token
from apps.accounts.web_sessions import revoke_session


@transaction.atomic
def revoke_browser_cookie(raw, context, request):
    token = decode_cookie(raw, context)
    actor = User.objects.select_for_update(no_key=True).filter(pk=token.get("user_id")).first()
    if actor is None or token_kind(actor) != token.get("kind"):
        return None
    # Revocation may have committed while we waited for User. Recheck the
    # blacklist inside the lock before modifying either token or session marker.
    token = decode_cookie(raw, context)
    # A restricted or suspended person passes these too (decision 361), so they can sign out.
    validate_account_token(actor, token)
    assert_surface(actor, token.get("surface"), request)
    token.blacklist()
    if token.get("sid"):
        revoke_session(actor, token["sid"])
    return actor
