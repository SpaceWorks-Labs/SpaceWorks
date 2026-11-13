"""JSON fields that hold no object or user references (split from `guards.py`; its drift guard still
demands exact equality)."""

# JSON fields that hold NO object or user references and therefore have no reference
# schema. Declared here rather than inline so that exempting a field stays a visible,
# reviewable act: the guard below still demands EXACT equality, so any JSON field that is
# neither declared in JSON_FIELDS nor listed here still fails discovery.
NON_REFERENCE_JSON_FIELDS = frozenset({
    # Stable widget keys map to booleans, never row IDs or person references.
    ("makerspaces.Makerspace", "public_stats_config"),
    # Opaque component UUIDs, labels and numeric counts; no model references.
    ("inventory.InventoryProduct", "kit_components"),
    ("boxes.Box", "kit_components"),
    ("hardware_requests.HardwareRequest", "box_issue_checklist"),
    ("hardware_requests.HardwareRequestItem", "issue_checklist"),
    ("hardware_requests.ReturnEvent", "kit_checklist"),
    # Inert filter snapshots; identity filters are not live relation edges. Reset
    # on tenant import so source identifiers never address unrelated target rows.
    ("operations.SavedView", "state"),
    # Controlled metric dimension labels (module key, period, report key) -- never an id.
    ("operations.ReportMetricRollup", "dimensions"),
    # Export inputs (dates, day window, payment enums) and staff-entered emails; no ids.
    ("operations.ReportSchedule", "filters"),
    ("operations.ReportSchedule", "recipient_emails"),
    ("operations.ReportSchedule", "condition"),
    # Slugs and action enums are tenant-local selector labels, never source IDs;
    # the entire schedule is DROP on tenant import.
    ("operations.ReportSchedule", "recipient_roles"),
    ("operations.ReportSchedule", "recipient_actions"),
})

from .classification_wp4 import NON_REFERENCE_JSON_FIELDS as WP4_JSON
from .classification_r2_l4 import NON_REFERENCE_JSON_FIELDS as R2_L4_JSON  # noqa: E402
from .classification_loan_context import NON_REFERENCE_JSON_FIELDS as LOAN_CONTEXT_JSON  # noqa: E402
from .classification_guest_passes import NON_REFERENCE_JSON_FIELDS as GUEST_PASS_JSON  # noqa: E402
NON_REFERENCE_JSON_FIELDS |= WP4_JSON | R2_L4_JSON | LOAN_CONTEXT_JSON | GUEST_PASS_JSON
from .classification_r3_org_units import NON_REFERENCE_JSON_FIELDS as R3_ORG_UNIT_JSON  # noqa: E402
NON_REFERENCE_JSON_FIELDS |= R3_ORG_UNIT_JSON
from .classification_r3_org_b4 import NON_REFERENCE_JSON_FIELDS as R3_ORG_B4_JSON  # noqa: E402
NON_REFERENCE_JSON_FIELDS |= R3_ORG_B4_JSON
from .classification_adapter import NON_REFERENCE_JSON_FIELDS as ADAPTER_JSON  # noqa: E402
NON_REFERENCE_JSON_FIELDS |= ADAPTER_JSON
from .classification_studio import NON_REFERENCE_JSON_FIELDS as STUDIO_JSON  # noqa: E402
NON_REFERENCE_JSON_FIELDS |= STUDIO_JSON
from .classification_account_profile import NON_REFERENCE_JSON_FIELDS as ACCOUNT_PROFILE_JSON  # noqa: E402
NON_REFERENCE_JSON_FIELDS |= ACCOUNT_PROFILE_JSON
