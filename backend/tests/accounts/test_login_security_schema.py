"""Lane S0: login-security schema, constraints, classification and the frozen contract."""

from datetime import timedelta

import pytest
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from apps.accounts import login_security_contract as contract
from apps.accounts import merge_registry
from apps.accounts.login_methods import _SWITCH_FIELDS, LOGIN_METHODS_CACHE_KEY, _switches
from apps.accounts.models import (
    IPAccessRule, IPAutoBlock, KnownDevice, KnownNetwork, MFAChallenge, PlatformLoginMethods, SecurityAlert,
    StaffMfaGrace, User, WebAuthnCeremony, WebAuthnCredential,
)
from apps.data_export.classification import EXPORTED_MODEL_FIELDS, OMITTED_MODELS
from apps.tenant_migration.tenant_dump_model_catalog import FIRST_PARTY_MODEL_RULES
from apps.tenant_migration.tenant_dump_types import ModelDisposition

pytestmark = pytest.mark.django_db
ACCOUNT_MODELS = ("WebAuthnCredential", "WebAuthnCeremony", "StaffMfaGrace", "KnownDevice", "KnownNetwork",
                  "SecurityAlert", "IPAccessRule", "IPAutoBlock")


@pytest.fixture
def person():
    return User.objects.create_user("s0-person", email="s0@example.test", password="x" * 20)


def refused(**create):
    model = create.pop("model")
    with pytest.raises(IntegrityError), transaction.atomic():
        model.objects.create(**create)


def test_passkey_credential_ids_are_unique_and_never_blank(person):
    WebAuthnCredential.objects.create(user=person, credential_id="abc", public_key=b"k", rp_id="space.test")
    refused(model=WebAuthnCredential, user=person, credential_id="abc", public_key=b"k", rp_id="space.test")
    refused(model=WebAuthnCredential, user=person, credential_id="", public_key=b"k", rp_id="space.test")
    refused(model=WebAuthnCredential, user=person, credential_id="def", public_key=b"k", rp_id="")


def test_ceremony_constraints(person):
    now = timezone.now()
    base = dict(model=WebAuthnCeremony, rp_id="space.test", origin="https://space.test",
                expires_at=now + timedelta(minutes=5), created_at=now)
    refused(**base, purpose="registration", challenge="c1")
    refused(**base, purpose="mfa", challenge="c2", user=person)
    refused(**base, purpose="bogus", challenge="c3", user=person)
    refused(**{**base, "expires_at": now}, purpose="login", challenge="c4")
    WebAuthnCeremony.objects.create(**{k: v for k, v in base.items() if k != "model"}, purpose="login", challenge="c5")


def test_ceremony_cascades_with_its_mfa_challenge(person):
    now = timezone.now()
    challenge = MFAChallenge.objects.create(user=person, token_digest="t" * 64, credential_fingerprint="f",
                                            auth_generation="g", mfa_version="00000000-0000-0000-0000-000000000001",
                                            expires_at=now + timedelta(minutes=5))
    WebAuthnCeremony.objects.create(purpose="mfa", user=person, mfa_challenge=challenge, challenge="m1",
                                    rp_id="space.test", origin="https://space.test",
                                    expires_at=now + timedelta(minutes=5))
    challenge.delete()
    assert not WebAuthnCeremony.objects.exists()


def test_known_network_and_device_are_unique_per_person(person):
    now = timezone.now()
    KnownNetwork.objects.create(user=person, granularity="ipv4_24", prefix_hmac="p", last_seen=now)
    refused(model=KnownNetwork, user=person, granularity="ipv4_24", prefix_hmac="p", last_seen=now)
    KnownNetwork.objects.create(user=person, granularity="ipv6_64", prefix_hmac="p", last_seen=now)
    refused(model=KnownNetwork, user=person, granularity="ipv4_16", prefix_hmac="q", last_seen=now)
    KnownDevice.objects.create(user=person, device_hmac="d", last_verified_at=now)
    refused(model=KnownDevice, user=person, device_hmac="d", last_verified_at=now)


