"""Relational and semantic reference registries for the global User closure."""
from .fields import FIELDS
from .models import EXPORTED_MODELS
from .references_json_fields import JSON_REFERENCE_FIELDS
from .references_core import (
    _EXCLUDED_USER_EDGE_REASONS as _CORE_EXCLUDED_USER_EDGE_REASONS,
    RAW_USER_REFERENCE_FIELDS,
    RELATIONAL_USER_FIELDS as _CORE_RELATIONAL_USER_FIELDS,
)
from .references_7c import LABEL_USER_FIELDS
from .references_7b import PRINTER_USER_FIELDS
from .references_devices import DEVICE_EXCLUDED_USER_EDGE_REASONS, DEVICE_USER_FIELDS

from apps.tenant_migration.catalog_notifications_contract import USER_FIELDS as NOTIFICATION_USER_FIELDS
from apps.tenant_migration.catalog_p2_presence import USER_FIELDS as PRESENCE_USER_FIELDS
RELATIONAL_USER_FIELDS = PRESENCE_USER_FIELDS | _CORE_RELATIONAL_USER_FIELDS | DEVICE_USER_FIELDS | PRINTER_USER_FIELDS | LABEL_USER_FIELDS | NOTIFICATION_USER_FIELDS
_EXCLUDED_USER_EDGE_REASONS = {
    **_CORE_EXCLUDED_USER_EDGE_REASONS, **DEVICE_EXCLUDED_USER_EDGE_REASONS,
}
from apps.tenant_migration import catalog_p2_events as _p2_events
RELATIONAL_USER_FIELDS |= _p2_events.USER_FIELDS
from apps.tenant_migration.catalog_public_pages import USER_FIELDS as PAGE_USER_FIELDS, EXCLUDED_USER_EDGES
RELATIONAL_USER_FIELDS |= PAGE_USER_FIELDS
_EXCLUDED_USER_EDGE_REASONS.update(EXCLUDED_USER_EDGES)
RELATIONAL_USER_FIELDS |= EXCLUDED_USER_EDGES.keys()
RELATIONAL_USER_FIELDS |= {("makerspaces.PublicHandleRedirect", "user")}
_EXCLUDED_USER_EDGE_REASONS[("makerspaces.PublicHandleRedirect", "user")] = "Retired reservations are deployment-local."
from apps.tenant_migration.catalog_events_programme_references import (
    USER_FIELDS as PROGRAMME_USER_FIELDS, EXCLUDED_USER_EDGE_REASONS as PROGRAMME_EXCLUDED_EDGES,
)
RELATIONAL_USER_FIELDS |= PROGRAMME_USER_FIELDS
from .classification_r2_l1 import RELATIONAL_USER_FIELDS as R2_L1_USER_FIELDS  # noqa: E402
RELATIONAL_USER_FIELDS |= R2_L1_USER_FIELDS
from .classification_r2_l2 import RELATIONAL_USER_FIELDS as R2_L2_USER_FIELDS  # noqa: E402
RELATIONAL_USER_FIELDS |= R2_L2_USER_FIELDS
from .classification_r2_l4 import RELATIONAL_USER_FIELDS as R2_L4_USER_FIELDS  # noqa: E402
RELATIONAL_USER_FIELDS |= R2_L4_USER_FIELDS
from .classification_r2_l5 import RELATIONAL_USER_FIELDS as R2_L5_USER_FIELDS  # noqa: E402
RELATIONAL_USER_FIELDS |= R2_L5_USER_FIELDS
from .classification_r2_l15 import RELATIONAL_USER_FIELDS as R2_L15_USER_FIELDS  # noqa: E402
RELATIONAL_USER_FIELDS |= R2_L15_USER_FIELDS
from .classification_l12 import RELATIONAL_USER_FIELDS as L12_USER_FIELDS  # noqa: E402
RELATIONAL_USER_FIELDS |= L12_USER_FIELDS
from .classification_l23 import RELATIONAL_USER_FIELDS as L23_USER_FIELDS  # noqa: E402
RELATIONAL_USER_FIELDS |= L23_USER_FIELDS
from .classification_l16 import RELATIONAL_USER_FIELDS as L16_USER_FIELDS  # noqa: E402
RELATIONAL_USER_FIELDS |= L16_USER_FIELDS
from .classification_l3 import EXCLUDED_USER_EDGE_REASONS as L3_EXCLUDED, RELATIONAL_USER_FIELDS as L3_USER_FIELDS  # noqa: E402
RELATIONAL_USER_FIELDS |= L3_USER_FIELDS
from .classification_r2_l6 import RELATIONAL_USER_FIELDS as R2_L6_USER_FIELDS  # noqa: E402
RELATIONAL_USER_FIELDS |= R2_L6_USER_FIELDS
from .classification_r2_l18 import (  # noqa: E402
    EXCLUDED_USER_EDGE_REASONS as R2_L18_EXCLUDED, RELATIONAL_USER_FIELDS as R2_L18_USER_FIELDS,
)
RELATIONAL_USER_FIELDS |= R2_L18_USER_FIELDS
_EXCLUDED_USER_EDGE_REASONS.update(L3_EXCLUDED)
_EXCLUDED_USER_EDGE_REASONS.update(R2_L18_EXCLUDED)
_EXCLUDED_USER_EDGE_REASONS.update(PROGRAMME_EXCLUDED_EDGES)
_EXCLUDED_USER_EDGE_REASONS.update(_p2_events.EXCLUDED_USER_EDGE_REASONS)
from apps.tenant_migration.catalog_reimbursements import (
    USER_FIELDS as REIMBURSEMENT_USER_FIELDS, EXCLUDED_USER_EDGE_REASONS as REIMBURSEMENT_EXCLUDED_EDGES,
)
RELATIONAL_USER_FIELDS |= REIMBURSEMENT_USER_FIELDS
_EXCLUDED_USER_EDGE_REASONS.update(REIMBURSEMENT_EXCLUDED_EDGES)
from .classification_security import USER_FIELDS as SECURITY_USER_FIELDS, EXCLUDED_USER_EDGE_REASONS as SECURITY_EDGES
RELATIONAL_USER_FIELDS |= SECURITY_USER_FIELDS
_EXCLUDED_USER_EDGE_REASONS.update(SECURITY_EDGES)
from .classification_unified_accounts import (  # noqa: E402
    RELATIONAL_USER_FIELDS as UA1_USER_FIELDS, EXCLUDED_USER_EDGE_REASONS as UA1_EDGES,
)
RELATIONAL_USER_FIELDS |= UA1_USER_FIELDS
_EXCLUDED_USER_EDGE_REASONS.update(UA1_EDGES)
from .classification_login_security import (  # noqa: E402
    RELATIONAL_USER_FIELDS as S0_USER_FIELDS, EXCLUDED_USER_EDGE_REASONS as S0_EDGES,
)
RELATIONAL_USER_FIELDS |= S0_USER_FIELDS
_EXCLUDED_USER_EDGE_REASONS.update(S0_EDGES)
from .classification_r2_l10 import (  # noqa: E402
    RELATIONAL_USER_FIELDS as R2_L10_USER_FIELDS, EXCLUDED_USER_EDGE_REASONS as R2_L10_EDGES,
)
RELATIONAL_USER_FIELDS |= R2_L10_USER_FIELDS
_EXCLUDED_USER_EDGE_REASONS.update(R2_L10_EDGES)
from .classification_r2_l11 import (  # noqa: E402
    RELATIONAL_USER_FIELDS as R2_L11_USER_FIELDS, EXCLUDED_USER_EDGE_REASONS as R2_L11_EDGES,
)
RELATIONAL_USER_FIELDS |= R2_L11_USER_FIELDS
_EXCLUDED_USER_EDGE_REASONS.update(R2_L11_EDGES)
from .types import (
    Fidelity,
    Omitted,
    SemanticUserRef,
    SourceLocalProvenance,
    UserEdge,
)
class DanglingUserReferenceError(RuntimeError):
    """A raw user ID cannot be bound safely in a portable archive."""
