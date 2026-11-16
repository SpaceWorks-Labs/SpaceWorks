"""Release 2 L23: source-gate declarations for the machine-session sweep."""

# The callable that opens a per-tenant `fanout_tenant_write` skip-and-count boundary.
FANOUT = {
    "apps.machines.sessions_sweep.run_session_sweep": "Machine-session auto-stop, one tenant at a time.",
}


def gate_tasks(internal, fanout):
    internal.update({
        "apps.machines.tasks_sessions.sweep_machine_sessions_task": (
            "Each auto-stop runs inside its own skip-and-count tenant boundary."
        ),
    })
    fanout.update(FANOUT)