def test_security_alert_constraints(person):
    now = timezone.now()
    SecurityAlert.objects.create(user=person, kind="new_device", nonce_digest="n1", expires_at=now + timedelta(days=1))
    refused(model=SecurityAlert, user=person, kind="new_device", nonce_digest="n1", expires_at=now + timedelta(days=1))
    refused(model=SecurityAlert, user=person, kind="bogus", nonce_digest="n2", expires_at=now + timedelta(days=1))
    refused(model=SecurityAlert, user=person, kind="lockout", nonce_digest="n3", sent_at=now, expires_at=now)


def test_one_staff_grace_per_person(person):
    now = timezone.now()
    StaffMfaGrace.objects.create(user=person, started_at=now, ends_at=now + contract.STAFF_MFA_GRACE, source="grant")
    refused(model=StaffMfaGrace, user=person, started_at=now, ends_at=now + timedelta(days=3), source="invite")
    other = User.objects.create_user("s0-other", email="s0o@example.test", password="x" * 20)
    refused(model=StaffMfaGrace, user=other, started_at=now, ends_at=now, source="grant")
    refused(model=StaffMfaGrace, user=other, started_at=now, ends_at=now + timedelta(days=3), source="bogus")


def test_ip_rules_and_blocks(person):
    IPAccessRule.objects.create(cidr="203.0.113.0/24", action="deny", created_by=person)
    refused(model=IPAccessRule, cidr="203.0.113.0/24", action="allow", created_by=person)
    refused(model=IPAccessRule, cidr="198.51.100.0/24", action="maybe", created_by=person)
    IPAutoBlock.objects.create(ip_key="k", network="203.0.113.7", blocked_until=timezone.now())
    refused(model=IPAutoBlock, ip_key="k", network="203.0.113.8", blocked_until=timezone.now())


def test_on_delete_choices():
    def rule(model, name):
        return model._meta.get_field(name).remote_field.on_delete
    for model in (WebAuthnCredential, KnownDevice, KnownNetwork, SecurityAlert, StaffMfaGrace):
        assert rule(model, "user") is models.CASCADE
    assert rule(IPAccessRule, "created_by") is models.PROTECT


def test_passkey_switch_defaults_on_and_reads_fail_open(settings):
    assert "passkeys_enabled" in _SWITCH_FIELDS
    assert PlatformLoginMethods.load().passkeys_enabled is True
    from django.core.cache import cache
    cache.set(LOGIN_METHODS_CACHE_KEY, {"password_enabled": True})  # a pre-S0 cached row
    assert _switches().passkeys_enabled is True


def test_merge_dispositions():
    expected = {("accounts.IPAccessRule", "created_by"): merge_registry.REPOINT,
                ("accounts.StaffMfaGrace", "user"): merge_registry.UNIQUE_RESOLVE}
    for label in ("WebAuthnCredential", "WebAuthnCeremony", "KnownDevice", "KnownNetwork", "SecurityAlert"):
        expected[(f"accounts.{label}", "user")] = merge_registry.KEEP_ON_SHELL
    for edge, disposition in expected.items():
        assert merge_registry.disposition_for(*edge) == disposition
    assert merge_registry.problems() == {key: [] for key in merge_registry.problems()}


def test_export_and_tenant_dump_classification():
    for name in ACCOUNT_MODELS:
        assert f"accounts.{name}" in OMITTED_MODELS
        assert FIRST_PARTY_MODEL_RULES[f"accounts.{name}"].disposition is ModelDisposition.DROP
    assert EXPORTED_MODEL_FIELDS["makerspaces.MakerspaceSecurityPolicy"] == "id makerspace values updated_at"
    assert FIRST_PARTY_MODEL_RULES["makerspaces.MakerspaceSecurityPolicy"].disposition is ModelDisposition.PROJECT


def test_contract_vocabularies_are_distinct():
    for values in (contract.ERROR_CODES, contract.MFA_METHODS, contract.FACTORS, contract.CHALLENGE_PURPOSES,
                   contract.CEREMONY_PURPOSES, contract.ALERT_KINDS, contract.GRACE_SOURCES,
                   tuple(setting.key for setting in contract.PER_SPACE_SETTINGS)):
        assert len(values) == len(set(values))
    assert all(action.startswith("auth.") for action in contract.AUDIT_ACTIONS)
    assert contract.STAFF_MFA_GRACE == timedelta(days=3)
    assert {value for value, _ in WebAuthnCeremony._meta.get_field("purpose").choices} == set(contract.CEREMONY_PURPOSES)
