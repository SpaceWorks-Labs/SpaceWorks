"""Release-2 lane source-gate declarations, composed in lane order (L2, L11, L12, L23).

Split out of `gate_policy_tasks.py` when it crossed the 300-line ceiling; each lane keeps
its own `gate_policy_r2_<lane>.py` and this function applies them to the shared tables.
"""


def gate_tasks(exemptions, internal, fanout):
    from .gate_policy_r2_l2 import gate_tasks as l2_tasks
    from .gate_policy_r2_l11 import gate_tasks as l11_tasks
    from .gate_policy_r2_l12 import gate_tasks as l12_tasks
    from .gate_policy_r2_l23 import gate_tasks as l23_tasks

    l2_tasks(internal, fanout)
    l11_tasks(exemptions)
    l12_tasks(internal, fanout)
    l23_tasks(internal, fanout)
