"""Staff recovery and revocation audits are written into the tenant's own audit scope."""

import pytest

from apps.accounts.credential_revocation import revoke_all_credentials
from apps.accounts.services_password_reset import confirm_password_reset, request_password_reset
from apps.accounts.services_password_reset_drain import (
    claim_pending_envelopes, finalize_delivery, prepare_delivery,
)
from apps.audit.models import AuditLog
from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_staff_recovery_and_revocation_audits_are_tenant_scoped(monkeypatch, settings):
    settings.PLATFORM_STAFF_ORIGINS = ["http://localhost:5000"]
    monkeypatch.setattr("apps.integrations.email.platform_email_configured", lambda: True)
    monkeypatch.setattr("apps.accounts.services_password_reset_drain.platform_email_configured", lambda: True)
    # Decisions 63/66: there is no staff recovery context; recovery is the platform account's
    # (or a person's), and its audits carry no tenant scope.
    staff = User.objects.create_superuser(username="gov-reset-actor", email="reset-actor@example.test",
        password="Governance starting password 178!")
    kwargs = {"context": "platform", "origin": "http://localhost:5000"}
    request_password_reset(staff.email, **kwargs)
    claim = claim_pending_envelopes(owner="audit-privacy")[0]
    attempt = prepare_delivery(claim)
    assert attempt is not None and not isinstance(attempt, str)
    assert finalize_delivery(claim, delivered=True)
    confirm_password_reset(staff.email, attempt.code, "Recovered governance password 781!", **kwargs)
    revoke_all_credentials(staff, reason="privacy_regression", actor=staff)
    actions = {"auth.password_reset_requested", "auth.password_reset_confirm_attempted",
        "user.password_reset_via_email", "account.credentials_revoked"}
    events = AuditLog.objects.filter(action__in=actions)
    assert set(events.values_list("action", flat=True)) == actions
    assert set(events.values_list("makerspace_id", flat=True)) == {None}
