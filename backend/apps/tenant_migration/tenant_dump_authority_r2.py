"""Release-2 lane tenant-dump authority entries, composed in lane order.

Split out of `tenant_dump_authority_supplement.py` when it reached the 300-line ceiling;
each lane keeps its own `catalog_*.py` and adds one line here.
"""


def lane_entries(authority, D):
    from .catalog_l12 import authority_entries as _l12
    from .catalog_l23 import authority_entries as _l23
    from .catalog_login_security import authority_entries as _s0_authority
    from .catalog_r2_l1 import authority_entries as _r2_l1_authority
    from .catalog_r2_l2 import authority_entries as _r2_l2_authority
    from .catalog_r2_l5 import authority_entries as _r2_l5_authority
    from .catalog_r2_l15 import authority_entries as _r2_l15_authority

    entries = ()
    entries += _r2_l1_authority(authority, D)
    entries += _r2_l2_authority(authority, D)
    entries += _r2_l5_authority(authority, D)
    entries += _s0_authority(authority, D)
    entries += _r2_l15_authority(authority, D)
    entries += _l12(authority, D)
    entries += _l23(authority, D)
    return entries
