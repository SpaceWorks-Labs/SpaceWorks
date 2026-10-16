"""Literal concrete-or-M2M field snapshot for the Lane D catalog.

This file is intentionally source-controlled rather than derived at import time. A
schema edit must add the field here and give any authority/disclosure input an
override in tenant_dump_authority.py before the catalog guard will pass.
"""

from .tenant_dump_field_snapshot_core import FIRST_PARTY_FIELD_NAMES

from .catalog_7b import PRINTER_FIELD_NAMES

FIRST_PARTY_FIELD_NAMES.update(PRINTER_FIELD_NAMES)
from .catalog_broadcasts import FIELD_NAMES as BROADCAST_FIELDS
FIRST_PARTY_FIELD_NAMES.update(BROADCAST_FIELDS)
from .catalog_website import FIELD_NAMES as WEBSITE_FIELDS
FIRST_PARTY_FIELD_NAMES.update(WEBSITE_FIELDS)
FIRST_PARTY_FIELD_NAMES["makerspaces.Makerspace"] |= {"website_embed_origins"}
FIRST_PARTY_FIELD_NAMES["integrations.EmailLog"] |= {"source_kind", "source_id", "source_metadata"}

from .catalog_7c import LABEL_FIELD_NAMES

FIRST_PARTY_FIELD_NAMES.update(LABEL_FIELD_NAMES)

from .catalog_w7_events import extend_event_field_snapshot
extend_event_field_snapshot(FIRST_PARTY_FIELD_NAMES)
FIRST_PARTY_FIELD_NAMES["events.Event"] |= {"show_registration_count"}
FIRST_PARTY_FIELD_NAMES["events.EventRegistration"] |= {"cancelled_at", "status_before_cancel", "waitlist_position_at"}

from .catalog_wp3 import WP3_FIELD_NAMES, WP3_EXTRA_FIELDS
FIRST_PARTY_FIELD_NAMES.update(WP3_FIELD_NAMES)
for _label, _names in WP3_EXTRA_FIELDS.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names

from .catalog_booking_arrival import FIELD_NAMES as BOOKING_ARRIVAL_FIELDS
FIRST_PARTY_FIELD_NAMES.update(BOOKING_ARRIVAL_FIELDS)
FIRST_PARTY_FIELD_NAMES["bookings.Booking"] |= {"checkin_token", "arrived_at"}

AUTO_CREATED_FIELD_NAMES = {
    'auth.Group_permissions': frozenset('group id permission'.split()),
    'accounts.User_groups': frozenset('group id user'.split()),
    'accounts.User_user_permissions': frozenset('id permission user'.split()),
}

THIRD_PARTY_FIELD_NAMES = {
    'admin.LogEntry': frozenset('action_flag action_time change_message content_type id object_id object_repr user'.split()),
    'auth.Permission': frozenset('codename content_type group id name user'.split()),
    'auth.Group': frozenset('id name permissions user'.split()),
    'axes.AccessFailureLog': frozenset('attempt_time http_accept id ip_address locked_out path_info user_agent username'.split()),
    'axes.AccessAttempt': frozenset('attempt_time failures_since_start get_data http_accept id ip_address path_info post_data user_agent username'.split()),
    'axes.AccessAttemptExpiration': frozenset('access_attempt expires_at'.split()),
    'axes.AccessLog': frozenset('attempt_time http_accept id ip_address logout_time path_info session_hash user_agent username'.split()),
    'contenttypes.ContentType': frozenset('app_label id model'.split()),
    'sessions.Session': frozenset('expire_date session_data session_key'.split()),
    'token_blacklist.OutstandingToken': frozenset('created_at expires_at id jti token user'.split()),
    'token_blacklist.BlacklistedToken': frozenset('blacklisted_at id token'.split()),
}

from .catalog_profiles import FIELD_NAMES as PROFILE_FIELD_NAMES, PROFILE_FIELDS, PROJECT_FIELDS
FIRST_PARTY_FIELD_NAMES.update(PROFILE_FIELD_NAMES)
FIRST_PARTY_FIELD_NAMES["makerspaces.MemberProfile"] |= frozenset(PROFILE_FIELDS.split())
FIRST_PARTY_FIELD_NAMES["makerspaces.MemberProject"] |= frozenset(PROJECT_FIELDS.split())

UNMANAGED_FIELD_NAMES = {}

from .tenant_dump_modules import MODULE_FIELD_NAMES
FIRST_PARTY_FIELD_NAMES["makerspaces.Makerspace"] |= MODULE_FIELD_NAMES
FIRST_PARTY_FIELD_NAMES["makerspaces.Makerspace"] |= {"event_default_registration_audience"}

from .catalog_wp4 import field_snapshot
FIRST_PARTY_FIELD_NAMES = field_snapshot(FIRST_PARTY_FIELD_NAMES)

FIRST_PARTY_FIELD_NAMES["bookings.Booking"] |= {"cancelled_at", "status_before_cancel"}
