"""Literal model classification: what a tenant export includes, references and omits.

The field names are deliberately literal.  Building this from ``_meta`` would make a new
database column export itself before a security review could classify it.
"""

from .types import Exported, NotTenantData, OmittedModel
from .classification_7c import LABEL_EXPORTED_MODEL_FIELDS
from .classification_7b import PRINTER_EXPORTED_MODEL_FIELDS
from .classification_devices import DEVICE_EXPORTED_MODEL_FIELDS, DEVICE_OMITTED_MODELS
from .classification_domain import EXPORTED_MODEL_FIELDS as _DOMAIN_EXPORTED_MODEL_FIELDS
from .classification_platform import GLOBAL_MODELS
from .classification_platform import OMITTED_MODELS as _PLATFORM_OMITTED_MODELS
from .classification_modules import EXPORTED_MODEL_FIELDS as _MODULE_FIELDS
from .classification_w7_events import extend_event_export_fields
from .classification_wp3 import WP3_EXPORTED_FIELDS, WP3_OMITTED_MODELS
from .classification_wp4 import exported_fields, OMITTED_MODELS as WP4_OMITTED
from apps.tenant_migration.catalog_notifications_contract import OMITTED_MODELS as NOTIFICATION_OMITTED

EXPORTED_MODEL_FIELDS = {
    **_DOMAIN_EXPORTED_MODEL_FIELDS,
    **DEVICE_EXPORTED_MODEL_FIELDS,
    **PRINTER_EXPORTED_MODEL_FIELDS,
    **LABEL_EXPORTED_MODEL_FIELDS,
    **_MODULE_FIELDS,
    **WP3_EXPORTED_FIELDS,
}
extend_event_export_fields(EXPORTED_MODEL_FIELDS)
from apps.tenant_migration.catalog_broadcasts import EXPORTED_FIELDS as BROADCAST_FIELDS
EXPORTED_MODEL_FIELDS.update(BROADCAST_FIELDS)
from apps.tenant_migration.catalog_website import EXPORTED_FIELDS as WEBSITE_FIELDS
EXPORTED_MODEL_FIELDS.update(WEBSITE_FIELDS)
EXPORTED_MODEL_FIELDS["makerspaces.Makerspace"] += " website_embed_origins"
EXPORTED_MODEL_FIELDS["events.Event"] += " show_registration_count organization_admission_blocked"
EXPORTED_MODEL_FIELDS["events.EventSeries"] += " organization_admission_blocked"
EXPORTED_MODEL_FIELDS["events.EventRegistration"] += " cancelled_at status_before_cancel waitlist_position_at"
EXPORTED_MODEL_FIELDS["makerspaces.Makerspace"] += " event_default_registration_audience"
EXPORTED_MODEL_FIELDS["bookings.Booking"] += " calendar_sequence calendar_updated_at cancelled_at status_before_cancel checkin_token arrived_at"
EXPORTED_MODEL_FIELDS["bookings.BookingCheckInEvent"] = "id booking actor action source recorded_at"
from apps.tenant_migration.catalog_p2_bookings import EXPORTED_FIELDS as P2_BOOKING_FIELDS, BOOKING_EXTRA_FIELDS
EXPORTED_MODEL_FIELDS.update(P2_BOOKING_FIELDS)
EXPORTED_MODEL_FIELDS["bookings.Booking"] += " " + " ".join(sorted(BOOKING_EXTRA_FIELDS))
EXPORTED_MODEL_FIELDS["notifications.MemberNotificationPreference"] += " daily_digest"
EXPORTED_MODEL_FIELDS["notifications.NotificationPreference"] = "id makerspace user category channels email_fallback updated_at"
from .classification_r2_l1 import extend as extend_r2_l1
extend_r2_l1(EXPORTED_MODEL_FIELDS)
from .classification_r2_l5 import extend as extend_r2_l5  # noqa: E402
extend_r2_l5(EXPORTED_MODEL_FIELDS)
EXPORTED_MODEL_FIELDS = exported_fields(EXPORTED_MODEL_FIELDS)
OMITTED_MODELS = {
    **NOTIFICATION_OMITTED,
    "bookings.BookingSpaceStaffGrant": "Resource authority is reissued on the target; never portable.",
    "bookings.BookingSpaceStaffGrantInvite": "Deployment-local single-use credential; never portable.",
    "events.EventStaffGrant": "Event-scoped authority is reissued on the target; never portable.",
    "events.EventStaffGrantInvite": "Deployment-local single-use credential; never portable.",
    **_PLATFORM_OMITTED_MODELS, **DEVICE_OMITTED_MODELS,
    **WP3_OMITTED_MODELS, **WP4_OMITTED,
}
from apps.tenant_migration.catalog_profiles import (
    EXPORTED_FIELDS as PROFILE_EXPORTED_FIELDS, PROFILE_FIELDS, PROJECT_FIELDS,
    OMITTED_MODELS as PROFILE_OMITTED_MODELS,
)
EXPORTED_MODEL_FIELDS.update(PROFILE_EXPORTED_FIELDS)
EXPORTED_MODEL_FIELDS["makerspaces.MemberProfile"] += " " + PROFILE_FIELDS
EXPORTED_MODEL_FIELDS["makerspaces.MemberProject"] += " " + PROJECT_FIELDS
OMITTED_MODELS.update(PROFILE_OMITTED_MODELS)
from apps.tenant_migration.catalog_p2_events import OMITTED_MODELS as P2_EVENT_OMITTED
OMITTED_MODELS.update(P2_EVENT_OMITTED)
from apps.tenant_migration.catalog_p2_presence import classify as classify_presence
classify_presence(EXPORTED_MODEL_FIELDS)
from .classification_m1f1 import EXPORTED_FIELDS as M1F1_FIELDS, FIELD_ADDITIONS as M1F1_ADDITIONS, OMITTED_MODELS as M1F1_OMITTED
EXPORTED_MODEL_FIELDS.update(M1F1_FIELDS)
for _label, _fields in M1F1_ADDITIONS.items():
    EXPORTED_MODEL_FIELDS[_label] += " " + _fields
