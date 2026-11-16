"""S-B: a person's subject export carries their own login-security memory, never secrets."""

import pytest
from django.utils import timezone

from apps.accounts.models import KnownDevice, KnownNetwork, WebAuthnCredential
from apps.data_export.subject_runtime import RUNTIME_FIELDS, runtime_projections, runtime_record
from tests.accounts.login_risk_helpers import person
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def test_runtime_projection_has_labels_and_dates_only():
    for label in ("accounts.KnownDevice", "accounts.WebAuthnCredential", "accounts.KnownNetwork"):
        fields = set(RUNTIME_FIELDS[label])
        assert not fields & {"device_hmac", "prefix_hmac", "public_key", "credential_id", "sign_count", "aaguid"}


def test_export_includes_only_the_persons_rows():
    user, other = person("export-owner"), person("export-other")
    space = make_space("export-space")
    now = timezone.now()
    KnownDevice.objects.create(user=user, device_hmac="a" * 64, ua_label="Safari on iOS", last_verified_at=now)
    KnownDevice.objects.create(user=other, device_hmac="b" * 64, ua_label="Edge on Windows", last_verified_at=now)
    KnownNetwork.objects.create(user=user, granularity="ipv4_24", prefix_hmac="c" * 64, last_seen=now)
    WebAuthnCredential.objects.create(user=user, credential_id="cred-export", public_key=b"key", sign_count=0,
                                      rp_id="example.test", name="Laptop")
    exported = {label: [runtime_record(label, row) for row in query]
                for label, query in runtime_projections(user, space.pk)}
    assert [row["ua_label"] for row in exported["accounts.KnownDevice"]] == ["Safari on iOS"]
    assert exported["accounts.KnownNetwork"][0]["granularity"] == "ipv4_24"
    assert "prefix_hmac" not in exported["accounts.KnownNetwork"][0]
    assert exported["accounts.WebAuthnCredential"][0]["name"] == "Laptop"
