"""Whole-registry drift gates; these run on the all-active integration profile."""

from pathlib import Path

import pytest
from django.apps import apps


def test_export_authority_object_reference_and_pointer_declarations():
    from apps.backup.public_page_registry import validate_public_page_registry
    from apps.data_export.guards import validate_all
    from apps.tenant_migration.authority_guards import validate_authority_registry
    from apps.tenant_migration.reference_guards import validate_reference_registry
    validate_all()
    validate_authority_registry()
    validate_reference_registry()
    assert validate_public_page_registry()


def test_source_gate_and_exact_service_participation():
    from apps.tenant_migration.source_gate_guards import validate_source_gate_coverage
    from apps.tenant_migration.source_gate_ast import APPS_DIR, all_functions
    from apps.tenant_migration.gate_policy_public_pages import PAGE_SERVICE_PARTICIPANTS
    functions = all_functions(APPS_DIR)
    assert set(PAGE_SERVICE_PARTICIPANTS) <= functions.keys()
    assert validate_source_gate_coverage()


def test_public_page_audit_actions_and_source_local_history():
    from apps.audit.presentation_guards import presentation_catalog_errors
    from apps.audit.presentation_catalog import PRESENTATION_CATALOG
    from apps.tenant_migration.audit_references import AUDIT_TARGET_DISPOSITIONS, AuditReferenceDisposition
    assert presentation_catalog_errors() == []
    assert "public_page.published" in PRESENTATION_CATALOG
    assert AUDIT_TARGET_DISPOSITIONS["makerspaces.makerspacepublicpagerevision"].disposition is AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT


def test_global_content_creator_and_nullable_link_stay_in_deployment():
    from apps.backup.main_projection_registry import (
        BoundaryDisposition, RowDisposition, boundary_rules, table_rules,
    )
    from apps.backup.public_page_registry import GLOBAL_PAGE_MODELS
    rules = table_rules()
    by_label = {rule.model._meta.label: rule for rule in rules}
    assert all(by_label[label].disposition == RowDisposition.RETAIN_GLOBAL for label in GLOBAL_PAGE_MODELS | {"accounts.User"})
    link = next(rule for rule in boundary_rules(rules)
                if rule.source_model._meta.label == "organizations.OrganizationPublicPageRevisionMember"
                and rule.field.name == "profile")
    assert link.disposition == BoundaryDisposition.PROJECT_NULL_TO_SLICE


def test_page_pointer_allowlist_rejects_field_shape_drift(monkeypatch):
    from apps.backup.public_page_registry import validate_public_page_registry
    from apps.backup.build_errors import BackupBuildError
    from apps.tenant_migration.page_pointer_fixups import PAGE_POINTERS
    monkeypatch.setitem(PAGE_POINTERS, ("organizations.OrganizationPublicPage", "draft_revision"),
                        "organizations.OrganizationPublicPageRevision")
    with pytest.raises(BackupBuildError, match="four reviewed"):
        validate_public_page_registry()


@pytest.mark.django_db
def test_tenant_slice_selects_tenant_handle_but_excludes_global_organization(page_owner):
    from apps.backup.raw_projection import canonical_owner_q
    from apps.data_export.datasets import DATASET_SPECS
    from apps.makerspaces.models_profiles import PublicHandle
    from apps.makerspaces import public_page_services as pages
    from apps.organizations.models import Organization
    from django.utils import timezone
    space, actor = page_owner
    pages.change_handle("makerspace", space.pk, actor=actor, version=0, handle="slice.lab")
    organization = Organization.objects.create(name="Global", slug="slice-global")
    PublicHandle.objects.create(organization=organization, handle="slice.global", changed_at=timezone.now())
    _, predicate = DATASET_SPECS["makerspaces.PublicHandle"]
    assert list(PublicHandle.objects.filter(canonical_owner_q(predicate, space.pk)).values_list("handle", flat=True)) == ["slice.lab"]


@pytest.mark.django_db
def test_mixed_handle_exception_does_not_export_foreign_collaborations(event_owner):
    from apps.backup.raw_projection import canonical_owner_q
    from apps.data_export.datasets import DATASET_SPECS
    from apps.events.models import EventCollaborator
    from apps.makerspaces.models import Makerspace
    space, actor, event = event_owner
    foreign = Makerspace.objects.create(name="Collaborator", slug="slice-collaborator")
    row = EventCollaborator.objects.create(event=event, makerspace=foreign, invited_by=actor)
    _, predicate = DATASET_SPECS["events.EventCollaborator"]
    assert EventCollaborator.objects.filter(canonical_owner_q(predicate, space.pk), pk=row.pk).exists()
    assert not EventCollaborator.objects.filter(canonical_owner_q(predicate, foreign.pk), pk=row.pk).exists()


def test_edge_crawler_and_reserved_root_snapshots():
    from apps.makerspaces.public_profile_reserved import RESERVED_SEGMENTS
    from apps.makerspaces.public_profile_route_inventory import route_segments
    root = Path(__file__).resolve().parents[3]
    assert "e" in RESERVED_SEGMENTS
    assert route_segments(root) <= RESERVED_SEGMENTS
    for relative in ("frontend/nginx.conf", "deploy/Caddyfile.saas", "deploy/Caddyfile.saas-install"):
        text = (root / relative).read_text(encoding="utf-8")
        assert "/share/pages/" in text and "/share/e/" in text
        assert "/share/events/" in text and "/share/bookings/" in text
        assert "/share/profiles/" not in text


def test_events_retention_adapters_survive_runtime_tombstone(monkeypatch):
    from apps.makerspaces.module_purge_plans import BY_KEY
    from apps.separability import registry
    monkeypatch.setattr(registry, "runtime_active", lambda label: label != "events")
    assert BY_KEY["events"].delete is not None
    for label in ("EventPageRevision", "EventSessionIdentity", "EventSessionAlias"):
        assert apps.get_model("events", label) is not None
