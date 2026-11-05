"""Release-2 lanes' audit metadata edges, composed in lane order.

Split out of `audit_references_meta.py` at the 300-line ceiling; each lane keeps its edges
in its own `audit_references_*` module and adds one line here. Later lanes win on a clash,
exactly as the sequential `update` calls did before the split.
"""


def lane_edges():
    from .audit_references_l12 import EDGES as l12
    from .audit_references_l3 import EDGES as l3
    from .audit_references_r2_l10 import EDGES as l10
    from .audit_references_r2_l15 import EDGES as l15
    from .audit_references_r2_l5 import EDGES as l5
    from .audit_references_r2_l6 import EDGES as l6
    from .audit_references_r2_l21a import EDGES as l21a
    from .audit_references_r2_l21b import EDGES as l21b
    from .audit_references_r2_submit_content import EDGES as submit_content

    return {**l5, **l15, **l10, **l12, **l3, **l6, **l21a, **l21b, **submit_content}