def require_raw_user(fidelity, *, model, row_pk, field, user_id, existing_user_ids):
    """Enforce the declared no-dangling contract before a raw ID is remapped."""
    if fidelity is Fidelity.PORTABLE and user_id not in existing_user_ids:
        raise DanglingUserReferenceError(
            f"{model} row {row_pk} has dangling {field}={user_id}"
        )
    return user_id
RELATIONAL_USER_FIELDS |= frozenset({("machines.MachineUsageEntry", "member"), ("integrations.PushDeliveryAttempt", "recipient")})
_EXCLUDED_USER_EDGE_REASONS[("integrations.PushDeliveryAttempt", "recipient")] = "Runtime delivery ownership is exported only through the personal allowlist; never a portable tenant user edge."
RELATIONAL_USER_FIELDS |= frozenset({("integrations.MessagingConsent", "user"), ("integrations.MessagingDelivery", "user")})
_EXCLUDED_USER_EDGE_REASONS[("integrations.MessagingDelivery", "user")] = "Personal runtime telemetry is omitted from tenant artifacts."
USER_EDGES = {}
for _fidelity in Fidelity:
    for _label, _field in RELATIONAL_USER_FIELDS | RAW_USER_REFERENCE_FIELDS:
        disposition = FIELDS.get((_fidelity, _label, _field))
        included = _label in EXPORTED_MODELS and not isinstance(disposition, Omitted)
        USER_EDGES[(_fidelity, _label, _field)] = UserEdge(
            included=included,
            raw=(_label, _field) in RAW_USER_REFERENCE_FIELDS,
            reason=(
                "Pull the referenced person into the bounded user closure."
                if included
                else _EXCLUDED_USER_EDGE_REASONS.get(
                    (_label, _field),
                    "The source model or field is excluded at this fidelity.",
                )
            ),
        )

