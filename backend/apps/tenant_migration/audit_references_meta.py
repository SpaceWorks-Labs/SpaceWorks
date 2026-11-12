"""AuditLog metadata reference declarations for portable tenant archives."""

from .audit_references_meta_devices import DEVICE_AUDIT_EDGES
from .audit_references_meta_devices_7d import DEVICE_7D_AUDIT_EDGES
from .audit_references_meta_kiosk import KIOSK_AUDIT_EDGES
from .audit_references_meta_membership import MEMBERSHIP_AUDIT_EDGES
from .audit_references_meta_payments import PAYMENT_AUDIT_EDGES
from .audit_references_meta_phase5 import PHASE5_AUDIT_EDGES
from .audit_references_meta_reports import REPORT_SCHEDULE_AUDIT_EDGES
from .audit_references_meta_source_local import SOURCE_LOCAL_AUDIT_EDGES
from .audit_references_meta_core import CORE_AUDIT_META_REFERENCES, R, S, _reference  # noqa: F401

_SOURCE_LOCAL_EDGES = SOURCE_LOCAL_AUDIT_EDGES

AUDIT_META_REFERENCES = dict(CORE_AUDIT_META_REFERENCES)

AUDIT_META_REFERENCES.update(_reference(S, None, *_SOURCE_LOCAL_EDGES))
from .audit_references_meta_snapshots import SNAPSHOT_AUDIT_EDGES

AUDIT_META_REFERENCES.update(SNAPSHOT_AUDIT_EDGES)
AUDIT_META_REFERENCES.update(PHASE5_AUDIT_EDGES)
AUDIT_META_REFERENCES.update(MEMBERSHIP_AUDIT_EDGES)
from .audit_references_guest_passes import EDGES as GUEST_PASS_AUDIT_EDGES  # noqa: E402
AUDIT_META_REFERENCES.update(GUEST_PASS_AUDIT_EDGES)
from .audit_references_l3b import EDGES as L3B_AUDIT_EDGES  # noqa: E402
AUDIT_META_REFERENCES.update(L3B_AUDIT_EDGES)
from .audit_references_r3_org_units import EDGES as R3_ORG_UNITS_AUDIT_EDGES  # noqa: E402
AUDIT_META_REFERENCES.update(R3_ORG_UNITS_AUDIT_EDGES)
from .audit_references_r3_org_b4 import EDGES as R3_ORG_B4_AUDIT_EDGES  # noqa: E402
AUDIT_META_REFERENCES.update(R3_ORG_B4_AUDIT_EDGES)
from .audit_references_r3_org_money import EDGES as R3_ORG_MONEY_AUDIT_EDGES  # noqa: E402
AUDIT_META_REFERENCES.update(R3_ORG_MONEY_AUDIT_EDGES)
from .audit_references_r0120 import EDGES as R0120_AUDIT_EDGES  # noqa: E402
AUDIT_META_REFERENCES.update(R0120_AUDIT_EDGES)
from .audit_references_cutout import EDGES as CUTOUT_AUDIT_EDGES  # noqa: E402
AUDIT_META_REFERENCES.update(CUTOUT_AUDIT_EDGES)
from .audit_references_studio import EDGES as STUDIO_AUDIT_EDGES  # noqa: E402
AUDIT_META_REFERENCES.update(STUDIO_AUDIT_EDGES)
AUDIT_META_REFERENCES.update(KIOSK_AUDIT_EDGES)
AUDIT_META_REFERENCES.update(PAYMENT_AUDIT_EDGES)
AUDIT_META_REFERENCES.update(REPORT_SCHEDULE_AUDIT_EDGES)
AUDIT_META_REFERENCES.update(DEVICE_AUDIT_EDGES)

from .audit_references_meta_7c import LABEL_AUDIT_EDGES

AUDIT_META_REFERENCES.update(LABEL_AUDIT_EDGES)
AUDIT_META_REFERENCES.update(DEVICE_7D_AUDIT_EDGES)

# Cloud programme: tick, staging, mail-budget and storage-receipt identifiers name
# deployment-local rows that never travel, so they are kept only as source snapshots.
AUDIT_META_REFERENCES.update(_reference(S, None, *(
    ("cloud.delivery_cancelled", "delivery_id"), ("cloud.tick_finished", "tick_id"),
    ("cloud.tick_started", "tick_id"), ("deployment.staging_available", "stage_id"),
    ("deployment.staging_created", "stage_id"), ("deployment.staging_deleted", "stage_id"),
    ("email.acceptance_reconciled", "reservation_id"), ("email.budget_reserved", "reservation_id"),
    ("email.budget_settled", "reservation_id"), ("notification.email_accepted", "delivery_id"),
    ("notification.email_accepted", "email_log_id"), ("storage.bucket_binding_migrated", "receipt_id"),
    ("storage.bucket_handoff_resumed", "receipt_id"), ("storage.legacy_receipt_bound", "receipt_id"),
)))

from .audit_references_meta_r2_l17 import SETTINGS_AUTHORITY_AUDIT_EDGES  # noqa: E402

AUDIT_META_REFERENCES.update(SETTINGS_AUTHORITY_AUDIT_EDGES)

from .audit_references_meta_r2_l1 import PUBLIC_SURFACE_AUDIT_EDGES  # noqa: E402

AUDIT_META_REFERENCES.update(PUBLIC_SURFACE_AUDIT_EDGES)

from .audit_references_meta_unified_accounts import UNIFIED_ACCOUNT_AUDIT_EDGES  # noqa: E402

AUDIT_META_REFERENCES.update(UNIFIED_ACCOUNT_AUDIT_EDGES)

# Release-2 lanes L5, L15, L10, L12, U-C, L23, L16, L3, L8, L6, L18, L21a, L21b, L24 and L22 compose in audit_references_meta_r2.py.
from .audit_references_meta_r2 import lane_edges as _r2_lane_edges  # noqa: E402
AUDIT_META_REFERENCES.update(_r2_lane_edges())
