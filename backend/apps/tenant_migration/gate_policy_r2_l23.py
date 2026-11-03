"""Release 2 L23: source-gate declaration for the machine-session sweep."""


def gate_tasks(internal):
    internal.update({
        "apps.machines.tasks_sessions.sweep_machine_sessions_task": (
            "Each auto-stop runs inside its own skip-and-count tenant boundary."
        ),
    })
