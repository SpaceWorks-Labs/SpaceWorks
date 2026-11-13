"""Refresh takes User before credential rows, matching Stage A revocation."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from time import monotonic, sleep

import pytest
from django.db import close_old_connections, connection, transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.accounts.account_deletion_credentials import revoke
from apps.accounts.models import User
from apps.accounts.models_devices import DeviceRefreshFamily
from apps.accounts.serializers_refresh import SpaceWorksTokenRefreshSerializer
from apps.accounts import services_device_tokens as devices
from apps.accounts.tokens import SpaceWorksRefreshToken
from tests.accounts.test_reauthentication_deletion import native_request

pytestmark = pytest.mark.django_db(transaction=True)


def _credential(kind):
    user = User.objects.create_user(username="refresh-deletion-" + kind, password="Refresh password 1234!")
    if kind == "web":
        raw = str(SpaceWorksRefreshToken.for_user(user))
        def rotate():
            serializer = SpaceWorksTokenRefreshSerializer(data={"refresh": raw})
            serializer.is_valid(raise_exception=True)
            return serializer.validated_data
    else:
        request, family = native_request(user)
        _, raw, _ = devices.issue_device_token_pair(user, request.device_grant, family=family)
        rotate = lambda: devices.rotate_device_refresh(raw)
    return user, raw, rotate


def _wait_until_blocked(pid, future):
    deadline = monotonic() + 5
    while monotonic() < deadline:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_stat_clear_snapshot()")
            cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", [pid])
            row = cursor.fetchone()
        if row and row[0] == "Lock":
            return
        if future.done():
            break
        sleep(0.01)
    raise AssertionError("Refresh never waited for the account lock")


@pytest.mark.parametrize("kind", ["web", "device"])
def test_deletion_revokes_credentials_while_refresh_waits_without_deadlock(kind):
    user, raw, rotate = _credential(kind)
    before = OutstandingToken.objects.filter(user=user).count()
    ready, pids = Event(), []
    def run():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                pids.append(cursor.fetchone()[0])
            ready.set()
            try:
                rotate()
            except (AuthenticationFailed, TokenError):
                return "refused"
            return "rotated"
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            locked = User.objects.select_for_update(no_key=True).get(pk=user.pk)
            future = pool.submit(run)
            assert ready.wait(timeout=5)
            _wait_until_blocked(pids[0], future)
            # With the old token -> User order, refresh held the token while
            # waiting. Stage A would deadlock here trying to revoke that token.
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '2s'")
            now = timezone.now()
            revoke(locked, now)
            locked.is_active = False
            locked.deletion_requested_at = now
            locked.save(update_fields=["is_active", "deletion_requested_at"])
        assert future.result(timeout=10) == "refused"
    assert OutstandingToken.objects.filter(user=user).count() == before


@pytest.mark.parametrize("kind", ["web", "device"])
def test_deletion_timestamp_alone_fences_refresh(kind):
    user, _, rotate = _credential(kind)
    User.objects.filter(pk=user.pk).update(deletion_requested_at=timezone.now())
    with pytest.raises((AuthenticationFailed, TokenError)):
        rotate()


def test_duplicate_device_rotation_preserves_reuse_revocation(monkeypatch):
    user, _, rotate = _credential("device")
    original_decoder = devices.UntypedToken
    decoded = Barrier(2)
    def synchronized(raw):
        token = original_decoder(raw)
        decoded.wait(timeout=10)
        return token
    monkeypatch.setattr(devices, "UntypedToken", synchronized)
    def run(_index):
        close_old_connections()
        try:
            try:
                rotate()
                return "rotated"
            except AuthenticationFailed:
                return "refused"
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert sorted(results) == ["refused", "rotated"]
    family = DeviceRefreshFamily.objects.get(user=user)
    assert family.revoked_at and family.reuse_detected_at
