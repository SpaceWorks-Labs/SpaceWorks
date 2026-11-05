"""Composition barrel for the audit presentation catalogue.

One entry per literal audit action, split into domain fragments so no file breaches the
size ceiling. Duplicates are refused at import: two fragments disagreeing about the same
action would make the disclosure policy depend on import order.
"""

from .presentation_catalog_accounts import ENTRIES as _ACCOUNTS
from .presentation_catalog_community import ENTRIES as _COMMUNITY
from .presentation_catalog_dynamic import (
    DENIED_ACTION_PREFIXES,
    DYNAMIC_EXACT_ACTIONS,
    NON_LITERAL_META_ACTIONS,
    WRAPPER_SITE_PREFIXES,
    is_denied,
)
from .presentation_catalog_hardware import ENTRIES as _HARDWARE
from .presentation_catalog_machines import ENTRIES as _MACHINES
from .presentation_catalog_makerspaces import ENTRIES as _MAKERSPACES
from .presentation_catalog_member_account import ENTRIES as _MEMBER_ACCOUNT
from .presentation_catalog_migration import ENTRIES as _MIGRATION
from .presentation_catalog_payments import ENTRIES as _PAYMENTS
from .presentation_catalog_platform import ENTRIES as _PLATFORM
from .presentation_catalog_merged import ENTRIES as _MERGED
from .presentation_catalog_types import AuditPresentation, P
from .presentation_catalog_profiles import ENTRIES as _PROFILES
from .presentation_catalog_p2_wa_twilio import ENTRIES as _WA_TWILIO
from .presentation_catalog_wa_meta import ENTRIES as _WA_META
from .presentation_catalog_p2_p_chat import ENTRIES as _P2_P_CHAT
from .presentation_catalog_p2_bookings import ENTRIES as _P2_BOOKINGS
from .presentation_catalog_p2_events import ENTRIES as _P2_EVENTS
from .presentation_catalog_notification_media import ENTRIES as _NOTIFICATION_MEDIA
from .presentation_catalog_messaging import ENTRIES as _MESSAGING
from .presentation_catalog_programme import ENTRIES as _PROGRAMME
from .presentation_catalog_reimbursements import ENTRIES as _REIMBURSEMENTS
from .presentation_catalog_l12 import ENTRIES as _L12
from .presentation_catalog_l23 import ENTRIES as _L23
from .presentation_catalog_l16 import ENTRIES as _L16
from .presentation_catalog_l3 import ENTRIES as _L3
from .presentation_catalog_r2_l6 import ENTRIES as _R2_L6
from .presentation_catalog_r2_l18 import ENTRIES as _R2_L18
from .presentation_catalog_r2_l21a import ENTRIES as _R2_L21A
from .presentation_catalog_r2_l21b import ENTRIES as _R2_L21B
from .presentation_catalog_r2_peoples_choice import ENTRIES as _R2_PEOPLES_CHOICE
from .presentation_catalog_r2_l24 import ENTRIES as _R2_L24
from .presentation_catalog_r2_l22 import ENTRIES as _R2_L22

# Closed name -> callable registry for target links. Phase 10 ships no resolver: a link
# needs a real route and query-level tenant authorization, which no generic one has.
LINK_RESOLVERS = {}

UNRECOGNIZED_LABEL = "Unrecognized audit action"


def _compose(*fragments):
    catalogue = {}
    for fragment in fragments:
        for entry in fragment:
            if entry.action in catalogue:
                raise ValueError(f"Duplicate audit presentation entry: {entry.action}")
            catalogue[entry.action] = entry
    return catalogue


from .presentation_catalog_p2_presence import ENTRIES as _PRESENCE
from .presentation_catalog_security import ENTRIES as _SECURITY
from .presentation_catalog_settings_authority import ENTRIES as _SETTINGS_AUTHORITY
from .presentation_catalog_r2_l1 import ENTRIES as _R2_L1
from .presentation_catalog_space_backup import ENTRIES as _SPACE_BACKUP
from .presentation_catalog_r2_l2 import ENTRIES as _R2_L2
from .presentation_catalog_unified_accounts import ENTRIES as _UNIFIED_ACCOUNTS
from .presentation_catalog_r2_l4 import ENTRIES as _R2_L4
from .presentation_catalog_r2_l5 import ENTRIES as _R2_L5
from .presentation_catalog_r2_l15 import ENTRIES as _R2_L15
from .presentation_catalog_r2_l10 import ENTRIES as _R2_L10
from .presentation_catalog_r2_l11 import ENTRIES as _R2_L11
from .presentation_catalog_r2_l8 import ENTRIES as _R2_L8
from .presentation_catalog_account_merge import ENTRIES as _ACCOUNT_MERGE
from .presentation_catalog_login_security import ENTRIES as _LOGIN_SECURITY
from .presentation_catalog_ip_security import ENTRIES as _IP_SECURITY
from .presentation_catalog_staff_roles import ENTRIES as _STAFF_ROLES
from .presentation_catalog_r2_l25 import ENTRIES as _R2_L25

PRESENTATION_CATALOG = _compose(
    _PROGRAMME,
    _REIMBURSEMENTS,
    _NOTIFICATION_MEDIA,
    _PRESENCE,
    _SECURITY,
    _SETTINGS_AUTHORITY,
    _R2_L1,
    _SPACE_BACKUP,
    _R2_L2,
    _UNIFIED_ACCOUNTS,
    _R2_L5,
    _R2_L15,
    _R2_L10,
    _R2_L11,
    _R2_L8,
    _ACCOUNT_MERGE,
    _LOGIN_SECURITY,
    _IP_SECURITY,
    _STAFF_ROLES,
    _ACCOUNTS, _MAKERSPACES, _HARDWARE, _MACHINES, _COMMUNITY, _MIGRATION, _PAYMENTS,
    _PLATFORM, _MEMBER_ACCOUNT, _MERGED, _PROFILES, _WA_TWILIO, _WA_META, _P2_P_CHAT, _P2_BOOKINGS, _P2_EVENTS,
    _MESSAGING, _R2_L4, _L12, _L23, _L16, _L3, _R2_L6, _R2_L18, _R2_L21A, _R2_L21B,
    _R2_L24,
    _R2_L22,
    _R2_L25,
    _R2_PEOPLES_CHOICE,
)


__all__ = [
    "DENIED_ACTION_PREFIXES",
    "DYNAMIC_EXACT_ACTIONS",
    "LINK_RESOLVERS",
    "NON_LITERAL_META_ACTIONS",
    "PRESENTATION_CATALOG",
    "UNRECOGNIZED_LABEL",
    "WRAPPER_SITE_PREFIXES",
    "AuditPresentation",
    "P",
    "is_denied",
]
