"""Run in Docker after migrations; these guards inspect actual Django state."""
import pytest


def test_export_and_user_edge_guards():
    from apps.data_export.guards import validate_all
    from apps.tenant_migration.omitted_field_guards import validate_omitted_field_reconstructions
    validate_all()
    validate_omitted_field_reconstructions()


def test_programme_models_match_literal_snapshot():
    from django.apps import apps
    from apps.tenant_migration.catalog_events_programme import FIELD_NAMES
    for label, names in FIELD_NAMES.items():
        assert {f.name for f in apps.get_model(label)._meta.concrete_fields} == names, label


def test_object_ownership_and_retention_are_complete():
    from apps.backup.object_ownership_registry import validate_object_reference_registry
    validate_object_reference_registry()


def test_claim_api_client_and_delegated_guards():
    from apps.accounts.claim_route_guard import validate_claim_route_matrix
    from apps.accounts.checks import check_delegated_routes
    from apps.apiclients.scope_registry import validate_registry
    validate_claim_route_matrix()
    assert not check_delegated_routes()
    validate_registry()


def test_source_gate_and_authority_guards():
    from apps.tenant_migration.source_gate_guards import validate_task_coverage, validate_http_coverage
    from apps.tenant_migration.authority_guards import validate_authority_registry
    validate_task_coverage()
    validate_http_coverage()
    validate_authority_registry()


@pytest.mark.django_db
def test_unknown_retention_rule_fails_before_querying():
    from apps.backup.object_ownership_registry import FieldObjectRule, BucketRule
    from apps.backup.object_reference_retention import adapter_for
    from apps.backup.build_errors import BackupBuildError
    with pytest.raises(BackupBuildError):
        adapter_for(FieldObjectRule("events.Event", "image_key", BucketRule.PUBLIC_IMAGE, retention_aware=True))
