"""Release 2 L21a: source-gate declaration for the attendance confirmation fan-out."""


def gate_tasks(resolvers):
    resolvers.update({
        # One staff send's notices; the round row names its space.
        "apps.events.tasks_attendance.send_attendance_round_task": ("events.EventAttendanceRound", 0, "makerspace_id"),
    })
