"""Invitation audit IDs must bind to the correct target models after import."""

import pytest

from apps.tenant_migration.audit_reference_guards import validate_audit_meta_references
from apps.tenant_migration.audit_references import AUDIT_META_REFERENCES
from apps.tenant_migration.reference_guards import ReferenceRegistryError
from apps.tenant_migration.semantic_remap import _remap_audit_dict


EDGES = (
    ("staff.invitation_created", "role_id", "makerspaces.MakerspaceRole"),
    ("staff.invitation_accepted", "role_id", "makerspaces.MakerspaceRole"),
    ("staff.invitation_accepted", "membership_id", "makerspaces.MakerspaceMembership"),
)


@pytest.mark.parametrize("action, field, target_label", EDGES)
def test_invitation_audit_meta_remaps_each_id_to_its_declared_model(action, field, target_label):
    class Map:
        def lookup(self, model, source_pk):
            assert model._meta.label == target_label
            assert source_pk == 17
            return 901

    assert _remap_audit_dict(action, {field: 17, "detail": "unchanged"}, Map(), "") == {
        field: 901, "detail": "unchanged",
    }


# The guard only demands declarations for ids the code still emits. Staff invitations now audit as
# `staff_invitation.*` (the `staff.invitation_*` names above remain for historical rows), so the live
# edges are the ones whose removal must be refused.
LIVE_EDGES = (
    ("staff_invitation.accepted", "membership_id"),
    ("staff_invitation.sent", "machine_type_ids"),
    ("staff_invitation.sent", "machine_ids"),
)


@pytest.mark.parametrize("action, field", LIVE_EDGES)
def test_invitation_audit_meta_guard_refuses_a_missing_declaration(action, field):
    declarations = dict(AUDIT_META_REFERENCES)
    del declarations[(action, field)]
    with pytest.raises(ReferenceRegistryError, match="audit meta ID paths drifted"):
        validate_audit_meta_references(declarations)
