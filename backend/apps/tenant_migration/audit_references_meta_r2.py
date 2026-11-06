"""Release-2 lane audit-meta reference edges, composed in lane order.

Split out of `audit_references_meta.py` when it crossed the 300-line ceiling; each lane keeps
its own `audit_references_*.py` and adds one line here. Later lanes win on a shared edge, as
they did in the barrel.
"""


def lane_edges():
    from .audit_references_account_merge import EDGES as account_merge
    from .audit_references_l12 import EDGES as l12
    from .audit_references_l16 import EDGES as l16
    from .audit_references_l23 import EDGES as l23
    from .audit_references_l3 import EDGES as l3
    from .audit_references_r2_l5 import EDGES as l5
    from .audit_references_r2_l10 import EDGES as l10
    from .audit_references_r2_l15 import EDGES as l15
    from .audit_references_r2_l8 import EDGES as l8
    from .audit_references_r2_l6 import EDGES as l6
    from .audit_references_r2_l18 import EDGES as l18
    from .audit_references_r2_l21a import EDGES as l21a
    from .audit_references_r2_l21b import EDGES as l21b
    from .audit_references_r2_l24 import EDGES as l24
    from .audit_references_r2_l22 import EDGES as l22
    from .audit_references_r2_submit_content import EDGES as submit_content
    from .audit_references_r2_hackmoney import EDGES as hackmoney
    from .audit_references_r2_peoples_choice import EDGES as peoples_choice
    from .audit_references_r2_certificates import EDGES as certificates
    from .audit_references_r2_superadmin import EDGES as superadmin

    edges = {}
    for lane in (l5, l15, l10, l12, account_merge, l23, l16, l3, l8, l6, l18, l21a, l21b, l24, l22, submit_content, hackmoney, peoples_choice, certificates, superadmin):
        edges.update(lane)
    return edges
