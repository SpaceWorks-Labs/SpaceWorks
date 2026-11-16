"""Exact integration declarations for tenant pages and deployment-global history."""

from django.apps import apps

from .build_errors import BackupBuildError

PORTABLE_POINTERS = {
    ("makerspaces.MakerspacePublicPage", "draft_revision"): "makerspaces.MakerspacePublicPageRevision",
    ("makerspaces.MakerspacePublicPage", "published_revision"): "makerspaces.MakerspacePublicPageRevision",
    ("events.EventPage", "draft_revision"): "events.EventPageRevision",
    ("events.EventPage", "published_revision"): "events.EventPageRevision",
}
GLOBAL_PAGE_MODELS = frozenset({
    "organizations.OrganizationPublicPage", "organizations.OrganizationPublicPageRevision",
    "organizations.OrganizationPublicPageAsset", "organizations.OrganizationPublicPageRevisionAsset",
    "organizations.OrganizationPublicPageRevisionMember", "organizations.OrganizationPublicPageStorage",
})
USER_ATTRIBUTION = {
    "makerspaces.MakerspacePublicPageRevision": True,
    "events.EventPageRevision": True,
    "organizations.OrganizationPublicPageRevision": False,
}


def validate_public_page_registry():
    from apps.data_export.datasets import DATASET_SPECS
    from apps.data_export.models import EXPORTED_MODELS
    from apps.data_export.references import USER_EDGES
    from apps.data_export.types import Fidelity
    from apps.tenant_migration.dependency_order import exported_models_in_dependency_order
    from apps.tenant_migration.page_pointer_fixups import PAGE_POINTERS, deferred_pointer
    from apps.tenant_migration.tenant_dump_model_catalog import PROJECTED_MODEL_LABELS
    from apps.tenant_migration.tenant_dump_authority import AUTHORITY_FIELD_OVERRIDES
    from apps.tenant_migration.tenant_dump_types import AuthorityDisposition as D
    from .main_projection_registry import RowDisposition, table_rules
    from .object_ownership_registry import validate_object_reference_registry
    if PAGE_POINTERS != PORTABLE_POINTERS:
        raise BackupBuildError("The four reviewed portable page-pointer edges drifted.")
    for (label, name), target in PAGE_POINTERS.items():
        field = apps.get_model(label)._meta.get_field(name)
        if not deferred_pointer(field) or field.related_model._meta.label != target:
            raise BackupBuildError("A portable page-pointer field changed shape.")
        expected = D.RESET if name == "published_revision" else D.PRESERVE
        if AUTHORITY_FIELD_OVERRIDES[(label, name)].dispositions != (expected,):
            raise BackupBuildError("A portable page-pointer disposition changed.")
    # Sort the entire registry, including empty page datasets, rather than a fixture subset.
    exported_models_in_dependency_order(apps)
    if GLOBAL_PAGE_MODELS & (EXPORTED_MODELS | PROJECTED_MODEL_LABELS | DATASET_SPECS.keys()):
        raise BackupBuildError("Global organization content entered a tenant artifact.")
    rules = {rule.model._meta.label: rule for rule in table_rules()}
    for label in GLOBAL_PAGE_MODELS | {"accounts.User"}:
        if rules[label].disposition != RowDisposition.RETAIN_GLOBAL:
            raise BackupBuildError("Global page content or creator attribution was assigned to a tenant slice.")
    for label, included in USER_ATTRIBUTION.items():
        for fidelity in Fidelity:
            if USER_EDGES[(fidelity, label, "created_by")].included != included:
                raise BackupBuildError("Public page creator user-closure policy drifted.")
    objects = {(rule.model_label, rule.field_name) for rule in validate_object_reference_registry()}
    expected_objects = {
        ("makerspaces.MakerspacePublicPageAsset", "object_key"),
        ("organizations.OrganizationPublicPageAsset", "object_key"),
        ("events.EventPageAsset", "object_key"),
        ("makerspaces.PublicPageObjectCleanup", "object_key"),
    }
    if not expected_objects.issubset(objects):
        raise BackupBuildError("Typed page private-byte declarations are incomplete.")
    return True
