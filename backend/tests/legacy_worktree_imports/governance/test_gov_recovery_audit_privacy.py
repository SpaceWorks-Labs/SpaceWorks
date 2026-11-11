"""Staff recovery auditing follows the tenant's hard control-plane privacy boundary."""

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import resolve

from apps.accounts.credential_revocation import revoke_all_credentials
from apps.accounts.models import User
from apps.accounts.services_password_reset import confirm_password_reset, request_password_reset
from apps.accounts.services_password_reset_drain import (
    claim_pending_envelopes, finalize_delivery, prepare_delivery,
)
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_staff

pytestmark = pytest.mark.django_db


def test_hidden_staff_recovery_and_revocation_audits_are_tenant_scoped(monkeypatch, settings):
    settings.PLATFORM_STAFF_ORIGINS = ["http://localhost:5000"]
    monkeypatch.setattr("apps.integrations.email.platform_email_configured", lambda: True)
    monkeypatch.setattr("apps.accounts.services_password_reset_drain.platform_email_configured", lambda: True)
    hidden = Makerspace.objects.create(name="Hidden audit", slug="gov-hidden-audit",
        superadmin_access_enabled=False)
    staff = make_staff(hidden, username="gov-hidden-reset-actor", email="hidden-reset@example.test",
        password="Governance starting password 178!")
    kwargs = {"context": "staff", "makerspace": hidden.slug, "origin": "http://localhost:5000"}
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
    assert events.count() == 5
    assert set(events.values_list("makerspace_id", flat=True)) == {hidden.pk}
    root = User.objects.create_superuser(username="gov-audit-operator")
    request = RequestFactory().get("/control/audit/auditlog/", {"q": staff.username})
    request.user = root
    request.resolver_match = resolve(request.path_info)
    model_admin = admin.site._registry[AuditLog]
    assert not model_admin.get_queryset(request).filter(pk__in=events.values("pk")).exists()
    assert not model_admin.get_changelist_instance(request).queryset.exists()
