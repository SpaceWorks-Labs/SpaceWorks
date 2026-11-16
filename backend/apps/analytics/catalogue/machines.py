"""Analytics views: machines, machine types, machine jobs, usage and downtime.

No pickup codes, public tokens, contacts, titles, descriptions, notes, file keys or
camera URLs: a job is its timings, quantities, money and outcome.
"""

from .types import Col, View

D = "machines"
_JOB_TIMES = tuple(Col(f"{name}_at", f"j.{name}_at", f"When the job was {label}.") for name, label in (
    ("created", "submitted"), ("queued", "queued"), ("accepted", "accepted"), ("started", "started"),
    ("completed", "completed"), ("collected", "collected"), ("failed", "marked failed"),
    ("cancelled", "cancelled"), ("paid", "paid"),
))
_MINUTES_DOWN = "round((extract(epoch FROM coalesce(d.ended_at, now()) - d.started_at) / 60.0)::numeric, 1)"

VIEWS = (
    View("machines", D, "Every machine with its current status.",
         "FROM {machines.Machine} m", "m.makerspace_id", (
             Col("machine_id", "m.id", "Machine id."),
             Col("machine_type_id", "m.machine_type_id", "Type (machine_types)."),
             Col("name", "m.name", "Machine name."),
             Col("status", "m.status", "Current status."),
             Col("status_since", "m.status_since", "Since when."),
             Col("is_public", "m.is_public", "Shown on the public page."),
             Col("is_active", "m.is_active", "In use (not retired)."),
             Col("created_at", "m.created_at", "Added."),
         )),
    View("machine_types", D, "Machine types: the space's own and the built-in ones.",
         "FROM {machines.MachineType} t", "t.makerspace_id", (
             Col("machine_type_id", "t.id", "Type id."),
             Col("slug", "t.slug", "Type key."),
             Col("name", "t.name", "Type name."),
             Col("is_builtin", "t.is_builtin", "Built into SpaceWorks (makerspace_id is empty)."),
         ), lookup=True, include_unowned=True),
    View("machine_jobs", D, "Machine service jobs (3D prints, laser cuts and others) from request to pickup.",
         "FROM {machines.MachineServiceRequest} j", "j.makerspace_id", (
             Col("job_id", "j.id", "Job id."),
             Col("member_id", "coalesce(j.member_id, j.requester_id)", "Requesting member (members)."),
             Col("queue_id", "j.queue_id", "Service queue."),
             Col("assigned_machine_id", "j.assigned_machine_id", "Machine it ran on (machines)."),
             Col("batch_id", "j.batch_id", "Batch, when started with others."),
             Col("status", "j.status", "Job state."),
             Col("urgent", "j.urgent", "Marked urgent."),
             Col("copies", "j.copies", "Copies asked for."),
             Col("own_material", "j.own_material", "Member brought the material."),
             Col("prepay", "j.prepay", "Paid before the run."),
             *_JOB_TIMES,
             Col("estimated_minutes", "j.estimated_minutes", "Estimated machine minutes."),
             Col("actual_minutes", "j.actual_minutes", "Measured machine minutes."),
             Col("planned_grams", "j.planned_grams", "Planned material, grams."),
             Col("actual_consumed_grams", "j.actual_consumed_grams", "Material used, grams."),
             Col("metering_unit", "j.metering_unit", "Unit for non-gram materials."),
             Col("actual_consumed_quantity", "j.actual_consumed_quantity", "Material used in that unit."),
             Col("payment_amount", "j.payment_amount", "Charge for the job."),
             Col("payment_status", "j.payment_status", "Payment state."),
             Col("fail_code", "j.fail_code", "Failure reason code."),
             Col("failure_outcome", "j.failure_outcome", "What happened after a failure."),
             Col("reject_code", "j.reject_code", "Rejection reason code."),
         )),
    View("machine_usage", D, "Logged machine time, from jobs and from walk-up use.",
         "FROM {machines.MachineUsageEntry} u JOIN {machines.Machine} m ON m.id = u.machine_id", "m.makerspace_id", (
             Col("usage_id", "u.id", "Entry id."),
             Col("machine_id", "u.machine_id", "Machine (machines)."),
             Col("member_id", "u.member_id", "Member who used it (members)."),
             Col("job_id", "u.service_request_id", "The job it ran, if any (machine_jobs)."),
             Col("started_at", "u.started_at", "Started."),
             Col("hours", "u.hours", "Hours logged."),
             Col("duration_minutes", "u.duration_minutes", "Minutes logged."),
             Col("outcome", "u.outcome", "Outcome."),
             Col("source", "u.source", "How it was logged."),
             Col("percent_complete", "u.percent_complete", "Progress at the end of a failed run."),
             Col("consumed_grams", "u.consumed_grams", "Material used, grams."),
             Col("metering_unit", "u.metering_unit", "Unit for non-gram materials."),
             Col("consumed_quantity", "u.consumed_quantity", "Material used in that unit."),
             Col("created_at", "u.created_at", "Logged."),
         )),
    View("machine_downtime", D, "Out-of-service periods per machine.",
         "FROM {machines.MachineDowntime} d", "d.makerspace_id", (
             Col("downtime_id", "d.id", "Period id."),
             Col("machine_id", "d.machine_id", "Machine (machines)."),
             Col("kind", "d.kind", "Planned or unplanned."),
             Col("started_at", "d.started_at", "Went down."),
             Col("ended_at", "d.ended_at", "Came back (empty while down)."),
             Col("expected_back_at", "d.expected_back_at", "Expected back."),
             Col("minutes", _MINUTES_DOWN, "Minutes down so far."),
         )),
)
