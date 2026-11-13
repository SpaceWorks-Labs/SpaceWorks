from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.accounts.reauthentication import versions
from apps.accounts.tokens import SpaceWorksRefreshToken


def verified_staff(actor):
    """S-A: staff MFA is mandatory. Give an elevated person an authenticator and VERIFIED
    proof, as a real sign-in would, so staff routes (strict ones too) admit the token."""
    from apps.accounts import mfa_policy
    if not mfa_policy.required(actor):
        return
    if not mfa_policy.totp_enabled(actor):
        from tests.accounts.mfa_helpers import enrolled
        enrolled(actor)
    mfa_policy.stamp(actor, mfa_policy.credential(actor), "totp")


def bearer_client(actor, *, recent=False, mfa=True):
    """Exercise real JWT authentication; force_authenticate skips the surface guard."""
    if mfa:
        verified_staff(actor)
    token = SpaceWorksRefreshToken.for_user(actor).access_token
    if recent:
        ReauthenticationSession.objects.update_or_create(session_id=token["sid"], defaults={
            "user": actor, "surface": token["surface"], "auth_time": timezone.now(), **versions(actor),
        })
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_ORIGIN="http://localhost:5000")
    return client
