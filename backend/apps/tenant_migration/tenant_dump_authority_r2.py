"""Release-2 lane tenant-dump authority entries, composed in lane order.

Split out of `tenant_dump_authority_supplement.py` when it reached the 300-line ceiling;
each lane keeps its own `catalog_*.py` and adds one line here.
"""


def lane_entries(authority, D):
    from .catalog_l12 import authority_entries as _l12
    from .catalog_l16 import authority_entries as _l16
    from .catalog_l23 import authority_entries as _l23
    from .catalog_l3 import authority_entries as _l3
    from .catalog_l3a import authority_entries as _l3a
    from .catalog_login_security import authority_entries as _s0_authority
    from .catalog_r2_l1 import authority_entries as _r2_l1_authority
    from .catalog_r2_l2 import authority_entries as _r2_l2_authority
    from .catalog_r2_l5 import authority_entries as _r2_l5_authority
    from .catalog_r2_l15 import authority_entries as _r2_l15_authority
    from .catalog_r2_l6 import authority_entries as _r2_l6_authority
    from .catalog_r2_l18 import authority_entries as _r2_l18_authority
    from .catalog_r2_l21a import authority_entries as _r2_l21a_authority
    from .catalog_r2_l22 import authority_entries as _r2_l22_authority
    from .catalog_hackmoney_payments import authority_entries as _hackmoney_authority
    from .catalog_guest_passes import authority_entries as _guest_pass_authority
    from .catalog_r3_org_units import authority_entries as _r3_org_units_authority
    from .catalog_l3b import authority_entries as _l3b_authority

    entries = ()
    entries += _r2_l1_authority(authority, D)
    entries += _r2_l2_authority(authority, D)
    entries += _r2_l5_authority(authority, D)
    entries += _s0_authority(authority, D)
    entries += _r2_l15_authority(authority, D)
    entries += _l12(authority, D)
    entries += _l16(authority, D)
    entries += _l23(authority, D)
    entries += _l3(authority, D)
    entries += _l3a(authority, D)
    entries += _r2_l6_authority(authority, D)
    entries += _r2_l18_authority(authority, D)
    entries += _r2_l21a_authority(authority, D)
    entries += _r2_l22_authority(authority, D)
    entries += _hackmoney_authority(authority, D)
    entries += _guest_pass_authority(authority, D)
    entries += _r3_org_units_authority(authority, D)
    entries += _l3b_authority(authority, D)
    return entries
