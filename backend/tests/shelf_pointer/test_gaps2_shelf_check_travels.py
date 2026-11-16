"""Decision 337e: ShelfCheck travels in tenant dumps and the space export, and is in no personal (subject) export."""
from apps.data_export.classification import EXPORTED_MODEL_FIELDS, OMITTED_MODELS
from apps.data_export.datasets import DATASET_SPECS
from apps.data_export.references import RELATIONAL_USER_FIELDS
from apps.data_export.subject_selectors import SUBJECT_PATHS
from apps.devices.models import ShelfCheck
from apps.tenant_migration.audit_references_adapter import EDGES
from apps.tenant_migration.audit_references_targets import AuditReferenceDisposition
from apps.tenant_migration.catalog_adapter import FIELD_NAMES
from apps.tenant_migration.tenant_dump_model_catalog import PROJECTED_MODEL_LABELS

LABEL = "devices.ShelfCheck"


def test_shelf_check_is_exported_with_a_field_list_and_not_omitted():
    fields = set(EXPORTED_MODEL_FIELDS[LABEL].split())
    assert LABEL not in OMITTED_MODELS and LABEL in DATASET_SPECS
    assert fields == {f.name for f in ShelfCheck._meta.concrete_fields} == set(FIELD_NAMES[LABEL])


def test_shelf_check_is_projected_in_the_tenant_dump_and_its_author_joins_the_user_closure():
    assert LABEL in PROJECTED_MODEL_LABELS
    assert (LABEL, "checked_by") in RELATIONAL_USER_FIELDS


def test_shelf_check_is_in_no_personal_export_and_its_audit_id_remaps():
    assert LABEL not in SUBJECT_PATHS
    edge = EDGES[("devices.shelf_check_saved", "shelf_check_id")]
    assert edge.disposition is AuditReferenceDisposition.REMAP and edge.target_model_label == LABEL
