"""Origin-scope table for release 2 L12's staff routes that name only a row.

Routes that carry `makerspace_id` in the URL already resolve their target; these name a
job, batch, machine, work order or To-Buy item, so their target is that row's own space and
a verified custom staff origin pins them like every other admin route.
"""

_JOB = ("machines.MachineServiceRequest", "makerspace_id")

MODEL_LOOKUPS = {
    **{name: _JOB for name in (
        "admin-machine-job-request-changes", "admin-machine-job-quote", "admin-machine-job-queue-now",
        "admin-machine-job-reorder", "admin-machine-job-urgent", "admin-machine-job-assign",
        "admin-machine-job-uncollected",
    )},
    "admin-machine-job-batch-complete": ("machines.MachineJobBatch", "makerspace_id"),
    "admin-machine-downtime": ("machines.Machine", "makerspace_id"),
    "admin-machine-lockout": ("machines.Machine", "makerspace_id"),
    "admin-work-order-status": ("maintenance.WorkOrder", "makerspace_id"),
    "admin-work-order-assign": ("maintenance.WorkOrder", "makerspace_id"),
    "to-buy-mark-bought": ("procurement.ToBuyItem", "makerspace_id"),
}