POLYMORPHIC_PAIRS = frozenset(
    {
        ("audit.AuditLog", "target_type+target_id"),
        ("boxes.QrCode", "target_type+target_id"),
        ("hardware_requests.PublicToolLoan", "target_type+target_id"),
        ("operations.QrPrintBatchItem", "target_type+target_id"),
    }
)

JSON_FIELDS = JSON_REFERENCE_FIELDS

SEMANTIC_REFERENCES = {}
for _fidelity in Fidelity:
    # PORTABLE keeps audit targets as inert source provenance, so it does not pull user
    # targets into the global closure. REDACTED remains shipped operator-facing behavior;
    # narrowing it would silently drop people from an existing export.
    SEMANTIC_REFERENCES[(_fidelity, "audit.AuditLog", "target_type+target_id")] = (
        (
            SemanticUserRef(
                "audit.AuditLog",
                "target_type=accounts.user + target_id",
                "A user audit target joins the REDACTED user closure, as shipped.",
            ),
            SourceLocalProvenance(
                "audit.AuditLog",
                "target_type!=accounts.user + target_id",
                "Non-user polymorphic targets retain their source model label.",
            ),
        )
        if _fidelity is Fidelity.REDACTED
        else (
            SourceLocalProvenance(
                "audit.AuditLog",
                "target_type + target_id",
                "The audit target registry decides remap versus inert source provenance.",
            ),
        )
    )
    for _model, _location in POLYMORPHIC_PAIRS - {
        ("audit.AuditLog", "target_type+target_id")
    }:
        SEMANTIC_REFERENCES[(_fidelity, _model, _location)] = (
            SourceLocalProvenance(
                _model, _location, "Physical/domain target IDs are source-local provenance."
            ),
        )
    for _model, _field in JSON_FIELDS:
        if (_model, _field) == ("events.SubmissionSnapshot", "sealed_member_ids"):
            decision = SemanticUserRef(_model, "sealed_member_ids[]",
                "Frozen roster members join portable identity closure; readable exports omit this private vector.",
                included=_fidelity is Fidelity.PORTABLE)
        elif (_model, _field) == ("audit.AuditLog", "meta"):
            decision = SourceLocalProvenance(
                _model,
                "meta id-bearing paths",
                "The per-action audit registry remaps or source-namespaces every ID path.",
            )
        elif _field.endswith("_actor_snapshot"):
            # `source_user_id` here is deliberately NOT a live reference: Phase 7 v13
            # made imported actor references typed TEXT snapshots precisely because the
            # source user may not exist at the target or may map to a different person.
            # Remapping it would bind evidence to the wrong human, so it stays
            # source-local at BOTH fidelities.
            decision = SourceLocalProvenance(
                _model,
                f"{_field}.source_user_id",
                "Imported actor provenance is source-local text and is never remapped.",
            )
        else:
            decision = SourceLocalProvenance(
                _model,
                f"{_field}.*_id",
                "Reviewed JSON schema contains no live user reference at this fidelity.",
            )
        SEMANTIC_REFERENCES[(_fidelity, _model, f"json:{_field}")] = (decision,)
