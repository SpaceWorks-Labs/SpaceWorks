"""Explicit already-verified browser sessions for unrelated authority regression tests.

New step-up tests do not use this helper: they exercise the real no-proof denial and
credential endpoints. This fixture records a proof; it never weakens production checks.
"""

import uuid
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.accounts.reauthentication import versions


def force_recent_authenticate(client, user=None, token=None):
    if user is None or not getattr(user, "pk", None):
        return client.force_authenticate(user=user, token=token)
    if token is not None and not hasattr(token, "get"):
        return client.force_authenticate(user=user, token=token)
    if user.account_kind == "platform" and settings.PLATFORM_STAFF_ORIGINS:
        client._credentials.setdefault("HTTP_ORIGIN", settings.PLATFORM_STAFF_ORIGINS[0])
    from apps.accounts.surface_policy import token_kind
    kind = token_kind(user)
    token = token or {"surface": "platform" if kind == "platform" else "member"}
    token.setdefault("kind", kind)
    token.setdefault("credential_generation", user.credential_generation)
    sid = token.get("sid") or "session:" + str(uuid.uuid4())
    token["sid"] = sid
    token["surface"] = token.get("surface") or ("platform" if kind == "platform" else "member")
    OutstandingToken.objects.get_or_create(jti=sid, defaults={"user": user, "token": "",
        "created_at": timezone.now(), "expires_at": timezone.now() + timedelta(days=1)})
    ReauthenticationSession.objects.update_or_create(session_id=sid, defaults={
        "user": user, "surface": token["surface"], "auth_time": timezone.now(), **versions(user)})
    return client.force_authenticate(user=user, token=token)


def force_recent_control_login(client, user):
    from tests.accounts.mfa_helpers import force_mfa_login
    force_mfa_login(client, user)
    if user.is_superuser:
        ReauthenticationSession.objects.update_or_create(session_id="control:" + client.session.session_key,
            defaults={"user": user, "surface": "control", "auth_time": timezone.now(), **versions(user)})


STEP_UP_PASSWORD = "Fresh step-up password 492!"


def session_token(user):
    """A live browser-session claim set (sid backed by an OutstandingToken), unverified."""
    from apps.accounts.surface_policy import token_kind
    kind = token_kind(user)
    surface = "platform" if kind == "platform" else "member"
    sid = "session:" + str(uuid.uuid4())
    OutstandingToken.objects.get_or_create(jti=sid, defaults={"user": user, "token": "",
        "created_at": timezone.now(), "expires_at": timezone.now() + timedelta(days=1)})
    return {"sid": sid, "surface": surface, "kind": kind,
            "credential_generation": user.credential_generation}


def reauthenticate(client, user):
    """The REAL step-up: verify the password through POST /auth/reauth on this session.

    Returns the session token so APIRequestFactory requests can reuse the proven session.
    """
    from rest_framework.test import APIClient
    if not user.check_password(STEP_UP_PASSWORD):
        user.set_password(STEP_UP_PASSWORD)
        user.save(update_fields=["password"])
        user.refresh_from_db()
    token = session_token(user)
    client = client or APIClient()
    client.force_authenticate(user=user, token=token)
    response = client.post("/api/v1/auth/reauth", {"password": STEP_UP_PASSWORD}, format="json")
    assert response.status_code == 200 and response.data["verified"], response.data
    return token
