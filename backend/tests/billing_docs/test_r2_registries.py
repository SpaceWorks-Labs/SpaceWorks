"""Document fetch capabilities never become portable or general API authority."""

import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.apps import apps

from apps.accounts.claim_route_types import Refused
from apps.accounts.claim_routes import CLAIM_ROUTES, policy_for
from apps.apiclients.scope_registry import SCOPE_REGISTRY, lookup
from apps.audit.presentation import project_meta
from apps.backup.main_projection_registry import (
    OMITTED_OPERATIONAL_MODELS, RowDisposition, table_rules,
)
from apps.data_export.classification import EXPORTED_MODELS, MODELS
from apps.data_export.types import OmittedModel
from apps.makerspaces.origin_scope_notification_media import media_grant_targets
from apps.makerspaces.origin_scope_routes import request_route_targets
from apps.tenant_migration.audit_references import (
    AUDIT_META_REFERENCES, AuditReferenceDisposition,
)
from apps.tenant_migration.tenant_dump_catalog import FIELD_POLICIES, validate_field_coverage
from apps.tenant_migration.tenant_dump_field_snapshot import FIRST_PARTY_FIELD_NAMES
from apps.tenant_migration.tenant_dump_model_catalog import FIRST_PARTY_MODEL_RULES
from apps.tenant_migration.tenant_dump_types import AuthorityDisposition, ModelDisposition
from apps.tenant_migration.unique_values import DEPLOYMENT_GLOBAL_UNIQUE_RULES
from apps.tenant_migration.projection_guards import validate_unique_constraint_risks


LABEL = "integrations.NotificationMediaGrant"


def test_media_grants_are_fully_classified_and_dropped_from_artifacts():
    model = apps.get_model(LABEL)
    assert LABEL not in EXPORTED_MODELS
    assert isinstance(MODELS[LABEL], OmittedModel)
    assert FIRST_PARTY_MODEL_RULES[LABEL].disposition is ModelDisposition.DROP
    assert FIRST_PARTY_FIELD_NAMES[LABEL] == {field.name for field in model._meta.fields}
    rules = {edge: rule for edge, rule in FIELD_POLICIES.items() if edge[0] == LABEL}
    validate_field_coverage((model,), rules)
    assert all(rule.dispositions == (AuthorityDisposition.DROP,) for rule in rules.values())
    # Omitted models are dropped as a whole and must not pollute the exported-row registry.
    assert not any(label == LABEL for label, _ in DEPLOYMENT_GLOBAL_UNIQUE_RULES)
    assert model._meta.get_field("token_digest").unique
    validate_unique_constraint_risks()
    assert LABEL in OMITTED_OPERATIONAL_MODELS
    backup_rule = next(rule for rule in table_rules() if rule.model is model)
    assert backup_rule.disposition is RowDisposition.OMIT_OPERATIONAL


@pytest.mark.parametrize("method", ["GET", "HEAD", "POST", "OPTIONS"])
def test_claim_and_api_client_scopes_cannot_substitute_for_media_capability(method):
    assert isinstance(policy_for("notification-media", method), Refused)
    assert lookup("notification-media", method) is None
    # The provider route lies outside the matrices' reachable/protected prefixes.
    assert ("notification-media", method) not in CLAIM_ROUTES
    assert ("notification-media", method) not in SCOPE_REGISTRY


@pytest.mark.parametrize("action", ["notification.media_grant_issued", "notification.media_grant_consumed"])
def test_media_audit_shows_only_references_and_classifies_their_portability(action):
    projected, redacted = project_meta(action, {
        "delivery_id": 18, "document_id": 27, "token": "secret", "pdf_bytes": "private",
    })
    assert projected == {"delivery_id": 18, "document_id": 27}
    assert redacted is True
    delivery = AUDIT_META_REFERENCES[action, "delivery_id"]
    document = AUDIT_META_REFERENCES[action, "document_id"]
    assert delivery.disposition is AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT
    assert document.disposition is AuditReferenceDisposition.REMAP
    assert document.target_model_label == "payments.PaymentDocument"


def test_media_cleanup_audit_keeps_only_source_local_grant_reference():
    projected, redacted = project_meta("notification.media_grant_cleaned", {
        "grant_id": 12, "token_digest": "private",
    })
    assert projected == {"grant_id": 12}
    assert redacted is True
    rule = AUDIT_META_REFERENCES["notification.media_grant_cleaned", "grant_id"]
    assert rule.disposition is AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT


def test_origin_resolution_hashes_token_and_does_not_consume(monkeypatch):
    # Media grants are issued as secrets.token_urlsafe(32): 43 URL-safe characters.
    token = "o" * 43
    model = Mock()
    rows = model.objects.filter.return_value
    rows.values_list.return_value.first.return_value = (42, None)
    monkeypatch.setattr("apps.integrations.notification_media.NotificationMediaGrant", model)
    request = SimpleNamespace(
        resolver_match=SimpleNamespace(url_name="notification-media", kwargs={"token": token}),
        GET={}, method="GET",
    )
    assert request_route_targets(request) == ("notification-media", {42}, False, True)
    filters = model.objects.filter.call_args.kwargs
    assert filters["token_digest"] == hashlib.sha256(token.encode("ascii")).hexdigest()
    assert filters["consumed_at__isnull"] is True
    assert "expires_at__gt" in filters
    rows.values_list.assert_called_once_with("delivery__makerspace_id", "storage_makerspace_id")
    rows.update.assert_not_called()


def test_unknown_media_token_cannot_gain_tenant_scope_from_a_query_hint(monkeypatch):
    model = Mock()
    model.objects.filter.return_value.values_list.return_value.first.return_value = None
    monkeypatch.setattr("apps.integrations.notification_media.NotificationMediaGrant", model)
    request = SimpleNamespace(
        resolver_match=SimpleNamespace(url_name="notification-media", kwargs={"token": "u" * 43}),
        GET={"makerspace_id": "42"}, method="GET",
    )
    assert request_route_targets(request) == ("notification-media", {42}, True, True)


@pytest.mark.parametrize("token", [None, "", "x" * 257, 123])
def test_malformed_media_tokens_never_query_the_database(monkeypatch, token):
    model = Mock()
    monkeypatch.setattr("apps.integrations.notification_media.NotificationMediaGrant", model)
    assert media_grant_targets(token) == set()
    model.objects.filter.assert_not_called()
