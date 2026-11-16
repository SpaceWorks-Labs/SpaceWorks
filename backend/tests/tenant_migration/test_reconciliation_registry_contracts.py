"""Moved authorization inputs and signature recovery retain explicit policies."""

from apps.tenant_migration.authority_guards import (
    APPS_DIR, AUTHORIZATION_SOURCES, DECLARED_AUTHORITY_FIELDS,
    discover_exported_authority_fields,
)
from apps.tenant_migration.gate_policy_http import HTTP_EXEMPTIONS
from apps.tenant_migration.target_projection import TARGET_FIELD_PROJECTION


def test_moved_authorization_sources_remain_scanned():
    paths = {
        "accounts/surface_policy.py", "accounts/credential_locks.py", "accounts/session_issuance.py",
        "organizations/governance.py", "organizations/access.py",
        "events/organizer_authority.py", "events/series_authority.py",
        "integrations/recipients_addressed.py", "integrations/recipients_owners.py",
        "integrations/notification_sources.py", "integrations/dispatch_policy.py",
        "integrations/messaging/ties.py", "integrations/messaging/eligibility.py",
        "integrations/messaging/consent.py",
    }
    assert {APPS_DIR / path for path in paths} <= set(AUTHORIZATION_SOURCES)
    assert discover_exported_authority_fields() <= DECLARED_AUTHORITY_FIELDS.keys()


def test_signature_ingress_families_remain_reachable_without_exempting_tenant_settings():
    assert {
        "messaging-twilio-platform-status", "messaging-twilio-platform-inbound",
        "messaging-twilio-status", "messaging-twilio-inbound", "messaging-meta-platform", "messaging-meta",
        "whatsapp-meta-webhook", "whatsapp-twilio-inbound", "whatsapp-twilio-status",
    } <= HTTP_EXEMPTIONS.keys()
    assert {"messaging-settings", "messaging-test", "whatsapp-template-list"}.isdisjoint(HTTP_EXEMPTIONS)


def test_imported_addressed_history_cannot_authorize_target_sending():
    assert TARGET_FIELD_PROJECTION[("integrations.MessagingConsent", "action")].value == "opted_out"
    assert TARGET_FIELD_PROJECTION[("integrations.MessagingConsent", "lifted_suppression_id")].value == []
    assert TARGET_FIELD_PROJECTION[("integrations.WhatsAppTemplateBinding", "is_active")].value is False
    assert TARGET_FIELD_PROJECTION[("integrations.WhatsAppTemplateBinding", "needs_review")].value is True


def test_signed_receipt_ingress_does_not_take_an_outer_source_lock(monkeypatch):
    from types import SimpleNamespace
    from apps.tenant_migration import middleware
    from apps.tenant_migration.gate_policy_http import PROVIDER_INGRESS_ROUTES

    def unexpected_resolution(*args):
        raise AssertionError("Signed receipt/STOP ingress must not take an outer tenant lock")

    monkeypatch.setattr(middleware, "_makerspace_ids", unexpected_resolution)
    for name in PROVIDER_INGRESS_ROUTES:
        match = SimpleNamespace(view_name=name)
        monkeypatch.setattr(middleware, "resolve", lambda _path: match)
        request = SimpleNamespace(method="POST", path_info="/provider/callback")
        handler = middleware.SourceMigrationGateMiddleware(lambda _request: "signature-owning-view")
        assert handler(request) == "signature-owning-view"
