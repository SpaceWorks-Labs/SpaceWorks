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
EXPORTED_MODEL_FIELDS["notifications.MemberNotificationPreference"] += " daily_digest"
EXPORTED_MODEL_FIELDS = exported_fields(EXPORTED_MODEL_FIELDS)
OMITTED_MODELS = {
    "bookings.BookingSpaceStaffGrant": "Resource authority is reissued on the target; never portable.",
    "bookings.BookingSpaceStaffGrantInvite": "Deployment-local single-use credential; never portable.",
    "events.EventStaffGrant": "Event-scoped authority is reissued on the target; never portable.",
    "events.EventStaffGrantInvite": "Deployment-local single-use credential; never portable.",
    **_PLATFORM_OMITTED_MODELS, **DEVICE_OMITTED_MODELS,
    **WP3_OMITTED_MODELS, **WP4_OMITTED,
}
from .classification_m1f1 import EXPORTED_FIELDS as M1F1_FIELDS, FIELD_ADDITIONS as M1F1_ADDITIONS, OMITTED_MODELS as M1F1_OMITTED
EXPORTED_MODEL_FIELDS.update(M1F1_FIELDS)
for _label, _fields in M1F1_ADDITIONS.items():
    EXPORTED_MODEL_FIELDS[_label] += " " + _fields
OMITTED_MODELS.update(M1F1_OMITTED)
from .classification_messaging import EXPORTED_FIELDS as MESSAGING_FIELDS, OMITTED_MODELS as MESSAGING_OMITTED
EXPORTED_MODEL_FIELDS.update(MESSAGING_FIELDS)
OMITTED_MODELS.update(MESSAGING_OMITTED)
EXPORTED_MODELS = frozenset(EXPORTED_MODEL_FIELDS)

NOT_TENANT_MODELS = {
    label: NotTenantData(reason) for label, reason in OMITTED_MODELS.items()
}
MODELS = {
    **{label: Exported() for label in EXPORTED_MODELS},
    **GLOBAL_MODELS,
    **{label: OmittedModel(value.reason) for label, value in NOT_TENANT_MODELS.items()},
}
