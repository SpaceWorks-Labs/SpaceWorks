"""Logout-all and browser/native rotation serialize on the same account row."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.accounts.attestation import VerifiedAttestation
from apps.accounts.credential_revocation import revoke_account_sessions
from apps.accounts.models import User
from apps.accounts.serializers_refresh import SpaceWorksTokenRefreshSerializer
from apps.accounts.services_device_grants import issue_first_device_session
from apps.accounts.services_device_tokens import rotate_device_refresh
from apps.accounts.tokens import SpaceWorksRefreshToken
from tests.accounts.account_factories import make_staff
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.native_helpers_m1d import configure_apple
from tests.accounts.test_account_issuance_races import waiting_worker, bounded_lock_wait
from tests.accounts.test_social_first_grant import create_challenge
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("kind", ["member", "staff"])
@pytest.mark.parametrize("transport", ["browser", "device"])
def test_logout_commits_before_waiting_rotation_without_token_user_deadlock(kind, transport, settings):
    if kind == "staff":
        user = make_staff(make_space("logout-race"), username="logout-race", password="Strong-logout-579!")
    else:
        user = User.objects.create_user(username="logout-race", password="Strong-logout-579!")
    if transport == "browser":
        raw = str(SpaceWorksRefreshToken.for_user(user))
        def rotate():
            serializer = SpaceWorksTokenRefreshSerializer(data={"refresh": raw})
            serializer.is_valid(raise_exception=True)
    else:
        registration = configure_apple(settings)
        challenge = create_challenge(registration, "logout-race-attestation")
        if kind == "staff":
            credential, _ = enrolled(user)
            user._mfa_verified_version = str(credential.version)
        _, raw, _ = issue_first_device_session(user, challenge, VerifiedAttestation("device", {}),
                                                login_method="password")
        rotate = lambda: rotate_device_refresh(raw)

    def rotating():
        try:
            rotate()
        except (AuthenticationFailed, TokenError):
            return "refused"
        return "rotated"

    count = OutstandingToken.objects.filter(user=user).count()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            User.objects.select_for_update(no_key=True).get(pk=user.pk)
            future = waiting_worker(pool, rotating)
            bounded_lock_wait()
            revoke_account_sessions(user)
        assert future.result(timeout=10) == "refused"
    assert OutstandingToken.objects.filter(user=user).count() == count
    assert not OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True).exists()
