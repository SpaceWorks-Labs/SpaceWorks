from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.accounts.services_challenge_purge import purge_spent_challenges
from apps.audit.models import AuditLog
from tests.return_helpers import make_user

pytestmark = pytest.mark.django_db


def aged_proof():
    user = make_user("proof-retention")
    proof = ReauthenticationSession.objects.create(user=user, session_id="session:aged",
        surface="staff_api", auth_generation="generation", credential_fingerprint="a" * 64)
    ReauthenticationSession.objects.filter(pk=proof.pk).update(updated_at=timezone.now() - timedelta(days=31))
    return proof


def test_old_proof_cleanup_is_audited_and_recent_proof_remains():
    old = aged_proof()
    fresh = ReauthenticationSession.objects.create(user=old.user, session_id="session:fresh",
        surface="staff_api", auth_generation="generation", credential_fingerprint="b" * 64)
    assert purge_spent_challenges()["accounts.ReauthenticationSession"] == 1
    assert not ReauthenticationSession.objects.filter(pk=old.pk).exists()
    assert ReauthenticationSession.objects.filter(pk=fresh.pk).exists()
    assert AuditLog.objects.get(action="auth.reauthentication_proofs_purged").meta == {"count": 1}


def test_proof_cleanup_rolls_back_when_disclosure_audit_fails(monkeypatch):
    old = aged_proof()
    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")
    monkeypatch.setattr("apps.audit.services.record", fail)
    assert purge_spent_challenges()["accounts.ReauthenticationSession"] == 0
    assert ReauthenticationSession.objects.filter(pk=old.pk).exists()
