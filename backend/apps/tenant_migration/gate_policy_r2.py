"""Release-2 lane source-gate declarations, composed in lane order (L2, L11, L12, L23, S-C, L3, S-B, L8, L6, L18, L21a, L22).

Split out of `gate_policy_tasks.py` when it crossed the 300-line ceiling; each lane keeps
its own `gate_policy_r2_<lane>.py` and this function applies them to the shared tables.
"""


def gate_tasks(exemptions, internal, fanout, resolvers=None):
    from .gate_policy_r2_l2 import gate_tasks as l2_tasks
    from .gate_policy_r2_l11 import gate_tasks as l11_tasks
    from .gate_policy_r2_l12 import gate_tasks as l12_tasks
    from .gate_policy_r2_l23 import gate_tasks as l23_tasks
    from .gate_policy_r2_sc import gate_tasks as sc_tasks
    from .gate_policy_r2_l3 import gate_tasks as l3_tasks
    from .gate_policy_r2_sb import gate_tasks as sb_tasks
    from .gate_policy_r2_l8 import gate_tasks as l8_tasks
    from .gate_policy_r2_l6 import gate_tasks as l6_tasks
    from .gate_policy_r2_l18 import gate_tasks as l18_tasks
    from .gate_policy_r2_l21a import gate_tasks as l21a_tasks
    from .gate_policy_r2_l22 import gate_tasks as l22_tasks

    l2_tasks(internal, fanout)
    l11_tasks(exemptions)
    l12_tasks(internal, fanout)
    l23_tasks(internal, fanout)
    sc_tasks(exemptions)
    l3_tasks(internal, exemptions, resolvers if resolvers is not None else {})
    sb_tasks(exemptions)
    l8_tasks(internal, fanout)
    l6_tasks(internal, resolvers if resolvers is not None else {})
    l18_tasks(internal)
    l21a_tasks(resolvers if resolvers is not None else {})
    l22_tasks(internal)
