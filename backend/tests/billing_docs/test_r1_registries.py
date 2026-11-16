"""All new fields travel with the core ledger; object ownership stays explicit."""

from types import SimpleNamespace

import pytest

from apps.backup.archive_objects import OBJECT_FIELD_NAMES
from apps.backup.object_ownership_registry import FIELD_OBJECT_RULES, BucketRule
from apps.data_export.classification import EXPORTED_MODEL_FIELDS
from apps.payments.models import MakerspaceBillingSettings, PaymentDocument
from apps.tenant_migration.money_digest import money_fingerprint, assert_money_unchanged, MoneyDriftRefused
from apps.tenant_migration.object_fields import PRIVATE_FIELDS
from apps.tenant_migration.projection_guards import validate_unique_constraint_risks
from apps.tenant_migration.tenant_dump_authority import AUTHORITY_FIELD_OVERRIDES
from apps.tenant_migration.tenant_dump_catalog import FIELD_POLICIES
from apps.tenant_migration.tenant_dump_field_snapshot import FIRST_PARTY_FIELD_NAMES
from apps.tenant_migration.tenant_dump_types import NoAuthorityField
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def test_document_and_billing_fields_have_export_snapshot_and_authority_coverage():
    validate_unique_constraint_risks()
    # Only the settings row's identity/tenant link is ordinary content. Financial
    # snapshots, numbering and reminder policy must retain explicit authority rules.
    ordinary = {("payments.MakerspaceBillingSettings", field) for field in ("id", "makerspace")}
    for model in (PaymentDocument, MakerspaceBillingSettings):
        label = model._meta.label
        fields = {field.name for field in model._meta.local_concrete_fields}
        assert fields == set(EXPORTED_MODEL_FIELDS[label].split()) == FIRST_PARTY_FIELD_NAMES[label]
        for field in fields:
            edge = (label, field)
            if edge in ordinary:
                assert edge not in AUTHORITY_FIELD_OVERRIDES
                assert isinstance(FIELD_POLICIES[edge], NoAuthorityField)
            else:
                assert edge in AUTHORITY_FIELD_OVERRIDES
                assert FIELD_POLICIES[edge] == AUTHORITY_FIELD_OVERRIDES[edge]
    assert "branding_logo_key" in OBJECT_FIELD_NAMES & PRIVATE_FIELDS
    assert any(rule.model_label == "payments.PaymentDocument" and rule.field_name == "branding_logo_key"
               and rule.bucket == BucketRule.PRIVATE for rule in FIELD_OBJECT_RULES)


@pytest.mark.parametrize("field,value", [("bill_prefix", "NEW-"), ("next_bill_number", 50)])
def test_bill_numbering_drift_refuses_publication(field, value):
    space = make_space("r1-numbering-drift")
    policy = MakerspaceBillingSettings.objects.create(makerspace=space)
    capture = SimpleNamespace(source_makerspace_id=space.pk, money_fingerprint_sha256=money_fingerprint(space.pk))
    setattr(policy, field, value)
    policy.save(update_fields=[field])
    with pytest.raises(MoneyDriftRefused):
        assert_money_unchanged(capture)
