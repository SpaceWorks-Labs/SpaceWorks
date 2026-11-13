"""Real PostgreSQL lock races: neither side may deadlock or leave a live descendant."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event, current_thread
from time import monotonic

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone
from rest_framework.exceptions import APIException
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts import credential_revocation as revocation
from apps.accounts.models import PasswordResetEnvelope, PasswordResetEnvelopeStatus, User
from apps.accounts.models_devices import DeviceGrant
from apps.accounts.password_reset_crypto import credential_fingerprint, otp_digest
from apps.accounts.serializers_refresh import SpaceWorksTokenRefreshSerializer
from apps.accounts.services_device_tokens import issue_device_token_pair, rotate_device_refresh
from apps.accounts.services_password_reset_confirmation import confirm_password_reset
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.makerspaces.models import Makerspace
from tests.account_split.p1_helpers import staff
from tests.device_helpers import make_native_app_registration

pytestmark = pytest.mark.django_db(transaction=True)
ORIGIN = "http://localhost:5000"
PASSWORD = "Race starting password 671!"
NEW_PASSWORD = "Race recovered password 927!"


def principal(kind):
    if kind == "staff":
        space = Makerspace.objects.create(name="Race", slug="s4c-race")
        return staff(space, "race-staff", email="race@example.test", password=PASSWORD)[0]
    create = User.objects.create_superuser if kind == "platform" else User.objects.create_user
    return create("race-user", email="race@example.test", password=PASSWORD)


def device_tokens(user):
    registration = make_native_app_registration()
    grant = DeviceGrant.objects.create(
        user=user, registration=registration, platform=registration.platform,
        app_id=registration.app_id, environment=registration.environment,
        signing_identity="s4c", attestation_subject_fingerprint="a" * 64,
        attested_at=timezone.now(), last_used_at=timezone.now(),
    )
    return issue_device_token_pair(user, grant)[1]


def recovery_otp(user):
    """Arrange an issued envelope; confirmation itself uses the production service."""
    code = "681924"
    PasswordResetEnvelope.objects.create(
        user=user, context=user.account_kind, makerspace=user.staff_makerspace,
        request_origin=ORIGIN, credential_generation=user.credential_generation,
        email_normalized=user.email, email_fingerprint="e" * 64,
        credential_fingerprint=credential_fingerprint(user, user.email),
        digest=otp_digest(code, user.email), digest_is_live=True,
        status=PasswordResetEnvelopeStatus.ISSUED, requested_at=timezone.now(),
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    return code


def wait_for_block(waiter, blocker):
    deadline = monotonic() + 10
    while monotonic() < deadline:
        with connection.cursor() as cursor:
            cursor.execute("SELECT %s = ANY(pg_blocking_pids(%s))", [blocker, waiter])
            if cursor.fetchone()[0]:
                return
        Event().wait(0.02)
    pytest.fail("The second DB connection did not contend with the paused transaction")


@pytest.mark.parametrize("first", ["refresh", "revoke"])
@pytest.mark.parametrize("operation", ["all", "sessions", "recovery"])
@pytest.mark.parametrize("kind,transport", [
    ("member", "browser"), ("staff", "browser"), ("platform", "browser"),
    ("member", "device"),
])
def test_refresh_and_credential_revocation_serialize(settings, monkeypatch, first, operation, kind, transport):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks and pg_blocking_pids")
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    user = principal(kind)
    raw = device_tokens(user) if transport == "device" else str(SpaceWorksRefreshToken.for_user(user))
    old_jti = SpaceWorksRefreshToken(raw)["jti"]
    code = recovery_otp(user) if operation == "recovery" else None
    paused, release = Event(), Event()
    pids, outcomes = {}, {}
    threads = {}
    ready = {name: Event() for name in ("refresh", "revoke")}

    def pause():
        paused.set()
        assert release.wait(timeout=15)

    original_blacklist = BlacklistedToken.objects.get_or_create

    def blacklist(*args, **kwargs):
        result = original_blacklist(*args, **kwargs)
        if (first == "refresh" and current_thread().ident == threads.get("refresh")
                and kwargs.get("token").jti == old_jti):
            # Reproduce the report's uncommitted blacklist entry while the other
            # connection tries to revoke. The actual SQL locks remain untouched.
            pause()
        return result

    original_revoke = revocation.revoke_authentication

    def revoke_authentication(*args, **kwargs):
        if first == "revoke":
            pause()  # User is held; no token rows have been touched yet.
        return original_revoke(*args, **kwargs)

    monkeypatch.setattr(BlacklistedToken.objects, "get_or_create", blacklist)
    monkeypatch.setattr(revocation, "revoke_authentication", revoke_authentication)

    def run(name):
        close_old_connections()
        try:
            threads[name] = current_thread().ident
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = '12s'")
                cursor.execute("SELECT pg_backend_pid()")
                pids[name] = cursor.fetchone()[0]
            ready[name].set()
            if name == "refresh":
                try:
                    if transport == "device":
                        outcomes[name] = rotate_device_refresh(raw)[1]
                    else:
                        serializer = SpaceWorksTokenRefreshSerializer(data={"refresh": raw})
                        serializer.is_valid(raise_exception=True)
                        outcomes[name] = serializer.validated_data["refresh"]
                except (TokenError, APIException):
                    outcomes[name] = None
            elif operation == "recovery":
                confirm_password_reset(user.email, code, NEW_PASSWORD, context=user.account_kind,
                    origin=ORIGIN)  # decisions 63/66: a staff person recovers as a member
            else:
                function = revocation.revoke_all_credentials if operation == "all" else revocation.revoke_sessions_only
                function(User.objects.get(pk=user.pk), reason="s4c.race")
        finally:
            connection.close()

    second = "revoke" if first == "refresh" else "refresh"
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(run, first)
        try:
            assert paused.wait(timeout=10)
            b = pool.submit(run, second)
            assert ready[second].wait(timeout=5)
            wait_for_block(pids[second], pids[first])
        finally:
            release.set()
        # OperationalError (including deadlock/timeout) is deliberately not caught.
        a.result(timeout=20)
        b.result(timeout=20)

    assert pids["refresh"] != pids["revoke"]
    user.refresh_from_db()
    assert user.credential_generation == 1
    assert not OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True).exists()
    if first == "revoke":
        assert outcomes["refresh"] is None
    else:
        assert outcomes["refresh"] is not None
        with pytest.raises(TokenError):
            SpaceWorksRefreshToken(outcomes["refresh"])
    if transport == "device":
        assert not user.device_grants.filter(status="active").exists()
        assert not user.device_refresh_families.filter(revoked_at__isnull=True).exists()
    if operation == "recovery":
        assert user.check_password(NEW_PASSWORD)
        assert PasswordResetEnvelope.objects.get(user=user).status == PasswordResetEnvelopeStatus.CONSUMED
