"""Release-2 lanes' tenant-dump authority entries, composed in lane order.

Split out of `tenant_dump_authority_supplement.py` at the 300-line ceiling; each lane keeps
its entries in its own `catalog_*` module and adds one line here.
"""


def lane_entries(authority, disposition):
    from .catalog_l12 import authority_entries as l12
    from .catalog_l3 import authority_entries as l3
    from .catalog_login_security import authority_entries as s0
    from .catalog_r2_l1 import authority_entries as l1
    from .catalog_r2_l15 import authority_entries as l15
    from .catalog_r2_l2 import authority_entries as l2
    from .catalog_r2_l5 import authority_entries as l5
    from .catalog_r2_l6 import authority_entries as l6
    from .catalog_r2_l22 import authority_entries as l22

    return (*l1(authority, disposition), *l2(authority, disposition), *l5(authority, disposition),
            *s0(authority, disposition), *l15(authority, disposition), *l12(authority, disposition),
            *l3(authority, disposition), *l6(authority, disposition),
            *l22(authority, disposition))
