"""S-B: retention for remembered devices, networks, alerts and passkey ceremonies (#157)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.login_risk_retention import purge_login_risk_state
from apps.accounts.models import KnownDevice, KnownNetwork, SecurityAlert, WebAuthnCeremony
from apps.accounts.services_challenge_purge import purge_spent_challenges
from tests.accounts.login_risk_helpers import person

pytestmark = pytest.mark.django_db


def _alert(user, *, sent_days_ago, ttl_days=14, digest="a"):
    sent = timezone.now() - timedelta(days=sent_days_ago)
    return SecurityAlert.objects.create(user=user, kind="new_device", nonce_digest=digest * 64,
                                        network_label="198.51.100.0/24", ua_label="Chrome on Android",
                                        sent_at=sent, expires_at=sent + timedelta(days=ttl_days))


def test_purge_follows_the_retention_table():
    user = person("retention")
    now = timezone.now()
    old_network = KnownNetwork.objects.create(user=user, granularity="ipv4_24", prefix_hmac="1" * 64,
                                              last_seen=now - timedelta(days=91))
    fresh_network = KnownNetwork.objects.create(user=user, granularity="ipv4_24", prefix_hmac="2" * 64,
                                                last_seen=now - timedelta(days=10))
    old_device = KnownDevice.objects.create(user=user, device_hmac="3" * 64, last_verified_at=now - timedelta(days=181))
    fresh_device = KnownDevice.objects.create(user=user, device_hmac="4" * 64, last_verified_at=now)
    expired = _alert(user, sent_days_ago=20, digest="b")
    gone = _alert(user, sent_days_ago=60, digest="c")
    live = _alert(user, sent_days_ago=1, digest="d")
    ceremony_old = WebAuthnCeremony.objects.create(purpose="login", challenge="x", rp_id="example.test",
                                                   origin="https://example.test", created_at=now - timedelta(days=3),
                                                   expires_at=now - timedelta(days=2))
    ceremony_new = WebAuthnCeremony.objects.create(purpose="login", challenge="y", rp_id="example.test",
                                                   origin="https://example.test", created_at=now - timedelta(hours=2),
                                                   expires_at=now - timedelta(hours=1))
    purge_login_risk_state()
    assert not KnownNetwork.objects.filter(pk=old_network.pk).exists()
    assert KnownNetwork.objects.filter(pk=fresh_network.pk).exists()
    assert not KnownDevice.objects.filter(pk=old_device.pk).exists()
    assert KnownDevice.objects.filter(pk=fresh_device.pk).exists()
    expired.refresh_from_db()
    assert expired.network_label is None and expired.ua_label is None
    assert not SecurityAlert.objects.filter(pk=gone.pk).exists()
    live.refresh_from_db()
    assert live.network_label == "198.51.100.0/24"
    assert not WebAuthnCeremony.objects.filter(pk=ceremony_old.pk).exists()
    assert WebAuthnCeremony.objects.filter(pk=ceremony_new.pk).exists()


def test_the_daily_auth_purge_runs_it():
    user = person("retention-daily")
    KnownNetwork.objects.create(user=user, granularity="ipv6_64", prefix_hmac="5" * 64,
                                last_seen=timezone.now() - timedelta(days=100))
    deleted = purge_spent_challenges()
    assert deleted["accounts.KnownNetwork"] == 1


def test_account_deletion_removes_every_login_security_row(monkeypatch):
    from apps.accounts import account_deletion_credentials
    user = person("retention-delete")
    now = timezone.now()
    KnownDevice.objects.create(user=user, device_hmac="6" * 64, last_verified_at=now)
    KnownNetwork.objects.create(user=user, granularity="ipv4_24", prefix_hmac="7" * 64, last_seen=now)
    _alert(user, sent_days_ago=0, digest="e")
    account_deletion_credentials.revoke(user, now)
    for model in (KnownDevice, KnownNetwork, SecurityAlert):
        assert not model.objects.filter(user=user).exists()
