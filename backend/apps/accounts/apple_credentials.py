"""Apple code exchange and encrypted, per-audience refresh credentials."""

import logging
import time
from uuid import uuid4

import jwt
import requests
from django.conf import settings
from django.db import transaction

from apps.accounts.models import User
from apps.accounts.models_account_purge import AppleRefreshCredential
from apps.accounts.models_social import PlatformSocialAuthSettings, SocialIdentity
from apps.accounts.social_jwt import decode_rs256_token
from apps.audit import services as audit
from apps.makerspaces.secrets import encrypt_value
from apps.accounts.staff_identity import is_person

logger = logging.getLogger(__name__)
APPLE_ISSUER = "https://appleid.apple.com"


def client_secret(client_id):
    configuration = PlatformSocialAuthSettings.load()
    key = configuration.get_apple_private_key()
    if not key or not configuration.apple_team_id or not configuration.apple_key_id:
        raise ValueError("Apple signing configuration unavailable")
    now = int(time.time())
    return jwt.encode({"iss": configuration.apple_team_id, "iat": now, "exp": now + 300,
                       "aud": APPLE_ISSUER, "sub": client_id}, key, algorithm="ES256",
                      headers={"kid": configuration.apple_key_id})


def apple_post(path, data):
    # Endpoint is fixed; redirects must not carry the private client assertion away.
    with requests.post(APPLE_ISSUER + path, data=data, timeout=10, allow_redirects=False) as response:
        if response.status_code != 200:
            raise ValueError("Apple endpoint refused request")
        if path == "/auth/revoke":
            return {}
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Invalid Apple token response")
        return result


def store_refresh_credential(user, claims, authorization_code, redirect_uri=""):
    if not is_person(user) or not authorization_code:
        return
    try:
        client_id = claims["aud"]
        data = {"client_id": client_id, "client_secret": client_secret(client_id),
                "code": authorization_code, "grant_type": "authorization_code"}
        if redirect_uri:
            data["redirect_uri"] = redirect_uri
        response = apple_post("/auth/token", data)
        returned = decode_rs256_token(response.get("id_token", ""), provider="apple",
                                     jwks_url=settings.SOCIAL_APPLE_JWKS_URL,
                                     issuer=APPLE_ISSUER, audience=client_id)
        token = response.get("refresh_token")
        if returned.get("sub") != claims["sub"] or not isinstance(token, str) or not 0 < len(token) <= 16384:
            raise ValueError("Invalid Apple exchange identity")
        encrypted = encrypt_value(token)
        with transaction.atomic():
            locked = User.objects.select_for_update(no_key=True).get(pk=user.pk)
            if not is_person(locked) or locked.account_purged_at or (not locked.is_active and not locked.deletion_requested_at):
                return
            identity = SocialIdentity.objects.filter(user=locked, provider="apple", provider_sub=claims["sub"]).first()
            if identity is None:
                return
            credential, _ = AppleRefreshCredential.objects.update_or_create(
                social_identity=identity, client_id=client_id,
                defaults={"token_ciphertext": encrypted, "version": uuid4()},
            )
            audit.record(user, "account.apple_credential_stored", target=user)
            if locked.deletion_requested_at:
                # A verified sign-in may finish its HTTP exchange after Stage A
                # committed. Keep that token in the durable revocation path too.
                from apps.accounts.apple_revocation import _enqueue, snapshot_credential
                snapshot_credential(locked, credential)
                transaction.on_commit(lambda: _enqueue(locked.pk), robust=True)
    except Exception as exc:
        # Availability of Apple's code exchange must never prevent a verified login.
        logger.warning("apple_credential_exchange_failed", extra={
            "user_id": user.pk, "error_type": type(exc).__name__,
        })
