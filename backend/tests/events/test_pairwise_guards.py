"""Registry guards the pairwise models and routes must satisfy (classification, routes, PII, gates)."""

import pytest
from django.apps import apps
from django.core.management import call_command


def test_data_export_classification_is_total():
    from apps.data_export.guards import validate_all
    validate_all()


def test_tenant_migration_fields_and_omissions_cover_the_pairwise_models():
    from apps.tenant_migration.catalog_events_programme import FIELD_NAMES
    from apps.tenant_migration.omitted_field_guards import validate_omitted_field_reconstructions
    validate_omitted_field_reconstructions()
    for label in ("events.JudgePairwiseComparison", "events.JudgePairwiseInvalidation", "events.JudgePairwiseCursor"):
        assert {f.name for f in apps.get_model(label)._meta.concrete_fields} == FIELD_NAMES[label], label


def test_object_reference_and_authority_registries():
    from apps.backup.object_ownership_registry import validate_object_reference_registry
    from apps.tenant_migration.authority_guards import validate_authority_registry
    from apps.tenant_migration.source_gate_guards import validate_http_coverage, validate_task_coverage
    validate_object_reference_registry()
    validate_task_coverage()
    validate_http_coverage()
    validate_authority_registry()


def test_every_pairwise_route_is_classified_for_claims_delegation_and_api_clients():
    from apps.accounts.checks import check_delegated_routes
    from apps.accounts.claim_route_guard import validate_claim_route_matrix
    from apps.apiclients.scope_registry import validate_registry
    validate_claim_route_matrix()
    assert not check_delegated_routes()
    validate_registry()


@pytest.mark.django_db
def test_models_match_the_migrations():
    call_command("makemigrations", "events", "--check", "--dry-run", verbosity=0)


def test_pairwise_notes_are_registered_scoped_pii():
    from apps.encryption.registry_events_programme import programme_pii_fields
    rows = programme_pii_fields(lambda *values: values)
    assert ("events.JudgePairwiseComparison", "notes") in {(row[0], row[1]) for row in rows}
