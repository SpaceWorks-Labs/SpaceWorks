"""Ordered registration of every domain capability-definition sibling.

Order is load-bearing: it fixes the iteration order of FEATURE_DEFINITIONS."""

from .capability_definitions_modules import module_family_features
from .capability_definitions_w7_events import event_features
from .capability_definitions_wp3 import wp3_features
from .capability_definitions_wp4 import definitions as wp4_definitions
from .capability_definitions_parity import definitions as parity_definitions
from .capability_definitions_events_programme import programme_features
from .capability_definitions_r2_l17 import definitions as r2_l17_definitions
from .capability_definitions_r2_l1 import definitions as r2_l1_definitions
from .capability_definitions_r2_l2 import definitions as r2_l2_definitions
from .capability_definitions_r2_l4 import definitions as r2_l4_definitions
from .capability_definitions_r2_l5 import definitions as r2_l5_definitions
from .capability_definitions_r2_l15 import definitions as r2_l15_definitions
from .capability_definitions_adapter_media import definitions as adapter_media_definitions
from .capability_definitions_r2_l10 import definitions as r2_l10_definitions
from .capability_definitions_r2_l12 import definitions as r2_l12_definitions
from .capability_definitions_r2_l19 import definitions as r2_l19_definitions
from .capability_definitions_r2_l23 import definitions as r2_l23_definitions
from .capability_definitions_r2_l3 import definitions as r2_l3_definitions
from .capability_definitions_r2_l13 import definitions as r2_l13_definitions
from .capability_definitions_r2_l6 import definitions as r2_l6_definitions
from .capability_definitions_r2_l18 import definitions as r2_l18_definitions
from .capability_definitions_r2_l21a import definitions as r2_l21a_definitions
from .capability_definitions_r2_l21b import definitions as r2_l21b_definitions
from .capability_definitions_hackmoney import definitions as hackmoney_definitions
from .capability_definitions_r2_peoples_choice import definitions as r2_peoples_choice_definitions
from .capability_definitions_r2_l24 import definitions as r2_l24_definitions
from .capability_definitions_r2_l22 import definitions as r2_l22_definitions
from .capability_definitions_r2_l20 import definitions as r2_l20_definitions
from .capability_definitions_gap2 import definitions as gap2_definitions
from .capability_definitions_l3a import definitions as l3a_definitions
from .capability_definitions_r2_guest_passes import definitions as guest_pass_definitions
from .capability_definitions_r3_org_units import definitions as r3_org_units_definitions
from .capability_definitions_r3_org_b4 import definitions as r3_org_b4_definitions
from .capability_definitions_r3_events_b3 import definitions as r3_events_b3_definitions
from .capability_definitions_r3_events_b5 import definitions as r3_events_b5_definitions
from .capability_definitions_r3_events_b4 import definitions as r3_events_b4_definitions
from .capability_definitions_r3_events_badges import definitions as r3_events_badges_definitions
from .capability_definitions_r3_events_b6 import definitions as r3_events_b6_definitions
from .capability_definitions_r3_events_b7 import definitions as r3_events_b7_definitions
from .capability_definitions_r3_events_b8 import definitions as r3_events_b8_definitions
from .capability_definitions_l3b import definitions as l3b_definitions
from .capability_definitions_cutout import definitions as cutout_definitions
from .capability_definitions_r3_display2 import definitions as r3_display2_definitions


def extension_features(feature_type):
    return (
        *event_features(feature_type),
        *programme_features(feature_type),
        *module_family_features(feature_type),
        *wp3_features(feature_type),
        *wp4_definitions(feature_type),
        *parity_definitions(feature_type),
        *r2_l17_definitions(feature_type),
        *r2_l1_definitions(feature_type),
        *r2_l2_definitions(feature_type),
        *r2_l4_definitions(feature_type),
        *r2_l5_definitions(feature_type),
        *r2_l15_definitions(feature_type),
        *r2_l10_definitions(feature_type),
        *adapter_media_definitions(feature_type),
        *r2_l12_definitions(feature_type),
        *r2_l19_definitions(feature_type),
        *r2_l23_definitions(feature_type),
        *r2_l3_definitions(feature_type),
        *r2_l13_definitions(feature_type),
        *r2_l6_definitions(feature_type),
        *r2_l18_definitions(feature_type),
        *r2_l21a_definitions(feature_type),
        *r2_l21b_definitions(feature_type),
        *r2_peoples_choice_definitions(feature_type),
        *r2_l24_definitions(feature_type),
        *r2_l22_definitions(feature_type),
        *r2_l20_definitions(feature_type),
        *gap2_definitions(feature_type),
        *l3a_definitions(feature_type),
        *hackmoney_definitions(feature_type),
        *guest_pass_definitions(feature_type),
        *r3_org_units_definitions(feature_type),
        *r3_org_b4_definitions(feature_type),
        *r3_events_b3_definitions(feature_type),
        *r3_events_b5_definitions(feature_type),
        *r3_events_b4_definitions(feature_type),
        *r3_events_badges_definitions(feature_type),
        *r3_events_b6_definitions(feature_type),
        *r3_events_b7_definitions(feature_type),
        *r3_events_b8_definitions(feature_type),
        *l3b_definitions(feature_type),
        *cutout_definitions(feature_type),
        *r3_display2_definitions(feature_type),
    )