OMITTED_MODELS.update(M1F1_OMITTED)
from .classification_messaging import EXPORTED_FIELDS as MESSAGING_FIELDS, OMITTED_MODELS as MESSAGING_OMITTED
EXPORTED_MODEL_FIELDS.update(MESSAGING_FIELDS)
OMITTED_MODELS.update(MESSAGING_OMITTED)
from apps.tenant_migration.catalog_public_pages import EXPORTED_FIELDS as PAGE_FIELDS, OMITTED_MODELS as PAGE_OMITTED
EXPORTED_MODEL_FIELDS.update(PAGE_FIELDS)
OMITTED_MODELS.update(PAGE_OMITTED)
EXPORTED_MODELS = frozenset(EXPORTED_MODEL_FIELDS)
from apps.tenant_migration.catalog_events_programme import (
    EXPORTED_FIELDS as PROGRAMME_FIELDS, EXTRA_FIELDS as PROGRAMME_EXTRA,
    OMITTED_MODELS as PROGRAMME_OMITTED,
)
EXPORTED_MODEL_FIELDS.update(PROGRAMME_FIELDS)
for _label, _names in PROGRAMME_EXTRA.items():
    EXPORTED_MODEL_FIELDS[_label] += " " + _names
OMITTED_MODELS.update(PROGRAMME_OMITTED)
from apps.tenant_migration.catalog_reimbursements import (
    OMITTED_MODELS as REIMBURSEMENT_OMITTED, EXTRA_FIELDS as REIMBURSEMENT_EXTRA,
    EXPORTED_FIELDS as REIMBURSEMENT_FIELDS,
)
EXPORTED_MODEL_FIELDS.update(REIMBURSEMENT_FIELDS)
OMITTED_MODELS.update(REIMBURSEMENT_OMITTED)
for _label, _names in REIMBURSEMENT_EXTRA.items():
    EXPORTED_MODEL_FIELDS[_label] += " " + _names
from .classification_security import OMITTED_MODELS as SECURITY_OMITTED
OMITTED_MODELS.update(SECURITY_OMITTED)
from .classification_r2_l2 import OMITTED_MODELS as R2_L2_OMITTED, EXTRA_FIELDS as R2_L2_EXTRA  # noqa: E402
OMITTED_MODELS.update(R2_L2_OMITTED)
from .classification_r2_l5 import OMITTED_MODELS as R2_L5_OMITTED  # noqa: E402
OMITTED_MODELS.update(R2_L5_OMITTED)
for _label, _names in R2_L2_EXTRA.items():
    EXPORTED_MODEL_FIELDS[_label] += " " + _names
from .classification_unified_accounts import OMITTED_MODELS as UA1_OMITTED, EXTRA_FIELDS as UA1_EXTRA  # noqa: E402
OMITTED_MODELS.update(UA1_OMITTED)
for _label, _names in UA1_EXTRA.items():
    EXPORTED_MODEL_FIELDS[_label] += " " + _names
from .classification_r2_l4 import (
    EXPORTED_FIELDS as R2_L4_FIELDS, FIELD_ADDITIONS as R2_L4_ADDITIONS, OMITTED_MODELS as R2_L4_OMITTED,
)
EXPORTED_MODEL_FIELDS.update(R2_L4_FIELDS)
for _label, _names in R2_L4_ADDITIONS.items():
    EXPORTED_MODEL_FIELDS[_label] += " " + _names
OMITTED_MODELS.update(R2_L4_OMITTED)
EXPORTED_MODELS = frozenset(EXPORTED_MODEL_FIELDS)

NOT_TENANT_MODELS = {
    label: NotTenantData(reason) for label, reason in OMITTED_MODELS.items()
}
MODELS = {
    **{label: Exported() for label in EXPORTED_MODELS},
    **GLOBAL_MODELS,
    **{label: OmittedModel(value.reason) for label, value in NOT_TENANT_MODELS.items()},
}
